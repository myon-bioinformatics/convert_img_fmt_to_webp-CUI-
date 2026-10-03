# Public vendor placement in CI

The pytest adapter is test-only. `vendor.lock.json` replaces the old adapter
provenance JSON and records exact xprobe source and LICENSE bytes with upstream
commit, Git blob and SHA-256. The checked-in adapter bytes are unchanged.

Ordinary push/PR CI verifies the baseline, recreates locked files from public
GitHub, and updates the allowlist once in `resolve-vendor`. It validates all
selected bytes before writing. Every Python matrix job downloads that same
`vendor-snapshot` and checks it offline before existing tests. Upstream changes
mid-run cannot select different versions for different Python jobs. A failed
update fails the job; subsequent checks cannot mask its exit code. The shared
tool uses anonymous public HTTP, with anonymous temporary Git fallback for
403/429 rate limits, and needs no dedicated token or enable variable.

The resolved lock, adapter and LICENSE are preserved in Actions artifacts both
before and after testing, including failures. JUnit/native collection remains
unchanged and cannot turn a failed producer green. Public repository Actions
artifacts are downloadable by signed-in users; raw reports are not published to
Pages. There is no commit, push, update PR creation or main writeback. The
conversion entry points, Pillow requirement and Docker job remain unchanged.
PyYAML is confined to `tests/requirements.txt` for workflow regression checks.

Workflow dispatch offers `vendor-mode: locked` to test the pinned baseline;
normal push/PR runs update automatically. ALM agents can use the same CLI in a
disposable working copy, without a separate manual activation step:

```bash
git clone https://github.com/myon-bioinformatics/myon-bioinformatics.git .vendor-sync-tools
git -C .vendor-sync-tools checkout --detach 37f30d5acdc1906d4acbd103ce6f652bc13ca7eb
python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json
# To restore missing locked files:
python -S .vendor-sync-tools/vendor_sync.py materialize --manifest vendor.lock.json
python -S .vendor-sync-tools/vendor_sync.py update --manifest vendor.lock.json
python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json
python -m pip install -r requirements.txt -r tests/requirements.txt
python -m pytest -p scripts.xprobe_pytest -q tests
python -m unittest discover -s tests -v
```

`check` is offline. `update` refuses locally edited locked bytes before fetching;
finish local edits separately rather than overwrite them. An artifact's exact
lock can be materialized later to reproduce its selected sources. Cross-repo
rollout is tracked in myon-bioinformatics/myon-bioinformatics#35; JUnit remains
tracked in #22.
