"""Actual Python HTTP/AFC/normal-input path at synthetic Qt boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.adapters import avatar_controls as controls
from ios.self_tests.test_ios_normal_input import Boundary as Transport


class Boundary(Transport):
    def __init__(self):
        super().__init__(); self.source_sequence = 0; self.screen = 'avatar'; self.dialog = 'none'
        self.focus = None; self.draft = ''; self.popup_title = ''; self.manage = False; self.scale = 1.
        self.name = ''; self.avatar_url = 'original'; self.wearable = False; self.phase = 'idle'
        self.intents = []; self.ignore = set(); self.lost = False
        self.shown = self.last_shown = True; self.visibility_revision = 0
        self.root_id = '22222222-2222-4222-8222-222222222222'
    def root(self): return self.root_id
    def rows(self):
        rows = []
        def add(identifier, **values):
            base = dict(id=identifier, enabled=True, focused=identifier == self.focus, inputReady=True)
            if identifier.startswith(('avatar.', 'people.')):
                base.update(rootId=self.root(), qmlSource='file:///app.bundle/qml/hifi/'+('AvatarApp.qml' if self.screen == 'avatar' else 'Pal.qml'))
            base.update(values)
            if identifier in ('avatar.entry', 'people.entry'): base.pop('rootId'); base.pop('qmlSource')
            base['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(base, sort_keys=True)+self.dialog+self.draft+self.phase+str(self.visibility_revision)))
            rows.append(base)
        add('tablet.home')
        if self.screen == 'home': add('avatar.entry'); add('people.entry')
        elif self.screen == 'avatar':
            add('avatar.page', inputReady=False, profile=controls.PROFILE, dialog=self.dialog,
                popupTitle=self.popup_title, manage=self.manage, favoriteName=self.name, favoritePresent=bool(self.name))
            if self.dialog == 'none':
                for identifier in ('avatar.url-open', 'avatar.settings-open', 'avatar.favorite-add', 'avatar.manage'): add(identifier)
            elif self.dialog == 'popup':
                add('avatar.url', text=self.draft); add('avatar.popup.confirm'); add('avatar.popup.cancel')
            elif self.dialog == 'favorite':
                add('avatar.favorite-name', text=self.draft); add('avatar.favorite.confirm', nameConflict=self.draft == 'existing')
                add('avatar.favorite.cancel')
            elif self.dialog == 'settings':
                add('avatar.scale', value=self.scale, minimum=.1, maximum=4.)
                add('avatar.settings.confirm'); add('avatar.settings.cancel')
        else:
            add('people.page', inputReady=False, profile=controls.PROFILE, dialog=self.dialog,
                connectionState=dict(phase=self.phase, message='', peerName='', peer='', requestId=''), activeTab='nearbyTab')
            if self.dialog == 'connection': add('people.cancel')
        return rows
    def observed(self):
        self.source_sequence += 1
        if self.shown != self.last_shown: self.visibility_revision += 1; self.last_shown = self.shown
        rows = self.rows() if self.shown else []
        for row in rows:
            if row['id'].startswith('tablet.'): row.pop('inputReady')
        return dict(schemaVersion=1, instance=self.instance, frameSpace='qt-window-logical', processId=42,
            sampleEpochMs=int(time.time()*1000), elapsedMs=int(self.clock*1000), lastSequence=self.sequence,
            tabletShown=self.shown, ready=True,
            controls=[row | dict(frame=dict(x=10, y=20, width=200, height=48)) for row in rows],
            avatarControlsVersion=1, avatarGeneration='33333333-3333-4333-8333-333333333333',
            avatarSourceSequence=self.source_sequence)
    def post(self, request, timeout):
        payload = json.loads(request.data)
        if payload['operation'] != 'edit': return super().post(request, timeout)
        self.requests.append(payload); query = payload['input']; original = self.rows()
        matches = [row for row in original if row['token'] == query['fieldToken']]
        valid = len(matches) == 1 and query['sequence'] == self.sequence+1 and query['instance'] == self.instance
        self.sequence += 1
        if valid:
            row = matches[0]; identifier = row['id']; action = query['operation']
            if identifier not in self.ignore:
                if action == 'replace': self.draft = query['text']
                elif action == 'set-value': self.scale = query['value']
                elif identifier == 'tablet.home': self.screen = 'home'; self.dialog = 'none'
                elif identifier in ('avatar.entry', 'people.entry'): self.screen = identifier.split('.')[0]
                elif identifier == 'avatar.url-open': self.dialog = 'popup'; self.popup_title = 'Specify Avatar URL'; self.draft = self.avatar_url
                elif identifier == 'avatar.url': self.focus = identifier
                elif identifier == 'avatar.popup.confirm': self.avatar_url = self.draft; self.dialog = 'none'; self.focus = None
                elif identifier == 'avatar.favorite-add': self.dialog = 'favorite'; self.draft = ''; self.focus = 'avatar.favorite-name'
                elif identifier == 'avatar.favorite-name': self.focus = identifier
                elif identifier == 'avatar.favorite.confirm': self.name = self.draft; self.dialog = 'none'; self.focus = None
                elif identifier == 'avatar.settings-open': self.dialog = 'settings'
                elif identifier == 'avatar.settings.confirm': self.dialog = 'none'
                elif identifier == 'people.cancel':
                    self.phase = 'idle' if self.phase in ('success', 'cancelled', 'declined', 'error') else 'cancelled'
                    if self.phase == 'idle': self.dialog = 'none'
        self.receipt = dict(schemaVersion=1, commandId=payload['commandId'], status=dict(schemaVersion=1,
            commandId=query['commandId'], instance=self.instance, sequence=self.sequence, performed=bool(valid),
            processId=42, sampleEpochMs=int(time.time()*1000)))
        self.response = json.dumps(payload).encode()
        if self.lost: raise NativeUIError('Synthetic result loss after actual input')
        return self


class AvatarControlTests(unittest.TestCase):
    def flow(self):
        source = Boundary(); native = source.input(); source.source_sequence = 0
        io = controls.IOSAvatarIO(native)
        ui = controls.AvatarUI(io, source.intents.append, monotonic=lambda: source.clock,
            sleep=lambda seconds: setattr(source, 'clock', source.clock+seconds))
        return source, io, ui
    def test_actual_transport_ordinary_pointer_IME_scale_and_original_readback(self):
        source, io, ui = self.flow()
        with patch.object(normal_input, 'urlopen', source.post):
            ui.avatar_url('https://controlled.invalid/avatar-a.fst'); ui.save_bookmark('owned'); ui.scale(1.5)
        self.assertEqual('https://controlled.invalid/avatar-a.fst', source.avatar_url)
        self.assertEqual(('owned', 1.5), (source.name, source.scale))
        inputs = [row['input'] for row in source.requests if row['operation'] == 'edit']
        self.assertEqual(list(range(1, len(inputs)+1)), [query['sequence'] for query in inputs])
        self.assertEqual(len(inputs), len(source.intents)); self.assertNotIn('featurePassed', inputs[0])
        self.assertTrue(all('reference' in intent for intent in source.intents))
    def test_cancel_then_close_are_two_separately_observed_original_events(self):
        source, io, ui = self.flow(); source.screen = 'people'; source.dialog = 'connection'; source.phase = 'outgoing'
        with patch.object(normal_input, 'urlopen', source.post): ui.close_connection()
        self.assertEqual(('idle', 'none'), (source.phase, source.dialog)); self.assertEqual(2, len(source.intents))
        self.assertEqual(['outgoing', 'cancelled'], [intent['reference']['controls'][1]['connectionState']['phase'] for intent in source.intents])
    def test_ignored_pointer_or_text_ACK_cannot_prove_the_original_UI_effect(self):
        for identifier in ('avatar.url-open', 'avatar.url'):
            source, io, ui = self.flow(); source.ignore.add(identifier)
            with patch.object(normal_input, 'urlopen', source.post), self.subTest(identifier=identifier), self.assertRaises(NativeUIError):
                ui.avatar_url('https://controlled.invalid/avatar-a.fst')
            self.assertEqual('original', source.avatar_url)
    def test_existing_bookmark_overwrite_is_refused_before_confirm_input(self):
        source, io, ui = self.flow()
        with patch.object(normal_input, 'urlopen', source.post), self.assertRaises(NativeUIError): ui.save_bookmark('existing')
        self.assertFalse(any(intent['controlId'] == 'avatar.favorite.confirm' for intent in source.intents))
    def test_changed_actual_draft_or_dialog_never_adopts_a_new_reference(self):
        source, io, ui = self.flow()
        with patch.object(normal_input, 'urlopen', source.post):
            ui.input('avatar.url-open'); before = io.capture(); source.draft = 'foreign'
            with self.assertRaises(NativeUIError): io.input('avatar.popup.confirm', 'activate', reference=before)
        self.assertEqual(1, source.sequence)
    def test_missing_source_false_version_foreign_root_extra_verdict_or_frame_refuse_input(self):
        source, io, ui = self.flow(); value = source.observed()
        for fault in ('missing', 'false', 'root', 'verdict', 'frame'):
            altered = deepcopy(value)
            if fault == 'missing': altered.pop('avatarControlsVersion')
            elif fault == 'false': altered['avatarControlsVersion'] = True
            elif fault == 'root': altered['controls'][1]['rootId'] = 'invalid'
            elif fault == 'verdict': altered['controls'][1]['avatarLoaded'] = True
            else: altered['controls'][1]['frame'] = None
            with self.subTest(fault=fault), self.assertRaises((NativeUIError, TypeError)):
                normal_input.observation(altered, 42, time.time()*1000)
    def test_lost_delivery_result_and_failed_durable_intent_are_not_retried(self):
        source, io, ui = self.flow(); source.lost = True
        with patch.object(normal_input, 'urlopen', source.post), self.assertRaises(NativeUIError): ui.input('avatar.url-open')
        self.assertEqual(1, len([row for row in source.requests if row['operation'] == 'edit']))
        source, io, ui = self.flow()
        def fail(_): raise NativeUIError('Durable storage unavailable')
        ui.intent = fail
        with patch.object(normal_input, 'urlopen', source.post), self.assertRaises(NativeUIError): ui.input('avatar.url-open')
        self.assertFalse(any(row['operation'] == 'edit' for row in source.requests))

    def test_real_visibility_changes_preserve_channel_birth_but_do_not_reuse_old_tokens(self):
        source, io, ui = self.flow()
        with patch.object(normal_input, 'urlopen', source.post):
            before = io.capture(); source.shown = False; hidden = io.capture()
            self.assertFalse(hidden['open']); self.assertEqual([], hidden['controls'])
            self.assertEqual(before['scope']['generation'], hidden['scope']['generation'])
            source.shown = True; after = io.capture()
            self.assertEqual(before['scope']['generation'], after['scope']['generation'])
            with self.assertRaises(NativeUIError): io.input('avatar.url-open', 'activate', reference=before)
        self.assertFalse(any(row['operation'] == 'edit' for row in source.requests))

    def test_replaced_actual_root_is_distinct_even_with_identical_values_and_same_channel_birth(self):
        source, io, ui = self.flow()
        with patch.object(normal_input, 'urlopen', source.post):
            before = io.capture(); source.root_id = '44444444-4444-4444-8444-444444444444'
            with self.assertRaises(NativeUIError): io.input('avatar.url-open', 'activate', reference=before)
        self.assertFalse(any(row['operation'] == 'edit' for row in source.requests))


if __name__ == '__main__': unittest.main()
