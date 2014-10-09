import argparse
import logging
import os

import anafora
import anafora.validate

def fix_thyme_errors(schema, input_dir, xml_name_regex, output_dir):
    """
    :param schema anafora.validate.Schema:
    :param input_dir str:
    :param output_dir str:
    :return:
    """
    for sub_dir, text_name, xml_names in anafora.walk(input_dir, xml_name_regex):
        for xml_name in xml_names:
            xml_path = os.path.join(input_dir, sub_dir, xml_name)
            data = anafora.AnaforaData.from_file(xml_path)
            changed = False
            while True:
                to_remove = []
                for annotation in data.annotations:
                    try:
                        schema.validate(annotation)
                    except anafora.validate.SchemaValidationError as e:
                        if annotation.type in {"TLINK", "ALINK"}:
                            logging.warning("%s: REMOVING %s", e.message, annotation)
                            to_remove.append(annotation)
                if not to_remove:
                    break
                for annotation in to_remove:
                    data.annotations.remove(annotation)
                    changed = True
            for span, annotations in anafora.validate.find_entities_with_identical_spans(data):
                try:
                    # sorts SECTIONTIME and DOCTIME before TIMEX3
                    special_time, timex = sorted(annotations, key=lambda a: a.type)
                except ValueError:
                    pass
                else:
                    if special_time.type in {"SECTIONTIME", "DOCTIME"} and timex.type == "TIMEX3":
                        msg = "multiple entities for span %s: REPLACING %s WITH %s"
                        logging.warning(msg, span, timex, special_time)
                        for annotation in data.annotations:
                            for name, value in annotation.properties.items():
                                if value is timex:
                                    annotation.properties[name] = special_time
                        data.annotations.remove(timex)
                        changed = True
            if changed:
                output_sub_dir = os.path.join(output_dir, sub_dir)
                if not os.path.exists(output_sub_dir):
                    os.makedirs(output_sub_dir)
                output_path = os.path.join(output_sub_dir, xml_name)
                data.to_file(output_path)



if __name__ == "__main__":
    choices = {
        "thyme": fix_thyme_errors,
    }

    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=choices, required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--xml-name-regex", default="[.]xml$")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    kwargs = vars(args)
    func = choices[kwargs.pop('type')]
    schema = anafora.validate.Schema.from_file(kwargs.pop("schema"))
    func(schema, **kwargs)
