import argparse
import ast
import itertools
import json
import logging
import os
import re
from typing import Any, Text, Mapping
import xml.etree.cElementTree as ET


def _iter_schemas(anafora_setting: ET.Element, schema_name=None):
    for an_schema_elem in anafora_setting.findall("./schemas/schema"):
        an_schema_name = an_schema_elem.attrib["name"]

        # the <file> may be listed directly
        if schema_name is None or schema_name == an_schema_name:
            an_schema_path = an_schema_elem.findtext("file")
            if an_schema_path:
                yield an_schema_name, an_schema_path

        # or there may be <mode>s, each with their own <file>
        for an_mode_elem in an_schema_elem.iter('mode'):
            an_mode_name = an_mode_elem.attrib["name"]
            an_schema_path = an_mode_elem.find("file").text
            an_schema_mode_name = f"{an_schema_name}-{an_mode_name}"
            if schema_name is None or schema_name == an_schema_mode_name:
                yield an_schema_mode_name, an_schema_path


def _iter_anafora_annotation_paths(
        anafora_path: Text,
        schema: Text,
        annotator: Text,
        status: Text,
        project: Text):
    an_filename_matcher = re.compile(
        f".*[.]{schema}[.]{annotator}[.]{status}[.]xml")
    for dirpath, dirnames, filenames in os.walk(anafora_path):
        if project is None or project in dirpath:
            for filename in filenames:
                if an_filename_matcher.match(filename):
                    yield os.path.join(anafora_path, dirpath, filename)


def anafora_to_labelstudio(
        anafora_path: Text,
        labelstudio_path: Text,
        annotator: Text,
        status: Text,
        project: Text,
        schema: Text):

    # iterate over the <schema> elements
    an_setting_tree = ET.parse(os.path.join(anafora_path, ".setting.xml"))
    for an_schema_name, an_schema_path in _iter_schemas(
            anafora_setting=an_setting_tree.getroot(),
            schema_name=schema):
        an_schema_path = os.path.join(anafora_path, ".schema", an_schema_path)
        if os.path.exists(an_schema_path):
            ls_tree, ls_property_types = anafora_schema_to_labelstudio_schema(
                anafora_tree=ET.parse(an_schema_path),
            )
            ET.indent(ls_tree, space="  ", level=0)
            ls_tree.write(f"{labelstudio_path}.{an_schema_name}.schema.xml")

            ls_data = []
            for an_annotations_path in _iter_anafora_annotation_paths(
                    anafora_path=anafora_path,
                    schema=an_schema_name,
                    annotator=annotator,
                    status=status,
                    project=project):
                logging.info(f"Processing {an_annotations_path}")
                text_path, _, _, _, _ = an_annotations_path.rsplit('.', 4)
                if not os.path.exists(text_path):
                    logging.warning(f"Skipping file because text file is "
                                    f"missing:\n{an_annotations_path}")
                    continue
                with open(text_path) as text_file:
                    text = text_file.read()
                ls_data.append(anafora_annotations_to_labelstudio_annotations(
                    anafora_tree=ET.parse(an_annotations_path),
                    text=text,
                    source=os.path.basename(text_path),
                    labelstudio_property_types=ls_property_types,
                ))

            ls_output_path = f"{labelstudio_path}.{an_schema_name}.data.json"
            with open(ls_output_path, 'w') as labelstudio_file:
                json.dump(ls_data, labelstudio_file, indent=4)


