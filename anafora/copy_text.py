import argparse
import os

import sys

import anafora
import anafora.timeml


def copy_timeml_text(timeml_dir, anafora_dir, xml_name_regex):
    timeml_paths = {}
    for dir_path, _, file_names in os.walk(timeml_dir):
        for file_name in file_names:
            if file_name.endswith(".tml"):
                timeml_paths[file_name[:-4]] = os.path.join(dir_path, file_name)

    for sub_dir, text_file_name, _ in anafora.walk(
            anafora_dir, xml_name_regex=xml_name_regex):
        if text_file_name not in timeml_paths:
            sys.exit("No .tml file found for " + text_file_name)
        text = anafora.timeml.to_text(timeml_paths[text_file_name])
        text_path = os.path.join(anafora_dir, sub_dir, text_file_name)
        if os.path.exists(text_path):
            sys.exit("Text file already exists: " + text_path)
        with open(text_path, 'w') as text_file:
            text_file.write(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    timeml_parser = subparsers.add_parser("timeml")
    timeml_parser.set_defaults(func=copy_timeml_text)
    timeml_parser.add_argument(
        "-x", "--xml-name-regex",
        metavar="REGEX", default=".*completed.*[.]xml$",
        help="A regular expression for matching XML files in the Anafora " +
             "subdirectories (default: %(default)r)")
    timeml_parser.add_argument("timeml_dir")
    timeml_parser.add_argument("anafora_dir")

    args = parser.parse_args()
    kwargs = vars(args)
    kwargs.pop("func")(**kwargs)
