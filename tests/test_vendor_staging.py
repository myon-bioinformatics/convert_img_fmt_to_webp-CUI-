"""Execute the workflow's canonical staging commands against real locked bytes."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.github/workflows').is_dir())


class VendorStagingTests(unittest.TestCase):
    def test_workflow_payload_and_fail_closed(self):
        tool = ROOT / '.vendor-sync-tools/vendor_stage.py'
        if not tool.is_file():
            self.skipTest('requires the workflow full-SHA parent checkout')
        commands = []
        for workflow in (ROOT / '.github/workflows').glob('*.yml'):
            text = workflow.read_text(encoding='utf-8')
            for match in re.finditer(r'(?m)^( +)- name: Stage canonical vendor evidence\n', text):
                indent = match[1]
                tail = text[match.end():]
                block = re.split(r'\n' + indent + r'- ', tail, maxsplit=1)[0] + '\n'
                self.assertIn('if: always()', block)
                self.assertNotIn('continue-on-error', block)
                run = re.search(r'(?m)^' + indent + r'  run: >-\n((?:' + indent + r'    [^\n]*\n)+)', block)
                self.assertIsNotNone(run)
                command = ' '.join(line.strip() for line in run[1].splitlines())
                if '$VENDOR_EVIDENCE_KIND' in command:
                    self.assertIn('--promotion-receipt vendor-promotion.json', command)
                output = shlex.split(command)[shlex.split(command).index('--output') + 1]
                upload = re.split(r'\n' + indent + r'- ', tail, maxsplit=1)[1]
                self.assertIn('path: ' + output, upload.split('retention-days:', 1)[0])
                commands.append(command)
        self.assertTrue(commands)
        for command in commands:
            kinds = ('locked', 'candidate') if '$VENDOR_EVIDENCE_KIND' in command else (shlex.split(command)[shlex.split(command).index('--kind') + 1],)
            for kind in kinds:
                for receipt in (False, True):
                    with self.subTest(command=command, kind=kind, receipt=receipt), tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        args = shlex.split(command.replace('$VENDOR_EVIDENCE_KIND', kind))
                        args[0] = sys.executable
                        args[2] = str(tool)
                        manifest = args[args.index('--manifest') + 1]
                        lock = json.loads((ROOT / manifest).read_text(encoding='utf-8'))
                        for entry in lock['files']:
                            dest = root / entry['destination']
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(ROOT / entry['destination'], dest)
                        # A newly enrolled member must be included without a workflow edit.
                        data = b'extra reviewed fixture\n'
                        extra = dict(lock['files'][0], destination='extra/LICENSE',
                                     blob_sha=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(),
                                     sha256=hashlib.sha256(data).hexdigest())
                        lock['files'].append(extra)
                        (root / 'extra').mkdir()
                        (root / 'extra/LICENSE').write_bytes(data)
                        (root / manifest).parent.mkdir(parents=True, exist_ok=True)
                        (root / manifest).write_text(json.dumps(lock), encoding='utf-8')
                        legacy = [args[i + 1] for i, value in enumerate(args) if value == '--legacy-evidence']
                        runtime = [args[i + 1] for i, value in enumerate(args) if value == '--runtime-evidence']
                        for member in legacy:
                            (root / member).parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(ROOT / member, root / member)
                        for member in runtime:
                            (root / member).write_text('{}', encoding='utf-8')
                        if receipt:
                            (root / 'vendor-promotion.json').write_text('{}', encoding='utf-8')
                        result = subprocess.run(args, cwd=root, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        output = root / args[args.index('--output') + 1]
                        evidence = json.loads((output / 'vendor-evidence.json').read_text(encoding='utf-8'))
                        expected = {manifest, *(e['destination'] for e in lock['files'])}
                        self.assertEqual(set(evidence['locked']), expected)
                        self.assertEqual(set(evidence['candidate']), expected)
                        self.assertEqual(evidence['kind'], kind)
                        self.assertEqual(set(evidence['legacy']), set(legacy))
                        if receipt and kind == 'candidate' and '--promotion-receipt' in args:
                            runtime.append('vendor-promotion.json')
                        self.assertEqual(set(evidence['runtime']), set(runtime))
                        expected |= set(legacy) | set(runtime)
                        self.assertEqual({p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}, expected | {'vendor-evidence.json'})
                        for member in expected:
                            self.assertEqual((output / member).read_bytes(), (root / member).read_bytes())
                            self.assertEqual(evidence['sha256'][member], hashlib.sha256((root / member).read_bytes()).hexdigest())
                        shutil.rmtree(output)
                        (root / lock['files'][0]['destination']).write_bytes(b'corrupt')
                        result = subprocess.run(args, cwd=root, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 2)
                        self.assertFalse(output.exists())
