#!/usr/bin/env python3
"""Consumer-side contract smoke for a pinned, parent-owned gh_ops (stdlib only).

Does not vendor a second implementation, access GitHub, or perform writes.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PARENT_SHA = "f9e8b77e407bfd80c79b55123b13da9fad4a05d9"
GH_OPS_BLOB = "6e5470e1e9395f9f3dd0908d3ce5190e0294e807"
GHI_BLOB = "57f96181fecaef0a6f19bf5052b93d9bdcab69c5"

def git(cwd, *args):
    result = subprocess.run(["git", "-C", str(cwd), *args],
                            text=True, capture_output=True, check=True, timeout=20)
    return result.stdout.strip()

def cli(script, *args):
    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    result = subprocess.run([sys.executable, "-S", str(script), "--json", *args],
                            capture_output=True, text=True, env=env, timeout=20)
    assert result.returncode == 0, (args, result.stderr, result.stdout)
    return json.loads(result.stdout)

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", default=".canonical-gh-ops")
    parser.add_argument("--repo", required=True)
    args = parser.parse_args(argv)
    root = Path(args.parent).resolve()
    script = root / "gh_ops.py"
    identity = root / "vendor" / "gh_identity.py"
    assert script.is_file() and identity.is_file()
    assert git(root, "rev-parse", "HEAD") == PARENT_SHA
    assert git(root, "hash-object", "gh_ops.py") == GH_OPS_BLOB
    assert git(root, "hash-object", "vendor/gh_identity.py") == GHI_BLOB

    # Public, network-free CLI surface.
    result = cli(script, "url", "pr", args.repo, "1")
    assert result["ok"] and result["web"].endswith("/pull/1")
    result = cli(script, "url", "runs", args.repo)
    assert result["ok"] and "/actions" in result["web"]

    # Offline JSON fixture: comments-file never needs credentials.
    with tempfile.TemporaryDirectory() as folder:
        fixture = Path(folder) / "comments.json"
        fixture.write_text(json.dumps([{"id": 17, "body": "test", "user": {"login": "fixture"},
                                        "created_at": "2026-10-08T00:00:00Z"}]), encoding="utf-8")
        result = cli(script, "comments-file", str(fixture), "--last", "1")
        assert result["ok"], result

    # The actual module can be loaded under python -S, with its adjacent
    # canonical GHI dependency. A dry-run dispatch may GET but MUST NOT POST.
    spec = importlib.util.spec_from_file_location("trial_parent_gh_ops", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.gh_identity.__file__ == str(identity)
    class ReadOnly:
        def __init__(self):
            self.reads = []
        def get(self, path, **kwargs):
            self.reads.append(path)
            return {"id": 99, "state": "active", "path": ".github/workflows/ci.yml"}
        def request(self, *args, **kwargs):
            raise AssertionError("write attempted in a dry-run")
    client = ReadOnly()
    result = module.workflow_dispatch(args.repo, "ci.yml", ref="main",
                                      client=client, write=False)
    assert result["ok"] and result["dry_run"] and not result["dispatched"]
    assert len(client.reads) == 1
    print(json.dumps({"schema": "gh-ops-consumer-smoke/1", "result": "success",
                      "repository": args.repo, "parent_sha": PARENT_SHA,
                      "source_blob": GH_OPS_BLOB, "ghi_blob": GHI_BLOB,
                      "verified": ["cli-url", "cli-comments-file", "module-import",
                                   "dry-run-no-write"]}, ensure_ascii=False))

if __name__ == "__main__":
    main()
