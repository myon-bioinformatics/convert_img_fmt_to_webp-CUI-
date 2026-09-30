"""Opt-in pytest adapter. Runtime xprobe.py remains stdlib-only."""
import hashlib
import json
from pathlib import Path
import re
import uuid

import pytest


def pytest_addoption(parser):
    group = parser.getgroup('xprobe')
    group.addoption('--xprobe-jsonl', help='Write native pytest observations as JSONL')
    group.addoption('--xprobe-repository', default=None)
    group.addoption('--xprobe-commit-sha', default=None, help='Measured canonical SHA only')
    group.addoption('--xprobe-run-id', default=None)
    group.addoption('--xprobe-max-records', type=int, default=10000)


def pytest_configure(config):
    destination = config.getoption('--xprobe-jsonl')
    if not destination:
        return
    # A single writer is deliberate; xdist needs a controller-specific adapter.
    if getattr(config.option, 'numprocesses', None) or hasattr(config, 'workerinput'):
        raise pytest.UsageError('xprobe JSONL currently requires serial pytest')
    repository = config.getoption('--xprobe-repository')
    sha = config.getoption('--xprobe-commit-sha')
    run_id = config.getoption('--xprobe-run-id') or uuid.uuid4().hex
    limit = config.getoption('--xprobe-max-records')
    if repository is not None and not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise pytest.UsageError('invalid xprobe repository')
    if sha is not None and (repository is None or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', sha)):
        raise pytest.UsageError('xprobe SHA requires canonical repository and full SHA')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', run_id) or not 1 <= limit <= 100000:
        raise pytest.UsageError('invalid xprobe run ID or record limit')
    writer = Recorder(destination, repository, sha, run_id, limit)
    config.pluginmanager.register(writer, 'xprobe-recorder')


class Recorder:
    def __init__(self, destination, repository, sha, run_id, limit):
        self.destination = Path(destination)
        self.context = {'repository': repository, 'commit_sha': sha.lower() if sha else None,
                        'report_id': run_id}
        self.prefix = (repository or 'unmeasured') + '/' + run_id
        self.limit = limit
        self.stream = None
        self.count = 0
        self.dropped = 0
        self.counts = {}

    def emit(self, category, value, *, envelope=False):
        if not envelope and self.count >= self.limit + 1:
            self.dropped += 1
            return
        row = {'id': self.prefix + '/' + str(self.count).zfill(6),
               'category': category, 'value': value,
               'reason': 'Observed pytest result; reproduction inputs are not inferred.',
               'context': self.context}
        self.stream.write(json.dumps(row, ensure_ascii=True, allow_nan=False, sort_keys=True) + '\n')
        self.stream.flush()
        self.count += 1

    def pytest_sessionstart(self, session):
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        # Do not silently overwrite previous evidence, including interrupted runs.
        try:
            self.stream = self.destination.open('x', encoding='utf-8')
        except OSError as error:
            raise pytest.UsageError('cannot create xprobe JSONL; use a new destination') from error
        self.emit('pytest_session', {'event': 'start', 'schema': 'xprobe.pytest.v1'}, envelope=True)

    def observe(self, report, phase):
        native = report.outcome
        expected_failure = hasattr(report, 'wasxfail')
        strict_xpass = (native == 'failed' and isinstance(report.longrepr, str)
                        and report.longrepr.startswith('[XPASS(strict)]'))
        if strict_xpass:
            outcome = 'xpass_strict'
        elif expected_failure:
            outcome = 'xfail' if native == 'skipped' else 'xpass' if native == 'passed' else native
        elif native == 'failed' and phase != 'call':
            outcome = 'error'
        else:
            outcome = native
        self.counts[outcome] = self.counts.get(outcome, 0) + 1
        # Preserve distinct parametrized identities without serializing their values.
        nodeid = report.nodeid
        display = nodeid.split('[', 1)[0][:500]
        self.emit('pytest_observation', {
            'event': 'report', 'node': display,
            'node_hash': hashlib.sha256(nodeid.encode('utf-8')).hexdigest(),
            'phase': phase, 'outcome': outcome, 'native_outcome': native,
            'wasxfail': expected_failure, 'strict_xpass': strict_xpass,
        })

    def pytest_runtest_logreport(self, report):
        self.observe(report, report.when)

    def pytest_collectreport(self, report):
        if report.failed or report.skipped:
            self.observe(report, 'collection')

    def pytest_sessionfinish(self, session, exitstatus):
        if self.stream is None:
            return
        self.emit('pytest_session', {
            'event': 'finish', 'exitstatus': int(exitstatus),
            'records_before_finish': self.count, 'dropped': self.dropped,
            'complete': self.dropped == 0, 'phase_outcomes': self.counts,
        }, envelope=True)
        self.stream.close()
        self.stream = None

    def pytest_unconfigure(self, config):
        if self.stream is not None:
            self.stream.close()
            self.stream = None
