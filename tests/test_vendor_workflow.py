"""CI update and evidence contracts; PyYAML stays test-only."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_public_vendor_ci_updates_without_repository_writes():
    import yaml
    ci = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    jobs = ci['jobs']
    resolve = jobs['resolve-vendor']['steps']
    test = jobs['test']['steps']
    update = next(s for s in resolve if s.get('name') == 'Update public vendor files for this run')
    assert update['if'] == "inputs.vendor-mode != 'locked'"
    assert update['shell'] == 'bash'
    assert not any(word in update['run'] for word in ('|| true', '|| :', 'set +e'))
    assert 'continue-on-error' not in update
    assert update['run'].splitlines() == [
        'python -S .vendor-sync-tools/vendor_sync.py update --manifest vendor.lock.json',
        'python -S .vendor-sync-tools/vendor_sync.py check --manifest vendor.lock.json']
    assert ci['on']['workflow_dispatch']['inputs']['vendor-mode']['default'] == 'update'
    assert jobs['test']['needs'] == 'resolve-vendor'
    assert sum('vendor_sync.py update' in s.get('run', '') for steps in (resolve, test) for s in steps) == 1
    download = next(i for i,s in enumerate(test) if s.get('uses', '').startswith('actions/download-artifact@'))
    verify = next(i for i,s in enumerate(test) if s.get('name') == 'Verify resolved vendor snapshot')
    assert test[download]['with']['name'] == 'vendor-snapshot'
    run_tests = next(i for i, s in enumerate(test) if s.get('name') == 'Run conversion tests with JUnit and native observations')
    assert download < verify < run_tests
    assert 'vendor_sync.py check' in test[verify]['run']
    assert all('vendor_sync.py update' not in s.get('run', '') for s in test)
    for steps, name in ((resolve, 'Preserve resolved vendor snapshot'), (test, 'Preserve vendor lock used by this run')):
        upload = next(s for s in steps if s.get('name') == name)
        assert upload['if'] == 'always()'
        assert upload['with']['if-no-files-found'] == 'error'
        assert set(upload['with']['path'].splitlines()) == {'vendor.lock.json', 'scripts/xprobe_pytest.py', 'scripts/xprobe-LICENSE'}
    pins = [s['with']['ref'] for steps in (resolve, test) for s in steps
            if s.get('with', {}).get('repository') == 'myon-bioinformatics/myon-bioinformatics']
    assert len(pins) == 2 and len(set(pins)) == 1
    assert all(re.fullmatch('[0-9a-f]{40}', pin) for pin in pins)
    assert not (ROOT / '.github/workflows/vendor-update.yml').exists()
    assert ci['permissions'] == {'contents': 'read'}
    for steps in (resolve, test):
        assert all(s['with']['persist-credentials'] == 'false' for s in steps if s.get('uses','').startswith('actions/checkout@'))
    text = (ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert not any(word in text for word in ('VENDOR_UPDATE_TOKEN', 'VENDOR_UPDATES_ENABLED', 'GH_TOKEN', 'git push', 'git commit', 'gh pr', 'continue-on-error'))



def test_failed_update_does_not_reach_successful_check(tmp_path):
    import shlex
    import shutil
    import subprocess
    import sys
    import yaml

    ci = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    step = next(s for s in ci['jobs']['resolve-vendor']['steps']
                if s.get('name') == 'Update public vendor files for this run')
    tool = tmp_path / '.vendor-sync-tools/vendor_sync.py'
    tool.parent.mkdir()
    tool.write_text("import pathlib, sys\n"
                    "if sys.argv[1] == 'update': sys.exit(2)\n"
                    "pathlib.Path('check-reached').touch()\n", encoding='utf-8')
    script = tmp_path / 'update.sh'
    script.write_text(step['run'].replace('python -S ', shlex.quote(sys.executable) + ' -S '), encoding='utf-8')
    result = subprocess.run([shutil.which('bash'), '--noprofile', '--norc', '-e', '-o', 'pipefail', str(script)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert not (tmp_path / 'check-reached').exists()
