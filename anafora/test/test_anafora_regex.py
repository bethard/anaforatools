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


def test_train():
    text1 = "aaa bb ccccc dddd"
    data1 = anafora.AnaforaData(anafora.ElementTree.fromstring("""
    <data>
        <annotations>
            <entity>
                <id>1</id>
                <type>AA</type>
                <span>0,6</span><!-- "aaa bb" -->
                <properties>
                    <a>A</a>
                </properties>
            </entity>
            <entity>
                <id>2</id>
                <type>AA</type>
                <span>7,12</span><!-- "ccccc" -->
                <properties>
                    <c>B</c>
                </properties>
            </entity>
            <entity>
                <id>3</id>
                <type>EMPTY</type>
                <span>0,0</span>
            </entity>
        </annotations>
    </data>
    """))
    text2 = "ccccc dddd ccccc dddd ccccc."
    data2 = anafora.AnaforaData(anafora.ElementTree.fromstring("""
    <data>
        <annotations>
            <entity>
                <id>1</id>
                <type>CC</type>
                <span>0,5</span><!-- "ccccc" -->
                <properties>
                    <c>B</c>
                </properties>
            </entity>
            <entity>
                <id>2</id>
                <type>CC</type>
                <span>11,16</span><!-- "ccccc" -->
                <properties>
                    <c>C</c>
                </properties>
            </entity>
            <entity>
                <id>3</id>
                <type>CC</type>
                <span>22,27</span><!-- "ccccc" -->
                <properties>
                    <c>C</c>
                    <d>D</d>
                </properties>
            </entity>
            <entity>
                <id>4</id>
                <type>PERIOD</type>
                <span>27,28</span><!-- "." -->
            </entity>
        </annotations>
    </data>
    """))

    annotator = anafora.regex.RegexAnnotator({
        r'\baaa\s+bb\b': ('AA', {"a": "A"}),
        r'\bccccc\b': ('CC', {"c": "C", "d": "D"}),
        r'\b\.': ('PERIOD', {}),
    })

    assert anafora.regex.RegexAnnotator.train([(text1, data1), (text2, data2)]) == annotator
