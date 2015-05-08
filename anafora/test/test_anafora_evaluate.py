import collections

import anafora
import anafora.evaluate


def test_score_data():
    reference = anafora.AnaforaData(anafora.ElementTree.fromstring("""
    <data>
        <annotations>
            <entity>
                <id>1</id>
                <span>0,5</span>
                <type>X</type>
            </entity>
            <entity>
                <id>2</id>
                <span>5,10</span>
                <type>Y</type>
            </entity>
            <entity>
                <id>3</id>
                <span>15,20</span>
                <type>Y</type>
            </entity>
            <relation>
                <id>4</id>
                <type>Z</type>
                <properties>
                    <Source>1</Source>
                    <Target>2</Target>
                    <Prop1>T</Prop1>
                    <Prop2>A</Prop2>
                </properties>
            </relation>
            <relation>
                <id>5</id>
                <type>Z</type>
                <properties>
                    <Source>2</Source>
                    <Target>3</Target>
                    <Prop1>T</Prop1>
                    <Prop2>B</Prop2>
                </properties>
            </relation>
        </annotations>
    </data>
    """))
    predicted = anafora.AnaforaData(anafora.ElementTree.fromstring("""
    <data>
        <annotations>
            <entity>
                <id>6</id><!-- different -->
                <span>0,5</span>
                <type>X</type>
            </entity>
            <entity>
                <id>7</id><!-- different -->
                <span>5,10</span>
                <type>X</type><!-- different -->
            </entity>
            <entity>
                <id>8</id><!-- different -->
                <span>15,20</span>
                <type>Y</type>
            </entity>
            <relation>
                <id>9</id><!-- different -->
                <type>Z</type>
                <properties>
                    <Source>6</Source>
                    <Target>7</Target>
                    <Prop1>T</Prop1>
                    <Prop2>A</Prop2>
                </properties>
            </relation>
            <relation>
                <id>10</id><!-- different -->
                <type>Z</type>
                <properties>
                    <Source>7</Source>
                    <Target>8</Target>
                    <Prop1>F</Prop1><!-- different -->
                    <Prop2>B</Prop2>
                </properties>
            </relation>
        </annotations>
    </data>
    """))
    named_scores = anafora.evaluate.score_data(reference, predicted)
    assert set(named_scores.keys()) == {
        "X", ("X", "<span>"),
        "Y", ("Y", "<span>"),
        "Z", ("Z", "<span>"), ("Z", "Source"), ("Z", "Target"), ("Z", "Prop1"), ("Z", "Prop2"),
        ("Z", "Prop1", "T"), ("Z", "Prop1", "F"), ("Z", "Prop2", "A"), ("Z", "Prop2", "B"),
    }
    scores = named_scores["X"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 2
    scores = named_scores["X", "<span>"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 2
    scores = named_scores["Y"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Y", "<span>"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z"]
    assert scores.correct == 0
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "<span>"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop2", "A"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2", "B"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, exclude=["X", "Y"])
    assert set(named_scores.keys()) == {
        ("Z"), ("Z", "<span>"), ("Z", "Source"), ("Z", "Target"), ("Z", "Prop1"), ("Z", "Prop2"),
        ("Z", "Prop1", "T"), ("Z", "Prop1", "F"), ("Z", "Prop2", "A"), ("Z", "Prop2", "B"),
    }
    scores = named_scores["Z"]
    assert scores.correct == 0
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "<span>"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop2", "A"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2", "B"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, include=[("Z", "Prop1", "T")])
    assert set(named_scores.keys()) == {("Z", "Prop1", "T")}
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, include=[("Z", "Prop1", "F")])
    assert set(named_scores.keys()) == {("Z", "Prop1", "F")}
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, include=["Z"], exclude=[("Z", "<span>")])
    assert set(named_scores.keys()) == {
        "Z", ("Z", "Source"), ("Z", "Target"), ("Z", "Prop1"), ("Z", "Prop2"),
        ("Z", "Prop1", "T"), ("Z", "Prop1", "F"), ("Z", "Prop2", "A"), ("Z", "Prop2", "B"),
    }
    scores = named_scores["Z"]
    assert scores.correct == 0
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop2", "A"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2", "B"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1


