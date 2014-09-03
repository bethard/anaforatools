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

        if event == "start" and elem.text is not None:
            offset += len(elem.text)
        if event == "end" and elem.tail is not None:
            offset += len(elem.tail)
    return data

#if __name__ == "__main__":
#    for timeml_dir in sys.argv[1:]:
#        for timeml_file in os.listdir(timeml_dir):
#            timeml_path = os.path.join(timeml_dir, timeml_file)
#            timeml_elem = anafora.ElementTree.parse(timeml_path).getroot()
#            data = to_anafora_data(timeml_elem)
