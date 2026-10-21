"""Partial-setup cancellation is separate from positive Graphics admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.graphics_lifetime import IOSGraphicsLifetime,GraphicsLifetimePending
from ios.self_tests.test_ios_graphics_lifetime import LifetimeHarness,RestartLifetimeHarness,WebSDK
from ios.self_tests.test_ios_graphics_scene import RUN


class AbortedLifetimeTests(LifetimeHarness,unittest.TestCase):
    def test_failed_setup_before_any_owned_resource_can_audit_and_prove_fresh_three_second_absence(self):
        with self.lock.held():
            owner=self.lifetime();ref=owner.observe_aborted();row=owner.load(ref);original=deepcopy(row['subject'])
            self.assertEqual('abort',row['mode']);self.assertEqual([],row['web']['contexts'])
            self.assertFalse(owner.state['activeProofs']);self.assertEqual('audited',owner.state['phase'])
            self.client.close();value=owner.wait_aborted(original)
            state=IOSGraphicsLifetime.archive(value,path=owner.store.path,run=RUN,fixture_url=self.client.url,
                provider_instance=owner.source.instance,role='primary',stage=0,binding=owner.binding)
            self.assertEqual('released',state['phase']);self.assertGreaterEqual(state['windows'][-1]['elapsedMs'],3000)
            self.assertFalse(state['activeProofs']);self.assertEqual(ref['ordinal'],state['abortProof'])
            with self.assertRaises(NativeUIError):owner.wait_released(original)

    def test_partial_world_resources_without_positive_marker_admission_must_still_drain(self):
        with self.lock.held():
            owner=self.lifetime();scene=self.scene();scene.prepare();original=deepcopy(scene.state['original']['subject'])
            ref=owner.observe_aborted();before=deepcopy(owner.load(ref));self.assertTrue(before['web']['contexts'])
            self.web.held='vulkan-image';self.restore()
            with self.assertRaises(NativeUIError):owner.wait_aborted(original)
            self.assertFalse(owner.state['windows'][-1]['complete']);self.assertFalse(owner.state['activeProofs'])
            self.web.held=None;owner=self.lifetime();owner.wait_aborted(original)
            self.assertEqual('released',owner.state['phase']);self.assertEqual(before,owner.load(ref))
            self.assertEqual(1,before['web']['contexts'][0]['resources']['vulkan-image']['pending'])

    def test_missing_admission_cannot_be_replaced_with_unobserved_empty_success(self):
        with self.lock.held():
            owner=self.lifetime();subject=self.adapter._graphics_subject_observer('owned',read_only=True).read(RUN,require_avatar=True,require_camera=True)
            with self.assertRaises(NativeUIError):owner.wait_aborted(subject)
            with self.assertRaises(NativeUIError):owner.wait_released(subject)
            self.assertIsNone(owner.state['abortProof']);self.assertEqual([],self.web.commands)

    def test_missing_gpu_creation_can_retire_failure_but_cannot_supply_positive_admission(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();original=deepcopy(self.scene().state['original']['subject'])
            def missing(value):
                for row in value['contexts']:row['resources']['vulkan-image']=dict(created=0,retired=0,pending=0)
            self.web.mutate=missing
            with self.assertRaises(GraphicsLifetimePending):owner.observe_active()
            owner=self.lifetime();owner.observe_aborted();self.assertFalse(owner.state['activeProofs'])
            self.assertEqual('abandoned',owner.load(owner.state['records'][0])['mode'])
            self.restore();owner.wait_aborted(original);self.assertEqual('released',owner.state['phase'])
            with self.assertRaises(NativeUIError):owner.observe_active()

    def test_lost_audit_record_adopts_original_without_another_native_request(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare()
            with patch.object(owner,'adopt',side_effect=OSError('Synthetic lost audit adoption')),self.assertRaises(OSError):owner.observe_aborted()
            count=len(self.web.commands);value=owner.record_store(1).read();owner=self.lifetime();ref=owner.observe_aborted()
            self.assertEqual(count,len(self.web.commands));self.assertEqual(digest(value),ref['sha256'])
            self.assertFalse(owner.state['activeProofs']);self.assertEqual('audited',owner.state['phase'])

    def test_lost_passive_audit_keeps_accepted_source_floor_before_a_distinct_fresh_request(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();self.web.lost=True
            with self.assertRaises(NativeUIError):owner.observe_aborted()
            floors=deepcopy(owner.state['cursors']);request=self.web.commands[-1]['commandId'];self.web.lost=False
            owner=self.lifetime();owner.observe_aborted();abandoned=owner.load(owner.state['records'][0])
            self.assertEqual('abandoned',abandoned['mode']);self.assertEqual(floors,abandoned['cursors'])
            self.assertNotEqual(request,self.web.commands[-1]['commandId']);self.assertFalse(owner.state['activeProofs'])

    def test_actual_active_record_with_lost_return_cannot_be_reclassified_as_aborted(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare()
            with patch.object(owner,'adopt',side_effect=OSError('Synthetic lost active adoption')),self.assertRaises(OSError):owner.observe_active()
            owner=self.lifetime()
            with self.assertRaises(NativeUIError):owner.observe_aborted()
            self.assertEqual([1],owner.state['activeProofs']);self.assertIsNone(owner.state['abortProof'])

    def test_abort_audit_cannot_turn_into_a_later_positive_marker_admission(self):
        with self.lock.held():
            owner=self.lifetime();owner.observe_aborted();self.scene().prepare();count=len(self.web.commands)
            with self.assertRaises(NativeUIError):owner.observe_active()
            self.assertEqual(count,len(self.web.commands));self.assertFalse(owner.state['activeProofs'])

    def test_forgotten_native_contexts_cannot_become_empty_abort_cleanup(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();original=deepcopy(self.scene().state['original']['subject'])
            owner.observe_aborted();self.restore();self.web.mutate=lambda value:value.update(contexts=[])
            with self.assertRaises(NativeUIError):owner.wait_aborted(original)
            self.assertFalse(owner.state['windows'][-1]['complete']);self.assertIsNotNone(owner.state['pending'])
            self.web.mutate=None;owner=self.lifetime();owner.wait_aborted(original)
            self.assertEqual('released',owner.state['phase']);self.assertEqual(2,len(owner.state['windows']))

    def test_retired_fixture_without_original_world_restoration_does_not_release_partial_resources(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();original=deepcopy(self.scene().state['original']['subject'])
            owner.observe_aborted();self.client.close()
            with self.assertRaises(NativeUIError):owner.wait_aborted(original)
            self.assertEqual(7,len(self.sdk.scene_rows));self.assertEqual('releasing',self.lifetime().state['phase'])

    def test_incomplete_native_source_cannot_be_admitted_as_an_empty_abort_audit(self):
        with self.lock.held():
            owner=self.lifetime();self.web.mutate=lambda value:value.update(complete=False)
            with self.assertRaises(NativeUIError):owner.observe_aborted()
            self.assertIsNone(owner.state['abortProof']);self.assertEqual([],owner.state['activeProofs'])
            self.assertIsNotNone(owner.state['pending']);self.assertEqual([],owner.state['records'])

    def test_interrupted_abort_quiet_window_starts_again_instead_of_accumulating_elapsed_time(self):
        with self.lock.held():
            owner=self.lifetime();self.scene().prepare();original=deepcopy(self.scene().state['original']['subject'])
            owner.observe_aborted();self.restore()
            with patch.object(owner,'sleep',side_effect=OSError('Synthetic interrupted abort quiet')),self.assertRaises(OSError):owner.wait_aborted(original)
            self.sdk.sleep(10);owner=self.lifetime();started=self.sdk.clock;owner.wait_aborted(original)
            self.assertGreaterEqual(self.sdk.clock-started,3);self.assertEqual(2,len(owner.state['windows']))
            self.assertFalse(owner.state['windows'][0]['complete']);self.assertTrue(owner.state['windows'][1]['complete'])

    def test_legacy_original_owner_and_record_versions_read_without_creating_an_abort_proof(self):
        with self.lock.held():
            owner,original=self.prepare();value=deepcopy(owner.previous);state=unpack(value['payload'])[0]
            state.pop('abortProof');records={}
            for ref in state['records']:
                record=owner.record_store(ref['ordinal']).read();record['iosGraphicsLifetimeRecordVersion']=1
                records[ref['ordinal']]=record;ref['sha256']=digest(record)
            value.update(iosGraphicsLifetimeVersion=1,payload=pack([state]));count=len(self.web.commands)
            decoded=IOSGraphicsLifetime.archive(value,path=owner.store.path,run=RUN,fixture_url=self.client.url,
                provider_instance=owner.source.instance,role='primary',stage=0,binding=owner.binding,records=records)
            self.assertEqual([1],decoded['activeProofs']);self.assertIsNone(decoded['abortProof'])
            self.assertEqual(count,len(self.web.commands))


class AbortedRestartLifetimeTests(RestartLifetimeHarness,unittest.TestCase):
    def test_new_process_partial_audit_requires_actual_old_pid_death_to_restore_old_world(self):
        with self.lock.held():
            old=self.lifetime(0);restart=self.prepare();old.observe_active();original=deepcopy(self.scene().state['original']['subject'])
            restart.act(self.call());self.web=WebSDK(self.sdk);self.web.birth='f'*32
            current=self.lifetime(1);current.observe_aborted();self.restored()
            with self.assertRaises(NativeUIError):current.wait_aborted(original)
            current.wait_aborted(original,restart=restart.state['receipt'])
            self.assertFalse(current.state['activeProofs']);self.assertEqual(42,current.state['original']['subject']['processId'])
            self.assertEqual(43,current.pid);self.assertEqual('ESRCH',current.state['original']['restart']['exit']['errorSymbol'])
            self.assertEqual([1],old.state['activeProofs']);self.assertEqual(['app.stop','app.launch'],self.inputs)


if __name__=='__main__':unittest.main()