def test_score_data_overlap():
    # This test is identical to the one above except that the spans have been changed so that they're overlapping
    # instead of being exactly equal
    reference = anafora.AnaforaData(anafora.ElementTree.fromstring("""
    <data>
        <annotations>
            <entity>
                <id>1</id>
                <span>0,5</span>
                <type>X</type>
            </entity>
            <entity>
                <id>2</id>
                <span>5,10</span>
                <type>Y</type>
            </entity>
            <entity>
                <id>3</id>
                <span>15,20</span>
                <type>Y</type>
            </entity>
            <relation>
                <id>4</id>
                <type>Z</type>
                <properties>
                    <Source>1</Source>
                    <Target>2</Target>
                    <Prop1>T</Prop1>
                    <Prop2>A</Prop2>
                </properties>
            </relation>
            <relation>
                <id>5</id>
                <type>Z</type>
                <properties>
                    <Source>2</Source>
                    <Target>3</Target>
                    <Prop1>T</Prop1>
                    <Prop2>B</Prop2>
                </properties>
            </relation>
            <relation>
                <id>6</id>
                <type>Ref</type>
                <properties>
                    <Ref>1</Ref>
                </properties>
            </relation>
            <relation>
                <id>7</id>
                <type>Ref</type>
                <properties>
                    <Ref>6</Ref>
                </properties>
            </relation>
        </annotations>
    </data>
    """))
    predicted = anafora.AnaforaData(anafora.ElementTree.fromstring("""
    <data>
        <annotations>
            <entity>
                <id>6</id><!-- different -->
                <span>0,4</span>
                <type>X</type>
            </entity>
            <entity>
                <id>7</id><!-- different -->
                <span>6,10</span>
                <type>X</type><!-- different -->
            </entity>
            <entity>
                <id>8</id><!-- different -->
                <span>19,20</span>
                <type>Y</type>
            </entity>
            <relation>
                <id>9</id><!-- different -->
                <type>Z</type>
                <properties>
                    <Source>6</Source>
                    <Target>7</Target>
                    <Prop1>T</Prop1>
                    <Prop2>A</Prop2>
                </properties>
            </relation>
            <relation>
                <id>10</id><!-- different -->
                <type>Z</type>
                <properties>
                    <Source>7</Source>
                    <Target>8</Target>
                    <Prop1>F</Prop1><!-- different -->
                    <Prop2>B</Prop2>
                </properties>
            </relation>
        </annotations>
    </data>
    """))
    named_scores = anafora.evaluate.score_data(reference, predicted, annotation_wrapper=anafora.evaluate._OverlappingWrapper)
    assert set(named_scores.keys()) == {
        "X", ("X", "<span>"),
        "Y", ("Y", "<span>"),
        "Z", ("Z", "<span>"), ("Z", "Source"), ("Z", "Target"), ("Z", "Prop1"), ("Z", "Prop2"),
        ("Z", "Prop1", "T"), ("Z", "Prop1", "F"), ("Z", "Prop2", "A"), ("Z", "Prop2", "B"),
        "Ref", ("Ref", "<span>"), ("Ref", "Ref"),
        }
    scores = named_scores["X"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 2
    scores = named_scores["X", "<span>"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 2
    scores = named_scores["Y"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Y", "<span>"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z"]
    assert scores.correct == 0
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "<span>"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop2", "A"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2", "B"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, exclude=["X", "Y"],
                                           annotation_wrapper=anafora.evaluate._OverlappingWrapper)
    assert set(named_scores.keys()) == {
        ("Z"), ("Z", "<span>"), ("Z", "Source"), ("Z", "Target"), ("Z", "Prop1"), ("Z", "Prop2"),
        ("Z", "Prop1", "T"), ("Z", "Prop1", "F"), ("Z", "Prop2", "A"), ("Z", "Prop2", "B"),
        "Ref", ("Ref", "<span>"), ("Ref", "Ref"),
        }
    scores = named_scores["Z"]
    assert scores.correct == 0
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "<span>"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop2", "A"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2", "B"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, include=[("Z", "Prop1", "T")],
                                           annotation_wrapper=anafora.evaluate._OverlappingWrapper)
    assert set(named_scores.keys()) == {("Z", "Prop1", "T")}
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, include=[("Z", "Prop1", "F")],
                                           annotation_wrapper=anafora.evaluate._OverlappingWrapper)
    assert set(named_scores.keys()) == {("Z", "Prop1", "F")}
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1

    named_scores = anafora.evaluate.score_data(reference, predicted, include=["Z"], exclude=[("Z", "<span>")],
                                           annotation_wrapper=anafora.evaluate._OverlappingWrapper)
    assert set(named_scores.keys()) == {
        "Z", ("Z", "Source"), ("Z", "Target"), ("Z", "Prop1"), ("Z", "Prop2"),
        ("Z", "Prop1", "T"), ("Z", "Prop1", "F"), ("Z", "Prop2", "A"), ("Z", "Prop2", "B"),
        }
    scores = named_scores["Z"]
    assert scores.correct == 0
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop1", "T"]
    assert scores.correct == 1
    assert scores.reference == 2
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop1", "F"]
    assert scores.correct == 0
    assert scores.reference == 0
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2"]
    assert scores.correct == 2
    assert scores.reference == 2
    assert scores.predicted == 2
    scores = named_scores["Z", "Prop2", "A"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1
    scores = named_scores["Z", "Prop2", "B"]
    assert scores.correct == 1
    assert scores.reference == 1
    assert scores.predicted == 1


def test_temporal_closure_scores():

    def annotation(source, target, value):
        return anafora.evaluate._AnnotationView((source, target), None, value)

    reference = {
        annotation("A", "B", "BEFORE"),
        annotation("B", "C", "IS_INCLUDED"),
        annotation("D", "C", "INCLUDES"),
        annotation("E", "D", "CONTAINS"),
        annotation("F", "E", "AFTER"),
        annotation("G", "H", "BEGINS-ON"),
        annotation("I", "G", "BEFORE"),
        annotation("J", "K", "IBEFORE"),
        annotation("K", "L", "BEGUN_BY"),
        annotation("L", "K", "BEGINS"), # duplicate
        # inferred:
        # A before B
        # A before F
        # B before F
        # C includes B
        # C before F
        # D includes B
        # D includes C
        # D before F
        # E includes B
        # E includes C
        # E includes D
        # E before F
        # G simultaneous-start H
        # I before G
        # I before H
    }
    predicted = {
        annotation("A", "B", "BEFORE"),   # (+)
        annotation("A", "B", "BEFORE"),   # duplicate
        annotation("B", "A", "AFTER"),    # duplicate
        annotation("B", "E", "CONTAINS"), # (-)
        annotation("B", "E", "INCLUDES"), # duplicate
        annotation("B", "F", "BEFORE"),   # (+)
        annotation("F", "D", "AFTER"),    # (+)
        annotation("H", "I", "AFTER"),    # (+)
        annotation("J", "L", "IBEFORE"),  # (+)
        annotation("K", "L", "BEGUN_BY"), # (+)
        # inferred:
        # (+) A before B
        # ( ) A before E
        # ( ) A before F
        # ( ) B includes E
        # ( ) B before F
        # ( ) D before F
        # (+) E before F
        # ( ) G after I
        # ( ) J i-before L
        # (+) K begun-by L
        # (+) J i-before K
    }
    scores = anafora.evaluate.TemporalClosureScores()
    scores.add(reference, predicted)
    assert scores.precision() == 6.0 / 7.0
    assert scores.recall() ==  4.0 / 9.0
