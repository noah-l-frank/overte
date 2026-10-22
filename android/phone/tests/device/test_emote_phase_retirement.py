"""Actual crossed-phase originals over synthetic producers; no device claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

import test_emote_role
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_emote_role import PhoneEmoteRole
from overte_phone_emote_failures import PhoneEmoteFailures
from overte_phone_emote_sources import EmotePhaseChanged
from overte_phone_script_history import pack,unpack
from test_emote_pixels import POLICY
from test_emote_sources import RUN


class PhaseRetirementTests(unittest.TestCase):
    setUp=test_emote_role.EmoteRoleTests.setUp
    owner=test_emote_role.EmoteRoleTests.owner
    prepared=test_emote_role.EmoteRoleTests.prepared

    def raced(self,run):
        m=self.model;role=PhoneEmoteRole(run,'actor',POLICY);send=m.native_send;fired=False
        def cross(request):
            nonlocal fired
            result=send(request)
            if not fired:fired=True;m.journal.activate(RUN,'f'*32,'open',{})
            return result
        with patch.object(m,'native_send',side_effect=cross),self.assertRaises(EmotePhaseChanged):role.read(0)
        self.assertTrue(fired);self.assertEqual('acquiring',role.state['phase']);self.assertEqual('ready',role.source.state['phase'])
        last=role.source.frames[-1];self.assertNotEqual(last['phaseBefore']['activations'][-1]['ticket'],last['phaseAfter']['activations'][-1]['ticket'])
        self.assertFalse(role.state['pending']['image']);self.assertIsNone(role.state['pending']['scopeId'])
        return deepcopy(role.previous)

    def retain(self,proof):
        store=PrivateFeatureState(self.model.root/'retained-phase.json');store.write(proof,store.read());self.assertEqual(proof,store.read())

    def test_real_crossed_source_retires_without_inputs_captures_or_public_sequence(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            header=self.raced(run);role=PhoneEmoteRole(run,'actor',POLICY);calls=deepcopy(m.calls)
            proof=role.transfer_phase(self.retain,archive_version=1);self.assertEqual(header,proof['header']);self.assertEqual(1,proof['emoteRolePhaseRetirementVersion'])
            self.assertEqual('ready',role.state['phase']);self.assertEqual(0,role.state['sequence']);self.assertEqual(0,role.state['index'])
            self.assertEqual([],m.controls.input_requests);self.assertIsNone(proof['scope']);self.assertNotIn('public',proof)
            self.assertTrue(all(call=='phase-read' for call in m.calls[len(calls):]));self.assertEqual(proof,role.phase_archive(proof))
            self.assertEqual([],list(m.root.glob('phone-emote-actor-observation-*.json')))

    def test_enclosing_owner_retains_phase_original_before_clear_and_new_phase_needs_new_measurement(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            header=self.raced(run);failure=PhoneEmoteFailures(run);failure.collect_phase()
            rows=failure.originals.restore(failure.state['manifests'],1);self.assertEqual('phase',rows[0]['kind']);self.assertEqual(7,rows[0]['emoteFailureRecordVersion'])
            self.assertEqual(header,rows[0]['archive']['header']);failure.record(rows[0],1);self.assertEqual(0,PhoneEmoteRole(run,'actor',POLICY).state['sequence'])
        run.act(m.call('open'))
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY);value=role.read(0)
            self.assertEqual(1,value['sequence']);self.assertTrue(value['state']['panel']);self.assertGreater(role.source.frames[-1]['group']['native']['sequence'],role.source.frames[0]['group']['native']['sequence'])
            self.assertEqual(header,rows[0]['archive']['header'])

    def test_lost_retention_and_later_cleanup_reuse_identical_historical_packet(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            self.raced(run);role=PhoneEmoteRole(run,'actor',POLICY)
            def lost(proof):self.retain(proof);raise OSError('Synthetic lost phase retention return')
            with self.assertRaises(OSError):role.transfer_phase(lost)
            proof=PrivateFeatureState(m.root/'retained-phase.json').read();calls=deepcopy(m.calls)
            m.journal.activate(RUN,'a'*32,'cleanup',{});m.sleep(2)
            role=PhoneEmoteRole(run,'actor',POLICY);self.assertEqual(proof,role.transfer_phase(self.retain,retained=proof))
            self.assertEqual(proof,PhoneEmoteRole(run,'actor',POLICY).transfer_phase(self.retain,retained=proof))
            self.assertTrue(all(call=='phase-read' for call in m.calls[len(calls):]));self.assertEqual(0,role.state['sequence'])

    def test_partial_original_index_and_lost_parent_completion_resume_exact_owned_bytes(self):
        for boundary in ('original-planned','original-opened','original-saved','manifest-planned','manifest-saved','final'):
            with self.subTest(boundary=boundary):
                self.setUp();m=self.model;run=self.prepared()
                with run.lock.held():
                    header=self.raced(run);failure=PhoneEmoteFailures(run);intent=failure.originals.intent;save=failure.save
                    def interrupted(kind,value):
                        intent(kind,value)
                        if kind+'-'+value['phase']==boundary:raise NativeUIError('Synthetic lost phase original commit')
                    def final():
                        if boundary=='final' and failure.state['pending'] is None:raise NativeUIError('Synthetic lost phase owner completion')
                        return save()
                    with patch.object(failure.originals,'intent',side_effect=interrupted),patch.object(failure,'save',side_effect=final),self.assertRaises(NativeUIError):failure.collect_phase()
                    calls=deepcopy(m.calls);recovered=PhoneEmoteFailures(run);recovered.collect_phase();recovered.collect_phase()
                    self.assertEqual(1,recovered.state['count']);self.assertIsNone(recovered.state['pending'])
                    rows=recovered.originals.restore(recovered.state['manifests'],1);self.assertEqual(header,rows[0]['archive']['header'])
                    self.assertTrue(all(call=='phase-read' for call in m.calls[len(calls):]));self.assertEqual(0,PhoneEmoteRole(run,'actor',POLICY).state['sequence'])

    def test_same_phase_failed_read_cannot_be_relabelled_as_obsolete_or_claim_parent_intent(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY)
            with patch.object(role.effects,'phase_measure',side_effect=NativeUIError('Synthetic same-phase failed join')),self.assertRaises(NativeUIError):role.read(0)
            header=deepcopy(role.previous);failure=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):failure.collect_phase()
            self.assertEqual(header,role.store.read());self.assertIsNone(failure.store.read())

    def test_rejected_slow_or_ignored_retention_cannot_clear_actor_ownership(self):
        for fault in ('reject','slow','clear'):
            with self.subTest(fault=fault):
                self.setUp();m=self.model;run=self.prepared()
                with run.lock.held():
                    header=self.raced(run);role=PhoneEmoteRole(run,'actor',POLICY)
                    def retain(proof):
                        self.retain(proof)
                        if fault=='reject':return False
                        if fault=='slow':m.clock+=6
                    if fault=='clear':
                        with patch.object(role.store,'write',return_value=None),self.assertRaises(NativeUIError):role.transfer_phase(retain,archive_version=1)
                    else:
                        with self.assertRaises(NativeUIError):role.transfer_phase(retain,archive_version=1)
                    self.assertEqual(header,role.store.read())

    def test_unknown_capture_or_world_owner_blocks_resource_free_phase_transfer(self):
        for kind in ('observation','capture','world'):
            with self.subTest(kind=kind):
                self.setUp();m=self.model;run=self.prepared()
                with run.lock.held():
                    header=self.raced(run);role=PhoneEmoteRole(run,'actor',POLICY)
                    if kind=='world':
                        store=m._world_render_capture('synthetic-selector',read_only=True,role='actor',require_frame_view=True).owner.store
                    else:store=PrivateFeatureState(m.root/('phone-emote-actor-'+kind+'-1.json'))
                    store.write(dict(unaccounted=True),None)
                    with self.assertRaises(NativeUIError):role.transfer_phase(self.retain,archive_version=1)
                    self.assertEqual(header,role.store.read());self.assertEqual(dict(unaccounted=True),store.read())

    def test_forged_image_or_scope_intent_cannot_use_phase_transfer(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            original=self.raced(run)
            for fault in ('image','scope'):
                header=deepcopy(original);state=unpack(header['payload'])[0];state['pending']['image']=True
                if fault=='scope':state['pending']['scopeId']='e'*32
                header['payload']=pack([state]);store=PrivateFeatureState(m.root/'phone-emote-actor-role.json');store.write(header,store.read())
                role=PhoneEmoteRole(run,'actor',POLICY);failure=PhoneEmoteFailures(run)
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):role.transfer_phase(self.retain,archive_version=1)
                self.assertEqual(header,role.store.read());self.assertIsNone(failure.store.read())

    def test_changed_role_namespace_cannot_claim_a_new_enclosing_phase_intent(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            original=self.raced(run);header=deepcopy(original);state=unpack(header['payload'])[0]
            state['segment']=1;header['payload']=pack([state]);store=PrivateFeatureState(m.root/'phone-emote-actor-role.json')
            store.write(header,store.read());owner=PhoneEmoteFailures(run)
            with self.assertRaises(NativeUIError):owner.collect_phase()
            self.assertEqual(header,store.read());self.assertIsNone(owner.store.read())

    def test_old_v5_pending_phase_v1_keeps_original_bytes_during_explicit_v6_completion(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            header=self.raced(run)
            with patch('overte_phone_emote_failures.VERSION',5):
                owner=PhoneEmoteFailures(run);save=owner.save
                def lost():
                    if owner.state['pending'] is None:raise NativeUIError('Synthetic lost old v5 phase completion')
                    return save()
                with patch.object(owner,'save',side_effect=lost),self.assertRaises(NativeUIError):owner.collect_phase()
            old=owner.store.read();self.assertEqual(5,old['emoteFailureOwnerVersion'])
            pending=unpack(old['payload'])[0]['pending'];self.assertEqual(1,pending['archive']['emoteRolePhaseRetirementVersion'])
            descriptor=pending['original'];path=owner.originals.path(descriptor);raw=path.read_bytes();inode=path.stat().st_ino
            owner=PhoneEmoteFailures(run);self.assertEqual(old,owner.previous);owner.collect_phase()
            self.assertEqual(7,owner.previous['emoteFailureOwnerVersion']);self.assertEqual(1,owner.state['count'])
            rows=owner.originals.restore(owner.state['manifests'],1)
            self.assertEqual(5,rows[0]['emoteFailureRecordVersion']);self.assertEqual(header,rows[0]['archive']['header'])
            self.assertEqual(raw,path.read_bytes());self.assertEqual(inode,path.stat().st_ino);owner.record(rows[0],1)

    def test_replaced_fixture_birth_is_rejected_before_new_parent_intent(self):
        m=self.model;run=self.prepared()
        with run.lock.held():header=self.raced(run)
        run=self.owner() # Fresh phase reader has no in-memory provider cursor.
        with run.lock.held():
            run.load();m.journal.phase_instance='e'*32;owner=PhoneEmoteFailures(run)
            with self.assertRaises((NativeUIError,ValueError)):owner.collect_phase()
            self.assertIsNone(owner.store.read());self.assertEqual(header,PhoneEmoteRole(run,'actor',POLICY).previous)

    def test_boolean_archive_version_cannot_adopt_a_retained_integer_version(self):
        run=self.prepared()
        with run.lock.held():
            self.raced(run);role=PhoneEmoteRole(run,'actor',POLICY);proof=role.transfer_phase(self.retain,archive_version=1)
            with self.assertRaises(NativeUIError):role.transfer_phase(self.retain,retained=proof,archive_version=True)

    def test_changed_or_foreign_retained_proof_cannot_reuse_ready_role(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            self.raced(run);role=PhoneEmoteRole(run,'actor',POLICY);proof=role.transfer_phase(self.retain,archive_version=1)
            for fault in ('version','role','binding','ticket','segment','kind'):
                value=deepcopy(proof)
                if fault=='version':value['emoteRolePhaseRetirementVersion']=3
                elif fault=='role':value['header']['role']='primary'
                elif fault=='binding':value['header']['binding']['processIdentity']='32:foreign'
                elif fault=='segment':value['segment']=1
                elif fault=='kind':value['emoteRoleFailureArchiveVersion']=value.pop('emoteRolePhaseRetirementVersion')
                else:value['phase']['activations'][-1]['ticket']=unpack(value['header']['payload'])[0]['pending']['ticket']
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):PhoneEmoteRole(run,'actor',POLICY).transfer_phase(self.retain,retained=value)
            self.assertEqual(0,role.state['sequence'])


if __name__=='__main__':unittest.main()
