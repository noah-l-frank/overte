"""Namespace lease counterexamples over actual stored synthetic source packets."""
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
from overte_phone_emote_inputs import PhoneEmoteInputs
from overte_phone_emote_namespaces import PhoneEmoteNamespaces
from overte_phone_script_history import pack,unpack
from test_emote_background_effects import Model


class EmoteNamespacesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-namespaces-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name));self.model.use_included_source()
        mock=patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=self.model.tablet)
        mock.start();self.addCleanup(mock.stop)

    def requested(self):
        m=self.model;opened=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(opened)
        call=m.call('play',dict(name='Crying'));owner.source.read()
        lease=PhoneEmoteNamespaces(owner.source);lease.request(call)
        return owner.source,call

    def frozen(self):
        m=self.model;primary,call=self.requested()
        main=PhoneEmoteNamespaces(primary);main.acknowledge()
        actor=m.source('actor');actor.read();secondary=PhoneEmoteNamespaces(actor);secondary.acknowledge()
        return primary,actor,call

    def test_both_independent_originals_freeze_before_an_atomic_bounded_advance(self):
        m=self.model
        with m.lock.held():
            primary,actor,call=self.frozen();before=deepcopy((primary.previous,actor.previous))
            lease=PhoneEmoteNamespaces(primary);self.assertEqual(1,lease.advance())
            self.assertEqual(call,lease.state['closed'][0]['call']);self.assertIsNone(lease.state['pending'])
            self.assertLess(lease.store.path.stat().st_size,65536)
            self.assertEqual(before,(primary.store.read(),actor.store.read()))
            with self.assertRaises(NativeUIError):PhoneEmoteNamespaces(primary).assert_acquiring()
            later=m.source(segment=1);later.read();PhoneEmoteNamespaces(later).assert_acquiring()
            self.assertEqual(1,PhoneEmoteNamespaces(later).state['current'])

    def test_one_role_or_frozen_role_read_permission_cannot_substitute_for_both(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);lease.acknowledge()
            with self.assertRaises(NativeUIError):lease.assert_acquiring()
            with self.assertRaises(NativeUIError):lease.advance()
            self.assertEqual(0,lease.state['current']);self.assertIsNone(lease.state['pending']['roles']['actor'])

    def test_cached_inactive_pose_cannot_acknowledge_an_actual_active_source(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();actor=m.source('actor');actor.read();lease=PhoneEmoteNamespaces(actor)
            m.start('Waving');actor.read();actor.frames[-1]['group']['native']['animation']['overrideActive']=False
            with self.assertRaises(NativeUIError):lease.acknowledge()
            self.assertIsNone(lease.state['pending']['roles']['actor'])

    def test_stale_actual_frame_never_becomes_fresh_by_reading_new_provider_metadata(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);m.epoch+=1600
            with self.assertRaises(NativeUIError):lease.acknowledge()
            self.assertIsNone(lease.state['pending']['roles']['primary'])

    def test_saved_native_statistics_are_recomputed_from_originals_before_advance(self):
        m=self.model
        with m.lock.held():
            primary,actor,_call=self.frozen();lease=PhoneEmoteNamespaces(primary)
            value=lease.store.read();state=unpack(value['payload'])[0]
            for role in ('primary','actor'):state['pending']['roles'][role]['callSequence']+=1
            value['payload']=pack([state]);lease.store.write(value,lease.previous)
            current=PhoneEmoteNamespaces(primary)
            with self.assertRaises(NativeUIError):current.advance()
            self.assertEqual(0,current.state['current'])

    def test_read_after_freeze_blocks_advance_without_dropping_ownership(self):
        m=self.model
        with m.lock.held():
            primary,actor,_call=self.frozen();actor.read();lease=PhoneEmoteNamespaces(primary)
            with self.assertRaises(NativeUIError):lease.advance()
            self.assertIsNotNone(lease.store.read());self.assertEqual(0,lease.state['current'])

    def test_old_ticket_cannot_acknowledge_a_later_requested_input(self):
        m=self.model
        with m.lock.held():
            opened=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(opened)
            actor=m.source('actor');actor.read()
            call=m.call('play',dict(name='Crying'));owner.source.read();PhoneEmoteNamespaces(owner.source).request(call)
            lease=PhoneEmoteNamespaces(actor)
            with self.assertRaises(NativeUIError):lease.acknowledge()
            self.assertIsNone(lease.state['pending']['roles']['actor'])

    def test_closed_namespace_header_mutation_is_rejected_after_advance(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();PhoneEmoteNamespaces(primary).advance()
            later=m.source(segment=1);later.read()
            changed=deepcopy(primary.previous);changed['artifactRoot']='foreign'
            primary.store.write(changed,primary.previous)
            with self.assertRaises(NativeUIError):PhoneEmoteNamespaces(later)

    def test_open_scope_ownership_blocks_freeze_without_claiming_or_deleting_it(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();path=m.root/'phone-emote-actor-observation-99.json'
            path.write_text('not an adoptable completed observation');path.chmod(0o600)
            actor=m.source('actor');actor.read();lease=PhoneEmoteNamespaces(actor)
            with self.assertRaises(NativeUIError):lease.acknowledge()
            self.assertTrue(path.exists());self.assertIsNone(lease.state['pending']['roles']['actor'])

    def test_missing_frozen_original_remains_owned_without_an_advance(self):
        m=self.model
        with m.lock.held():
            primary,actor,_call=self.frozen()
            manifest=actor.originals.manifest(actor.state['manifests'][-1]);reference=actor.originals.expand(manifest[-1])
            actor.originals.path(reference).unlink();lease=PhoneEmoteNamespaces(primary)
            with self.assertRaises(FileNotFoundError):lease.advance()
            self.assertIsNotNone(lease.store.read());self.assertEqual(0,lease.state['current'])

    def test_ignored_advance_commit_cannot_report_a_new_namespace(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();lease=PhoneEmoteNamespaces(primary)
            with patch.object(lease.store,'write',return_value=None),self.assertRaises(NativeUIError):lease.advance()
            restored=PhoneEmoteNamespaces(primary)
            self.assertEqual(0,restored.state['current']);self.assertIsNotNone(restored.state['pending'])
            self.assertEqual(1,restored.advance())

    def test_lost_committed_advance_return_is_observed_without_a_second_transition(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();lease=PhoneEmoteNamespaces(primary);write=lease.store.write
            def lost(value,previous):write(value,previous);raise RuntimeError('Synthetic lost committed return')
            with patch.object(lease.store,'write',side_effect=lost),self.assertRaises(RuntimeError):lease.advance()
            restored=PhoneEmoteNamespaces(primary);self.assertEqual(1,restored.state['current'])
            self.assertEqual(1,len(restored.state['closed']))
            with self.assertRaises(NativeUIError):restored.advance()

    def test_slow_final_guard_and_provider_phase_change_cannot_acknowledge_freeze(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);guard=primary.guard
            def slow():m.clock+=6;return guard()
            primary.guard=slow
            with self.assertRaises(NativeUIError):lease.acknowledge()
            self.assertIsNone(lease.state['pending']['roles']['primary']);self.assertIsNone(lease.started)
            primary.guard=guard;m.call('close')
            with self.assertRaises(NativeUIError):lease.acknowledge()

    def test_abort_and_override_are_not_namespace_openers(self):
        m=self.model
        with m.lock.held():
            opened=m.call('open');owner=PhoneEmoteInputs(m.source());owner.act(opened)
            for verb,inputs in (('cancel',{}),('override',dict(name='Crying'))):
                call=m.call(verb,inputs);owner.source.read();lease=PhoneEmoteNamespaces(owner.source)
                with self.subTest(verb=verb),self.assertRaises(NativeUIError):lease.request(call)
                self.assertIsNone(lease.store.read())


if __name__=='__main__':unittest.main()
