import anafora
import argparse
import collections
import os

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--train-dir", required=True)
    parser.add_argument("--train-text-dir")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    ddict = collections.defaultdict
    text_type_map = ddict(lambda: collections.Counter())
    text_type_attrib_map = ddict(lambda: ddict(lambda: ddict(lambda: collections.Counter())))

    for sub_dir, text_name, xml_names in anafora.walk(args.train_dir):
        if args.train_text_dir is not None:
            text_path = os.path.join(args.train_text_dir, text_name)
        else:
            text_path = os.path.join(args.train_dir, sub_dir, text_name)
        with open(text_path) as text_file:
            text = text_file.read().decode(args.encoding)

        for xml_name in xml_names:
            data = anafora.AnaforaData.from_file(os.path.join(args.train_dir, sub_dir, xml_name))
            for annotation in data.annotations:
                if isinstance(annotation, anafora.AnaforaEntity):
                    annotation_text = ' '.join(text[begin:end] for begin, end in annotation.spans)
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

    # TODO: apply predictions to text from input-dir
    # TODO: write results to output-dir
