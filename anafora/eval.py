__author__ = 'bethard'

import argparse
import collections
import logging
import os

import anafora
import anafora.validate


class Scores(object):
    def __init__(self):
        self.reference = 0
        self.predicted = 0
        self.correct = 0

    def add(self, reference, predicted):
        """
        :param set reference: the reference annotations
        :param set predicted: the predicted annotations
        :return tuple: (annotations only in reference, annotations only predicted)
        """
        self.reference += len(reference)
        self.predicted += len(predicted)
        self.correct += len(reference & predicted)
        return reference - predicted, predicted - reference

    def update(self, other):
        self.reference += other.reference
        self.predicted += other.predicted
        self.correct += other.correct

    def precision(self):
        return 1.0 if self.predicted == 0 else self.correct / float(self.predicted)

    def recall(self):
        return 1.0 if self.reference == 0 else self.correct / float(self.reference)

    def f1(self):
        p = self.precision()
        r = self.recall()
        return 0.0 if p + r == 0.0 else 2 * p * r / (p + r)

    def __repr__(self):
        return "{0}(reference={1}, predicted={2}, correct={3}".format(
            self.__class__.__name__, self.reference, self.predicted, self.correct
        )


def _group_by(reference_iterable, predicted_iterable, key_function):
    result = collections.defaultdict(lambda: (set(), set()))
    for iterable, index in [(reference_iterable, 0), (predicted_iterable, 1)]:
        for item in iterable:
            result[key_function(item)][index].add(item)
    return result


def score_data(reference_data, predicted_data, include=None, exclude=None, xml_name=None):
    """
    :param AnaforaData reference_data: reference ("gold standard") Anafora data
    :param AnaforaData predicted_data: predicted (system-generated) Anafora data
    :param set include: types of annotations to include (others will be excluded); may be type names,
        (type-name, property-name) tuples, (type-name, property-name, property-value) tuples
    :param set exclude: types of annotations to exclude; may be type names, (type-name, property-name) tuples,
        (type-name, property-name, property-value) tuples
    :param string xml_name: name of the Anafora XML file being compared (used only for logging purposes)
    :return dict: mapping of (annotation type, property) to Scores object
    """
    def _props(annotations):
        props = set()
        for ann in annotations:
            if exclude is not None and ann.type in exclude:
                continue
            spans = ann.spans
            if ((include is None or ann.type in include or (ann.type, "span") in include) and
                    (exclude is None or (ann.type, "span") not in exclude)):
                props.add((spans, "span"))
            for prop_name in ann.properties:
                value = ann.properties[prop_name]
                type_name = ann.type, prop_name
                type_name_value = ann.type, prop_name, value
                if ((include is None or ann.type in include or type_name in include or type_name_value in include) and
                        (exclude is None or (type_name not in exclude and type_name_value not in exclude))):
                    props.add((spans, prop_name, value))
        return props

    result = collections.defaultdict(lambda: Scores())
    predicted_annotations = [] if predicted_data is None else predicted_data.annotations
    groups = _group_by(reference_data.annotations, predicted_annotations, lambda a: a.type)
    for ann_type in sorted(groups):
        reference_annotations, predicted_annotations = groups[ann_type]
        if (include is None or ann_type in include) and (exclude is None or ann_type not in exclude):
            missed, added = result[ann_type, ""].add(reference_annotations, predicted_annotations)
            if predicted_data is not None:
                for annotation in missed:
                    logging.debug("Missed%s:\n%s", " in " + xml_name if xml_name else "", str(annotation).rstrip())
                for annotation in added:
                    logging.debug("Added%s:\n%s", " in " + xml_name if xml_name else "", str(annotation).rstrip())

        prop_groups = _group_by(_props(reference_annotations), _props(predicted_annotations), lambda t: t[1])
        for name in sorted(prop_groups):
            reference_tuples, predicted_tuples = prop_groups[name]
            result[ann_type, name].add(reference_tuples, predicted_tuples)

    return result


def _load_and_validate(schema, xml_path):
    if not os.path.exists(xml_path):
        logging.warn("%s: no such file", xml_path)
        return None
    try:
        data = anafora.AnaforaData.from_file(xml_path)
    except anafora.ElementTree.ParseError:
        logging.warn("%s: ignoring invalid XML", xml_path)
        return None
    else:
        for annotation, error in schema.errors(data):
            logging.warn("%s: removing invalid annotation: %s", xml_path, error)
            data.annotations.remove(annotation)
        for span, annotations in anafora.validate.find_entities_with_identical_spans(data):
            logging.warn("%s: removing all but first annotation with span %s", xml_path, span)
            for annotation in annotations[1:]:
                data.annotations.remove(annotation)
        return data


def score_dirs(schema, reference_dir, predicted_dir, include=None, exclude=None):
    """
    :param string reference_dir: directory containing reference ("gold standard") Anafora XML directories
    :param string predicted_dir: directory containing predicted (system-generated) Anafora XML directories
    :param set include: types of annotations to include (others will be excluded); may be type names,
        (type-name, property-name) tuples, (type-name, property-name, property-value) tuples
    :param set exclude: types of annotations to exclude; may be type names, (type-name, property-name) tuples,
        (type-name, property-name, property-value) tuples
    :return dict: mapping of (annotation type, property) to Scores object
    """
    result = collections.defaultdict(lambda: Scores())

    for _, sub_dir, xml_name in anafora.walk(reference_dir):
        reference_xml_path = os.path.join(reference_dir, sub_dir, xml_name)
        predicted_xml_path = os.path.join(predicted_dir, sub_dir, xml_name)

        reference_data = _load_and_validate(schema, reference_xml_path)
        predicted_data = _load_and_validate(schema, predicted_xml_path)

        named_scores = score_data(reference_data, predicted_data, include, exclude, xml_name)
        for name, scores in named_scores.items():
            result[name].update(scores)

    return result


def _print_scores(named_scores):
    """
    :param dict named_scores: mapping of (annotation type, span or property) to Scores object
    """
    print("{0:10}\t{1:20}\t{2:^5}\t{3:^5}\t{4:^5}\t{5:^5}\t{6:^5}\t{7:^5}".format(
        "", "", "ref", "pred", "corr", "P", "R", "F1"))
    for ann_type, ann_name in sorted(named_scores):
        scores = named_scores[ann_type, ann_name]
        print("{0:10}\t{1:20}\t{2:5}\t{3:5}\t{4:5}\t{5:5.3f}\t{6:5.3f}\t{7:5.3f}".format(
            ann_type, ann_name, scores.reference, scores.predicted, scores.correct,
            scores.precision(), scores.recall(), scores.f1()))


if __name__ == "__main__":
    def split_tuple_on_colons(string):
        result = tuple(string.split(":"))
        return result[0] if len(result) == 1 else result

    parser = argparse.ArgumentParser()
    parser.add_argument("schema_xml")
    parser.add_argument("reference_dir")
    parser.add_argument("predicted_dir")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--include", nargs="+", type=split_tuple_on_colons)
    parser.add_argument("--exclude", nargs="+", type=split_tuple_on_colons)
    args = parser.parse_args()
    basic_config_kwargs = {"format": "%(levelname)s:%(message)s"}
    if args.debug:
        basic_config_kwargs["level"] = logging.DEBUG
    logging.basicConfig(**basic_config_kwargs)

    _print_scores(score_dirs(
        anafora.validate.Schema.from_file(args.schema_xml),
        args.reference_dir, args.predicted_dir, args.include, args.exclude))
