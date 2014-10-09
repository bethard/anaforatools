__author__ = 'bethard'

import argparse
import collections
import functools
import glob
import logging
import os
import re

import anafora


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
        return "{0}(reference={1}, predicted={2}, correct={3})".format(
            self.__class__.__name__, self.reference, self.predicted, self.correct
        )


class DebuggingScores(Scores):
    def __init__(self):
        Scores.__init__(self)
        self.errors = []

    def add(self, reference, predicted):
        Scores.add(self, reference, predicted)
        errors = []
        for item in reference - predicted:
            errors.append((item, "not in predicted"))
        for item in predicted - reference:
            errors.append((item, "not in reference"))
        errors.sort()
        self.errors.extend(errors)

    def update(self, other):
        Scores.update(self, other)
        self.errors.extend(other.errors)


class TemporalClosureScores(object):
    def __init__(self):
        self.reference = 0
        self.predicted = 0
        self.precision_correct = 0
        self.recall_correct = 0

    @property
    def correct(self):
        return (self.precision_correct, self.recall_correct)

    def add(self, reference, predicted):
        """
        :param set reference: the reference annotations
        :param set predicted: the predicted annotations
        :return tuple: (annotations only in reference, annotations only predicted)
        """
        reference = {self._normalize(a) for a in reference if self._is_valid(a)}
        predicted = {self._normalize(a) for a in predicted if self._is_valid(a)}
        self.reference += len(reference)
        self.predicted += len(predicted)
        self.precision_correct += len(self._closure(reference) & predicted)
        self.recall_correct += len(reference & self._closure(predicted))

    def update(self, other):
        self.reference += other.reference
        self.predicted += other.predicted
        self.precision_correct += other.precision_correct
        self.recall_correct += other.recall_correct

    def precision(self):
        return 1.0 if self.predicted == 0 else self.precision_correct / float(self.predicted)

    def recall(self):
        return 1.0 if self.reference == 0 else self.recall_correct / float(self.reference)

    def f1(self):
        p = self.precision()
        r = self.recall()
        return 0.0 if p + r == 0.0 else 2 * p * r / (p + r)

    def __repr__(self):
        return "{0}(reference={1}, predicted={2}, precision_correct={3}, recall_correct={4})".format(
            self.__class__.__name__, self.reference, self.predicted, self.precision_correct, self.recall_correct
        )

    def _is_valid(self, annotation):
        if not isinstance(annotation, _AnnotationView):
            raise RuntimeError("temporal closure cannot be applied to {0}".format(annotation))
        try:
            (source, target) = annotation.spans
        except ValueError:
            logging.warning("invalid spans for temporal closure {0}".format(annotation))
            return False
        else:
            if annotation.value not in self._rename and annotation.value not in self._transitivity:
                logging.warning("invalid relation for temporal closure {0}".format(annotation))
                return False
            return True

    def _normalize(self, annotation):
        value = annotation.value
        if value in self._rename:
            value = self._rename[value]
        return _AnnotationView(annotation.spans, annotation.name, value)

    def _closure(self, annotations):
        result = set()
        new_annotations = set(annotations)
        while new_annotations:
            result.update(new_annotations)
            for annotation in new_annotations:
                result.add(self._reversed(annotation))
            new_annotations = set()
            for annotation1 in result:
                (source1, target1) = annotation1.spans
                transitivity1 = self._transitivity[annotation1.value]
                for annotation2 in result:
                    if annotation2 is not annotation1 and annotation2.name == annotation1.name:
                        (source2, target2) = annotation2.spans
                        if target1 == source2 and source1 != target2:
                            value3 = transitivity1[annotation2.value]
                            if value3 is not None:
                                annotation3 = _AnnotationView((source1, target2), annotation1.name, value3)
                                if annotation3 not in result:
                                    new_annotations.add(annotation3)
        return result

    def _point_closure(self, annotations):
        # TODO: replace interval closure with this and test thoroughly
        start = self._start
        end = self._end
        point_relations = set()
        new_relations = set()
        for annotation in annotations:
            interval1, interval2 = annotation.spans
            new_relations.add(((interval1, start), "<", (interval1, end)))
            new_relations.add(((interval2, start), "<", (interval2, end)))
            for point1, relation, point2 in self._interval_to_point[annotation.value]:
                new_relations.add(((interval1, point1), relation, (interval2, point2)))
            for point2, relation, point1 in self._interval_to_point[self._reverse[annotation.value]]:
                new_relations.add(((interval2, point2), relation, (interval1, point1)))
        while new_relations:
            point_relations.update(new_relations)
            new_relations = set()
            for point1, relation12, point2 in point_relations:
                for point2x, relation23, point3 in point_relations:
                    if point2 == point2x:
                        relation13 = self._point_transitions[relation12][relation23]
                        if relation13 is not None:
                            new_relation = (point1, relation13, point3)
                            if new_relation not in point_relations:
                                new_relations.add(new_relation)
        result = set()
        intervals = set()
        for annotation in annotations:
            for span in annotation.spans:
                intervals.add((annotation.name, span))
        for name1, interval1 in sorted(intervals):
            for name2, interval2 in sorted(intervals):
                if interval1 != interval2 and name1 == name2:
                    for relation, requirements in self._interval_to_point.items():
                        if all(((interval1, p1), r, (interval2, p2)) in point_relations for p1, r, p2 in requirements):
                            annotation = _AnnotationView((interval1, interval2), name1, relation)
                            result.add(annotation)
        return result



    def _reversed(self, annotation):
        return _AnnotationView(annotation.spans[::-1], annotation.name, self._reverse[annotation.value])

    _start = 0
    _end = 1
    _interval_to_point = {
        "BEFORE": [(_end, "<", _start)],
        "AFTER": [(_start, ">", _end)],
        "IBEFORE": [(_end, "=", _start)],
        "IAFTER": [(_start, "=", _end)],
        "CONTAINS": [(_start, "<", _start), (_end, ">", _end)],
        "INCLUDES": [(_start, "<", _start), (_end, ">", _end)],
        "IS_INCLUDED": [(_start, ">", _start), (_end, "<", _end)],
        "BEGINS-ON": [(_start, "=", _start)],
        "ENDS-ON": [(_end, "=", _end)],
        "BEGINS": [(_start, "=", _start), (_end, "<", _end)],
        "BEGUN_BY": [(_start, "=", _start), (_end, ">", _end)],
        "ENDS":  [(_start, ">", _start), (_end, "=", _end)],
        "ENDED_BY":  [(_start, "<", _start), (_end, "=", _end)],
        "SIMULTANEOUS": [(_start, "=", _start), (_end, "=", _end)],
        "IDENTITY": [(_start, "=", _start), (_end, "=", _end)],
        "DURING": [(_start, "=", _start), (_end, "=", _end)],
        "DURING_INV": [(_start, "=", _start), (_end, "=", _end)],
        "OVERLAP": [(_start, "<", _end), (_end, ">", _start)],
    }
    _point_transitions = {
        "<": {"<": "<", "=": "<", ">": None},
        ">": {"<": None, "=": ">", ">": ">"},
        "=": {"<": "<", "=": "=", ">": ">"},
    }


    _BEFORE = "BEFORE"
    _AFTER = "AFTER"
    _IMMEDIATELY_BEFORE = "IBEFORE"
    _IMMEDIATELY_AFTER = "IAFTER"
    _INCLUDES = "INCLUDES"
    _IS_INCLUDED = "IS_INCLUDED"
    _OVERLAP = "OVERLAP"
    _BEGINS = "BEGINS"
    _BEGUN_BY = "BEGUN_BY"
    _ENDS = "ENDS"
    _ENDED_BY = "ENDED_BY"
    _SIMULTANEOUS = "SIMULTANEOUS"
    _SIMULTANEOUS_START = "SIMULTANEOUS_START"
    _SIMULTANEOUS_END = "SIMULTANEOUS_END"

    _rename = {
        "CONTAINS": _INCLUDES,
        "BEGINS-ON": _SIMULTANEOUS_START,
        "ENDS-ON": _SIMULTANEOUS_END,
        "IDENTITY": _SIMULTANEOUS,
        "DURING": _SIMULTANEOUS,
        "DURING_INV": _SIMULTANEOUS,
    }

    _reverse = {
        _BEFORE: _AFTER,
        _AFTER: _BEFORE,
        _IMMEDIATELY_BEFORE: _IMMEDIATELY_AFTER,
        _IMMEDIATELY_AFTER: _IMMEDIATELY_BEFORE,
        _INCLUDES: _IS_INCLUDED,
        _IS_INCLUDED: _INCLUDES,
        _OVERLAP: _OVERLAP,
        _BEGINS: _BEGUN_BY,
        _BEGUN_BY: _BEGINS,
        _ENDS: _ENDED_BY,
        _ENDED_BY: _ENDS,
        _SIMULTANEOUS: _SIMULTANEOUS,
        _SIMULTANEOUS_START: _SIMULTANEOUS_START,
        _SIMULTANEOUS_END: _SIMULTANEOUS_END}

    _transitivity = {
        _BEFORE: {
            _BEFORE: _BEFORE,
            _AFTER: None,
            _IMMEDIATELY_BEFORE: _BEFORE,
            _IMMEDIATELY_AFTER: None,
            _INCLUDES: _BEFORE,
            _IS_INCLUDED: None,
            _OVERLAP: None,
            _BEGINS: _BEFORE,
            _BEGUN_BY: _BEFORE,
            _ENDS: None,
            _ENDED_BY: _BEFORE,
            _SIMULTANEOUS: _BEFORE,
            _SIMULTANEOUS_START: _BEFORE,
            _SIMULTANEOUS_END: None},
        _AFTER: {
            _BEFORE: None,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: None,
            _IMMEDIATELY_AFTER: _AFTER,
            _INCLUDES: _AFTER,
            _IS_INCLUDED: None,
            _OVERLAP: None,
            _BEGINS: None,
            _BEGUN_BY: _AFTER,
            _ENDS: _AFTER,
            _ENDED_BY: _AFTER,
            _SIMULTANEOUS: _AFTER,
            _SIMULTANEOUS_START: None,
            _SIMULTANEOUS_END: _AFTER},
        _IMMEDIATELY_BEFORE: {
            _BEFORE: _BEFORE,
            _AFTER: None,
            _IMMEDIATELY_BEFORE: _BEFORE,
            _IMMEDIATELY_AFTER: None,
            _INCLUDES: _BEFORE,
            _IS_INCLUDED: None,
            _OVERLAP: None,
            _BEGINS: _IMMEDIATELY_BEFORE,
            _BEGUN_BY: _IMMEDIATELY_BEFORE,
            _ENDS: None,
            _ENDED_BY: _BEFORE,
            _SIMULTANEOUS: _IMMEDIATELY_BEFORE,
            _SIMULTANEOUS_START: _IMMEDIATELY_BEFORE,
            _SIMULTANEOUS_END: None},
        _IMMEDIATELY_AFTER: {
            _BEFORE: None,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: None,
            _IMMEDIATELY_AFTER: _AFTER,
            _INCLUDES: _AFTER,
            _IS_INCLUDED: None,
            _OVERLAP: None,
            _BEGINS: None,
            _BEGUN_BY: _AFTER,
            _ENDS: _IMMEDIATELY_AFTER,
            _ENDED_BY: _IMMEDIATELY_AFTER,
            _SIMULTANEOUS: _IMMEDIATELY_AFTER,
            _SIMULTANEOUS_START: None,
            _SIMULTANEOUS_END: _IMMEDIATELY_AFTER},
        _INCLUDES: {
            _BEFORE: None,
            _AFTER: None,
            _IMMEDIATELY_BEFORE: _OVERLAP,
            _IMMEDIATELY_AFTER: _OVERLAP,
            _INCLUDES: _INCLUDES,
            _IS_INCLUDED: _OVERLAP,
            _OVERLAP: _OVERLAP,
            _BEGINS: _OVERLAP,
            _BEGUN_BY: _INCLUDES,
            _ENDS: _OVERLAP,
            _ENDED_BY: _INCLUDES,
            _SIMULTANEOUS: _INCLUDES,
            _SIMULTANEOUS_START: _OVERLAP,
            _SIMULTANEOUS_END: _OVERLAP},
        _IS_INCLUDED: {
            _BEFORE: _BEFORE,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: _BEFORE,
            _IMMEDIATELY_AFTER: _AFTER,
            _INCLUDES: None,
            _IS_INCLUDED: _IS_INCLUDED,
            _OVERLAP: None,
            _BEGINS: _IS_INCLUDED,
            _BEGUN_BY: None,
            _ENDS: _IS_INCLUDED,
            _ENDED_BY: None,
            _SIMULTANEOUS: _IS_INCLUDED,
            _SIMULTANEOUS_START: None,
            _SIMULTANEOUS_END: None},
        _OVERLAP: {
            _BEFORE: None,
            _AFTER: None,
            _IMMEDIATELY_BEFORE: None,
            _IMMEDIATELY_AFTER: None,
            _INCLUDES: None,
            _IS_INCLUDED: _OVERLAP,
            _OVERLAP: None,
            _BEGINS: _OVERLAP,
            _BEGUN_BY: None,
            _ENDS: _OVERLAP,
            _ENDED_BY: None,
            _SIMULTANEOUS: _OVERLAP,
            _SIMULTANEOUS_START: None,
            _SIMULTANEOUS_END: None},
        _BEGINS: {
            _BEFORE: _BEFORE,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: _BEFORE,
            _IMMEDIATELY_AFTER: _IMMEDIATELY_AFTER,
            _INCLUDES: None,
            _IS_INCLUDED: _IS_INCLUDED,
            _OVERLAP: None,
            _BEGINS: _BEGINS,
            _BEGUN_BY: _SIMULTANEOUS_START,
            _ENDS: _OVERLAP,
            _ENDED_BY: None,
            _SIMULTANEOUS: _BEGINS,
            _SIMULTANEOUS_START: _SIMULTANEOUS_START,
            _SIMULTANEOUS_END: None},
        _BEGUN_BY: {
            _BEFORE: None,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: _OVERLAP,
            _IMMEDIATELY_AFTER: _IMMEDIATELY_AFTER,
            _INCLUDES: _INCLUDES,
            _IS_INCLUDED: _OVERLAP,
            _OVERLAP: _OVERLAP,
            _BEGINS: _SIMULTANEOUS_START,
            _BEGUN_BY: _BEGUN_BY,
            _ENDS: _OVERLAP,
            _ENDED_BY: _INCLUDES,
            _SIMULTANEOUS: _BEGUN_BY,
            _SIMULTANEOUS_START: _SIMULTANEOUS_START,
            _SIMULTANEOUS_END: _OVERLAP},
        _ENDS: {
            _BEFORE: _BEFORE,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: _IMMEDIATELY_BEFORE,
            _IMMEDIATELY_AFTER: _AFTER,
            _INCLUDES: None,
            _IS_INCLUDED: _IS_INCLUDED,
            _OVERLAP: None,
            _BEGINS: _OVERLAP,
            _BEGUN_BY: None,
            _ENDS: _ENDS,
            _ENDED_BY: _SIMULTANEOUS_END,
            _SIMULTANEOUS: _ENDS,
            _SIMULTANEOUS_START: None,
            _SIMULTANEOUS_END: _SIMULTANEOUS_END},
        _ENDED_BY: {
            _BEFORE: _BEFORE,
            _AFTER: None,
            _IMMEDIATELY_BEFORE: _IMMEDIATELY_BEFORE,
            _IMMEDIATELY_AFTER: _OVERLAP,
            _INCLUDES: _INCLUDES,
            _IS_INCLUDED: _OVERLAP,
            _OVERLAP: _OVERLAP,
            _BEGINS: _OVERLAP,
            _BEGUN_BY: _INCLUDES,
            _ENDS: _SIMULTANEOUS_END,
            _ENDED_BY: _ENDED_BY,
            _SIMULTANEOUS: _ENDED_BY,
            _SIMULTANEOUS_START: _OVERLAP,
            _SIMULTANEOUS_END: _SIMULTANEOUS_END},
        _SIMULTANEOUS: {
            _BEFORE: _BEFORE,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: _IMMEDIATELY_BEFORE,
            _IMMEDIATELY_AFTER: _IMMEDIATELY_AFTER,
            _INCLUDES: _INCLUDES,
            _IS_INCLUDED: _IS_INCLUDED,
            _OVERLAP: _OVERLAP,
            _BEGINS: _BEGINS,
            _BEGUN_BY: _BEGUN_BY,
            _ENDS: _ENDS,
            _ENDED_BY: _ENDED_BY,
            _SIMULTANEOUS: _SIMULTANEOUS,
            _SIMULTANEOUS_START: _SIMULTANEOUS_START,
            _SIMULTANEOUS_END: _SIMULTANEOUS_END},
        _SIMULTANEOUS_START: {
            _BEFORE: None,
            _AFTER: _AFTER,
            _IMMEDIATELY_BEFORE: None,
            _IMMEDIATELY_AFTER: _IMMEDIATELY_AFTER,
            _INCLUDES: None,
            _IS_INCLUDED: _OVERLAP,
            _OVERLAP: _OVERLAP,
            _BEGINS: _SIMULTANEOUS_START,
            _BEGUN_BY: _SIMULTANEOUS_START,
            _ENDS: _OVERLAP,
            _ENDED_BY: None,
            _SIMULTANEOUS: _SIMULTANEOUS_START,
            _SIMULTANEOUS_START: _SIMULTANEOUS_START,
            _SIMULTANEOUS_END: None},
        _SIMULTANEOUS_END: {
            _BEFORE: _BEFORE,
            _AFTER: None,
            _IMMEDIATELY_BEFORE: _IMMEDIATELY_BEFORE,
            _IMMEDIATELY_AFTER: None,
            _INCLUDES: None,
            _IS_INCLUDED: _OVERLAP,
            _OVERLAP: _OVERLAP,
            _BEGINS: _OVERLAP,
            _BEGUN_BY: None,
            _ENDS: _SIMULTANEOUS_END,
            _ENDED_BY: _SIMULTANEOUS_END,
            _SIMULTANEOUS: _SIMULTANEOUS_END,
            _SIMULTANEOUS_START: None,
            _SIMULTANEOUS_END: _SIMULTANEOUS_END},
    }
    # sanity check
    for _value in _transitivity.values():
        if set(_transitivity.keys()) != set(_value.keys()):
            msg = "incomplete transitivity table: expected {0}, found {1}"
            raise RuntimeError(msg.format(sorted(_transitivity.keys()), sorted(_value.keys())))

