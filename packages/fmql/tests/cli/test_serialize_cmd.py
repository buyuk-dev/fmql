from __future__ import annotations

import io
import json
from pathlib import Path

from ruamel.yaml import YAML
from typer.testing import CliRunner

from fmql.cli.main import app


def _yaml_safe() -> YAML:
    yaml = YAML(typ="safe")
    return yaml


def _yaml_load(text: str):
    return _yaml_safe().load(io.StringIO(text))


def test_serialize_json_default(tmp_path: Path):
    src = "---\ntitle: Today\ntags: [inbox]\n---\n# Today\n\nbody\n"
    f = tmp_path / "today.md"
    f.write_text(src, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["serialize", str(f)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {
        "header": {"title": "Today", "tags": ["inbox"]},
        "body": "# Today\n\nbody\n",
    }


def test_serialize_yaml_format(tmp_path: Path):
    src = "---\ntitle: Today\ntags:\n  - inbox\n---\n# Today\n"
    f = tmp_path / "today.md"
    f.write_text(src, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["serialize", str(f), "--format", "yaml"])
    assert result.exit_code == 0, result.output
    payload = _yaml_load(result.stdout)
    assert payload == {
        "header": {"title": "Today", "tags": ["inbox"]},
        "body": "# Today\n",
    }


def test_serialize_no_frontmatter(tmp_path: Path):
    src = "plain markdown only\n"
    f = tmp_path / "plain.md"
    f.write_text(src, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["serialize", str(f), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {"body": "plain markdown only\n"}


def test_serialize_missing_file(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["serialize", str(tmp_path / "nope.md")])
    assert result.exit_code == 2


def test_serialize_invalid_yaml_frontmatter(tmp_path: Path):
    f = tmp_path / "bad.md"
    f.write_text("---\nstatus: : : bad\n---\nbody\n", encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["serialize", str(f)])
    assert result.exit_code == 2


def test_serialize_non_string_scalars_in_json(tmp_path: Path):
    src = (
        "---\n"
        "priority: 3\n"
        "draft: true\n"
        "due: 2026-05-01\n"
        "tags: [a, b]\n"
        "meta:\n"
        "  owner: alice\n"
        "---\n"
        "body\n"
    )
    f = tmp_path / "doc.md"
    f.write_text(src, encoding="utf-8")
    runner = CliRunner()
    result = runner.invoke(app, ["serialize", str(f), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["header"] == {
        "priority": 3,
        "draft": True,
        "due": "2026-05-01",
        "tags": ["a", "b"],
        "meta": {"owner": "alice"},
    }
    assert payload["body"] == "body\n"
