from __future__ import absolute_import

import codecs
import collections
import json

import regex

import anafora


class RegexAnnotator(object):

    _whitespace_pattern = regex.compile(r'\s+')

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
                regex_type_attributes_map[expression] = (entity_type, attributes)
            return cls(regex_type_attributes_map)

    @classmethod
    def train(cls, text_data_pairs):
        ddict = collections.defaultdict
        text_type_map = ddict(lambda: collections.Counter())
        text_type_attrib_map = ddict(lambda: ddict(lambda: ddict(lambda: collections.Counter())))
        for text, data in text_data_pairs:
            for annotation in data.annotations:
                if isinstance(annotation, anafora.AnaforaEntity):
                    # TODO: prefix and suffix \b where appropriate
                    annotation_text = ' '.join(text[begin:end] for begin, end in annotation.spans)
                    annotation_text = cls._whitespace_pattern.sub(r'\s+', annotation_text)
                    if annotation_text:
                        text_type_map[annotation_text][annotation.type] += 1
                        for key, value in annotation.properties.items():
                            if isinstance(value, basestring):
                                text_type_attrib_map[annotation_text][annotation.type][key][value] += 1
        predictions = {}
        for text, entity_types in text_type_map.items():
            [(entity_type, _)] = entity_types.most_common(1)
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
            for key, value in attributes.items():
                entity.properties[key] = value
            data.annotations.append(entity)

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