class _OverlappingWrapper(object):
    def __init__(self, annotation, seen=None):
        self.annotation = annotation
        self.type = self.annotation.type
        self.parents_type = self.annotation.parents_type
        if isinstance(annotation, anafora.AnaforaEntity):
            self.spans = _OverlappingSpans(self.annotation.spans)
        if isinstance(annotation, anafora.AnaforaRelation):
            self.spans = tuple(map(_OverlappingSpans, annotation.spans))
        if seen is None:
            seen = set()
        self.properties = {}
        for name, value in self.annotation.properties.items():
            if id(value) not in seen:
                seen.add(id(value))
                if isinstance(value, anafora.AnaforaAnnotation):
                    self.properties[name] = _OverlappingWrapper(value, seen)
                else:
                    self.properties[name] = value

    def _key(self):
        return self.spans, self.type, self.parents_type, self.properties

    def __eq__(self, other):
        return self._key() == other._key()

    def __hash__(self):
        return hash(anafora._to_frozensets(self))

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, self.annotation)

@functools.total_ordering
class _OverlappingSpans(object):
    def __init__(self, spans):
        self.spans = spans

    def __iter__(self):
        return iter(self.spans)

    def __eq__(self, other):
        for self_start, self_end in self.spans:
            for other_start, other_end in other.spans:
                if self_start < other_end and other_start < self_end:
                    return True
        return False

    def __hash__(self):
        return 0

    def __lt__(self, other):
        return self.spans < other.spans

    def __repr__(self):
        return "{0}({1})".format(self.__class__.__name__, self.spans)