def anafora_schema_to_labelstudio_schema(
        anafora_tree: ET.ElementTree) -> tuple[ET.ElementTree, Mapping[Text, Text]]:
    # the overall view
    ls_view_elem = ET.Element('View', dict(style="display: flex;"))

    # the view of the label choices
    ls_labels_view_elem = ET.SubElement(ls_view_elem, 'View', dict(
        style="flex: 20%"))
    ls_labels_elem = ET.SubElement(ls_labels_view_elem, 'Labels', dict(
        name="type", toName="text", showInline="false"))
    ls_relations_elem = ET.SubElement(ls_labels_view_elem, 'Relations')
    relation_types = set()

    # the view of the text
    ls_text_view_elem = ET.SubElement(ls_view_elem, 'View', dict(
        style="flex: 60%"))
    ET.SubElement(ls_text_view_elem, 'Text', dict(name="text", value="$text"))

    # the view of the attribute choices
    ls_attrib_view_elem = ET.SubElement(ls_view_elem, 'View', dict(
        style="flex: 20%"))

    an_root = anafora_tree.getroot()
    default_attributes = dict(required=False)
    for an_defaults_elem in an_root.iter("defaultattribute"):
        for elem in an_defaults_elem:
            default_attributes[elem.tag] = ast.literal_eval(elem.text)

    def get(attrib, name):
        return attrib.get(name, default_attributes[name])

    ls_property_types = {}
    for an_entities_elem in an_root.iter('entities'):
        entities_type = an_entities_elem.attrib["type"]
        ET.SubElement(ls_labels_elem, 'Header', dict(value=f"{entities_type}:"))
        for an_entity_elem in an_entities_elem.iter('entity'):
            entity_type = an_entity_elem.attrib["type"]
            ls_label_attrib = dict(value=entity_type)
            hotkey = an_entity_elem.attrib.get("hotkey")
            if hotkey is not None:
                ls_label_attrib["hotkey"] = hotkey
            color = an_entity_elem.attrib.get("color")
            if color is not None:
                ls_label_attrib["background"] = f"#{color}"
            ET.SubElement(ls_labels_elem, 'Label', ls_label_attrib)
            for an_property_elem in an_entity_elem.iter('property'):
                property_type = an_property_elem.attrib["type"]
                property_input = an_property_elem.attrib["input"]
                property_required = get(an_property_elem.attrib, "required")
                ls_property_name = f"{entity_type}-{property_type}"
                ls_prop_attrib = dict(
                    visibleWhen="region-selected",
                    whenTagName="type",
                    whenLabelValue=entity_type)

                if property_input == "text":
                    ls_property_types[ls_property_name] = "textarea"
                    ls_prop_elem = ET.SubElement(
                        ls_attrib_view_elem, 'View', ls_prop_attrib)
                    ET.SubElement(ls_prop_elem, 'Header', dict(
                        value=f"{property_type}:"))
                    ls_text_area_attrib = dict(
                        name=ls_property_name,
                        toName="text",
                        perRegion="true")
                    if property_required:
                        ls_text_area_attrib["required"] = "true"
                    ET.SubElement(ls_prop_elem, 'TextArea', ls_text_area_attrib)

                elif property_input == "choice":
                    ls_property_types[ls_property_name] = "choices"
                    ls_prop_elem = ET.SubElement(
                        ls_attrib_view_elem, 'View', ls_prop_attrib)
                    ls_choices_attrib = dict(
                        name=ls_property_name,
                        toName="text",
                        perRegion="true")
                    if property_required:
                        ls_choices_attrib["required"] = "true"
                    ls_choices_elem = ET.SubElement(
                        ls_prop_elem, 'Choices', ls_choices_attrib)
                    ET.SubElement(ls_choices_elem, 'Header', dict(
                        value=f"{property_type}:"))
                    for choice in an_property_elem.text.split(','):
                        if choice:
                            ET.SubElement(ls_choices_elem, 'Choice', dict(
                                value=choice))

                elif property_input == "list":
                    ls_property_types[ls_property_name] = 'relation'
                    if property_type not in relation_types:
                        ET.SubElement(ls_relations_elem, 'Relation', dict(
                            value=property_type))
                        relation_types.add(property_type)

                else:
                    raise ValueError(f'unexpected input_type: {property_input}')

    for an_relations_elem in an_root.iter('relations'):
        relations_type = an_relations_elem.attrib["type"]
        for an_relation_elem in an_relations_elem.iter('relation'):
            relation_type = an_relation_elem.attrib["type"]
            argument_types = []
            relation_subtypes = []
            for an_property_elem in an_relation_elem.iter('property'):
                property_type = an_property_elem.attrib["type"]
                property_input = an_property_elem.attrib["input"]
                ls_property_name = f"{relation_type}-{property_type}"
                if property_input == "choice":
                    relation_subtypes.append([
                        f"{property_type}={value}"
                        for value in an_property_elem.text.split(',')])
                    ls_property_types[ls_property_name] = 'choices'
                elif property_input == "list":
                    ls_property_types[ls_property_name] = 'relation'
                    argument_types.append(property_type)
                else:
                    raise ValueError(f'unexpected input_type: {property_input}')

            source_type = argument_types[0]
            for argument_type in argument_types[1:]:
                if not relation_subtypes:
                    relation_strings = [f"{relation_type}:{source_type}:"
                                        f"{argument_type}"]
                else:
                    relation_strings = [
                        f"{relation_type}:{':'.join(subtypes)}:{source_type}:"
                        f"{argument_type}"
                        for subtypes in itertools.product(*relation_subtypes)
                    ]
                for relation_string in relation_strings:
                    ET.SubElement(ls_relations_elem, 'Relation', dict(
                        value=relation_string))
    ls_tree = ET.ElementTree(ls_view_elem)
    return ls_tree, ls_property_types


