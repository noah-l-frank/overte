"""Short owned host-model worker; never a product or device attestation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import sys

from adapters.pico4.browser_common_export import JourneyConsumptionExport
from feature_journeys.engine import Journey
from self_tests.test_feature_journeys import Boundary, POLICY, RUN


def sources():
    root = Path(__file__).resolve().parents[3]
    result = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename: continue
        path = Path(filename).resolve()
        if not path.is_relative_to(root): continue
        info = path.lstat()
        result[str(path)] = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            physical=[info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
                info.st_size, info.st_mtime_ns, info.st_ctime_ns])
    return result


def emit(value):
    print(json.dumps(value, sort_keys=True, separators=(',', ':')), flush=True)


def main():
    assert sys.argv[1:] == ['--area', 'tablet-web']
    boundary = Boundary('tablet-web')
    root = Path(os.environ['OVT_COMMON_MODEL_ROOT'])
    nonce = os.environ['OVT_COMMON_MODEL_NONCE']
    url = f'http://controlled.test/feature-fixture/v1/runs/{RUN}/'
    rpc_mode = os.environ.get('OVT_COMMON_MODEL_RPC') == 'cleanup'
    def rpc(operation, fields=None):
        emit(dict(rpc=operation, fields=fields))
        return json.loads(sys.stdin.readline(4*1024*1024+1))['result']
    def send(request):
        emit(dict(request=request))
        return json.loads(sys.stdin.readline(65538))
    if rpc_mode:
        run = os.environ['OVT_COMMON_MODEL_RUN']; url = os.environ['OVT_COMMON_MODEL_URL']
    else:
        run = RUN
    export = JourneyConsumptionExport(root, 'tablet-web', run, url, nonce, send, lambda: None)
    journey = Journey('tablet-web', run, url,
        invoke=(lambda operation, fields:rpc('invoke', dict(operation=operation, fields=fields))) if rpc_mode else boundary.invoke,
        witness=(lambda:rpc('witness')) if rpc_mode else boundary.witness,
        activate=boundary.activate, read_artifact=boundary.files.__getitem__, image_policy=POLICY,
        continuity=boundary.continuity,
        monotonic=(lambda:rpc('monotonic')) if rpc_mode else lambda: boundary.clock,
        epoch_ms=(lambda:rpc('epoch')) if rpc_mode else boundary.epoch,
        sleep=(lambda seconds:rpc('sleep', seconds)) if rpc_mode else boundary.sleep,
        report=boundary.reports.append, after_cleanup_baseline=export.callback)
    export.attach(journey)
    before = sources(); emit(dict(ready=True, sources=before))
    command = sys.stdin.readline(65538)
    begin = json.loads(command) if rpc_mode else None
    assert rpc_mode or command == 'begin\n'
    try:
        error = None
        try:
            if rpc_mode:
                from feature_journeys.scenarios import SCENARIOS
                journey.wait('cleanup-restored-baseline', begin['ticket'], begin['barrier'],
                    SCENARIOS['tablet-web']['baseline'], ['peer'], duration=3)
                journey.consumed_cleanup(begin['ticket'], begin['barrier'], begin['started'])
            else:
                journey.execute()
        except Exception as failure:
            error = type(failure).__name__
        emit(dict(completed=export.complete, failed=export.failed, error=error,
            sources=sources(), rawSha256=hashlib.sha256(export.raw).hexdigest()))
        assert sys.stdin.readline(16) == 'stop\n'
    finally:
        assert export.close_host()


if __name__ == '__main__':
    main()
