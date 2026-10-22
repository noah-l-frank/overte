"""Original actor image retirement after actual controlled phase changes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_role
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_script_history import pack,unpack
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class ImagePhaseRetirementTests(unittest.TestCase):
    setUp=test_emote_role.EmoteRoleTests.setUp
    owner=test_emote_role.EmoteRoleTests.owner
    prepared=test_emote_role.EmoteRoleTests.prepared

    def cancel_ready(self):
        # Real ordinary input and this actor's own playback originals. No image
        # policy override or fabricated expected native/image state is used.
        m=self.model;run=self.prepared();run.act(m.call('sit'))
        with run.lock.held():PhoneEmoteRole(run,'actor',POLICY).read(0)
        run.act(m.call('override',dict(name='Crying')))
        with run.lock.held():PhoneEmoteRole(run,'actor',POLICY).read(0)
        run.act(m.call('cancel'));return run

    def next_phase(self):self.model.journal.activate(RUN,'f'*32,'close',{})

    def retain(self,proof):
        store=PrivateFeatureState(self.model.root/'retained-image-phase.json')
        store.write(dict(testRetainedImagePhaseVersion=1,payload=pack([proof])),store.read())
        self.assertEqual([proof],unpack(store.read()['payload']))

    def failed_capture(self,run,*,ignored=False):
        m=self.model;m.capture_fault='lost-return';m.world.storage.ignore_release=ignored
        role=PhoneEmoteRole(run,'actor',POLICY)
        with self.assertRaises((NativeUIError,RuntimeError)):role.read(0)
        m.capture_fault=None;self.assertTrue(role.state['pending']['image']);self.assertIsNotNone(role.state['pending']['scopeId'])
        return deepcopy(role.previous)

    def test_actual_actor_cancel_image_crosses_phase_and_retains_real_release_before_clear(self):
        m=self.model;run=self.cancel_ready()
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY);fired=False
            def crossed():
                nonlocal fired
                if not fired:fired=True;self.next_phase()
            with patch.object(m,'on_capture',crossed),self.assertRaises(NativeUIError):role.read(0)
            self.assertTrue(fired);header=deepcopy(role.previous);before=m.world.counters['capture'];inputs=deepcopy(m.controls.input_requests)
            role=PhoneEmoteRole(run,'actor',POLICY);proof=role.transfer_phase(self.retain)
            self.assertEqual(2,proof['emoteRolePhaseRetirementVersion']);self.assertEqual(header,proof['header'])
            self.assertEqual('failed',proof['scope']['kind']);child=proof['scope']['archive']['childRetirement']
            self.assertIsNotNone(child['cleanup']['retirement']);self.assertFalse(child['cleanup']['retirement']['memory']['present'])
            self.assertFalse(child['cleanup']['completeImageRecord']);self.assertEqual(2,role.state['sequence'])
            self.assertEqual('ready',role.state['phase']);self.assertEqual(before,m.world.counters['capture']);self.assertEqual(inputs,m.controls.input_requests)
            self.assertEqual([],list(m.root.glob('phone-emote-actor-observation-*.json')))
            self.assertEqual([],list(m.root.glob('phone-emote-actor-capture-*.json')));self.assertEqual(proof,role.phase_archive(proof))

    def test_ignored_actual_buffer_release_keeps_all_owners_until_verified_retry(self):
        m=self.model;run=self.cancel_ready()
        with run.lock.held():
            header=self.failed_capture(run,ignored=True);self.next_phase();before=m.world.counters['capture']
            failure=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):failure.collect_phase()
            self.assertEqual(header,PhoneEmoteRole(run,'actor',POLICY).previous)
            self.assertTrue((m.root/'phone-emote-actor-observation-3.json').exists())
            self.assertTrue((m.world_root/'world-actor.json').exists());self.assertEqual(0,failure.state['count'])
            m.world.storage.ignore_release=False;failure=PhoneEmoteFailures(run);failure.collect_phase()
            rows=failure.originals.restore(failure.state['manifests'],1);proof=rows[0]['archive']
            self.assertEqual(header,proof['header']);self.assertEqual(7,rows[0]['emoteFailureRecordVersion'])
            self.assertFalse(proof['scope']['archive']['childRetirement']['cleanup']['retirement']['memory']['present'])
            self.assertFalse((m.world_root/'world-actor.json').exists());self.assertEqual(before,m.world.counters['capture'])
            self.assertEqual(2,PhoneEmoteRole(run,'actor',POLICY).state['sequence']);failure.record(rows[0],1)

    def test_complete_scope_and_partial_role_original_stay_failed_not_published(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved','commit'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.cancel_ready()
                with run.lock.held():
                    role=PhoneEmoteRole(run,'actor',POLICY);intent=role.originals.intent;commit=role.commit
                    def interrupted(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost actor image record return')
                    def lost_commit(*args):
                        if boundary=='commit':raise NativeUIError('Synthetic lost final actor image commit')
                        return commit(*args)
                    with patch.object(role.originals,'intent',side_effect=interrupted),patch.object(role,'commit',side_effect=lost_commit),self.assertRaises(NativeUIError):role.read(0)
                    header=deepcopy(role.previous);self.next_phase();before=m.world.counters['capture']
                    role=PhoneEmoteRole(run,'actor',POLICY);proof=role.transfer_phase(self.retain)
                    self.assertEqual(header,proof['header']);self.assertEqual('complete',proof['scope']['kind'])
                    self.assertEqual(2,role.state['sequence']);self.assertEqual(2,role.state['index']);self.assertEqual('ready',role.state['phase'])
                    self.assertEqual(before,m.world.counters['capture']);self.assertEqual(proof,role.phase_archive(proof))
                    self.assertIsNone(role.state['lastImage']);self.assertIsNotNone(proof['scope']['archive']['result']['image'])

    def test_failure_owner_partial_archive_and_lost_completion_reuse_same_image_proof(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved','final'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.cancel_ready()
                with run.lock.held():
                    header=self.failed_capture(run);self.next_phase();failure=PhoneEmoteFailures(run);intent=failure.originals.intent;save=failure.save
                    def interrupted(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost image-phase archive write')
                    def final():
                        if boundary=='final' and failure.state['pending'] is None:raise NativeUIError('Synthetic lost image-phase owner completion')
                        return save()
                    with patch.object(failure.originals,'intent',side_effect=interrupted),patch.object(failure,'save',side_effect=final),self.assertRaises(NativeUIError):failure.collect_phase()
                    before=m.world.counters['capture'];failure=PhoneEmoteFailures(run);failure.collect_phase();failure.collect_phase()
                    rows=failure.originals.restore(failure.state['manifests'],1);self.assertEqual(header,rows[0]['archive']['header'])
                    self.assertEqual(1,failure.state['count']);self.assertIsNone(failure.state['pending']);self.assertEqual(before,m.world.counters['capture'])
                    self.assertEqual(2,PhoneEmoteRole(run,'actor',POLICY).state['sequence']);failure.record(rows[0],1)

    def test_same_phase_image_error_cannot_be_relabelled_obsolete_before_parent_intent(self):
        run=self.cancel_ready()
        with run.lock.held():
            header=self.failed_capture(run);failure=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):failure.collect_phase()
            self.assertEqual(header,PhoneEmoteRole(run,'actor',POLICY).previous);self.assertIsNone(failure.store.read())

    def test_foreign_child_retirement_or_header_cannot_release_ready_role(self):
        run=self.cancel_ready()
        with run.lock.held():
            self.failed_capture(run);self.next_phase();role=PhoneEmoteRole(run,'actor',POLICY);proof=role.transfer_phase(self.retain)
            for fault in ('scope','memory','binding','kind','version','legacy'):
                value=deepcopy(proof)
                if fault=='scope':value['scope']['archive']['header']['scopeId']='e'*32
                elif fault=='memory':value['scope']['archive']['childRetirement']['cleanup']['retirement']['memory']['present']=True
                elif fault=='binding':value['header']['binding']['artifactSha256']='f'*64
                elif fault=='kind':value['scope']['kind']='complete'
                elif fault=='legacy':value['emoteRolePhaseRetirementVersion']=1
                else:value['emoteRolePhaseRetirementVersion']=3
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,KeyError)):PhoneEmoteRole(run,'actor',POLICY).transfer_phase(self.retain,retained=value)
            self.assertEqual(2,role.state['sequence'])
            owner=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):owner.record(dict(emoteFailureRecordVersion=5,index=1,kind='phase',archive=proof),1)

    def test_rejected_and_twenty_second_callback_preserve_role_and_child_ownership(self):
        for fault in ('reject','slow'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model;run=self.cancel_ready()
                with run.lock.held():
                    header=self.failed_capture(run);self.next_phase();role=PhoneEmoteRole(run,'actor',POLICY)
                    def retain(proof):
                        self.retain(proof)
                        if fault=='reject':return False
                        m.clock+=21
                    with self.assertRaises(NativeUIError):role.transfer_phase(retain)
                    self.assertEqual(header,role.store.read());self.assertEqual(2,role.state['sequence'])
                    self.assertTrue((m.root/'phone-emote-actor-observation-3.json').exists())


if __name__=='__main__':unittest.main()
