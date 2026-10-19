"""Synthetic native UI/OpenXR/SDK/render boundaries; no device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import uuid

from adb_transport import AdbTransport

SDK = r'''#!/usr/bin/env python3
import os,shlex,subprocess,sys
from pathlib import Path
args=sys.argv[1:]
assert args[:2]==['-P','5038']
assert args[2:5]==['-s','synthetic-private-target','exec-out'] and len(args)==6
remote=shlex.split(args[5])
assert remote[:4]==['run-as','org.overte.pico','sh','-c']
assert remote[5]=='overte-snapshot-files'
result=subprocess.run(['sh','-c',remote[4],*remote[5:]],
    cwd=Path(os.environ['OVERTE_PICO_SNAPSHOT_TEST_APP']),stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
sys.stdout.buffer.write(result.stdout)
raise SystemExit(0)
'''


def create(base, digest, state_root, *, mutation='', fixtures=None):
    class SnapshotAdb(base):
        def __init__(self):
            super().__init__(digest, state_root)
            self.identity = '123:987654321'
            self.mutation, self.fixtures = mutation, fixtures
            self.screen, self.popup = 'home', None
            self.mode, self.format = 'animated', 'webp'
            self.capturing = False
            self.captures, self.clock = 0, 0.0
            self.reports = []
            self.app = state_root.parent / 'synthetic snapshot app'
            self.files = self.app / 'files/Snapshots'
            self.files.mkdir(parents=True)
            self.artifacts = state_root.parent / 'snapshot artifacts'
            sdk = state_root.parent / 'snapshot-adb.py'
            sdk.write_text(SDK); sdk.chmod(0o700)
            self.transport = AdbTransport(str(sdk), server_port=5038)

        def snapshot(self):
            names = []
            if self.opened:
                if self.popup:
                    choices = ('still', 'animated', 'panorama', 'cubemap') if self.popup == 'snapshot.mode' else ('png', 'jpg', 'webp')
                    names = [self.popup + '.' + choice for choice in choices]
                elif self.screen == 'home':
                    names = ['tablet.page.1', 'tablet.page.2'] + (['snapshot.entry'] if self.page == 2 else [])
                else:
                    names = ['snapshot.name', 'snapshot.mode', 'snapshot.format', 'snapshot.capture']
                    if self.capturing: names.append('snapshot.cancel')
            controls = []
            for name in names:
                row = dict(id=name, token=str(uuid.uuid5(uuid.NAMESPACE_URL, 'overte-synthetic-ui/' + name)),
                    enabled=not self.capturing if name in ('snapshot.mode', 'snapshot.capture') else True,
                    focused=self.focused and name == 'snapshot.name')
                if name.startswith('snapshot.mode.') or name.startswith('snapshot.format.'):
                    row['checked'] = name.rsplit('.', 1)[1] == (self.mode if self.popup == 'snapshot.mode' else self.format)
                controls.append(row)
            value = dict(schemaVersion=1, bridgeId=self.bridge_id, generation=self.generation,
                processId=123, elapsedMs=self.native_elapsed, updatedEpochMs=self.epoch_milliseconds(self.target),
                lastCommandSequence=self.sequence, open=self.opened, ready=self.opened, controls=controls)
            if self.snapshot_mutation: self.snapshot_mutation(value)
            return value

        def write_debug_app_file(self, target, package, path, raw):
            assert target == self.target and package == 'org.overte.pico'
            assert path == 'files/overte-e2e/navigation-ui-command.json'
            value = json.loads(raw)
            current = {row['id']: row for row in self.snapshot()['controls']}
            control, action = value['controlId'], value['action']
            assert control in current and current[control]['enabled']
            assert value['controlToken'] == current[control]['token']
            assert value['sequence'] == self.sequence + 1
            assert value['bridgeId'] == self.bridge_id and value['generation'] == self.generation
            self.input_ages.append(self.native_elapsed - value['observedElapsedMs'])
            assert 0 <= self.input_ages[-1] <= 5000
            self.sequence += 1; self.inputs.append(value)
            performed = True
            if action == 'replace':
                assert control == 'snapshot.name' and self.focused
                if self.mutation != 'name-ignored': self.text = value['text']
            else:
                assert action == 'activate'
                if control.startswith('tablet.page.'): self.page = int(control.rsplit('.', 1)[1])
                elif control == 'snapshot.entry':
                    self.screen = 'snapshot'
                    performed = self.mutation != 'partial-entry-error'
                elif control == 'snapshot.name': self.focused = True
                elif control in ('snapshot.mode', 'snapshot.format'):
                    self.popup = control; self.focused = False
                elif control.startswith('snapshot.mode.'):
                    if self.mutation != 'mode-ignored': self.mode = control.rsplit('.', 1)[1]
                    self.popup = None
                elif control.startswith('snapshot.format.'):
                    if self.mutation != 'format-ignored': self.format = control.rsplit('.', 1)[1]
                    self.popup = None
                elif control == 'snapshot.capture': self.take()
                elif control == 'snapshot.cancel': self.capturing = False
                else: raise AssertionError('Unexpected synthetic UI operation')
            self.status = dict(schemaVersion=1, bridgeId=self.bridge_id, commandId=value['commandId'],
                sequence=value['sequence'], performed=performed, error='' if performed else 'synthetic-delivery-failed',
                processId=123, updatedEpochMs=self.epoch_milliseconds(target))
            if self.status_mutation: self.status_mutation(self.status)
            if self.after_send:
                callback, self.after_send = self.after_send, None
                callback()

        def take(self):
            self.captures += 1
            if self.mutation == 'ack-only': return
            self.capturing = self.mutation == 'capture-pending'
            if not self.capturing:
                formats = (self.format, 'gif') if self.mode == 'animated' else (self.format,)
                for extension in formats:
                    if self.mutation == 'missing-gif' and extension == 'gif': continue
                    label = ('gif' if extension == 'gif' else 'still-' + self.format
                             if self.mode == 'still' else self.mode)
                    payload = self.fixtures[label] if self.fixtures is not None else b'original synthetic Pico bytes'
                    (self.files / (self.text + '-snap_1792368000000_' + str(self.captures) + '.' + extension)).write_bytes(payload)
            self.opened = False  # Actual VR capture may hide its owned tablet.

        def execute_bytes(self, args, *, target, timeout=20):
            return self.transport.execute_bytes(args, target=target, timeout=timeout)

        def require_process_identity(self, identity):
            assert identity == self.identity

        def stage(self, identity, operation, values):
            assert identity == self.identity and values == {'holdMilliseconds': 1000}
            assert operation in ('tablet.open', 'tablet.close')
            states = list(self.state_root.glob('normal-snapshot-ui-*.json'))
            assert len(states) == 1 and json.loads(states[0].read_text())['tabletOwned'] is True
            self.controllers.append(operation)
            self.opened = operation == 'tablet.open'
            return {'performed': True}

        def sleep(self, seconds): self.clock += seconds * 20

    return SnapshotAdb()
