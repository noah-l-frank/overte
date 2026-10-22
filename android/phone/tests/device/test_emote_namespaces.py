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

    def cleanup_phase(self):self.model.journal.activate(self.model.source().run,'a'*32,'cleanup',{})

    def cleanup_frames(self):
        m=self.model;m.widgets.tablet=False;m.widgets.page=False;m.widgets.active=''
        primary=m.source();PhoneEmoteNamespaces(primary).assert_acquiring();primary.read()
        actor=m.source('actor');PhoneEmoteNamespaces(actor).assert_acquiring();actor.read()
        return m.source()

    def test_partial_freeze_cleanup_preserves_actual_one_role_originals_without_advancing(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);lease.acknowledge()
            frozen=deepcopy(primary.previous);pending=deepcopy(lease.state['pending']);self.cleanup_phase()
            lease.begin_cleanup();self.assertEqual(0,lease.state['current']);self.assertIsNone(lease.state['pending'])
            self.assertEqual(pending,lease.state['cleanup']['pending'])
            self.assertEqual(frozen,lease.state['cleanup']['headers']['primary'])
            self.assertIsNone(lease.state['cleanup']['pending']['roles']['actor'])
            lease.assert_acquiring();primary.read();restored=PhoneEmoteNamespaces(primary);restored.assert_acquiring()
            self.assertEqual(frozen,restored.state['cleanup']['headers']['primary']);self.assertEqual(0,restored.state['current'])
            with self.assertRaises(NativeUIError):restored.advance()

    def test_cleanup_requires_real_cleanup_phase_and_exact_original_pending_headers(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);lease.acknowledge()
            with self.assertRaises(NativeUIError):lease.begin_cleanup()
            primary.read();self.cleanup_phase();lease=PhoneEmoteNamespaces(primary)
            with self.assertRaises(NativeUIError):lease.begin_cleanup()
            self.assertIsNone(lease.state['cleanup']);self.assertIsNotNone(lease.store.read())

    def test_cleanup_lease_retirement_retains_originals_before_discarding_only_lease_metadata(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();self.cleanup_phase();lease=PhoneEmoteNamespaces(primary);lease.begin_cleanup()
            primary=self.cleanup_frames();lease=PhoneEmoteNamespaces(primary);retained=[]
            result=lease.retire(lambda value:retained.append(value))
            self.assertEqual([result],retained);self.assertIsNone(lease.store.read())
            self.assertIsNotNone(primary.store.read());self.assertTrue((m.root/'phone-emote-inputs.json').exists())
            self.assertEqual(0,unpack(result['header']['payload'])[0]['current'])
            self.assertEqual({'primary','actor'},set(result['roles']))

    def test_absent_actor_or_open_ui_cannot_be_retired_after_partial_cleanup(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();self.cleanup_phase();lease=PhoneEmoteNamespaces(primary);lease.begin_cleanup()
            primary.read();retained=[]
            with self.assertRaises(NativeUIError):lease.retire(lambda value:retained.append(value))
            actor=m.source('actor');actor.read();lease=PhoneEmoteNamespaces(primary)
            with self.assertRaises(NativeUIError):lease.retire(lambda value:retained.append(value))
            self.assertEqual([],retained);self.assertIsNotNone(lease.store.read())

    def test_rejected_or_ignored_retirement_transfer_keeps_lease_and_all_originals(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();self.cleanup_phase();PhoneEmoteNamespaces(primary).begin_cleanup()
            primary=self.cleanup_frames();lease=PhoneEmoteNamespaces(primary)
            with self.assertRaises(NativeUIError):lease.retire(lambda _:False)
            self.assertIsNotNone(lease.store.read())
            with patch.object(lease.store,'discard',return_value=None),self.assertRaises(NativeUIError):lease.retire(lambda _:True)
            self.assertIsNotNone(lease.store.read());self.assertIsNotNone(primary.store.read())

    def test_deleted_frozen_original_or_truncated_current_prefix_cannot_be_hidden_after_cleanup(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();self.cleanup_phase();lease=PhoneEmoteNamespaces(primary);lease.begin_cleanup()
            primary=self.cleanup_frames();lease=PhoneEmoteNamespaces(primary)
            frozen=lease.state['cleanup']['headers']['primary'];state=unpack(frozen['payload'])[0]
            reference=primary.originals.manifest(state['manifests'][0])[0]
            primary.originals.path(primary.originals.expand(reference)).unlink()
            with self.assertRaises(FileNotFoundError):PhoneEmoteNamespaces(primary)
            self.assertIsNotNone(lease.store.read())

    def test_actor_cannot_begin_cleanup_or_retire_the_run_wide_lease(self):
        m=self.model
        with m.lock.held():
            primary,actor,_call=self.frozen();self.cleanup_phase()
            with self.assertRaises(NativeUIError):PhoneEmoteNamespaces(actor).begin_cleanup()
            PhoneEmoteNamespaces(primary).begin_cleanup();self.cleanup_frames();actor=m.source('actor')
            with self.assertRaises(NativeUIError):PhoneEmoteNamespaces(actor).retire(lambda _:True)

    def test_normal_acquisition_and_new_action_cannot_reopen_cleanup_mode(self):
        m=self.model
        with m.lock.held():
            primary,call=self.requested();self.cleanup_phase();lease=PhoneEmoteNamespaces(primary);lease.begin_cleanup()
            m.call('play',dict(name='Crying'))
            with self.assertRaises(NativeUIError):lease.assert_acquiring()
            with self.assertRaises(NativeUIError):lease.request(call)
            self.assertIsNotNone(lease.store.read())

    def test_legacy_v1_freeze_is_read_without_rewrite_and_upgraded_on_explicit_cleanup(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);value=lease.store.read()
            state=unpack(value['payload'])[0];state.pop('cleanup');value.update(emoteNamespacesVersion=1,payload=pack([state]))
            lease.store.write(value,lease.previous);restored=PhoneEmoteNamespaces(primary)
            self.assertEqual(value,restored.store.read());self.assertIsNone(restored.state['cleanup'])
            self.cleanup_phase();restored.begin_cleanup();self.assertEqual(2,restored.store.read()['emoteNamespacesVersion'])

    def test_slow_retention_or_modified_sources_after_retention_cannot_lose_the_lease(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();self.cleanup_phase();PhoneEmoteNamespaces(primary).begin_cleanup()
            primary=self.cleanup_frames();lease=PhoneEmoteNamespaces(primary)
            def late(_):m.clock+=6
            with self.assertRaises(NativeUIError):lease.retire(late)
            self.assertIsNotNone(lease.store.read());lease=PhoneEmoteNamespaces(primary)
            with self.assertRaises(NativeUIError):lease.retire(lambda _:primary.read())
            self.assertIsNotNone(lease.store.read())

    def test_cleanup_after_completed_rollover_keeps_closed_headers_and_uses_current_segment(self):
        m=self.model
        with m.lock.held():
            primary,actor,_call=self.frozen();PhoneEmoteNamespaces(primary).advance();old=deepcopy((primary.previous,actor.previous))
            current=m.source(segment=1);self.cleanup_phase();lease=PhoneEmoteNamespaces(current);lease.begin_cleanup()
            m.widgets.tablet=False;m.widgets.page=False
            PhoneEmoteNamespaces(current).assert_acquiring();current.read()
            actor=m.source('actor',segment=1);PhoneEmoteNamespaces(actor).assert_acquiring();actor.read()
            lease=PhoneEmoteNamespaces(current);retained=[];lease.retire(lambda value:retained.append(value))
            self.assertEqual(1,len(unpack(retained[0]['header']['payload'])[0]['closed']))
            self.assertEqual(old,(m.source().previous,m.source('actor').previous))

    def test_stale_cleanup_frames_and_changed_inputs_prevent_lease_retirement(self):
        m=self.model
        with m.lock.held():
            primary,_actor,_call=self.frozen();self.cleanup_phase();PhoneEmoteNamespaces(primary).begin_cleanup()
            primary=self.cleanup_frames();lease=PhoneEmoteNamespaces(primary);m.epoch+=1600
            with self.assertRaises(NativeUIError):lease.retire(lambda _:True)
            self.assertIsNotNone(lease.store.read())
            store=PhoneEmoteInputs(primary).store;old=store.read();changed=deepcopy(old);changed['runId']='f'*32;store.write(changed,old)
            with self.assertRaises(NativeUIError):PhoneEmoteNamespaces(primary)

    def test_lost_committed_cleanup_release_is_reconstructed_without_a_namespace_advance(self):
        m=self.model
        with m.lock.held():
            primary,_call=self.requested();lease=PhoneEmoteNamespaces(primary);lease.acknowledge();self.cleanup_phase()
            write=lease.store.write
            def lost(value,previous):write(value,previous);raise RuntimeError('Synthetic committed cleanup return lost')
            with patch.object(lease.store,'write',side_effect=lost),self.assertRaises(RuntimeError):lease.begin_cleanup()
            restored=PhoneEmoteNamespaces(primary);restored.begin_cleanup();restored.assert_acquiring()
            self.assertEqual(0,restored.state['current']);self.assertIsNone(restored.state['pending'])
            self.assertIsNotNone(restored.state['cleanup']['pending']['roles']['primary'])
            self.assertIsNone(restored.state['cleanup']['pending']['roles']['actor'])


    def closed_lease(self,*,advance=False):
        m=self.model;primary,_actor,_call=self.frozen()
        if advance:
            PhoneEmoteNamespaces(primary).advance();primary=m.source(segment=1);primary.read()
            actor=m.source('actor',segment=1);actor.read()
        self.cleanup_phase();PhoneEmoteNamespaces(primary).begin_cleanup()
        m.widgets.tablet=False;m.widgets.page=False;m.widgets.active=''
        primary=m.source(segment=1 if advance else 0);primary.read()
        m.source('actor',segment=1 if advance else 0).read()
        return PhoneEmoteNamespaces(primary)

    def test_closed_lease_retains_all_originals_with_no_fresh_native_claim(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease();sources=[lease.source.store.read(),m.source('actor').store.read()]
            m.journal.close(lease.run);m.epoch+=10000;m.clock+=10;retained=[]
            proof=lease.retire_closed(lambda value:retained.append(deepcopy(value)))
            self.assertEqual([proof],retained);self.assertEqual(2,proof['emoteNamespaceRetirementVersion'])
            self.assertEqual(sources,[proof['sources'][0][role] for role in ('primary','actor')])
            self.assertFalse(proof['cleanup']['active']);self.assertIsNone(lease.store.read())
            self.assertIsNotNone(lease.source.store.read());self.assertEqual(proof,lease.retirement_archive(proof))
            fresh=PhoneEmoteNamespaces(m.source());self.assertEqual(proof,fresh.retire_closed(lambda _:None,retained=proof))

    def test_closed_lease_replays_multiple_namespaces_and_rejects_missing_dependencies(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease(advance=True);m.journal.close(lease.run)
            proof=lease.retire_closed(lambda _:None);self.assertEqual(2,len(proof['sources']))
            self.assertEqual(1,unpack(proof['header']['payload'])[0]['current'])
            for field in ('sources','inputs'):
                bad=deepcopy(proof);bad[field].pop(0)
                with self.subTest(field=field),self.assertRaises(NativeUIError):lease.retirement_archive(bad)

    def test_closed_lease_requires_real_closure_and_exact_role_statistics(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease()
            with self.assertRaises(NativeUIError):lease.retire_closed(lambda _:None)
            self.assertIsNotNone(lease.store.read());m.journal.close(lease.run)
            proof=lease.retire_closed(lambda _:None)
            for fault in ('version','provider','statistics','input','source'):
                bad=deepcopy(proof)
                if fault=='version':bad['emoteNamespaceRetirementVersion']=True
                elif fault=='provider':bad['cleanup']['instance']='9'*32
                elif fault=='statistics':bad['roles']['actor']['callSequence']+=1
                elif fault=='input':bad['inputs'][0]=None
                else:bad['sources'][0]['actor']=deepcopy(bad['sources'][0]['primary'])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):lease.retirement_archive(bad)

    def test_closed_lease_handoff_rejection_ignored_delete_and_lost_return_remain_owned(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease();m.journal.close(lease.run);receipts=[]
            with self.assertRaises(NativeUIError):lease.retire_closed(lambda _:False)
            self.assertIsNotNone(lease.store.read())
            with patch.object(lease.store,'discard',return_value=None),self.assertRaises(NativeUIError):
                lease.retire_closed(lambda value:receipts.append(deepcopy(value)))
            self.assertIsNotNone(lease.store.read());discard=lease.store.discard
            def lost(value):discard(value);raise OSError('Synthetic lost lease removal')
            with patch.object(lease.store,'discard',side_effect=lost),self.assertRaises(OSError):
                lease.retire_closed(lambda _:None,retained=receipts[0])
            fresh=PhoneEmoteNamespaces(m.source())
            with self.assertRaises(NativeUIError):fresh.retire_closed(lambda _:None)
            self.assertEqual(receipts[0],fresh.retire_closed(lambda _:None,retained=receipts[0]))

    def test_closed_lease_rejects_new_scopes_foreign_controls_and_slow_retention(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease();m.journal.close(lease.run)
            def late(_):m.clock+=6
            with self.assertRaises(NativeUIError):lease.retire_closed(late)
            self.assertIsNotNone(lease.store.read())
            from adapters.normal_feature_state import PrivateFeatureState
            scope=PrivateFeatureState(m.root/'phone-emote-actor-capture-unknown.json');scope.write({'owned':True},None)
            with self.assertRaises(NativeUIError):lease.retire_closed(lambda _:None)
            scope.discard(scope.read());receipts=[]
            def replace(value):
                receipts.append(value);store=lease.source.store;bad=store.read();bad['runId']='9'*32;store.write(bad,store.read())
            with self.assertRaises(NativeUIError):lease.retire_closed(replace)
            self.assertIsNotNone(lease.store.read());self.assertEqual(1,len(receipts))

    def test_closed_lease_replay_requires_unchanged_original_file_after_removal(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease();m.journal.close(lease.run);proof=lease.retire_closed(lambda _:None)
            fresh=PhoneEmoteNamespaces(m.source())
            path=next(m.root.glob('emote-frame-sources-*.json'));path.write_bytes(b'{}')
            with self.assertRaises(NativeUIError):fresh.retire_closed(lambda _:None,retained=proof)


    def test_closed_retained_lease_replays_files_after_dependency_control_retirement(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease();m.journal.close(lease.run);proof=lease.retire_closed(lambda _:None)
            from adapters.normal_feature_state import PrivateFeatureState
            for name in ('phone-emote-primary-sources.json','phone-emote-actor-sources.json','phone-emote-inputs.json'):
                store=PrivateFeatureState(m.root/name);store.discard(store.read())
            # Historical retry uses the already bound primary context and its
            # parent-retained originals, never opens a replacement live source.
            retry=PhoneEmoteNamespaces(lease.source)
            self.assertEqual(proof,retry.retire_closed(lambda _:None,retained=proof))
            self.assertEqual(proof,retry.retirement_archive(proof))
            with self.assertRaises(NativeUIError):retry.retire_closed(lambda _:None)

    def test_closed_historical_namespace_replay_remains_bounded(self):
        m=self.model
        with m.lock.held():
            lease=self.closed_lease();m.journal.close(lease.run);proof=lease.retire_closed(lambda _:None)
            guard=lease.source.guard
            def slow():m.clock+=6;return guard()
            lease.source.guard=slow
            with self.assertRaises(NativeUIError):lease.retirement_archive(proof)
            self.assertIsNone(lease.started)


if __name__=='__main__':unittest.main()