_AnnotationView = collections.namedtuple("AnnotationView", ["spans", "name", "value"])

def _group_by(reference_iterable, predicted_iterable, key_function):
    result = collections.defaultdict(lambda: (set(), set()))
    for iterable, index in [(reference_iterable, 0), (predicted_iterable, 1)]:
        for item in iterable:
            result[key_function(item)][index].add(item)
    return result


def score_data(reference_data, predicted_data, include=None, exclude=None,
               scores_type=Scores, annotation_wrapper=None):
    """
    :param AnaforaData reference_data: reference ("gold standard") Anafora data
    :param AnaforaData predicted_data: predicted (system-generated) Anafora data
    :param set include: types of annotations to include (others will be excluded); may be type names,
        (type-name, property-name) tuples, (type-name, property-name, property-value) tuples
    :param set exclude: types of annotations to exclude; may be type names, (type-name, property-name) tuples,
        (type-name, property-name, property-value) tuples
    :param type scores_type: type for calculating matches between predictions and reference
    :param type annotation_wrapper: wrapper type to apply to AnaforaAnnotations
    :return dict: mapping of (annotation type, property) to Scores object
    """
    def _accept(type_name, prop_name=None, prop_value=None):
        if include is not None:
            if type_name not in include:
                if (type_name, prop_name) not in include:
                    if (type_name, prop_name, prop_value) not in include:
                        return False
        if exclude is not None:
            if type_name in exclude:
                return False
            if (type_name, prop_name) in exclude:
                return False
            if (type_name, prop_name, prop_value) in exclude:
                return False
        return True

    def _views(annotations):
        views = set()
        for ann in annotations:
            spans = ann.spans
            if _accept(ann.type, "<span>"):
                views.add(_AnnotationView(spans, (ann.type, "<span>"), None))
            for view_name in ann.properties:
                view_value = ann.properties[view_name]
                if _accept(ann.type, view_name):
                    views.add(_AnnotationView(spans, (ann.type, view_name), view_value))
                if _accept(ann.type, view_name, view_value) and isinstance(view_value, basestring):
                    views.add(_AnnotationView(spans, (ann.type, view_name, view_value), view_value))
        return views

    result = collections.defaultdict(lambda: scores_type())
    reference_annotations = reference_data.annotations
    predicted_annotations = [] if predicted_data is None else predicted_data.annotations
    if annotation_wrapper is not None:
        reference_annotations = map(annotation_wrapper, reference_annotations)
        predicted_annotations = map(annotation_wrapper, predicted_annotations)
    results_by_type = _group_by(reference_annotations, predicted_annotations, lambda a: a.type)
    for ann_type in sorted(results_by_type):
        type_reference_annotations, type_predicted_annotations = results_by_type[ann_type]
        if _accept(ann_type):
            result[ann_type].add(type_reference_annotations, type_predicted_annotations)
        reference_views = _views(type_reference_annotations)
        predicted_views = _views(type_predicted_annotations)
        results_by_view = _group_by(reference_views, predicted_views, lambda t: t.name)
        for view_name in sorted(results_by_view):
            view_reference_annotations, view_predicted_annotations = results_by_view[view_name]
            result[view_name].add(view_reference_annotations, view_predicted_annotations)

    return result


