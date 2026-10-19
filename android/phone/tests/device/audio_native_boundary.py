"""Host fixture of the original Qt/probe boundary; no native client is run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from self_tests.test_token_audio_ui import AudioBoundary


class ControlNativeBoundary:
    def __init__(self, ui=None, wire_action="phone-audio-ui"):
        self.ui = AudioBoundary() if ui is None else ui
        self.wire_action = wire_action
        self.command_sequence = self.source_sequence = 0
        self.value, self.mutate, self.before_input = None, None, None
        self.commands, self.input_requests = [],[]

    def snapshot(self):
        self.source_sequence += 1
        value = self.ui.capture()
        for row in value['controls']: row['focused'] = False
        return dict(value,schemaVersion=1,sourceSequence=self.source_sequence,
            lastCommandSequence=self.command_sequence,elapsedMs=round(self.ui.clock*1000),
            capturedEpochMs=20000,processId=31)

    def send(self, outer):
        assert set(outer) == {'schemaVersion','commandId','action','request'}
        assert outer['action'] == self.wire_action
        self.commands.append(deepcopy(outer)); request = outer['request']
        assert request['commandId'] == outer['commandId']
        action = request['action']
        if action == 'observe':
            assert set(request) == {'schemaVersion','commandId','action'}
            self.value = dict(self.snapshot(),commandId=request['commandId'],action=action)
        else:
            fields = {'schemaVersion','commandId','action','instance','generation','sequence',
                      'observedElapsedMs','controlId','controlToken'}
            if action == 'scroll': fields.add('direction')
            if action == 'set-value': fields.add('value')
            assert set(request) == fields
            if self.before_input: self.before_input()
            current = self.snapshot()
            rows = [r for r in current['controls'] if r['id'] == request['controlId']]
            assert request['sequence'] == self.command_sequence+1
            self.command_sequence = request['sequence']
            valid = (request['instance'] == current['instance'] and request['generation'] == current['generation']
                     and len(rows) == 1 and rows[0]['token'] == request['controlToken'])
            self.input_requests.append(deepcopy(request))
            if valid:
                if action == 'activate': self.ui.activate(request['controlId'],token=request['controlToken'])
                elif action == 'set-value': self.ui.set_value(request['controlId'],request['value'],token=request['controlToken'])
                elif action == 'scroll': self.ui.scroll(request['controlId'],request['direction'],token=request['controlToken'])
                else: raise AssertionError(action)
            self.value = dict(schemaVersion=1,commandId=request['commandId'],action=action,performed=valid,
                instance=current['instance'],generation=current['generation'],sequence=self.command_sequence,processId=31)
        if self.mutate: self.mutate(self.value)


AudioNativeBoundary = ControlNativeBoundary
