import anafora


def _flatten(items):
    for item in items:
        if not isinstance(item, int):
            for sub_item in _flatten(item):
                yield sub_item
        else:
            yield item


def add_relations_to_closest(data, source_type, target_type,
                             relation_type, relation_source_property, relation_target_property,
                             other_properties=None):
    """

    :param anafora.AnaforaData data: the Anafora data where relations should be added
    :return:
    """
    points = {}
    for source_entity in data.annotations.select_type(source_type):
        points[source_entity.id] = list(_flatten(source_entity.spans))
    for target_entity in data.annotations.select_type(target_type):
        points[target_entity.id] = list(_flatten(target_entity.spans))

    for source_entity in data.annotations.select_type(source_type):
        def distance_to_source_entity(entity):
            return min(abs(p1 - p2) for p1 in points[source_entity.id] for p2 in points[entity.id])
        target_entity = min(data.annotations.select_type(target_type), key=distance_to_source_entity)
        relation = anafora.AnaforaRelation()
        relation.id = "{0}@{1}".format(source_entity.id, target_entity.id)
        data.annotations.append(relation)
        relation.type = relation_type
        relation.properties[relation_source_property] = source_entity
        relation.properties[relation_target_property] = target_entity
        if other_properties is not None:
            for name in other_properties:
                relation.properties[name] = other_properties[name]
