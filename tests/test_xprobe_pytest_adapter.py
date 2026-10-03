import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "scripts" / "xprobe_pytest.py"


def _git_blob_sha(data):
    header = ("blob " + str(len(data)) + "\0").encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _run_native(tmp_path, source, filename="test_native_sample.py"):
    (tmp_path / filename).write_text(source, encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    env.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "scripts.xprobe_pytest",
            "-q",
            filename,
            "--xprobe-jsonl=events.jsonl",
            "--xprobe-repository=myon-bioinformatics/convert_img_fmt_to_webp-CUI-",
            "--xprobe-run-id=adapter-regression",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    evidence = tmp_path / "events.jsonl"
    rows = [
        json.loads(line)
        for line in evidence.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if evidence.exists() else []
    return result, rows


def test_vendored_adapter_and_license_match_lock():
    lock = json.loads((ROOT / "vendor.lock.json").read_text(encoding="utf-8"))
    assert lock["schema"] == "vendor-lock/1"
    assert len(lock["files"]) == 2
    assert {(e["source"], e["destination"]) for e in lock["files"]} == {
        ("scripts/xprobe_pytest.py", "scripts/xprobe_pytest.py"),
        ("LICENSE", "scripts/xprobe-LICENSE"),
    }
    for entry in lock["files"]:
        assert entry["repository"] == "myon-bioinformatics/xprobe"
        assert entry["ref"] == "refs/heads/main"
        assert re.fullmatch(r"[0-9a-f]{40}", entry["commit"])
        data = (ROOT / entry["destination"]).read_bytes()
        assert _git_blob_sha(data) == entry["blob_sha"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_native_adapter_preserves_outcomes_without_sensitive_values(tmp_path):
    result, rows = _run_native(
        tmp_path,
        """import pytest

@pytest.mark.parametrize("value", ["SECRET_PARAMETER"])
def test_failed(value):
    assert False, value

@pytest.mark.skip(reason="SECRET_SKIP")
def test_skipped():
    pass

@pytest.mark.xfail(reason="SECRET_XFAIL")
def test_xfail():
    assert False

@pytest.mark.xfail(reason="SECRET_XPASS")
def test_xpass():
    pass

@pytest.mark.xfail(strict=True, reason="SECRET_STRICT")
def test_xpass_strict():
    pass
""",
    )

    assert result.returncode == 1
    assert rows
    events = [row["value"].get("event") for row in rows]
    assert events[0] == "start"
    assert events[-1] == "finish"
    finish = rows[-1]["value"]
    assert finish["exitstatus"] == 1
    assert finish["complete"] is True

    outcomes = {
        row["value"].get("outcome")
        for row in rows
        if row["value"].get("event") == "report"
    }
    assert {"failed", "skipped", "xfail", "xpass", "xpass_strict"} <= outcomes
    assert all(row["context"]["commit_sha"] is None for row in rows)

    serialized = json.dumps(rows, sort_keys=True)
    assert "SECRET_" not in serialized


def test_interrupted_native_run_has_no_false_complete_finish(tmp_path):
    result, rows = _run_native(
        tmp_path,
        """import os

def test_abort():
    os._exit(17)
""",
        filename="test_abort_sample.py",
    )

    assert result.returncode == 17
    assert rows
    assert rows[0]["value"]["event"] == "start"
    assert not any(row["value"].get("event") == "finish" for row in rows)

