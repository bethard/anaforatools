import anafora
import argparse
import collections
import os
import re

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--train-dir", required=True)
    parser.add_argument("--train-text-dir")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    def normalize_whitespace(text, pattern=re.compile(r'\s+')):
        return pattern.sub(' ', text)

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
                    annotation_text = normalize_whitespace(annotation_text)
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

    patterns = [re.sub(r'\s+', r'\s+', re.escape(text)) for text in predictions]
    patterns = sorted(patterns, key=len, reverse=True)
    pattern = re.compile('|'.join(patterns))

    for sub_dir, text_name, xml_names in anafora.walk(args.input_dir):
        text_path = os.path.join(args.input_dir, sub_dir, text_name)
        with open(text_path) as text_file:
            text = text_file.read().decode(args.encoding)

        data = anafora.AnaforaData()
        for i, match in enumerate(pattern.finditer(text)):
            entity_type, attrib = predictions[normalize_whitespace(match.group())]
            entity = anafora.AnaforaEntity()
            entity.id = "{0}@{1}".format(i, text_name)
            entity.type = entity_type
            entity.spans = ((match.start(), match.end()),)
            for name, value in attrib.items():
                entity.properties[name] = value
            data.annotations.append(entity)

        output_dir = os.path.join(args.output_dir, sub_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_path = os.path.join(output_dir, text_name + ".xml")
        with open(output_path, 'w') as output_file:
            anafora.ElementTree.ElementTree(data.xml).write(output_file)
