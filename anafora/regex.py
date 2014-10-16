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
        :param string|file path_or_file: a string path or a file object containing a serialized RegexAnnotator
        """
        try:
            path_or_file.readline
        except AttributeError:
            with codecs.open(path_or_file, 'r', 'utf-8') as output_file:
                return cls.from_file(output_file)
        else:
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
                try:
                    regex.compile(expression)
                except regex.error as e:
                    raise ValueError("{0} in {1!r}".format(e.message, expression))
                if cls._capturing_group_pattern.search(expression):
                    raise ValueError("capturing groups are not allowed: " + expression)
                regex_type_attributes_map[expression] = (entity_type, attributes)
            return cls(regex_type_attributes_map)

    @classmethod
    def train(cls, text_data_pairs, min_count=None):
        ddict = collections.defaultdict
        text_type_map = ddict(lambda: collections.Counter())
        text_type_attrib_map = ddict(lambda: ddict(lambda: ddict(lambda: collections.Counter())))
        for text, data in text_data_pairs:
            for annotation in data.annotations:
                if isinstance(annotation, anafora.AnaforaEntity):
                    annotation_text = ' '.join(text[begin:end] for begin, end in annotation.spans)
                    if annotation_text:
                        annotation_regex = r'\s+'.join(regex.escape(s) for s in annotation_text.split())
                        begin = min(begin for begin, end in annotation.spans)
                        prefix = r'\b' if cls._word_boundary_pattern.match(text, begin) is not None else ''
                        end = max(end for begin, end in annotation.spans)
                        suffix = r'\b' if cls._word_boundary_pattern.match(text, end) is not None else ''
                        annotation_regex = '{0}{1}{2}'.format(prefix, annotation_regex, suffix)
                        text_type_map[annotation_regex][annotation.type] += 1
                        for key, value in annotation.properties.items():
                            if isinstance(value, basestring):
                                text_type_attrib_map[annotation_regex][annotation.type][key][value] += 1
        predictions = {}
        for text, entity_types in text_type_map.items():
            [(entity_type, _)] = entity_types.most_common(1)
            if min_count is None or entity_types[entity_type] >= min_count:
                attrib = {}
                for name, values in text_type_attrib_map[text][entity_type].items():
                    [(value, _)] = values.most_common(1)
                    attrib[name] = value
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
        :param string text: the text to be annotated
        :param anafora.AnaforaData data: the data to which the annotations should be added
        """
        patterns = sorted(self.regex_type_attributes_map, key=len, reverse=True)
        pattern = regex.compile('|'.join('({0})'.format(pattern) for pattern in patterns))
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
        pattern_scores = collections.defaultdict(lambda: anafora.evaluate.Scores())
        for text, data in text_data_pairs:
            reference_type_spans_map = collections.defaultdict(lambda: set())
            for annotation in data.annotations:
                reference_type_spans_map[annotation.type].add(annotation.spans)
            for pattern in self.regex_type_attributes_map:
                predicted_spans = {((m.start(), m.end()),) for m in regex.finditer(pattern, text)}
                if predicted_spans:
                    predicted_type, _ = self.regex_type_attributes_map[pattern]
                    pattern_scores[pattern].add(reference_type_spans_map[predicted_type], predicted_spans)
        for pattern, scores in pattern_scores.items():
            if scores.precision() < min_precision:
                del self.regex_type_attributes_map[pattern]

    def to_file(self, path_or_file):
        """
        :param string|file path_or_file: a string path or a file object where the RegexAnnotator should be serialized
        """
        try:
            write = path_or_file.write
        except AttributeError:
            with codecs.open(path_or_file, 'w', 'utf-8') as output_file:
                self.to_file(output_file)
        else:
            for expression, (entity_type, attributes) in sorted(self.regex_type_attributes_map.items()):
                write(expression)
                write('\t')
                write(entity_type)
                write('\t')
                write(json.dumps(attributes))
                write('\n')


def _train(train_dir, model_file, text_dir=None, text_encoding="utf-8", min_count=None, min_precision=None):
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

    model = RegexAnnotator.train(text_data_pairs(), min_count)
    if min_precision is not None:
        model.prune_by_precision(min_precision, text_data_pairs())
    model.to_file(model_file)


def _annotate(model_file, text_dir, output_dir, get_iterator, text_encoding="utf-8"):
    model = RegexAnnotator.from_file(model_file)
    for input_sub_dir, output_sub_dir, text_name, _ in get_iterator(text_dir):
        text_path = os.path.join(text_dir, input_sub_dir, text_name)
        with codecs.open(text_path, 'r', text_encoding) as text_file:
            text = text_file.read()

        data = anafora.AnaforaData()
        model.annotate(text, data)

        data_output_dir = os.path.join(output_dir, output_sub_dir)
        if not os.path.exists(data_output_dir):
            os.makedirs(data_output_dir)
        data_output_path = os.path.join(data_output_dir, text_name + ".xml")
        data.indent()
        data.to_file(data_output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    train_parser = subparsers.add_parser("train")
    train_parser.set_defaults(func=_train)
    train_parser.add_argument("--train-dir", required=True)
    train_parser.add_argument("--model-file", required=True)
    train_parser.add_argument("--text-dir")
    train_parser.add_argument("--text-encoding", default="utf-8")
    train_parser.add_argument("--min-count", type=int)
    train_parser.add_argument("--min-precision", type=float)

    annotate_parser = subparsers.add_parser("annotate")
    annotate_parser.set_defaults(func=_annotate)
    annotate_parser.add_argument("--model-file", required=True)
    annotate_parser.add_argument("--output-dir", required=True)
    annotate_parser.add_argument("--text-dir", required=True)
    structures = {
        "anafora": anafora.walk_anafora_to_anafora,
        "flat": anafora.walk_flat_to_anafora,
    }
    annotate_parser.add_argument("--text-dir-structure", choices=structures, default="flat")
    annotate_parser.add_argument("--text-encoding", default="utf-8")

    args = parser.parse_args()
    kwargs = vars(args)
    if 'text_dir_structure' in kwargs:
        kwargs['get_iterator'] = structures[kwargs.pop('text_dir_structure')]
    kwargs.pop("func")(**kwargs)
