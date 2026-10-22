"""Actual Pico Chat transport/recipe; Qt/OpenXR/device effects are synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
import unittest
from unittest.mock import patch
import uuid
import test_normal_scripts as existing
from adapters.token_chat_ui import TokenChatUI
from feature_journeys.fixtures import context
from self_tests.test_chat_erase_controls import CleanupWidgets, RUN


class PicoChatControlsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.PicoNormalScriptsTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.instance, self.native = self.fixture.instance, self.fixture.native
        self.widget = CleanupWidgets(); self.widget.panel = True
        self.widget.instance, self.widget.generation = self.native.bridge_id, self.native.generation
        self.widget.domain = [context(RUN)['unicode']]; self.intents = []
        self.native.opened = True; self.before_input = None
        capture_original = self.widget.capture
        def capture():
            value = capture_original()
            for row in value['controls']:
                row['token'] = str(uuid.UUID(row['token']))
                if row['id'].startswith('tablet.'): row.pop('inputReady', None)
            return value
        self.widget.capture = capture
        snapshot_original, write_original = self.native.snapshot, self.native.write_debug_app_file
        def snapshot():
            value = snapshot_original(); actual = self.widget.capture()
            value.update(chatControlsVersion=2, controls=deepcopy(actual['controls']),
                elapsedMs=actual['scope']['elapsedMs'], lastCommandSequence=self.widget.sequence)
            return value
        def write(target, package, path, raw):
            if path != 'files/overte-e2e/navigation-ui-command.json': return write_original(target, package, path, raw)
            command = json.loads(raw)
            if self.before_input: self.before_input()
            original = self.widget.capture(); row = next(r for r in original['controls'] if r['id'] == command['controlId'])
            valid = (row['token'] == command['controlToken'] and command['sequence'] == self.widget.sequence + 1
                and command['bridgeId'] == self.widget.instance and command['generation'] == self.widget.generation)
            self.native.inputs.append(deepcopy(command))
            if valid: self.widget.input(command['controlId'], command['action'], original, command.get('text'))
            self.native.sequence = self.widget.sequence
            self.native.status = dict(schemaVersion=1, bridgeId=self.native.bridge_id, commandId=command['commandId'],
                sequence=command['sequence'], performed=valid, error='' if valid else 'control-unavailable', processId=123,
                updatedEpochMs=self.native.epoch_milliseconds(target))
        for boundary in (patch.object(self.native, 'snapshot', side_effect=snapshot),
                patch.object(self.native, 'write_debug_app_file', side_effect=write),
                patch('adapters.token_chat_ui.TokenChatUI', partial(TokenChatUI,
                    monotonic=lambda: self.widget.clock, sleep=self.widget.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.flow = self.instance._chat_controls(self.native.target, self.intents.append, RUN)

    def test_original_v2_settings_and_erase_reach_actual_bound_pico_input_commands(self):
        self.flow.erase_history(lambda original: self.widget.digest() == next(r['historySha256']
            for r in original['controls'] if r['id'] == 'chat.erase'))
        self.assertEqual(1, self.widget.erased)
        self.assertEqual(['chat.settings', 'chat.erase'], [row['controlId'] for row in self.native.inputs])
        self.assertEqual(['chat.settings', 'chat.erase'], [row['controlId'] for row in self.intents])
        self.assertFalse(any(cap.startswith('feature.chat.') for cap in self.instance.capabilities(self.native.target)))

    def test_same_count_history_change_at_actual_backend_admission_preserves_original_without_erase(self):
        def before():
            if self.native.inputs and self.native.inputs[-1]['controlId'] == 'chat.settings':
                self.widget.domain[0] = 'foreign original row'
        self.before_input = before
        with self.assertRaises((RuntimeError, ValueError)): self.flow.erase_history(lambda _v: True)
        self.assertEqual(0, self.widget.erased); self.assertEqual(['foreign original row'], self.widget.domain)
        self.assertEqual('chat.erase', self.intents[-1]['controlId'])

    def test_current_candidate_loss_blocks_another_command_and_keeps_original_intent(self):
        def authorize(_v): self.native.digest = 'f' * 64; return True
        with self.assertRaises((RuntimeError, ValueError)): self.flow.erase_history(authorize)
        self.assertEqual(0, self.widget.erased)
        self.assertEqual(['chat.settings'], [row['controlId'] for row in self.native.inputs])


if __name__ == '__main__': unittest.main()
