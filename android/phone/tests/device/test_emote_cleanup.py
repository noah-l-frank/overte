"""Original cleanup ownership over synthetic native/Qt/SDK boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from overte_phone_emote_cleanup import PhoneEmoteCleanup
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_script_history import pack,unpack
from test_emote_effects import EffectsModel
from test_emote_sources import RUN


class EmoteCleanupTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-cleanup-');self.addCleanup(temporary.cleanup)
        self.model=EffectsModel(Path(temporary.name));self.model.use_included_source()
        for module in ('overte_phone_emote_inputs','overte_phone_emote_cleanup'):
            mock=patch(module+'.PhoneScriptUI',side_effect=self.model.tablet);mock.start();self.addCleanup(mock.stop)

    def baseline(self):
        m=self.model;m.widgets.tablet=False;m.widgets.page=False
        m.journal.activate(RUN,'b'*32,'baseline',{});source=m.source();source.read();return source

    def playing(self):
        m=self.model;source=self.baseline();owner=PhoneEmoteInputs(source)
        owner.act(m.call('play',dict(name='Crying')));return owner

    def cleanup(self,owner):
        m=self.model;m.journal.activate(RUN,'a'*32,'cleanup',{})
        clean=PhoneEmoteCleanup(owner);clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
        return clean

    def test_aborted_owned_play_uses_real_cleanup_phase_and_one_normal_toggle(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();old=deepcopy(owner.previous);clean=self.cleanup(owner)
            self.assertEqual(old,owner.store.read());self.assertEqual('acknowledged',clean.state['current']['phase'])
            self.assertFalse(m.widgets.tablet);self.assertIsNone(m.actual_name)
            self.assertEqual(['override','restore'],[row['kind'] for row in m.events])
            self.assertEqual(['emote.play.Crying','emote.play.Crying'],[row['controlId'] for row in m.controls.input_requests if row['controlId'].startswith('emote.play.')])
            self.assertNotIn('verb',clean.state['current']['call'])
            for item in clean.state['current']['intents']:
                if item['kind']=='qt':self.assertEqual(dict(verb='cleanup',inputs={}),item['provider']['activations'][-1]['stimulus'])
            before=deepcopy((m.controls.input_requests,m.tablet_inputs));restored=PhoneEmoteCleanup(PhoneEmoteInputs(m.source()))
            restored.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,(m.controls.input_requests,m.tablet_inputs));self.assertIsNotNone(clean.store.read())

    def test_cleanup_of_original_closed_idle_does_not_create_or_acknowledge_normal_input(self):
        m=self.model
        with m.lock.held():
            owner=PhoneEmoteInputs(self.baseline());clean=self.cleanup(owner)
            self.assertIsNone(owner.store.read());self.assertEqual([],m.controls.input_requests)
            self.assertEqual([],m.tablet_inputs);self.assertIsNotNone(clean.state['final'])

    def test_normal_phase_cannot_be_used_as_cleanup(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();clean=PhoneEmoteCleanup(owner);before=deepcopy(m.controls.input_requests)
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.controls.input_requests);self.assertIsNone(clean.store.read())

    def test_original_open_tablet_is_not_adopted_as_owned_cleanup(self):
        m=self.model
        with m.lock.held():
            m.journal.activate(RUN,'b'*32,'baseline',{});source=m.source();source.read()
            with self.assertRaises(NativeUIError):PhoneEmoteCleanup(PhoneEmoteInputs(source))
            self.assertEqual([],m.controls.input_requests);self.assertTrue(m.widgets.tablet)

    def test_unowned_or_foreign_native_override_is_never_cancelled(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();m.start('Crying');before=deepcopy(m.controls.input_requests)
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            self.assertEqual(before,m.controls.input_requests);self.assertIsNotNone((m.root/'phone-emote-cleanup-inputs.json').stat())

    def test_foreign_same_name_native_caller_cannot_be_owned(self):
        m=self.model;m.foreign=True
        with m.lock.held():
            owner=self.playing();before=deepcopy(m.controls.input_requests)
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            self.assertEqual(before,m.controls.input_requests)

    def test_wrong_widget_selection_cannot_cancel_a_different_owned_native_clip(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();m.widgets.active='Dancing';before=deepcopy(m.controls.input_requests)
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            self.assertEqual(before,m.controls.input_requests)

    def test_consumed_cancel_which_ignores_native_restore_never_finishes_or_repeats(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();m.ignore_native=True
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            before=deepcopy((m.controls.input_requests,m.tablet_inputs));m.ignore_native=False
            clean=PhoneEmoteCleanup(PhoneEmoteInputs(m.source()))
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,(m.controls.input_requests,m.tablet_inputs));self.assertIsNone(clean.state['final'])

    def test_lost_cleanup_qt_return_is_observed_without_replaying_the_toggle(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();send=m.controls.send
            def lost(value):
                send(value)
                if value['request']['action']!='observe':raise NativeUIError('Synthetic consumed receipt return lost')
            m.controls.send=lost
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            m.controls.send=send;clean=PhoneEmoteCleanup(PhoneEmoteInputs(m.source()))
            clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(2,len([row for row in m.controls.input_requests if row['controlId']=='emote.play.Crying']))
            self.assertEqual(['override','restore'],[row['kind'] for row in m.events]);self.assertFalse(m.widgets.tablet)

    def test_ignored_cleanup_qt_without_consumed_sequence_is_not_replayed(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();send=m.controls.send
            def ignored(value):
                if value['request']['action']=='observe':send(value)
                else:raise NativeUIError('Synthetic input delivery unknown')
            m.controls.send=ignored
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            m.controls.send=send;before=deepcopy(m.controls.input_requests)
            clean=PhoneEmoteCleanup(PhoneEmoteInputs(m.source()))
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.controls.input_requests);self.assertEqual('issuing',clean.state['current']['phase'])

    def test_lost_normal_input_ack_can_be_observed_in_cleanup_without_normal_replay(self):
        m=self.model
        with m.lock.held():
            owner=PhoneEmoteInputs(self.baseline());send=m.controls.send
            def lost(value):
                send(value)
                if value['request']['action']=='activate' and value['request']['controlId']=='emote.play.Crying':
                    raise NativeUIError('Synthetic normal play return lost')
            m.controls.send=lost
            with self.assertRaises(NativeUIError):owner.act(m.call('play',dict(name='Crying')))
            m.controls.send=send;owner=PhoneEmoteInputs(m.source());old=deepcopy(owner.previous)
            clean=self.cleanup(owner);self.assertEqual(old,owner.store.read());self.assertIsNotNone(clean.state['normalRecovery'])
            self.assertEqual('issuing',owner.state['current']['phase']);self.assertFalse(m.widgets.tablet)

    def test_missing_original_cannot_be_hidden_by_live_owner_or_completed_cleanup(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();clean=self.cleanup(owner)
            references=owner.source.originals.manifest(owner.source.state['manifests'][0])
            owner.source.originals.path(owner.source.originals.expand(references[0])).unlink()
            before=deepcopy(m.controls.input_requests)
            with self.assertRaises(FileNotFoundError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.controls.input_requests);self.assertIsNotNone(clean.store.read())

    def test_changed_original_input_control_or_cleanup_ticket_is_not_adopted(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();clean=self.cleanup(owner);before=deepcopy(m.controls.input_requests)
            m.journal.activate(RUN,'e'*32,'cleanup',{})
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.controls.input_requests);self.assertIsNotNone(clean.store.read())

    def test_lost_sdk_close_return_uses_actual_absence_without_a_second_close(self):
        m=self.model;tablet=m.tablet;lost=[True]
        def factory(*args):
            value=tablet(*args);close=value.close_tablet
            def close_once():
                close()
                if lost[0]:raise NativeUIError('Synthetic consumed SDK close return lost')
            value.close_tablet=close_once;return value
        with m.lock.held(),patch('overte_phone_emote_cleanup.PhoneScriptUI',side_effect=factory):
            owner=self.playing()
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            self.assertFalse(m.widgets.tablet);lost[0]=False
            clean=PhoneEmoteCleanup(PhoneEmoteInputs(m.source()));before=list(m.tablet_inputs)
            clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.tablet_inputs);self.assertIsNotNone(clean.state['final'])

    def test_ignored_sdk_close_keeps_pending_ownership_and_never_retries_delivery(self):
        m=self.model;tablet=m.tablet
        def factory(*args):
            value=tablet(*args)
            value.close_tablet=lambda:m.tablet_inputs.append('tablet.close.ignored')
            value.wait_tablet_absent=lambda:None
            return value
        with m.lock.held(),patch('overte_phone_emote_cleanup.PhoneScriptUI',side_effect=factory):
            owner=self.playing()
            with self.assertRaises(NativeUIError):self.cleanup(owner)
            self.assertTrue(m.widgets.tablet);before=list(m.tablet_inputs)
            clean=PhoneEmoteCleanup(PhoneEmoteInputs(m.source()))
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.tablet_inputs);self.assertEqual('issuing',clean.state['current']['phase'])

    def test_failed_cleanup_intent_commit_dispatches_nothing_and_invalidates_live_owner(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();m.journal.activate(RUN,'a'*32,'cleanup',{});clean=PhoneEmoteCleanup(owner)
            before=deepcopy(m.controls.input_requests);write=clean.store.write
            def ignored(value,previous):
                if unpack(value['payload'])[0]['current']['phase']!='issuing':write(value,previous)
            clean.store.write=ignored
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)
            self.assertEqual(before,m.controls.input_requests);self.assertTrue(clean.failed)
            with self.assertRaises(NativeUIError):clean.cleanup(dict(contractVersion=VERSION,runId=RUN),sleep=m.sleep)

    def test_saved_final_with_missing_native_restore_cannot_replay_success(self):
        m=self.model
        with m.lock.held():
            owner=self.playing();clean=self.cleanup(owner)
            # Truncating the referenced final cannot promote the old initial
            # active native/UI frame into a completed cleanup.
            value=clean.store.read();state=unpack(value['payload'])[0]
            state['final']=deepcopy(state['current']['before']);value['payload']=pack([state])
            clean.store.write(value,clean.previous)
            with self.assertRaises(NativeUIError):PhoneEmoteCleanup(PhoneEmoteInputs(m.source()))
            self.assertIsNotNone(clean.store.read())


if __name__=='__main__':unittest.main()
