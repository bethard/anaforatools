import pytest

import anafora


def test_empty():
    data = anafora.AnaforaData(anafora.ElementTree.fromstring('<data/>'))
    assert list(data.annotations) == []

    data = anafora.AnaforaData(anafora.ElementTree.fromstring('<data><annotations></annotations></data>'))
    assert list(data.annotations) == []


def test_duplicate_id():
    with pytest.raises(ValueError):
        anafora.AnaforaData(anafora.ElementTree.fromstring('''
        <data>
            <annotations>
                <entity><id>1</id></entity>
                <entity><id>1</id></entity>
            </annotations>
        </data>'''))

    data = anafora.AnaforaData()
    entity1 = anafora.AnaforaEntity()
    entity1.id = "1"
    entity2 = anafora.AnaforaEntity()
    entity2.id = "1"
    data.annotations.append(entity1)
    with pytest.raises(ValueError):
        data.annotations.append(entity2)


def test_add_entity():
    data = anafora.AnaforaData()
    assert str(data) == '<data />'
    entity = anafora.AnaforaEntity()
    with pytest.raises(ValueError) as exception_info:
        data.annotations.append(entity)
    assert "id" in exception_info.value.message
    assert str(data) == '<data />'
    entity.id = "1"
    data.annotations.append(entity)
    assert str(data) == '<data><annotations><entity><id>1</id></entity></annotations></data>'
    entity.type = "X"
    entity.parents_type = "Y"
    entity.properties["name1"] = "value1"
    assert str(data) == ('<data><annotations><entity>' +
                         '<id>1</id>' +
                         '<type>X</type>' +
                         '<parentsType>Y</parentsType>' +
                         '<properties><name1>value1</name1></properties>' +
                         '</entity></annotations></data>')


def test_add_reference():
    data = anafora.AnaforaData()
    entity1 = anafora.AnaforaEntity()
    entity1.id = "@1@"
    entity2 = anafora.AnaforaEntity()
    entity2.id = "@2@"
    with pytest.raises(ValueError) as exception_info:
        entity2.properties["link"] = entity1
    assert "<annotations" in exception_info.value.message
    data.annotations.append(entity1)
    with pytest.raises(ValueError):
        entity2.properties["link"] = entity1
    assert "<annotations" in exception_info.value.message
    data.annotations.append(entity2)
    entity2.properties["link"] = entity1
    assert str(data) == ('<data><annotations>' +
                         '<entity><id>@1@</id></entity>' +
                         '<entity><id>@2@</id><properties><link>@1@</link></properties></entity>' +
                         '</annotations></data>')


def test_remove():
    data = anafora.AnaforaData()
    assert str(data) == '<data />'
    entity1 = anafora.AnaforaEntity()
    entity1.id = "@1@"
    data.annotations.append(entity1)
    entity2 = anafora.AnaforaEntity()
    entity2.id = "@2@"
    entity2.properties["name"] = "value"
    data.annotations.append(entity2)
    assert list(data.annotations) == [entity1, entity2]
    assert str(data) == ('<data><annotations>' +
                         '<entity><id>@1@</id></entity>' +
                         '<entity><id>@2@</id><properties><name>value</name></properties></entity>' +
                         '</annotations></data>')
    data.annotations.remove(entity1)
    assert list(data.annotations) == [entity2]
    assert str(data) == ('<data><annotations>' +
                         '<entity><id>@2@</id><properties><name>value</name></properties></entity>' +
                         '</annotations></data>')
    data.annotations.remove(entity2)
    assert list(data.annotations) == []
    assert str(data) == '<data><annotations /></data>'



def test_recursive_entity():
    data = anafora.AnaforaData()
    entity1 = anafora.AnaforaEntity()
    entity1.id = "@1@"
    data.annotations.append(entity1)
    entity1.properties["self"] = entity1
    entity2 = anafora.AnaforaEntity()
    entity2.id = "@2@"
    data.annotations.append(entity2)
    entity2.properties["self"] = entity2
    assert hash(entity1) == hash(entity2)
    assert entity1 == entity2
