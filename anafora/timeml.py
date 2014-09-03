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
    data = anafora.AnaforaData()
    offset = 0
    for event, elem in anafora.ElementTree.iterparse(timeml_path, events=("start", "end")):
        if elem.tag in entity_id_attrs:
            id_attr = entity_id_attrs[elem.tag]
            entity_id = elem.attrib[id_attr]
            if event == "start":
                entity = anafora.AnaforaEntity()
                entity.id = entity_id
                entity.type = elem.tag
                entity.spans = ((offset, offset),)
                for name, value in elem.attrib.items():
                    if name != id_attr:
                        entity.properties[name] = value
                data.annotations.append(entity)
            elif event == "end":
                entity = data.annotations.select_id(entity_id)
                (start, _), = entity.spans
                entity.spans = ((start, offset),)

        # TODO: handle MAKEINSTANCE
        # if elem.tag == "MAKEINSTANCE":
        #     eiid = elem.attrib["eiid"]
        #     entity = data.annotations[elem.attrib["eventID"]]
        #     for name, value in elem.attrib.items():
        #         if name != "eiid" and name != "eventID":
        #             entity.properties[name] = value

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
