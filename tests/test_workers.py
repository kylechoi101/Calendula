"""Contract tests every worker must pass. Add per-worker logic tests in test_<role>.py."""

import json

import pytest

from calendula import protocol, workers


def ask(role, type_, data):
    return json.loads(workers.answer(role, json.dumps(protocol.envelope(type_, data, "t1"))))


@pytest.mark.parametrize("role,type_", protocol.ROLE_TYPE.items())
def test_reply_matches_protocol_shape(role, type_):
    reply = ask(role, type_, protocol.EXAMPLES[type_]["request"])
    assert reply["type"] == type_ and reply["id"] == "t1", reply
    assert set(reply["data"]) == set(protocol.EXAMPLES[type_]["reply"])


@pytest.mark.parametrize("role", protocol.ROLE_TYPE)
def test_whoami(role):
    assert ask(role, "whoami", {})["data"] == {"role": role}


def test_bad_requests_get_error_envelopes_not_crashes():
    assert json.loads(workers.answer("doctor", "garbage"))["type"] == "error"
    assert ask("doctor", "coverage", {"plan_id": "PLAN-B", "hospital_ids": []})["type"] == "error"
    assert ask("dentist", "whoami", {})["type"] == "error"
