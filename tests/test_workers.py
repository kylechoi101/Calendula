"""Contract tests every worker must pass. Add per-worker logic tests in test_<role>.py."""

import json

import pytest

from calendula import protocol, workers


# Teammates are moving these workers to protocol v2; drop a role from here once it passes.
PENDING_V2 = {"doctor", "hospital", "insurance", "travel"}


def v2(role):
    return pytest.param(role, marks=pytest.mark.xfail(reason="worker not on protocol v2 yet")) \
        if role in PENDING_V2 else role


def ask(role, type_, data):
    return json.loads(workers.answer(role, json.dumps(protocol.envelope(type_, data, "t1"))))


@pytest.mark.parametrize("role", [v2(r) for r in protocol.ROLE_TYPE])
def test_reply_matches_protocol_shape(role):
    type_ = protocol.ROLE_TYPE[role]
    reply = ask(role, type_, protocol.EXAMPLES[type_]["request"])
    assert reply["type"] == type_ and reply["id"] == "t1", reply
    assert set(reply["data"]) == set(protocol.EXAMPLES[type_]["reply"])


@pytest.mark.parametrize("role", protocol.ROLE_TYPE)
def test_whoami(role):
    assert ask(role, "whoami", {})["data"] == {"role": role}


def test_bad_requests_get_error_envelopes_not_crashes():
    assert json.loads(workers.answer("doctor", "garbage"))["type"] == "error"
    assert ask("review", "coverage", {"insurer": "SierraCare Health Plan"})["type"] == "error"
    assert ask("dentist", "whoami", {})["type"] == "error"
