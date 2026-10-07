# Public vendor placement in CI

The pytest adapter is test-only. `vendor.lock.json` records exact xprobe and
GHI source and LICENSE bytes with upstream commit, Git blob and SHA-256. GHI is
enrolled as an unused sandbox module: CI loads it directly under `python -S`,
while the conversion entry points do not import or call it. Enrollment is
separate from adopting GHI in the runtime. The import smoke checks loadability
without site packages; it does not exercise GHI's GitHub operations or enforce
absence of import-time I/O in future upstream versions.

Ordinary push/PR CI verifies the baseline, recreates locked files from public
GitHub, and promotes the allowlist once in `resolve-vendor` using the pinned
canonical `vendor_sync.py`. It validates all selected bytes before writing,
checks the promoted baseline offline, and records a `vendor-promotion/1` JSON
receipt. Every Python matrix job downloads that same `vendor-snapshot` and
checks it offline before existing tests. Upstream changes
mid-run cannot select different versions for different Python jobs. A failed
update fails the job; subsequent checks cannot mask its exit code. The shared
tool uses anonymous public HTTP, with anonymous temporary Git fallback for
403/429 rate limits, and needs no dedicated token or enable variable.

The resolved lock, both modules and both LICENSE files are preserved in Actions
artifacts before and after testing, including failures. Update runs also preserve
the promotion receipt, for six files in each successful snapshot. JUnit/native
collection remains unchanged and cannot turn a failed producer green. Public repository Actions
artifacts are downloadable by signed-in users; raw reports are not published to
Pages. There is no commit, push, update PR creation or main writeback. The
conversion entry points, Pillow requirement and Docker job remain unchanged.
PyYAML is confined to `tests/requirements.txt` for workflow regression checks.

Workflow dispatch offers `vendor-mode: locked` to test the pinned baseline.
It materializes and verifies all four locked source/LICENSE files but does not
promote, generate a promotion receipt, or include a receipt path in its artifact
uploads; each successful locked snapshot contains five files. A successful
update with no upstream byte changes still produces a real promotion receipt
with empty `changed_paths` and `promoted` lists. Normal push/PR runs update
automatically. ALM agents can use the same CLI in a disposable working copy,
without a separate manual activation step:

```bash
set -euo pipefail
git clone https://github.com/myon-bioinformatics/myon-bioinformatics.git .vendor-sync-tools
git -C .vendor-sync-tools checkout --detach 08dc3757deeb930c950bdcc6bd55ec3112ba49fc
python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json
# To restore missing locked files:
python -S .vendor-sync-tools/vendor_sync.py materialize --manifest vendor.lock.json
python -S .vendor-sync-tools/vendor_sync.py promote --manifest vendor.lock.json | tee vendor-promotion.json
python -S -m json.tool vendor-promotion.json > /dev/null
python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json
python -m pip install -r requirements.txt -r tests/requirements.txt
python -m pytest -p scripts.xprobe_pytest -q tests
python -m unittest discover -s tests -v
```

`check` is offline. `promote` refuses locally edited locked bytes before fetching;
finish local edits separately rather than overwrite them. An artifact's exact
lock can be materialized later to reproduce its selected sources. Cross-repo
rollout is tracked in myon-bioinformatics/myon-bioinformatics#35; JUnit remains
tracked in #22.
