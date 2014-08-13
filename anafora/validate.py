import argparse
import collections
import logging
import os

import anafora


class Schema(object):
    def __init__(self, xml):
        """
        :param xml.etree.ElementTree.Element xml: the <schema> element
        """
        default_attribute_elem = xml.find("defaultattribute")
        definition_elem = xml.find("definition")
        entities_elem = definition_elem.find("entities")
        relations_elem = definition_elem.find("relations")
        if entities_elem is None and relations_elem is None:
            raise ValueError("no entities or relations in schema")

        self.default_attributes = {}
        for attribute_elem in default_attribute_elem:
            self.default_attributes[attribute_elem.tag] = attribute_elem.text

        self.type_to_properties = {}
        for annotations_elem in [entities_elem, relations_elem]:
            if annotations_elem is not None:
                for annotation_elem in annotations_elem:
                    annotation_type = annotation_elem.attrib["type"]
                    properties = {}
                    properties_elem = annotation_elem.find("properties")
                    if properties_elem is not None:
                        for property_elem in properties_elem:
                            schema_property = SchemaProperty(property_elem, self.default_attributes)
                            properties[schema_property.type] = schema_property
                    self.type_to_properties[annotation_type] = properties

    @classmethod
    def from_file(cls, xml_path):
        return cls(anafora.ElementTree.parse(xml_path).getroot())

    def errors(self, data):
        """
        :param AnaforaData data: the data to be validated
        :return: a list of (invalid annotation, explanation string)
        """
        errors = []
        for annotation in data.annotations:
            error = self._first_error(annotation)
            if error is not None:
                errors.append((annotation, error))
        return errors

    def _first_error(self, annotation):
        """
        :param AnaforaAnnotation annotation: one annotation from an AnaforaData
        :return: an explanation string if the annotation is invalid, otherwise None
        """
        schema_properties = self.type_to_properties.get(annotation.type)
        if schema_properties is None:
            return 'invalid type "{0}"'.format(annotation.type)
        for schema_property in schema_properties.values():
            if schema_property.required and not schema_property.type in annotation.properties:
                return 'missing required property "{0}"'.format(schema_property.type)
        for name, value in annotation.properties.items():
            schema_property = schema_properties[name]
            if schema_property.instance_of is not None:
                if not isinstance(value, anafora.AnaforaAnnotation):
                    return 'invalid value {0} for property "{1}"'.format(value, schema_property.type)
                if not value.type in schema_property.instance_of:
                    return 'invalid type "{0}" for property "{1}"'.format(value.type, schema_property.type)
        return None


class SchemaProperty(object):
    def __init__(self, xml, default_attributes):
        """
        :param xml.etree.ElementTree.Element xml: the <property> element
        :param dict default_attributes: a mapping holding default attribute (name, value) pairs
        """

        def get(name, default):
            return xml.attrib.get(name, default_attributes.get(name, default))

        self.type = get("type", None)
        self.required = get("required", None) == "True"
        self.instance_of = get("instanceOf", None)
        if self.instance_of is not None:
            self.instance_of = self.instance_of.split(",")


def log_schema_errors(schema, anafora_dir):
    """
    :param Schema schema: the schema to validate against
    :param string anafora_dir: the Anafora directory containing directories to validate
    """
    for anafora_dir, sub_dir, xml_names in anafora.walk(anafora_dir):
        for xml_name in xml_names:
            xml_path = os.path.join(anafora_dir, sub_dir, xml_name)
            try:
                data = anafora.AnaforaData.from_file(xml_path)
            except anafora.ElementTree.ParseError:
                logging.warn("%s: invalid XML", xml_path)
            else:
                for annotation, error in schema.errors(data):
                    logging.warn("%s: %s", xml_path, error)


def find_entities_with_identical_spans(data):
    """
    :param AnaforaData data: the Anafora data to be searched
    """
    span_entities = collections.defaultdict(lambda: [])
    for ann in data.entities:
        span_entities[ann.spans].append(ann)
    for span, annotations in span_entities.items():
        if len(annotations) > 1:
            yield span, annotations


def log_entities_with_identical_spans(anafora_dir):
    """
    :param AnaforaData data: the Anafora data to be searched
    """
    for anafora_dir, sub_dir, xml_names in anafora.walk(anafora_dir):
        for xml_name in xml_names:
            xml_path = os.path.join(anafora_dir, sub_dir, xml_name)
            try:
                data = anafora.AnaforaData.from_file(xml_path)
            except anafora.ElementTree.ParseError:
                pass
            else:
                for span, annotations in find_entities_with_identical_spans(data):
                    logging.warn("%s: multiple entities for span %s:\n%s",
                                 xml_path, span, "\n".join(str(ann).rstrip() for ann in annotations))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("schema_xml")
    parser.add_argument("anafora_dir")
    args = parser.parse_args()
    logging.basicConfig(format="%(levelname)s:%(message)s")

    log_schema_errors(Schema.from_file(args.schema_xml), args.anafora_dir)
    log_entities_with_identical_spans(args.anafora_dir)