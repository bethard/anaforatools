import argparse
import os
import re

import anafora

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoding", default="utf-8")
    parser.add_argument("entity_type")
    parser.add_argument("regex_file")
    parser.add_argument("input_dir")
    parser.add_argument("output_dir")
    args = parser.parse_args()

    with open(args.regex_file) as regex_file:
        lines = [line.rstrip("\r\n") for line in regex_file.readlines()]
        regex = re.compile(r"\b" + r"\b|\b".join(lines) + r"\b", re.IGNORECASE)

    for sub_dir, text_name, _ in anafora.walk(args.input_dir):
        text_path = os.path.join(args.input_dir, sub_dir, text_name)
        with open(text_path) as text_file:
            text = text_file.read().decode(args.encoding)

        data = anafora.AnaforaData()
        for i, match in enumerate(regex.finditer(text.lower())):
            start, end = match.span()
            annotation = anafora.AnaforaEntity()
            annotation.id = "{0}@{1}".format(i, text_name)
            annotation.type = args.entity_type
            annotation.spans = ((start, end),)
            data.annotations.append(annotation)

        output_dir = os.path.join(args.output_dir, sub_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        output_path = os.path.join(output_dir, text_name + ".xml")
        with open(output_path, 'w') as output_file:
            anafora.ElementTree.ElementTree(data.xml).write(output_file)