def _load(xml_path):
    if not os.path.exists(xml_path):
        logging.warn("%s: no such file", xml_path)
        return None
    try:
        data = anafora.AnaforaData.from_file(xml_path)
    except anafora.ElementTree.ParseError:
        logging.warn("%s: ignoring invalid XML", xml_path)
        return None
    else:
        return data


def score_dirs(reference_dir, predicted_dir, text_dir=None,
               include=None, exclude=None, scores_type=Scores, annotation_wrapper=None):
    """
    :param string reference_dir: directory containing reference ("gold standard") Anafora XML directories
    :param string predicted_dir: directory containing predicted (system-generated) Anafora XML directories
    :param string text_dir: directory containing the raw texts corresponding to the Anafora XML
        (if None, texts are assumed to be in the reference dir)
    :param set include: types of annotations to include (others will be excluded); may be type names,
        (type-name, property-name) tuples, (type-name, property-name, property-value) tuples
    :param set exclude: types of annotations to exclude; may be type names, (type-name, property-name) tuples,
        (type-name, property-name, property-value) tuples
    :param type scores_type: type for calculating matches between predictions and reference
    :param type annotation_wrapper: wrapper object to apply to AnaforaAnnotations
    :return dict: mapping of (annotation type, property) to Scores object
    """
    result = collections.defaultdict(lambda: scores_type())

    for sub_dir, text_name, reference_xml_names in anafora.walk(reference_dir):
        try:
            [reference_xml_name] = reference_xml_names
        except ValueError:
            logging.warn("expected one reference file for %s, found %s", text_name, reference_xml_names)
            if not reference_xml_names:
                continue
            reference_xml_name = reference_xml_names[0]
        reference_xml_path = os.path.join(reference_dir, sub_dir, reference_xml_name)
        reference_data = _load(reference_xml_path)

        predicted_xml_glob = os.path.join(predicted_dir, sub_dir, text_name + "*.xml")
        predicted_xml_paths = glob.glob(predicted_xml_glob)
        try:
            [predicted_xml_path] = predicted_xml_paths
            predicted_data = _load(predicted_xml_path)
        except ValueError:
            logging.warn("expected one predicted file at %s, found %s", predicted_xml_glob, predicted_xml_paths)
            if not predicted_xml_paths:
                predicted_data = anafora.AnaforaData()
            else:
                predicted_data = _load(predicted_xml_paths[0])

        if text_dir is None:
            text_path = os.path.join(reference_dir, sub_dir, text_name)
        else:
            text_path = os.path.join(text_dir, text_name)
        if not os.path.exists(text_path) or not os.path.isfile(text_path):
            def _span_text(_):
                raise RuntimeError("no text file found at {0}".format(text_path))
        else:
            with open(text_path) as text_file:
                text = text_file.read()

            def _span_text(spans):
                return "...".join(text[start:end] for start, end in spans)


        named_scores = score_data(reference_data, predicted_data, include, exclude,
                                  scores_type=scores_type, annotation_wrapper=annotation_wrapper)
        for name, scores in named_scores.items():
            result[name].update(scores)
            if not predicted_xml_paths:
                continue
            for annotation, message in getattr(scores, "errors", []):
                logging.debug('%s: %s: "%s" %s"', text_name, message, _span_text(annotation.spans), annotation)

    return result


