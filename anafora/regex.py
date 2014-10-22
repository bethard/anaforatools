from __future__ import absolute_import

import argparse
import codecs
import collections
import json
import logging
import os

import regex

import anafora
import anafora.evaluate


class RegexAnnotator(object):

    _word_boundary_pattern = regex.compile(r'\b')
    _capturing_group_pattern = regex.compile(r'[^\\]\([^?]')

    @classmethod
    def from_file(cls, path_or_file):
        """
        :param str|file path_or_file: a string path or a file object containing a serialized RegexAnnotator
        """

        # if passed a path instead of a file, open the path as a file for reading and recursively call from_file
        try:
            path_or_file.readline
        except AttributeError:
            with codecs.open(path_or_file, 'r', 'utf-8') as output_file:
                return cls.from_file(output_file)
        else:

            # parse each line in the model file, which should be: <regex>\t<type>\t<attributes>
            regex_type_attributes_map = {}
            for line in path_or_file:
                items = line.rstrip().split("\t")
                if len(items) < 2 or len(items) > 3:
                    raise ValueError('expected {0!r}, found {1!r}'.format("<regex>\t<type>\t<attributes>", line))
                if len(items) == 2:
                    [expression, entity_type] = items
                    attributes = {}
                else:
                    [expression, entity_type, attributes_string] = items
                    attributes = json.loads(attributes_string)

                # make sure the <regex> is a valid regular expression and does not use any capturing groups
                try:
                    regex.compile(expression)
                except regex.error as e:
                    raise ValueError("{0} in {1!r}".format(e, expression))
                if cls._capturing_group_pattern.search(expression):
                    raise ValueError("capturing groups are not allowed: " + expression)

                # map the regular exrpression to the type and attributes
                regex_type_attributes_map[expression] = (entity_type, attributes)
            return cls(regex_type_attributes_map)

    @classmethod
    def train(cls, text_data_pairs, min_count=None):
        """
        Train a regex model from a set of annotated entities

        :param collections.Iterable text_data_pairs: an iterable of `(text, data)` pairs where `text` is a string and
            `data` is an anafora.AnaforaData object
        :param int min_count: the minimum number of matched entities required to keep a pattern
        """

        # prepare mappings from text to type and attributes
        ddict = collections.defaultdict
        text_type_map = ddict(lambda: collections.Counter())
        text_type_attrib_map = ddict(lambda: ddict(lambda: ddict(lambda: collections.Counter())))

        # save a regular expression for each entity
        for text, data in text_data_pairs:
            for annotation in data.annotations:
                if isinstance(annotation, anafora.AnaforaEntity):
                    annotation_text = ' '.join(text[begin:end] for begin, end in annotation.spans)
                    if annotation_text:

                        # convert text into a regular expression, with generic whitespace matchers
                        annotation_regex = r'\s+'.join(regex.escape(s) for s in annotation_text.split())

                        # prefix and suffix with word break matchers if appropriate
                        begin = min(begin for begin, end in annotation.spans)
                        prefix = r'\b' if cls._word_boundary_pattern.match(text, begin) is not None else ''
                        end = max(end for begin, end in annotation.spans)
                        suffix = r'\b' if cls._word_boundary_pattern.match(text, end) is not None else ''

                        # update counts of the regular expression and its corresponding type and attributes
                        annotation_regex = '{0}{1}{2}'.format(prefix, annotation_regex, suffix)
                        text_type_map[annotation_regex][annotation.type] += 1
                        for key, value in annotation.properties.items():
                            if not isinstance(value, anafora.AnaforaAnnotation):
                                text_type_attrib_map[annotation_regex][annotation.type][key][value] += 1

        # convert the collected counts into a model by selecting the most common
        predictions = {}
        for text, entity_types in text_type_map.items():

            # select the most common type for this expression
            [(entity_type, _)] = entity_types.most_common(1)

            # only save to the model if we've seen this entity frequently enough
            if min_count is None or entity_types[entity_type] >= min_count:

                # select the most common value for each attribute
                attrib = {}
                for name, values in text_type_attrib_map[text][entity_type].items():
                    [(value, _)] = values.most_common(1)
                    attrib[name] = value

                # associate the type and attributes with the regular expression
                predictions[text] = (entity_type, attrib)
        return cls(predictions)

    def __init__(self, regex_type_attributes_map):
        self.regex_type_attributes_map = regex_type_attributes_map

    def __eq__(self, other):
        return self.regex_type_attributes_map == other.regex_type_attributes_map

    def __repr__(self):
        return '{0}({1})'.format(self.__class__.__name__, self.regex_type_attributes_map)

    def annotate(self, text, data):
        """
        Adds annotations by matching the model's regular expressions against the text.

        :param str text: the text to be annotated
        :param anafora.AnaforaData data: the data to which the annotations should be added
        """

        # create an overall regular expression where longest expressions are matched first
        # NOTE: we have to use the regex library, not the re library, because we need more that 100 groups
        patterns = sorted(self.regex_type_attributes_map, key=len, reverse=True)
        pattern = regex.compile('|'.join('({0})'.format(pattern) for pattern in patterns))

        # for each match, create an annotation with the appropriate type and attributes
        for i, match in enumerate(pattern.finditer(text)):
            pattern = patterns[match.lastindex - 1]
            entity_type, attributes = self.regex_type_attributes_map[pattern]
            entity = anafora.AnaforaEntity()
            entity.id = "{0}@regex".format(i)
            entity.type = entity_type
            entity.spans = ((match.start(), match.end()),)
            for key, value in attributes.items():
                entity.properties[key] = value
            data.annotations.append(entity)

    def prune_by_precision(self, min_precision, text_data_pairs):
        """
        Removes patterns from the model that don't reach a minimum precision

        :param float min_precision: the minimum precision required of a pattern when applied to the given data
        :param collections.Iterable text_data_pairs: an iterable of `(text, data)` pairs where `text` is a string and
            `data` is an anafora.AnaforaData object
        """
        pattern_scores = collections.defaultdict(lambda: anafora.evaluate.Scores())
        for text, data in text_data_pairs:

            # collect the spans of each type of reference annotation
            reference_type_spans_map = collections.defaultdict(lambda: set())
            for annotation in data.annotations:
                reference_type_spans_map[annotation.type].add(annotation.spans)

            # make predictions with each pattern in the model
            for pattern in self.regex_type_attributes_map:
                predicted_spans = {((m.start(), m.end()),) for m in regex.finditer(pattern, text)}
                if predicted_spans:
                    predicted_type, _ = self.regex_type_attributes_map[pattern]

                    # update the scores for this pattern
                    pattern_scores[pattern].add(reference_type_spans_map[predicted_type], predicted_spans)

        # delete any pattern with a precision lower than the minimum requested
        for pattern, scores in pattern_scores.items():
            if scores.precision() < min_precision:
                del self.regex_type_attributes_map[pattern]

    def to_file(self, path_or_file):
        """
        :param string|file path_or_file: a string path or a file object where the RegexAnnotator should be serialized
        """

        # if passed a path instead of a file, open the path as a file for writing and recursively call to_file
        try:
            write = path_or_file.write
        except AttributeError:
            with codecs.open(path_or_file, 'w', 'utf-8') as output_file:
                self.to_file(output_file)
        else:

            # write out each pattern as a line in the model file: <regex>\t<type>\t<attributes>
            for expression, (entity_type, attributes) in sorted(self.regex_type_attributes_map.items()):
                write(expression)
                write('\t')
                write(entity_type)
                write('\t')
                write(json.dumps(attributes))
                write('\n')


