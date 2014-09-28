from __future__ import absolute_import

import codecs
import json

import regex

import anafora


class RegexAnnotator(object):

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
        pattern = regex.compile('|'.join(r'\b({0})\b'.format(pattern) for pattern in patterns))
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
