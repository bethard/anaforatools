import argparse
import os

import anafora


def _flatten(items):
    for item in items:
        if not isinstance(item, int):
            for sub_item in _flatten(item):
                yield sub_item
        else:
            yield item


def add_relations_to_closest(data, source_type, target_type,
                             relation_type, relation_source_property, relation_target_property,
                             other_properties=None):
    """

    :param anafora.AnaforaData data: the Anafora data where relations should be added
    :return:
    """
    points = {}
    for source_entity in data.annotations.select_type(source_type):
        points[source_entity.id] = list(_flatten(source_entity.spans))
    for target_entity in data.annotations.select_type(target_type):
        points[target_entity.id] = list(_flatten(target_entity.spans))

    for source_entity in data.annotations.select_type(source_type):
        def distance_to_source_entity(entity):
            return min(abs(p1 - p2) for p1 in points[source_entity.id] for p2 in points[entity.id])
        target_entities = list(data.annotations.select_type(target_type))
        if target_entities:
            target_entity = min(target_entities, key=distance_to_source_entity)
            relation = anafora.AnaforaRelation()
            relation.id = "{0}@{1}".format(source_entity.id, target_entity.id)
            data.annotations.append(relation)
            relation.type = relation_type
            relation.properties[relation_source_property] = source_entity
            relation.properties[relation_target_property] = target_entity
            if other_properties is not None:
                for name in other_properties:
                    relation.properties[name] = other_properties[name]


if __name__ == "__main__":
    def _to_dict(value):
        return dict(item.split("=") for item in value.split(","))

    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--xml-name-regex", default="[.]xml$")
    parser.add_argument("--output-dir", required=True)

    subparsers = parser.add_subparsers()

    relations_to_closest_parser = subparsers.add_parser('closest')
    relations_to_closest_parser.set_defaults(func=add_relations_to_closest)
    relations_to_closest_parser.add_argument("--source-type", required=True)
    relations_to_closest_parser.add_argument("--target-type", required=True)
    relations_to_closest_parser.add_argument("--relation-type", required=True)
    relations_to_closest_parser.add_argument("--relation-source-property", required=True)
    relations_to_closest_parser.add_argument("--relation-target-property", required=True)
    relations_to_closest_parser.add_argument("--other-properties", type=_to_dict)

    args = parser.parse_args()
    kwargs = vars(args)
    func = kwargs.pop("func")
    input_dir = kwargs.pop('input_dir')
    xml_name_regex = kwargs.pop('xml_name_regex')
    output_dir = kwargs.pop('output_dir')

    for sub_dir, _, xml_file_names in anafora.walk(input_dir, xml_name_regex):
        for xml_file_name in xml_file_names:
            input_data = anafora.AnaforaData.from_file(os.path.join(input_dir, sub_dir, xml_file_name))
            func(input_data, **kwargs)
            output_sub_dir = os.path.join(output_dir, sub_dir)
            if not os.path.exists(output_sub_dir):
                os.makedirs(output_sub_dir)
            input_data.to_file(os.path.join(output_dir, sub_dir, xml_file_name))
