"""A closed original journal can retire responsibility, never create feature success."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.graphics_run_retirement import IOSGraphicsRunRetirement,validate
from ios.self_tests.test_ios_graphics_samples import SamplesHarness
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET


class RetiredSampleTests(SamplesHarness,unittest.TestCase):
    def interrupted(self,*,close=True):
        self.scene().prepare();samples=self.samples();self.gpu.lost=True
        with self.assertRaises(NativeUIError):samples.read(TICKET,self.sdk.host_epoch())
        self.gpu.lost=False
        if close:self.client.close()
        return self.samples(cleanup=True)

    def test_retired_same_ticket_releases_original_responsibility_without_a_new_capture_or_fact(self):
        with self.lock.held():
            samples=self.interrupted();count=sum(q['operation']=='read' for q in self.gpu.commands)
            proof=samples.retire_inactive_run();self.assertIsNone(proof['phase'])
            self.assertFalse(proof['provider']['active']);self.assertFalse(proof['runRetirement']['authorityAfter']['active'])
            self.assertEqual(TICKET,proof['runRetirement']['authorityAfter']['activations'][-1]['ticket'])
            self.assertEqual('abandoned',samples.state['owners'][-1]['phase']);self.assertEqual(0,samples.state['sequence'])
            self.assertEqual(count,sum(q['operation']=='read' for q in self.gpu.commands));self.assertEqual(0,proof['retirement']['source']['callbacks'])
            self.assertEqual('ready',self.archive_index(samples)['phase'])

    def test_active_same_ticket_stays_unresolved_and_cannot_authorize_retirement(self):
        with self.lock.held():
            samples=self.interrupted(close=False);count=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):samples.retire_inactive_run()
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual('reading',samples.state['phase'])
            self.assertIsNone(samples.sample_store(samples.state['owners'][-1]).read())

    def test_retired_resource_provider_without_original_journal_authority_is_insufficient(self):
        with self.lock.held():
            samples=self.interrupted();self.server.journal.retired_phases.pop(RUN);count=len(self.gpu.commands)
            with self.assertRaises(ValueError):samples.retire_inactive_run()
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual('reading',samples.state['phase'])

    def test_changed_gpu_birth_cannot_fill_old_consumer_absence_after_real_fixture_retirement(self):
        with self.lock.held():
            samples=self.interrupted();self.gpu.birth='f'*32
            with self.assertRaises(NativeUIError):samples.retire_inactive_run()
            self.assertEqual('reading',samples.state['phase']);self.assertEqual(1,sum(q['operation']=='read' for q in self.gpu.commands))

    def test_lost_committed_original_is_adopted_without_recapturing_or_releasing_again(self):
        with self.lock.held():
            samples=self.interrupted();target=samples.sample_store(samples.state['owners'][-1]).path;write=PrivateFeatureState.write
            def lost(store,value,previous):
                write(store,value,previous)
                if store.path==target:raise OSError('Synthetic lost committed retired sample return')
            with patch.object(PrivateFeatureState,'write',new=lost),self.assertRaises(OSError):samples.retire_inactive_run()
            original=PrivateFeatureState(target).read();count=len(self.gpu.commands)
            recovered=self.samples(cleanup=True);proof=recovered.retire_inactive_run()
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual(original,PrivateFeatureState(target).read())
            self.assertEqual(proof,unpack(original['payload'])[0]);self.assertEqual('ready',recovered.state['phase'])

    def test_replaced_or_active_authority_cannot_validate_as_retired_originals(self):
        with self.lock.held():
            samples=self.interrupted();proof=samples.retire_inactive_run();original=proof['runRetirement']
            for mode in ('active','foreign'):
                changed=deepcopy(original)
                if mode=='active':changed['authorityAfter'].update(active=True,retiredEpochMs=None)
                else:changed['authorityAfter']['instance']='e'*32
                with self.subTest(mode=mode),self.assertRaises((NativeUIError,ValueError)):
                    validate(changed,run=RUN,url=self.client.url,instance=samples.instance)
            before=deepcopy(original);self.sdk.clock+=100
            self.assertEqual(before,validate(original,run=RUN,url=self.client.url,instance=samples.instance))

    def test_new_closed_authority_form_cannot_be_relabelled_as_an_old_version_two_sample(self):
        from adapters.native_clock_join import digest
        with self.lock.held():
            samples=self.interrupted();samples.retire_inactive_run();row=samples.state['owners'][-1]
            store=samples.sample_store(row);value=store.read();changed=deepcopy(value);changed['iosGraphicsSamplesVersion']=2
            store.write(changed,value);altered=dict(row,sampleSha256=digest(changed))
            with self.assertRaises(NativeUIError):samples.record(altered)

    def test_version_two_complete_originals_remain_readable_before_next_writer_migration(self):
        from adapters.script_feature.history import pack
        from adapters.native_clock_join import digest
        with self.lock.held():
            self.scene().prepare();samples=self.samples();samples.read(TICKET,self.sdk.host_epoch())
            row=samples.state['owners'][-1];store=samples.sample_store(row);value=store.read();old=deepcopy(value)
            old['iosGraphicsSamplesVersion']=2;store.write(old,value)
            index=deepcopy(samples.previous);state=unpack(index['payload'])[0];state['owners'][-1]['sampleSha256']=digest(old)
            index.update(iosGraphicsSamplesVersion=2,payload=pack([state]));samples.store.write(index,samples.previous)
            recovered=self.samples();self.assertEqual(2,recovered.previous['iosGraphicsSamplesVersion'])
            self.assertEqual(unpack(old['payload'])[0],recovered.archive(recovered.state['owners'][-1])[0])
            recovered.read(TICKET,self.sdk.host_epoch());self.assertEqual(3,recovered.previous['iosGraphicsSamplesVersion'])
            self.assertEqual(old,store.read())

    def test_new_fixture_authority_acquisition_has_its_own_clocks_and_no_live_journal_get(self):
        with self.lock.held():
            samples=self.interrupted();source=IOSGraphicsRunRetirement(samples.fixture,monotonic=lambda:self.sdk.clock)
            with patch.object(self.client,'observe',side_effect=AssertionError('Retired journal cannot be read')):
                a=source.read();self.sdk.clock+=.1;b=source.read()
            self.assertLess(a['authorityAfter']['sequence'],b['authorityBefore']['sequence'])
            self.assertNotEqual(a['authorityAfter']['requestId'],b['authorityBefore']['requestId'])
            self.assertLess(a['acquisition']['hostAfterEpochMs'],b['acquisition']['hostBeforeEpochMs'])


if __name__=='__main__':unittest.main()
