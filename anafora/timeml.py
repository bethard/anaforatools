import argparse
import os

import anafora


def to_text(timeml_path):
    """
    :param xml.etree.ElementTree.Element timeml_path: path of the TimeML XML
    :return string: the (plain) text content of the XML
    """
    return ''.join(anafora.ElementTree.parse(timeml_path).getroot().itertext())


def to_anafora_data(timeml_path):
    """
    :param xml.etree.ElementTree.Element timeml_path: path of the TimeML XML
    :return anafora.AnaforaData: an Anafora version of the TimeML annotations
    """
    entity_id_attrs = {
        "TIMEX3": "tid",
        "EVENT": "eid",
        "SIGNAL": "sid",
    }
    relation_id_attrs = {
        "MAKEINSTANCE": "eiid",
        "TLINK": "lid",
        "SLINK": "lid",
        "ALINK": "lid",
    }
    text = to_text(timeml_path)
    data = anafora.AnaforaData()
    offset = 0
    for event, elem in anafora.ElementTree.iterparse(timeml_path, events=("start", "end")):
        if event == "start":
            annotation = None
            if elem.tag in entity_id_attrs:
                id_attrs = entity_id_attrs
                annotation = anafora.AnaforaEntity()
            elif elem.tag in relation_id_attrs:
                id_attrs = relation_id_attrs
                annotation = anafora.AnaforaRelation()

            if annotation is not None:
                id_attr = id_attrs[elem.tag]
                annotation.id = elem.attrib[id_attr]
                annotation.type = elem.tag
                if elem.tag in entity_id_attrs:
                    annotation.spans = ((offset, offset),)
                for name, value in elem.attrib.items():
                    if name != id_attr:
                        annotation.properties[name] = value
                data.annotations.append(annotation)

        elif event == "end" and elem.tag in entity_id_attrs:
            annotation_id = elem.attrib[entity_id_attrs[elem.tag]]
            annotation = data.annotations.select_id(annotation_id)
            (start, _), = annotation.spans
            annotation.spans = ((start, offset),)
            if elem.text != text[start:offset]:
                raise ValueError('{0}: "{1}" != "{2} ({3})"'.format(timeml_path, elem.text, text[start:offset], elem.attrib))

        if event == "start" and elem.text is not None:
            offset += len(elem.text)
        if event == "end" and elem.tail is not None:
            offset += len(elem.tail)
    return data


# http://effbot.org/zone/element-lib.htm#prettyprint
def _indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            _indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def _timeml_dir_to_anafora_dir(timeml_dir, anafora_dir):
    for root, _, file_names in os.walk(timeml_dir):
        for file_name in file_names:
            if file_name.endswith(".tml"):
                file_path = os.path.join(root, file_name)
                text = to_text(file_path)
                data = to_anafora_data(file_path)
                _indent(data.xml)

                anafora_file_name = file_name[:-4]
                anafora_file_dir = os.path.join(anafora_dir, anafora_file_name)
                if not os.path.exists(anafora_file_dir):
                    os.makedirs(anafora_file_dir)
                anafora_file_path = os.path.join(anafora_file_dir, anafora_file_name)

                with open(anafora_file_path, 'w') as text_file:
                    text_file.write(text)
                with open(anafora_file_path + ".timeml.timeml.gold.completed.xml", 'w') as xml_file:
                    anafora.ElementTree.ElementTree(data.xml).write(xml_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("timeml_dir")
    parser.add_argument("anafora_dir")
    args = parser.parse_args()
    _timeml_dir_to_anafora_dir(args.timeml_dir, args.anafora_dir)