def score_annotators(anafora_dir, xml_name_regex, include=None, exclude=None,
                     scores_type=Scores, annotation_wrapper=None):
    """
    :param anafora_dir: directory containing Anafora XML directories
    :param xml_name_regex: regular expression matching the annotator files to be compared
    :param include: types of annotations to include (others will be excluded); may be type names,
        (type-name, property-name) tuples, (type-name, property-name, property-value) tuples
    :param set exclude: types of annotations to exclude; may be type names, (type-name, property-name) tuples,
        (type-name, property-name, property-value) tuples
    :param type scores_type: type for calculating matches between predictions and reference
    :param type annotation_wrapper: wrapper object to apply to AnaforaAnnotations
    :return dict: mapping of (annotation type, property) to Scores object
    """
    result = collections.defaultdict(lambda: scores_type())

    annotator_name_regex = "([^.]*)[.][^.]*[.]xml$"

    def make_prefix(annotators):
        return "{0}-vs-{1}".format(*sorted(annotators))

    for sub_dir, text_name, xml_names in anafora.walk(anafora_dir, xml_name_regex):
        if len(xml_names) < 2:
            logging.warn("%s: found fewer than 2 annotators: %s", text_name, xml_names)
            continue

        annotator_data = []
        for xml_name in xml_names:
            if '.inprogress.' in xml_name:
                continue
            annotator_name = re.search(annotator_name_regex, xml_name).group(1)
            xml_path = os.path.join(anafora_dir, sub_dir, xml_name)
            if os.stat(xml_path).st_size == 0:
                continue
            data = _load(xml_path)
            annotator_data.append((annotator_name, data))

        for i in range(len(annotator_data)):
            annotator1, data1 = annotator_data[i]
            for j in range(i + 1, len(annotator_data)):
                annotator2, data2 = annotator_data[j]
                prefix = make_prefix([annotator1, annotator2])
                general_prefix = make_prefix(
                    a if a == "gold" else "annotator" for a in [annotator1, annotator2])
                named_scores = score_data(data1, data2, include, exclude,
                                          scores_type=scores_type, annotation_wrapper=annotation_wrapper)
                for name, scores in named_scores.items():
                    if not isinstance(name, tuple):
                        name = name,
                    result[(prefix,) + name].update(scores)
                    result[(general_prefix,) + name].update(scores)

    return result


