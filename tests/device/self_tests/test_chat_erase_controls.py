"""Normal Settings/Erase admission on synthetic widgets; no product execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI, same_reference, snapshot
from feature_journeys.fixtures import context
from self_tests.test_token_chat_ui import Widgets, RUN


class CleanupWidgets(Widgets):
    def __init__(self):
        super().__init__(); self.cleanup_tokens = {}; self.erased = 0

    def digest(self):
        return hashlib.sha256(json.dumps([self.local, self.domain], ensure_ascii=False).encode()).hexdigest()

    def capture(self):
        value = super().capture(); value['chatControlsVersion'] = 2
        if not self.panel: return value
        if self.channel == 'settings':
            value['controls'] = [row for row in value['controls'] if row['id'] not in ('chat.input', 'chat.send')]
        for identifier in ('chat.settings',) + (('chat.erase',) if self.channel == 'settings' else ()):
            signature = (self.page_life, self.channel, self.draft, self.focus, self.geometry,
                         self.digest() if identifier == 'chat.erase' else None)
            if identifier not in self.cleanup_tokens or self.cleanup_tokens[identifier][0] != signature:
                self.cleanup_tokens[identifier] = (signature, uuid.uuid4().hex)
            row = dict(id=identifier, token=self.cleanup_tokens[identifier][1], enabled=True, focused=False, inputReady=True)
            if identifier == 'chat.erase': row['historySha256'] = self.digest()
            value['controls'].append(row)
        return value

    def input(self, identifier, action, reference, value=None):
        if identifier not in ('chat.settings', 'chat.erase'): return super().input(identifier, action, reference, value)
        if self.before: self.before()
        same_reference(reference, self.capture(), identifier)
        self.calls.append((identifier, action, value))
        if self.ignore: return
        self.sequence += 1
        if self.ignore_effect: return
        if identifier == 'chat.settings': self.channel = 'settings'
        else: self.erased += 1; self.local.clear(); self.domain.clear()
        if self.lose_ack: raise NativeUIError('Input acknowledgment was lost')


class ChatEraseControlsTests(unittest.TestCase):
    def setUp(self):
        self.widgets = CleanupWidgets(); self.intents = []
        self.ui = TokenChatUI(self.widgets, lambda v: self.intents.append(deepcopy(v)), RUN,
            monotonic=lambda: self.widgets.clock, sleep=self.widgets.sleep)
        self.ui.open(); self.widgets.domain = [context(RUN)['unicode']]

    def test_normal_settings_and_erase_use_original_digest_and_do_not_claim_stored_history(self):
        digest = self.widgets.digest(); admitted = []
        def authorize(value):
            admitted.append(value)
            return next(row['historySha256'] for row in value['controls'] if row['id'] == 'chat.erase') == digest
        self.ui.erase_history(authorize)
        self.assertEqual(1, self.widgets.erased)
        self.assertEqual(['chat.entry', 'chat.settings', 'chat.erase'], [row[0] for row in self.widgets.calls])
        self.assertEqual(1, len(admitted)); self.assertEqual('settings', self.ui.page(self.ui.capture())['channel'])
        self.assertNotIn(context(RUN)['unicode'], str(self.intents))
        self.assertNotIn('storage', self.ui.capture())

    def test_unowned_refusal_and_missing_authority_never_issue_erase(self):
        with self.assertRaises(NativeUIError): self.ui.erase_history(lambda _v: False)
        with self.assertRaises(NativeUIError): self.ui.erase_history(None)
        self.assertEqual(0, self.widgets.erased)
        self.assertNotIn('chat.erase', [row[0] for row in self.widgets.calls])
        with self.assertRaises(NativeUIError): self.ui.input('chat.erase')

    def test_same_count_foreign_history_after_authority_is_not_recaptured_for_erase(self):
        def authorize(_original):
            self.widgets.domain[0] = 'unowned private row'
            return True
        with self.assertRaises(NativeUIError): self.ui.erase_history(authorize)
        self.assertEqual(['unowned private row'], self.widgets.domain)
        self.assertEqual(0, self.widgets.erased)
        self.assertNotIn('chat.erase', [v['controlId'] for v in self.intents])

    def test_changed_original_generation_or_backend_admission_after_intent_cannot_erase(self):
        def authorize(_original):
            self.widgets.before = lambda: setattr(self.widgets, 'generation', 'f' * 32)
            return True
        with self.assertRaises(NativeUIError): self.ui.erase_history(authorize)
        self.assertEqual(0, self.widgets.erased)
        self.assertEqual('chat.erase', self.intents[-1]['controlId'])

    def test_uncertain_erase_is_sent_once_and_keeps_its_original_intent(self):
        self.ui.input('chat.settings'); self.widgets.lose_ack = True
        with self.assertRaises(NativeUIError): self.ui.erase_history(lambda _v: True)
        self.assertEqual(1, self.widgets.erased)
        before = len(self.widgets.calls)
        with self.assertRaises(NativeUIError): self.ui.erase_history(lambda _v: True)
        self.assertEqual(before, len(self.widgets.calls)); self.assertEqual('chat.erase', self.intents[-1]['controlId'])

    def test_ignored_erase_or_fake_ack_never_proves_actual_model_clear(self):
        for ignored in ('ignore', 'ignore_effect'):
            self.setUp(); self.ui.input('chat.settings'); setattr(self.widgets, ignored, True)
            with self.subTest(ignored=ignored), self.assertRaises(NativeUIError): self.ui.erase_history(lambda _v: True)
            self.assertEqual([context(RUN)['unicode']], self.widgets.domain)
            self.assertEqual(1, len([v for v in self.widgets.calls if v[0] == 'chat.erase']))

    def test_draft_and_old_producer_prevent_destructive_input(self):
        self.ui.type(context(RUN)['unicode'])
        with self.assertRaises(NativeUIError): self.ui.erase_history(lambda _v: True)
        self.assertEqual(0, self.widgets.erased)
        old = Widgets(); ui = TokenChatUI(old, lambda _v: None, RUN); ui.open()
        with self.assertRaises(NativeUIError): ui.erase_history(lambda _v: True)

    def test_version_and_hash_are_closed_and_old_reader_cannot_relabel_new_controls(self):
        self.ui.input('chat.settings'); original = self.ui.capture()
        for edit in ('old', 'hash', 'private'):
            value = deepcopy(original)
            row = next(v for v in value['controls'] if v['id'] == 'chat.erase')
            if edit == 'old': value['chatControlsVersion'] = 1
            elif edit == 'hash': row['historySha256'] = 'bad'
            else: row['messages'] = ['private']
            with self.assertRaises(NativeUIError): snapshot(value)


if __name__ == '__main__': unittest.main()
