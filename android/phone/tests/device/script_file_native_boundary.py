"""Explicit Qt file UI/probe boundary for host checks; never an APK execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tests/device'))
from self_tests.test_token_script_file_ui import NativeBoundary


class FileNativeBoundary:
    def __init__(self, root):
        self.ui = NativeBoundary(root)
        self.source_sequence = self.command_sequence = 0
        self.generation = 'b' * 32
        self.value = None
        self.commands, self.input_requests = [], []
        self.focused = None
        self.ignore_result = False
        self.mutate = None

    def snapshot(self):
        value = self.ui.capture()
        for row in value['controls']:
            source = row.get('sourceUrl', str(row.get('currentIndex', '')))
            row['token'] = hashlib.sha256((row['id'] + '\0' + source).encode()).hexdigest()[:32]
            row['focused'] = row['id'] == self.focused
        self.source_sequence += 1
        return dict(value, schemaVersion=1, generation=self.generation, sourceSequence=self.source_sequence,
            lastCommandSequence=self.command_sequence, elapsedMs=round(self.ui.clock * 1000),
            capturedEpochMs=20000, processId=31)

    def send(self, outer):
        self.commands.append(deepcopy(outer))
        assert set(outer) == {'schemaVersion', 'commandId', 'action', 'request'}
        assert outer['action'] == 'phone-script-file-ui'
        command = outer['request']
        assert outer['commandId'] == command['commandId']
        action = command['action']
        current = self.snapshot()
        if action == 'observe':
            assert set(command) == {'schemaVersion', 'commandId', 'action'}
            self.value = dict(current, commandId=command['commandId'], action=action)
        else:
            expected = {'schemaVersion', 'commandId', 'action', 'instance', 'generation', 'sequence',
                        'observedElapsedMs', 'controlId', 'controlToken'}
            if action == 'replace': expected.add('text')
            if action == 'select-index': expected.add('index')
            assert set(command) == expected
            rows = [row for row in current['controls'] if row['id'] == command['controlId']]
            assert len(rows) == 1 and rows[0]['token'] == command['controlToken']
            assert command['sequence'] == self.command_sequence + 1
            assert command['instance'] == current['instance'] and command['generation'] == self.generation
            self.command_sequence = command['sequence']
            self.input_requests.append(deepcopy(command))
            identifier = command['controlId']
            if action == 'activate':
                if identifier == 'script-file.primary':
                    self.ui.actions.append(identifier)  # Actual popup/focus route; no selection assignment.
                else:
                    self.ui.activate(identifier, source=rows[0].get('sourceUrl'))
                self.focused = identifier
            elif action == 'replace': self.ui.replace(identifier, command['text'])
            elif action == 'submit': self.ui.submit(identifier)
            elif action == 'select-index': self.ui.select_index(identifier, command['index'])
            else: raise AssertionError('Unexpected native boundary input')
            self.value = dict(schemaVersion=1, commandId=command['commandId'], action=action,
                instance=current['instance'], generation=self.generation, sequence=self.command_sequence,
                processId=31, performed=True)
        if self.ignore_result: self.value['commandId'] = 'f' * 32
        if self.mutate: self.mutate(self.value)