def anafora_annotations_to_labelstudio_annotations(
        anafora_tree: ET.ElementTree,
        text: Text,
        source: Text,
        labelstudio_property_types: Mapping[Text, Text]) -> Mapping[Text, Any]:
    ls_types = labelstudio_property_types
    ls_type_to_value = {"textarea": "text", "choices": "choices"}
    ls_results = []
    ls_meta_info = {"source": source}

    an_root = anafora_tree.getroot()
    an_info_elem = an_root.find('info')
    for an_elem in an_info_elem:
        ls_meta_info[an_elem.tag] = an_elem.text

    an_annotations_elem = an_root.find("annotations")
    for an_elem in an_annotations_elem:
        an_id = an_elem.find("id").text
        an_type = an_elem.find("type").text
        an_parents_type = an_elem.find("parentsType").text

        if an_elem.tag == "entity":
            an_spans = [
                tuple(int(offset) for offset in tuple(span_text.split(",")))
                for span_text in an_elem.find("span").text.split(";")
            ]
            for i, (start, end) in enumerate(an_spans):
                an_revised_id = an_id if i == 0 else f"{an_id}-{i}"
                ls_results.append({
                    "value": {
                        "start": start,
                        "end": end,
                        "labels": [an_type],
                    },
                    "id": an_revised_id,
                    "from_name": "type",
                    "to_name": "text",
                    "type": "labels"
                })
                for an_prop_elem in an_elem.find('properties'):
                    an_prop_name = an_prop_elem.tag
                    an_prop_value = an_prop_elem.text
                    if an_prop_value:
                        ls_property_name = f"{an_type}-{an_prop_name}"
                        ls_property_type = ls_types[ls_property_name]
                        if ls_property_type == 'relation':
                            ls_results.append({
                                "from_id": an_revised_id,
                                "to_id": an_prop_value,
                                "type": "relation",
                                "labels": [an_prop_name],
                            })
                        else:
                            ls_results.append({
                                "value": {
                                    "start": start,
                                    "end": end,
                                    ls_type_to_value[ls_property_type]: [
                                        an_prop_value
                                    ],
                                },
                                "id": an_revised_id,
                                "from_name": ls_property_name,
                                "to_name": "text",
                                "type": ls_property_type
                            })

        elif an_elem.tag == "relation":
            choices_elems = []
            relations_elems = []
            for an_prop_elem in an_elem.find('properties'):
                ls_property_type = labelstudio_property_types[f"{an_type}-{an_prop_elem.tag}"]
                if ls_property_type == "choices":
                    choices_elems.append(an_prop_elem)
                elif ls_property_type == "relation":
                    relations_elems.append(an_prop_elem)
                else:
                    raise ValueError(f'unexpected property type: {ls_property_type}')

            relation_string = an_type
            for an_prop_elem in choices_elems:
                relation_string += f":{an_prop_elem.tag}={an_prop_elem.text}"

            ls_source_id = relations_elems[0].text
            ls_source_type = relations_elems[0].tag
            for an_prop_elem in relations_elems[1:]:
                ls_target_id = an_prop_elem.text
                ls_target_type = an_prop_elem.tag
                ls_results.append({
                    "from_id": ls_source_id,
                    "to_id": ls_target_id,
                    "type": "relation",
                    "from_name": "",
                    "labels": [
                        f"{relation_string}:{ls_source_type}:{ls_target_type}"
                    ]
                })
        else:
            raise ValueError(f'unexpected element type: {an_elem.tag}')

    return {
        "data": {
            "text": text,
            "meta_info": ls_meta_info
        },
        "annotations": [{"result": ls_results}]
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""%(prog)s converts Anafora schema XML and Anafora
        annotations XML into Label Studio schema XML and Label Studio
        annotations JSON.""")
    parser.add_argument("anafora_path",
                        help="""Path to the root directory of an Anafora
                        installation, including the .setting.xml file, the
                        .schema directory, and the directories of XML data
                        files.""")
    parser.add_argument("labelstudio_path",
                        help="""Prefix of the Label Studio XML schema and JSON
                        annotation files to be written out.""")
    parser.add_argument("--annotator", default="gold", metavar="NAME",
                        help="""Selects which annotator's files should be
                        converted (default: %(default)s).""")
    parser.add_argument("--status", default="completed", metavar="TYPE",
                        help="""Selects which status of annotations should be
                        converted (default: %(default)s).""")
    parser.add_argument("--project", metavar="NAME",
                        help="""Selects which annotation projects should be
                        converted (default: all)""")
    parser.add_argument("--schema", metavar="NAME",
                        help="""Selects which annotation schemas should be
                        converted (default: all)""")
    anafora_to_labelstudio(**vars(parser.parse_args()))
