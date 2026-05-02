from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fmql.cli.main import app
from fmql.document_io import to_yaml
from fmql.parser import parse


def _invoke(input_text: str, *args: str):
    runner = CliRunner()
    return runner.invoke(app, ["deserialize", *args], input=input_text)


def test_deserialize_json_basic():
    payload = json.dumps({"header": {"title": "Today", "tags": ["inbox"]}, "body": "# Today\n"})
    result = _invoke(payload)
    assert result.exit_code == 0, result.output
    assert result.stdout == "---\ntitle: Today\ntags:\n  - inbox\n---\n# Today\n"


def test_deserialize_json_no_header():
    payload = json.dumps({"body": "plain\n"})
    result = _invoke(payload)
    assert result.exit_code == 0, result.output
    assert result.stdout == "plain\n"


def test_deserialize_json_empty_header_emits_fence_pair():
    payload = json.dumps({"header": {}, "body": "body\n"})
    result = _invoke(payload)
    assert result.exit_code == 0, result.output
    assert result.stdout == "---\n---\nbody\n"


def test_deserialize_yaml_basic():
    src = "header:\n  title: Today\nbody: |\n  # Today\n"
    result = _invoke(src, "--format", "yaml")
    assert result.exit_code == 0, result.output
    assert result.stdout == "---\ntitle: Today\n---\n# Today\n"


def test_deserialize_yaml_round_trip_byte_identical():
    src = "---\n" "title: Today\n" "tags:\n" "  - inbox\n" "---\n" "# Today\n" "\n" "body line\n"
    structured = to_yaml(parse(src, abspath=Path("/tmp/today.md")))
    result = _invoke(structured, "--format", "yaml")
    assert result.exit_code == 0, result.output
    assert result.stdout == src


def test_deserialize_invalid_json():
    result = _invoke("{not json")
    assert result.exit_code == 2


def test_deserialize_invalid_yaml():
    result = _invoke("a: : :", "--format", "yaml")
    assert result.exit_code == 2


def test_deserialize_non_mapping_root():
    result = _invoke("[1, 2, 3]")
    assert result.exit_code == 2


def test_deserialize_bad_header_type():
    payload = json.dumps({"header": "not a map", "body": ""})
    result = _invoke(payload)
    assert result.exit_code == 2


def test_deserialize_bad_body_type():
    payload = json.dumps({"header": {}, "body": 42})
    result = _invoke(payload)
    assert result.exit_code == 2


def test_deserialize_unexpected_keys():
    payload = json.dumps({"header": {}, "body": "", "extra": True})
    result = _invoke(payload)
    assert result.exit_code == 2