def _train(train_dir, model_file, text_dir=None, text_encoding="utf-8", min_count=None, min_precision=None):

    # returns an iterator over (text, data) pairs
    def text_data_pairs():
        for sub_dir, text_name, xml_names in anafora.walk(train_dir):
            if text_dir is not None:
                text_path = os.path.join(text_dir, text_name)
            else:
                text_path = os.path.join(train_dir, sub_dir, text_name)
            if not os.path.exists(text_path):
                logging.warning("no text found at %s", text_path)
                continue
            with codecs.open(text_path, 'r', text_encoding) as text_file:
                text = text_file.read()
            for xml_name in xml_names:
                data = anafora.AnaforaData.from_file(os.path.join(train_dir, sub_dir, xml_name))
                yield text, data

    # train the model, prune if requested, and write it to a file
    model = RegexAnnotator.train(text_data_pairs(), min_count)
    if min_precision is not None:
        model.prune_by_precision(min_precision, text_data_pairs())
    model.to_file(model_file)


def _annotate(model_file, text_dir, output_dir, get_iterator, text_encoding="utf-8"):

    # load a model from the file
    model = RegexAnnotator.from_file(model_file)

    # annotate each text
    for input_sub_dir, output_sub_dir, text_name, _ in get_iterator(text_dir):

        # read in the text
        text_path = os.path.join(text_dir, input_sub_dir, text_name)
        with codecs.open(text_path, 'r', text_encoding) as text_file:
            text = text_file.read()

        # annotate the text
        data = anafora.AnaforaData()
        model.annotate(text, data)

        # save the annotated data to the output directory
        data_output_dir = os.path.join(output_dir, output_sub_dir)
        if not os.path.exists(data_output_dir):
            os.makedirs(data_output_dir)
        data_output_path = os.path.join(data_output_dir, text_name + ".xml")
        data.indent()
        data.to_file(data_output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    train_parser = subparsers.add_parser("train", help="Train a regex model from a set of annotated entities")
    train_parser.set_defaults(func=_train)
    train_parser.add_argument("-i", "--input", metavar="DIR", required=True, dest="train_dir",
                              help="The root of a set of Anafora XML files containing entity annotations.")
    train_parser.add_argument("-m", "--model", metavar="FILE", dest="model_file", required=True,
                              help="The file where the trained regex model should be written.")
    train_parser.add_argument("-t", "--text", metavar="DIR", dest="text_dir",
                              help="A flat directory containing the raw text. By default, the input directory is " +
                                   "assumed to contain the raw text alongside the Anafora XMLs.")
    train_parser.add_argument("-te", "--text-encoding", metavar="ENCODING", default="utf-8",
                              help="The encoding of the text files, important for correct character offsets " +
                                   "(default: %(default)s)")
    train_parser.add_argument("-mc", "--min-count", metavar="N", type=int,
                              help="Only keep regular expressions that matched at least N entities.")
    train_parser.add_argument("-mp", "--min-precision", metavar="X", type=float,
                              help="Only keep regular expressions with precision of at least X on the training data")

    annotate_parser = subparsers.add_parser("annotate", help="Predict entity annotations in data using a regex model")
    annotate_parser.set_defaults(func=_annotate)
    annotate_parser.add_argument("-m", "--model", metavar="FILE", dest="model_file", required=True,
                                 help="The file containing the trained regex model.")
    annotate_parser.add_argument("-o", "--output", metavar="DIR", required=True, dest="output_dir",
                                 help="The directory where the Anafora XML files containing the model predictions " +
                                      "should be written.")
    annotate_parser.add_argument("-t", "--text", metavar="DIR", dest="text_dir",
                                 help="The raw text that should be annotated with the regex model")
    structures = {
        "anafora": anafora.walk_anafora_to_anafora,
        "flat": anafora.walk_flat_to_anafora,
    }
    # this should really use type=structures.get, but that seems to interact poorly with the choices= argument
    annotate_parser.add_argument("-ts", "--text-structure", dest="get_iterator", choices=structures, default="flat",
                                 help="The hierarchical structure of the text directory (default: %(default)s)")
    annotate_parser.add_argument("-te", "--text-encoding", metavar="ENCODING", default="utf-8",
                                 help="The encoding of the text files (important for correct character offsets).")

    args = parser.parse_args()
    kwargs = vars(args)
    if 'get_iterator' in kwargs:
        kwargs['get_iterator'] = structures[kwargs['get_iterator']]
    kwargs.pop("func")(**kwargs)
