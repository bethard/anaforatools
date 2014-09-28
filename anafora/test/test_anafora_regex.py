import anafora
import anafora.regex


def test_regex_annotator():
    annotator = anafora.regex.RegexAnnotator({
        'aa+': ('A', {}),
        'a': ('A', {'X': '2'}),
        'bb': ('B', {'Y': '1'})
    })
    text = "bb aaa"
    data = anafora.AnaforaData()
    annotator.annotate(text, data)

    assert len(list(data.annotations)) == 2
    [b_annotation, a_annotation] = data.annotations
    assert b_annotation.type == "B"
    assert dict(b_annotation.properties.items()) == {'Y': '1'}
    assert a_annotation.type == "A"
    assert dict(a_annotation.properties.items()) == {}


def test_many_groups():
    regex_predictions = {}
    for i in range(1, 1000):
        regex_predictions['a' * i] = ('A' * i, {})
    annotator = anafora.regex.RegexAnnotator(regex_predictions)
    text = "aaaaaaaaaa"
    data = anafora.AnaforaData()
    annotator.annotate(text, data)

    assert len(list(data.annotations)) == 1
    [annotation] = data.annotations
    assert annotation.type == "AAAAAAAAAA"
    assert dict(annotation.properties.items()) == {}


def test_file_roundtrip(tmpdir):
    annotator_path = str(tmpdir.join("temp.annotator"))
    annotator = anafora.regex.RegexAnnotator({
        'the year': ('DATE', {}),
        'John': ('PERSON', {'type': 'NAME', 'gender': 'MALE'}),
        '.1.2.\d+;': ('OTHER', {})
    })
    annotator.to_file(annotator_path)
    assert anafora.regex.RegexAnnotator.from_file(annotator_path) == annotator


def test_simple_file(tmpdir):
    path = tmpdir.join("temp.annotator")
    path.write("""\
aaa aaa\tA
b\tB\t{"x": "y"}
\\dc\\s+x\tC
""")
    annotator = anafora.regex.RegexAnnotator({
        'aaa aaa': ('A', {}),
        'b': ('B', {'x': 'y'}),
        r'\dc\s+x': ('C', {})
    })
    assert anafora.regex.RegexAnnotator.from_file(str(path)) == annotator
