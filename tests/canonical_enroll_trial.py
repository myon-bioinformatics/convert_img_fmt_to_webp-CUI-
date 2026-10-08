#!/usr/bin/env python3
"""Disposable end-to-end smoke of parent canonical vendor enrollment (stdlib only)."""
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path.cwd()
SCRATCH = ROOT / "scratch-vendor-enroll"
CANONICAL = ROOT / ".canonical"
COMMIT = "d849c17f5e7c18037e2ab2c04bc71eee3e22cd35"
SOURCES = {
    "cli_args.py": ("vendor/cli_args.py", "cb7dbc095ea4079321494dd3a79df695a2d8bffd",
                    "591cf44634d684e2d8e3abe3f8b19d32f49ec75f569189d839bb29d84bc5a220"),
    "LICENSE": ("vendor/cli_args-LICENSE", "4ec4989b801bf1a3df6184d21f79e6e7ed5931f6",
                "15f66204c4a6a1ce0c94f0ed4319ff9400f872e85fd32c95f21695c2f231af59"),
}

def run(*args, expected=0):
    result = subprocess.run([sys.executable, "-S", *map(str, args)],
                            cwd=ROOT, capture_output=True, text=True, timeout=120)
    if result.returncode != expected:
        raise AssertionError(f"command failed {args}: rc={result.returncode}, stdout={result.stdout}, stderr={result.stderr}")
    return json.loads(result.stdout) if expected == 0 else result

def main():
    SCRATCH.mkdir(exist_ok=False)
    entries = []
    for source, (dest, expected_blob, expected_sha256) in SOURCES.items():
        url = f"https://raw.githubusercontent.com/myon-bioinformatics/cli_args/{COMMIT}/{source}"
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = response.read()
        blob = hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()
        assert blob == expected_blob, (source, blob)
        assert hashlib.sha256(payload).hexdigest() == expected_sha256, source
        entries.append({"repository": "myon-bioinformatics/cli_args",
                        "ref": "refs/heads/main", "commit": COMMIT, "source": source,
                        "destination": dest, "blob_sha": blob,
                        "sha256": expected_sha256})
    lock = SCRATCH / "vendor.lock.json"
    lock.write_text(json.dumps({"schema": "vendor-lock/1", "files": entries}, indent=2) + "\n")
    sync = CANONICAL / "vendor_sync.py"
    stage = CANONICAL / "vendor_stage.py"
    cmd = ["--root", str(SCRATCH), "--manifest", "vendor.lock.json"]
    # Missing destinations must fail offline check before enrollment.
    run(sync, "check", *cmd, expected=2)
    first = run(sync, "enroll", *cmd)
    assert set(first["changed_paths"]) == set(row[0] for row in SOURCES.values())
    run(sync, "check", *cmd)
    second = run(sync, "enroll", *cmd)
    assert second["changed_paths"] == [], second
    run(stage, "--root", SCRATCH, "--manifest", "vendor.lock.json",
        "--kind", "locked", "--output", "evidence")
    evidence = json.loads((SCRATCH / "evidence/vendor-evidence.json").read_text())
    assert evidence["runtime"] == [], evidence
    for entry in entries:
        target = SCRATCH / entry["destination"]
        staged = SCRATCH / "evidence" / entry["destination"]
        assert hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]
        assert staged.read_bytes() == target.read_bytes()
    # Existing mismatch is never repaired by enroll.
    source_file = SCRATCH / "vendor/cli_args.py"
    source_file.write_bytes(b"do not overwrite me\n")
    run(sync, "enroll", *cmd, expected=2)
    assert source_file.read_bytes() == b"do not overwrite me\n"
    # A separate import check uses the verified artifact, not the deliberately corrupted copy.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(SCRATCH / "evidence/vendor"))
    module = importlib.import_module("cli_args")
    assert module.__file__.endswith("cli_args.py")
    expected = {"vendor-evidence.json", "vendor.lock.json", "vendor/cli_args.py", "vendor/cli_args-LICENSE"}
    actual = {p.relative_to(SCRATCH / "evidence").as_posix() for p in (SCRATCH / "evidence").rglob("*") if p.is_file()}
    assert actual == expected, (actual, expected)
    print(json.dumps({"result": "success", "commit": COMMIT,
                      "first": first["changed_paths"], "second": second["changed_paths"],
                      "files": [{"path": e["destination"], "sha256": e["sha256"], "blob": e["blob_sha"]}
                                for e in entries]}, indent=2))

if __name__ == "__main__":
    main()
