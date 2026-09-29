import json

import pytest

from calendula import protocol


def test_parse_roundtrip():
    env = protocol.envelope("coverage", {"plan_id": "PLAN-B", "hospital_ids": ["H1"]})
    assert protocol.parse(json.dumps(env)) == env


@pytest.mark.parametrize("payload", [
    "not json",
    json.dumps({"v": 2, "type": "coverage", "id": "x", "data": {}}),
    json.dumps({"v": 1, "type": "nope", "id": "x", "data": {}}),
    json.dumps({"v": 1, "type": "coverage", "id": "x", "data": {"plan_id": "PLAN-B"}}),
])
def test_parse_rejects(payload):
    with pytest.raises(protocol.ProtocolError):
        protocol.parse(payload)


def test_every_role_type_has_example_and_required_fields():
    for type_ in protocol.ROLE_TYPE.values():
        assert set(protocol.REQUIRED[type_]) <= set(protocol.EXAMPLES[type_]["request"])