def _print_scores(named_scores):
    """
    :param dict named_scores: mapping of (annotation type, span or property) to Scores object
    """
    def _score_name(name):
        if isinstance(name, tuple):
            name = ":".join(name)
        return name

    print("{0:40}\t{1:^5}\t{2:^5}\t{3:^5}\t{4:^5}\t{5:^5}\t{6:^5}".format(
        "", "ref", "pred", "corr", "P", "R", "F1"))
    for name in sorted(named_scores, key=_score_name):
        scores = named_scores[name]
        print("{0:40}\t{1:5}\t{2:5}\t{3:5}\t{4:5.3f}\t{5:5.3f}\t{6:5.3f}".format(
            _score_name(name), scores.reference, scores.predicted, scores.correct,
            scores.precision(), scores.recall(), scores.f1()))


if __name__ == "__main__":
    def split_tuple_on_colons(string):
        result = tuple(string.split(":"))
        return result[0] if len(result) == 1 else result

    parser = argparse.ArgumentParser()
    parser.set_defaults(scores_type=Scores)
    parser.add_argument("--reference-dir", required=True)
    parser.add_argument("--predicted-dir")
    parser.add_argument("--text-dir")
    parser.add_argument("--debug", action="store_const", const=DebuggingScores, dest="scores_type")
    parser.add_argument("--temporal-closure", action="store_const", const=TemporalClosureScores, dest="scores_type")
    parser.add_argument("--include", nargs="+", type=split_tuple_on_colons)
    parser.add_argument("--exclude", nargs="+", type=split_tuple_on_colons)
    parser.add_argument("--overlap", dest="annotation_wrapper", action="store_const", const=_OverlappingWrapper)
    parser.add_argument("--xml-name-regex", default="[.]xml$")
    args = parser.parse_args()
    basic_config_kwargs = {"format": "%(levelname)s:%(message)s"}
    if args.scores_type == DebuggingScores:
        basic_config_kwargs["level"] = logging.DEBUG
    logging.basicConfig(**basic_config_kwargs)

    if args.predicted_dir is not None:
        _print_scores(score_dirs(
            reference_dir=args.reference_dir,
            predicted_dir=args.predicted_dir,
            text_dir=args.text_dir,
            include=args.include,
            exclude=args.exclude,
            scores_type=args.scores_type,
            annotation_wrapper=args.annotation_wrapper))
    else:
        _print_scores(score_annotators(
            anafora_dir=args.reference_dir,
            xml_name_regex=args.xml_name_regex,
            include=args.include,
            exclude=args.exclude,
            scores_type=args.scores_type,
            annotation_wrapper=args.annotation_wrapper))
