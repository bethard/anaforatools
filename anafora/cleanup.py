import argparse
import logging
import os

import anafora
import anafora.validate

def fix_thyme_errors(schema, input_dir, output_dir, xml_name_regex="[.]xml$"):
    """
    :param schema anafora.validate.Schema: the THYME schema
    :param input_dir str: the root of a set of THYME Anafora XML directories
    :param output_dir str: the directory where the cleaned versions of the THYME Anafora XML files should be written.
        The directory structure will mirror the input directory structure.
    """
    for sub_dir, text_name, xml_names in anafora.walk(input_dir, xml_name_regex):
        for xml_name in xml_names:
            xml_path = os.path.join(input_dir, sub_dir, xml_name)

            # load the data from the Anafora XML
            try:
                data = anafora.AnaforaData.from_file(xml_path)
            except anafora.ElementTree.ParseError as e:
                logging.warning("SKIPPING invalid XML: %s: %s", e, xml_path)
                continue

            # remove invalid TLINKs and ALINKs
            changed = False
            to_remove = []
            for annotation in data.annotations:
                try:
                    schema.validate(annotation)
                except anafora.validate.SchemaValidationError as e:
                    if annotation.type in {"TLINK", "ALINK"}:
                        logging.warning("REMOVING %s: %s", e, annotation)
                        to_remove.append(annotation)
            for annotation in to_remove:
                data.annotations.remove(annotation)
                changed = True

            # remove TIMEX3s that are directly on top of SECTIONTIMEs and DOCTIMEs
            for span, annotations in anafora.validate.find_entities_with_identical_spans(data):
                try:
                    # sorts SECTIONTIME and DOCTIME before TIMEX3
                    special_time, timex = sorted(annotations, key=lambda a: a.type)
                except ValueError:
                    pass
                else:
                    if special_time.type in {"SECTIONTIME", "DOCTIME"} and timex.type == "TIMEX3":
                        msg = "REPLACING multiple entities for span %s: %s WITH %s"
                        logging.warning(msg, span, timex, special_time)
                        for annotation in data.annotations:
                            for name, value in annotation.properties.items():
                                if value is timex:
                                    annotation.properties[name] = special_time
                        data.annotations.remove(timex)
                        changed = True

            # if we found and fixed any errors, write out the new XML file
            if changed:
                output_sub_dir = os.path.join(output_dir, sub_dir)
                if not os.path.exists(output_sub_dir):
                    os.makedirs(output_sub_dir)
                output_path = os.path.join(output_sub_dir, xml_name)
                data.to_file(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    thyme_parser = subparsers.add_parser('thyme')
    thyme_parser.set_defaults(func=fix_thyme_errors)
    thyme_parser.add_argument("-s", "--schema", metavar="FILE", required=True, type=anafora.validate.Schema.from_file,
                              help="An Anafora schema XML file which Anafora annotation XML files will be validated " +
                                   "against.")
    thyme_parser.add_argument("-i", "--input", metavar="DIR", required=True, dest="input_dir",
                              help="The root of a set of Anafora annotation XML directories.")
    thyme_parser.add_argument("-o", "--output", metavar="DIR", required=True, dest="output_dir",
                              help="The directory where the cleaned versions of the Anafora annotation XML files " +
                                   "should be written. The directory structure will mirror the input directory " +
                                   "structure.")
    thyme_parser.add_argument("-x", "--xml-name-regex", metavar="REGEX", default="[.]xml$",
                              help="A regular expression for matching XML files, typically used to restrict the " +
                                   "validation to a subset of the available files (default: %(default)r)")

    args = parser.parse_args()
    kwargs = vars(args)
    kwargs.pop('func')(**kwargs)
