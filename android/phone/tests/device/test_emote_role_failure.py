"""Real role/Scope/file retirement over synthetic sources, not device acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_role
from test_emote_pixels import POLICY
from test_emote_sources import RUN
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_emote_observation import PhoneEmoteObservation
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_script_history import unpack


class EmoteRoleFailureTests(unittest.TestCase):
    setUp=test_emote_role.EmoteRoleTests.setUp
    owner=test_emote_role.EmoteRoleTests.owner
    prepared=test_emote_role.EmoteRoleTests.prepared

    def cleaning(self,run):
        self.model.journal.activate(RUN,'a'*32,'cleanup',{})
        with run.lock.held():run.state.update(phase='cleaning-inputs',cleanupTicket='a'*32);run.save()

    def retain(self,value):
        path=self.model.root/'role-failure-retained.json';store=PrivateFeatureState(path)
        store.write(value,store.read());self.assertEqual(value,store.read())

    def test_failed_native_only_baseline_transfers_without_adding_a_public_sequence(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY)
            with patch.object(role.effects,'phase_measure',side_effect=NativeUIError('Synthetic failed source join')),self.assertRaises(NativeUIError):role.read(0)
            header=deepcopy(role.previous)
        self.cleaning(run)
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY);calls=deepcopy(m.calls);value=role.transfer_failed(self.retain)
            self.assertEqual(header,value['header']);self.assertIsNone(value['scope']);self.assertEqual(0,role.state['sequence'])
            self.assertEqual('ready',role.state['phase']);self.assertTrue(all(call=='phase-read' for call in m.calls[len(calls):]))
            self.assertEqual(value,role.failure_archive(value));self.assertEqual(0,role.state['index'])

    def test_complete_scope_and_partial_motion_file_are_retained_without_fresh_sample(self):
        for phase in ('planned','opened','saved'):
            with self.subTest(phase=phase):
                self.setUp();m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
                with run.lock.held():
                    role=PhoneEmoteRole(run,'primary',POLICY);intent=role.motion_intent
                    def interrupt(value):
                        intent(value)
                        if value['phase']==phase:raise NativeUIError('Synthetic lost motion file callback')
                    role.motion_intent=interrupt
                    with self.assertRaises(NativeUIError):role.read(0)
                    header=deepcopy(role.previous)
                self.cleaning(run)
                with run.lock.held():
                    role=PhoneEmoteRole(run,'primary',POLICY);value=role.transfer_failed(self.retain)
                    self.assertEqual(header,value['header']);self.assertEqual('complete',value['scope']['kind'])
                    self.assertEqual(0,role.state['sequence']);self.assertEqual('ready',role.state['phase'])
                    if phase=='opened':self.assertEqual(0,value['motionDiagnostic']['bytes'])
                    else:self.assertIsNone(value['motionDiagnostic'])
                    self.assertEqual([],list(m.root.glob('phone-emote-primary-observation-*.json')))
                    self.assertEqual(value,role.failure_archive(value))

    def test_failed_capture_cleanup_retains_actual_buffer_retirement_before_scope_disappears(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')));m.capture_fault='lost-return'
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with self.assertRaises((NativeUIError,RuntimeError)):role.read(0)
            self.assertEqual(0,role.state['sequence'])
        m.capture_fault=None;self.cleaning(run)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);value=role.transfer_failed(self.retain)
            self.assertEqual('failed',value['scope']['kind']);child=value['scope']['archive']['childRetirement']
            self.assertIsNotNone(child['cleanup']['retirement']);self.assertFalse(child['cleanup']['completeImageRecord'])
            self.assertEqual('ready',role.state['phase']);self.assertEqual(0,role.state['sequence'])
            self.assertEqual(value,role.failure_archive(value))

    def test_lost_retention_can_resume_same_packet_and_cannot_relabel_another_cleanup(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with patch.object(role.effects,'phase_measure',side_effect=NativeUIError('Synthetic lost baseline join')),self.assertRaises(NativeUIError):role.read(0)
        self.cleaning(run)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            def lost(value):self.retain(value);raise NativeUIError('Synthetic lost durable role return')
            with self.assertRaises(NativeUIError):role.transfer_failed(lost)
            original=PrivateFeatureState(m.root/'role-failure-retained.json').read();role=PhoneEmoteRole(run,'primary',POLICY)
            self.assertEqual(original,role.transfer_failed(lambda value:self.assertEqual(original,value),retained=original))
            role=PhoneEmoteRole(run,'primary',POLICY)
            self.assertEqual(original,role.transfer_failed(lambda value:self.assertEqual(original,value),retained=original))
            wrong=deepcopy(original);wrong['cleanup']['activations'][-1]['ticket']='f'*32
            with self.assertRaises(NativeUIError):role.transfer_failed(lambda _value:None,retained=wrong)

    def test_real_run_archives_failed_scope_then_restores_actual_normal_inputs(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')));m.capture_fault='lost-return'
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with self.assertRaises((NativeUIError,RuntimeError)):role.read(0)
            header=deepcopy(role.previous)
        m.capture_fault=None;m.journal.activate(RUN,'a'*32,'cleanup',{})
        result=run.cleanup_inputs(dict(contractVersion=17,runId=RUN));self.assertEqual(1,result['emoteCleanupInputsVersion'])
        self.assertIsNone(m.actual_name);self.assertFalse(m.widgets.tablet)
        with run.lock.held():
            failure=PhoneEmoteFailures(run);rows=failure.originals.restore(failure.state['manifests'],failure.state['count'])
            self.assertEqual(['role','admission'],[row['kind'] for row in rows]);self.assertEqual(header,rows[0]['archive']['header'])
            self.assertEqual(6,rows[0]['emoteFailureRecordVersion']);failure.record(rows[0],1)
            role=PhoneEmoteRole(run,'primary',POLICY);self.assertEqual('ready',role.state['phase']);self.assertEqual(0,role.state['sequence'])
            self.assertIsNotNone(failure.store.read());self.assertEqual([],list(m.root.glob('phone-emote-primary-observation-*.json')))

    def test_role_transfer_recovers_partial_archive_and_lost_final_parent_completion(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved','final'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')));m.capture_fault='lost-return'
                with run.lock.held():
                    role=PhoneEmoteRole(run,'primary',POLICY)
                    with self.assertRaises((NativeUIError,RuntimeError)):role.read(0)
                m.capture_fault=None;self.cleaning(run)
                with run.lock.held():
                    owner=PhoneEmoteFailures(run);intent=owner.originals.intent;save=owner.save
                    def interrupt(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost role archive callback')
                    def final():
                        if owner.state['pending'] is None:raise NativeUIError('Synthetic lost final role ownership commit')
                        return save()
                    owner.originals.intent=interrupt
                    with patch.object(owner,'save',side_effect=final if boundary=='final' else save),self.assertRaises(NativeUIError):owner.collect_roles()
                    recovered=PhoneEmoteFailures(run);frozen=deepcopy(recovered.state['pending']['archive'])
                    recovered.collect_roles();rows=recovered.originals.restore(recovered.state['manifests'],recovered.state['count'])
                    self.assertEqual(1,len(rows));self.assertEqual('role',rows[0]['kind']);self.assertEqual(frozen,rows[0]['archive'])
                    self.assertIsNone(recovered.state['pending']);self.assertEqual(0,PhoneEmoteRole(run,'primary',POLICY).state['sequence'])

    def test_unmaterialized_scope_keeps_failure_without_claiming_native_retirement(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with patch('overte_phone_emote_observation.PhoneEmoteObservation.save',side_effect=NativeUIError('Synthetic ignored first scope journal')),self.assertRaises(NativeUIError):role.read(0)
            self.assertIsNotNone(role.state['pending']['scopeId']);self.assertEqual(0,m.world.counters['capture'])
        self.cleaning(run)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);value=role.transfer_failed(self.retain)
            self.assertEqual(dict(kind='absent',archive=None),value['scope']);self.assertEqual(0,role.state['sequence'])
            self.assertNotIn('retirement',value);self.assertEqual(value,role.failure_archive(value))

    def test_ignored_actual_buffer_release_retains_role_scope_and_native_ownership(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')));m.world.storage.ignore_release=True
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with self.assertRaises(NativeUIError):role.read(0)
            header=deepcopy(role.previous);captures=m.world.counters['capture']
        self.cleaning(run)
        with run.lock.held():
            owner=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):owner.collect_roles()
            self.assertEqual(header,PhoneEmoteRole(run,'primary',POLICY).previous);self.assertEqual(0,owner.state['count'])
            self.assertTrue(m.world.storage.present);self.assertIsNotNone(owner.state['pending'])
            m.world.storage.ignore_release=False;recovered=PhoneEmoteFailures(run);recovered.collect_roles()
            self.assertFalse(m.world.storage.present);self.assertEqual(captures,m.world.counters['capture'])
            self.assertEqual(1,recovered.state['count']);self.assertEqual(0,PhoneEmoteRole(run,'primary',POLICY).state['sequence'])

    def test_partial_motion_mutation_during_retention_blocks_role_and_scope_release(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);intent=role.motion_intent
            def interrupt(value):
                intent(value)
                if value['phase']=='opened':raise NativeUIError('Synthetic lost opened motion file')
            role.motion_intent=interrupt
            with self.assertRaises(NativeUIError):role.read(0)
            header=deepcopy(role.previous);motion=deepcopy(role.state['pending']['motion'])
        self.cleaning(run)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            def changed(value):self.retain(value);(m.root/motion['name']).write_bytes(b'foreign')
            with self.assertRaises(NativeUIError):role.transfer_failed(changed)
            self.assertEqual(header,role.store.read());self.assertIsNotNone(role.state['pending'])
            self.assertTrue((m.root/'phone-emote-primary-observation-1.json').exists())

    def test_forged_scope_binding_diagnostic_and_sequence_cannot_borrow_saved_motion(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);intent=role.motion_intent
            def interrupt(value):
                intent(value)
                if value['phase']=='opened':raise NativeUIError('Synthetic lost motion callback')
            role.motion_intent=interrupt
            with self.assertRaises(NativeUIError):role.read(0)
        self.cleaning(run)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);proof=role.transfer_failed(self.retain)
            for fault in ('scope','binding','diagnostic','sequence'):
                value=deepcopy(proof)
                if fault=='scope':value['scope']['archive']['header']['scopeId']='f'*32
                elif fault=='binding':value['header']['binding']['artifactSha256']='f'*64
                elif fault=='diagnostic':value['motionDiagnostic']['bytes']=1
                else:
                    from overte_phone_script_history import pack
                    state=unpack(value['header']['payload'])[0];state['sequence']=1;value['header']['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):role.failure_archive(value)

    def test_partial_role_original_or_manifest_never_becomes_a_successful_public_sample(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
                with run.lock.held():
                    role=PhoneEmoteRole(run,'primary',POLICY);intent=role.originals.intent
                    def interrupt(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic interrupted role original/index')
                    role.originals.intent=interrupt
                    with self.assertRaises(NativeUIError):role.read(0)
                    self.assertEqual('retaining',role.state['phase']);header=deepcopy(role.previous)
                self.cleaning(run)
                with run.lock.held():
                    role=PhoneEmoteRole(run,'primary',POLICY);value=role.transfer_failed(self.retain)
                    self.assertEqual(header,value['header']);self.assertEqual('complete',value['scope']['kind'])
                    self.assertEqual(0,role.state['sequence']);self.assertEqual([],role.state['manifests']);self.assertEqual('ready',role.state['phase'])
                    self.assertEqual(value,role.failure_archive(value))

    def test_lost_complete_scope_parent_commit_can_cleanup_then_observe_only_new_idle_data(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with patch.object(role,'commit',side_effect=NativeUIError('Synthetic lost final role write')),self.assertRaises(NativeUIError):role.read(0)
            old=role.originals.read(role.state['pending']['original'])['public'];self.assertEqual(0,role.state['sequence'])
            self.assertFalse((m.root/'phone-emote-primary-observation-1.json').exists())
        m.journal.activate(RUN,'a'*32,'cleanup',{});run.cleanup_resources(dict(contractVersion=17,runId=RUN))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);value=role.read(0)
            self.assertEqual(1,value['sequence']);self.assertFalse(value['state']['override']);self.assertEqual('idle',value['state']['animation'])
            self.assertEqual([],value['artifacts']);self.assertEqual([],value['resources']);self.assertGreater(value['capturedEpochMs'],old['capturedEpochMs'])
            failure=PhoneEmoteFailures(run);rows=failure.originals.restore(failure.state['manifests'],failure.state['count'])
            self.assertEqual('role',rows[0]['kind']);self.assertTrue(unpack(rows[0]['archive']['header']['payload'])[0]['pending']['image'])

    def test_retention_rejection_phase_change_and_late_commit_keep_exact_role_responsibility(self):
        for fault in ('reject','phase','slow','commit'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model;run=self.prepared()
                with run.lock.held():
                    role=PhoneEmoteRole(run,'actor',POLICY)
                    with patch.object(role.effects,'phase_measure',side_effect=NativeUIError('Synthetic missing baseline result')),self.assertRaises(NativeUIError):role.read(0)
                    header=deepcopy(role.previous)
                self.cleaning(run)
                with run.lock.held():
                    role=PhoneEmoteRole(run,'actor',POLICY)
                    def retain(value):
                        self.retain(value)
                        if fault=='reject':return False
                        if fault=='phase':m.journal.activate(RUN,'b'*32,'open',{})
                        elif fault=='slow':m.clock+=20.1
                    if fault=='commit':
                        with patch.object(role.store,'write',return_value=None),self.assertRaises(NativeUIError):role.transfer_failed(retain)
                    else:
                        with self.assertRaises(NativeUIError):role.transfer_failed(retain)
                    self.assertEqual(header,role.store.read());self.assertEqual(0,unpack(role.store.read()['payload'])[0]['sequence'])

    def test_unknown_ready_role_version_cannot_skip_collection_validation(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY);role.read(0)
            foreign=deepcopy(role.previous);foreign['emoteRoleVersion']=99;role.store.write(foreign,role.previous)
        self.cleaning(run)
        with run.lock.held():
            owner=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):owner.collect_roles()
            self.assertEqual(foreign,role.store.read());self.assertIsNone(owner.store.read())


if __name__=='__main__':unittest.main()
