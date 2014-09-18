import anafora
import argparse
import collections
import os
import re


def _normalize_whitespace(text, pattern=re.compile(r'\s+')):
    return pattern.sub(' ', text)


def train(train_dir, train_text_dir=None, encoding="utf-8"):
    ddict = collections.defaultdict
    text_type_map = ddict(lambda: collections.Counter())
    text_type_attrib_map = ddict(lambda: ddict(lambda: ddict(lambda: collections.Counter())))

    for sub_dir, text_name, xml_names in anafora.walk(train_dir):
        if train_text_dir is not None:
            text_path = os.path.join(train_text_dir, text_name)
        else:
            text_path = os.path.join(train_dir, sub_dir, text_name)
        with open(text_path) as text_file:
            text = text_file.read().decode(encoding)

        for xml_name in xml_names:
            data = anafora.AnaforaData.from_file(os.path.join(train_dir, sub_dir, xml_name))
            for annotation in data.annotations:
                if isinstance(annotation, anafora.AnaforaEntity):
                    annotation_text = ' '.join(text[begin:end] for begin, end in annotation.spans)
                    annotation_text = _normalize_whitespace(annotation_text)
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
    return predictions


def predict(predictions, output_dir, input_anafora_dir=None, input_text_dir=None, encoding="utf-8"):
    patterns = [r'\b{0}\b'.format(re.sub(r'\s+', r'\s+', re.escape(text))) for text in predictions]
    patterns = sorted(patterns, key=len, reverse=True)
    pattern = re.compile('|'.join(patterns))

    if input_anafora_dir is not None:
        root = input_anafora_dir
        walk_iter = ((sub_dir, sub_dir, text_name) for sub_dir, text_name, _ in anafora.walk(input_anafora_dir))
    else:
        root = input_text_dir
        walk_iter = (('', file_name, file_name) for file_name in os.listdir(input_text_dir))

    for input_sub_dir, output_sub_dir, text_name in walk_iter:
        text_path = os.path.join(root, input_sub_dir, text_name)
        with open(text_path) as text_file:
            text = text_file.read().decode(encoding)

        data = anafora.AnaforaData()
        for i, match in enumerate(pattern.finditer(text)):
            entity_type, attrib = predictions[_normalize_whitespace(match.group())]
            entity = anafora.AnaforaEntity()
            entity.id = "{0}@{1}".format(i, text_name)
            entity.type = entity_type
            entity.spans = ((match.start(), match.end()),)
            for name, value in attrib.items():
                entity.properties[name] = value
            data.annotations.append(entity)

        data_output_dir = os.path.join(output_dir, output_sub_dir)
        if not os.path.exists(data_output_dir):
            os.makedirs(data_output_dir)
        data_output_path = os.path.join(data_output_dir, text_name + ".xml")
        with open(data_output_path, 'w') as output_file:
            anafora.ElementTree.ElementTree(data.xml).write(output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("--train-dir", required=True)
    parser.add_argument("--train-text-dir")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-anafora-dir")
    group.add_argument("--input-text-dir")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    model = train(
        train_dir=args.train_dir,
        train_text_dir=args.train_text_dir,
        encoding=args.encoding)
    predict(
        predictions=model,
        input_anafora_dir=args.input_anafora_dir,
        input_text_dir=args.input_text_dir,
        output_dir=args.output_dir,
        encoding=args.encoding)
