"""Composed role ownership over synthetic IO, without device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import secrets
import threading
from unittest.mock import patch

from test_emote_observation import Model as ImageModel
import test_emote_run
from test_emote_run import Model as RunModel
from test_emote_pixels import POLICY
from overte_phone_emote_role import PhoneEmoteRole
from adapters.normal_ui import NativeUIError
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhaseFixtureReader
from test_emote_sources import RUN
from overte_phone_script_history import pack,unpack


class Model(ImageModel,RunModel):
    def world_send(self,key,request):
        from overte_phone_script_history import unpack
        from adapters.normal_feature_state import PrivateFeatureState
        role=self.world.active_role
        # Read the actual outstanding scope index, never inject capture facts.
        pending=PrivateFeatureState(self.root/('phone-emote-'+role+'-role.json')).read()
        self.current_index=unpack(pending['payload'])[0]['pending']['index']
        return super().world_send(key,request)


class EmoteRoleTests(unittest.TestCase):
    owner=test_emote_run.EmoteRunTests.owner
    prepared=test_emote_run.EmoteRunTests.prepared

    def setUp(self):
        with patch('test_emote_run.Model',Model):test_emote_run.EmoteRunTests.setUp(self)

    def test_distinct_roles_measure_baseline_and_reopen_originals_without_reemitting_cached_samples(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            first=PhoneEmoteRole(run,'primary',POLICY);a=first.read(0)
            second=PhoneEmoteRole(run,'actor',POLICY);b=second.read(0)
            self.assertEqual(1,a['sequence']);self.assertEqual(1,b['sequence']);self.assertEqual([],a['resources'])
            self.assertEqual([],a['artifacts']);self.assertFalse(a['state']['override'])
            self.assertGreater(b['capturedEpochMs'],a['capturedEpochMs'])
            calls=deepcopy(m.calls);self.assertEqual(a,first.stored(1)['public']);self.assertEqual(calls,m.calls)
            reopened=PhoneEmoteRole(run,'primary',POLICY);next_value=reopened.read(1)
            self.assertEqual(2,next_value['sequence']);self.assertGreater(next_value['capturedEpochMs'],a['capturedEpochMs'])

    def test_primary_play_retains_actual_image_motion_and_input_source_originals(self):
        m=self.model;run=self.prepared();call=m.call('play',dict(name='Crying'));run.act(call)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            value=role.read(0);row=role.stored(1)
            self.assertTrue(value['state']['override']);self.assertEqual('Crying',value['state']['animation'])
            self.assertEqual(['image','file'],[item['kind'] for item in value['artifacts']])
            self.assertEqual(call['ticket'],row['ticket']);self.assertIsNotNone(row['motion']);self.assertIsNotNone(row['archive'])
            self.assertEqual('ready',role.state['phase']);self.assertIsNotNone(role.state['played'])
            self.assertEqual(0,len(list(m.root.glob('phone-emote-primary-observation-*.json'))))
            self.assertEqual(value,PhoneEmoteRole(run,'primary',POLICY).stored(1)['public'])

    def test_actor_uses_its_own_native_observation_without_primary_pixel_or_motion_adoption(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            actor=PhoneEmoteRole(run,'actor',POLICY)
            value=actor.read(0);row=actor.stored(1)
            self.assertEqual('Crying',value['state']['animation']);self.assertEqual([],value['artifacts'])
            self.assertEqual('actor',row['sourceHeader']['role']);self.assertEqual('primary',row['inputSourceHeader']['role'])
            self.assertFalse(row['image']);self.assertIsNone(row['archive'])


    def test_wait_completion_reports_actual_active_state_until_original_native_restore(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);playing=role.read(0)
        run.act(m.call('wait-complete'))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);pending=role.read(playing['sequence'])
            self.assertTrue(pending['state']['override']);self.assertEqual([],pending['artifacts'])
            self.assertIn('emotePendingRestoreVersion',role.stored(2)['effect'])
        m.epoch+=2100;m.restore()
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);complete=role.read(pending['sequence'])
            self.assertFalse(complete['state']['override']);self.assertEqual('idle',complete['state']['animation'])
            self.assertEqual(['image'],[item['kind'] for item in complete['artifacts']])
            self.assertFalse(complete['state']['restoredBeforeNominalEnd'])

    def test_ignored_native_input_cannot_publish_expected_motion_or_success(self):
        m=self.model;run=self.prepared();m.ignore_native=True;run.act(m.call('play',dict(name='Crying')))
        before=deepcopy(m.controls.input_requests)
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual(0,role.state['sequence']);self.assertEqual('acquiring',role.state['phase'])
            self.assertEqual(before,m.controls.input_requests);self.assertIsNotNone(role.store.read())

    def test_public_resource_artifact_and_current_source_claims_are_recomputed_from_originals(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);role.read(0);row=role.stored(1)
            for fault in ('resources','artifacts','ticket','frame'):
                value=deepcopy(row)
                if fault=='resources':value['public']['resources']=[]
                elif fault=='artifacts':value['public']['artifacts']=[]
                elif fault=='ticket':value['ticket']='e'*32
                else:value['frame']['revision']-=1
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,AssertionError)):role.record(value,1)

    def test_lost_final_parent_commit_recovers_original_transfer_without_replay_or_fresh_result(self):
        m=self.model;run=self.prepared();run.act(m.call('play',dict(name='Crying')))
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with patch.object(role,'commit',side_effect=NativeUIError('Synthetic lost final parent write')),self.assertRaises(NativeUIError):role.read(0)
            self.assertEqual('retaining',role.state['phase']);self.assertEqual(0,role.state['sequence'])
            calls=deepcopy(m.calls);before=deepcopy(m.controls.input_requests)
            recovered=PhoneEmoteRole(run,'primary',POLICY);self.assertIsNone(recovered.recover())
            self.assertEqual('ready',recovered.state['phase']);self.assertEqual(1,recovered.state['sequence'])
            self.assertEqual(calls,m.calls);self.assertEqual(before,m.controls.input_requests)
            self.assertEqual(1,recovered.stored(1)['public']['sequence'])
            value=recovered.read(1);self.assertEqual(2,value['sequence'])

    def test_duplicate_native_frame_cannot_be_wrapped_in_a_new_public_sequence(self):
        run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);role.read(0);row=deepcopy(role.stored(1))
            row.update(sequence=2,index=2);row['public']['sequence']=2
            with self.assertRaises(NativeUIError):role.record(row,2)
            self.assertEqual(1,role.state['sequence'])

    def test_saved_original_and_manifest_callback_interruptions_recover_without_new_native_reads(self):
        for boundary in ('original','manifest'):
            with self.subTest(boundary=boundary):
                # Each independent run has its own private source/evidence root.
                self.setUp();m=self.model
                with patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet):
                    run=self.prepared();run.act(m.call('play',dict(name='Crying')))
                    with run.lock.held():
                        role=PhoneEmoteRole(run,'primary',POLICY);intent=role.originals.intent
                        def interrupted(kind,value):
                            intent(kind,value)
                            if kind==boundary and value['phase']=='saved':raise NativeUIError('Synthetic lost durable archive callback')
                        role.originals.intent=interrupted
                        with self.assertRaises(NativeUIError):role.read(0)
                        calls=deepcopy(m.calls);recovered=PhoneEmoteRole(run,'primary',POLICY);recovered.recover()
                        self.assertEqual(calls,m.calls);self.assertEqual(1,recovered.state['sequence'])
                        self.assertEqual('ready',recovered.state['phase']);self.assertIsNotNone(recovered.stored(1)['archive'])

    def test_missing_transferred_original_blocks_recovery_and_preserves_owner(self):
        run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY)
            with patch.object(role,'commit',side_effect=NativeUIError('Synthetic parent interruption')),self.assertRaises(NativeUIError):role.read(0)
            path=role.originals.path(role.state['pending']['original']);path.unlink()
            recovered=PhoneEmoteRole(run,'primary',POLICY);header=deepcopy(recovered.previous)
            with self.assertRaises(FileNotFoundError):recovered.recover()
            self.assertEqual(header,recovered.store.read());self.assertEqual(0,recovered.state['sequence'])

    def test_stale_actual_delivery_is_rejected_without_redating_retained_measurement(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);commit=role.commit
            def slow(row,manifests):
                commit(row,manifests);m.epoch+=1600;m.clock+=1.6
            with patch.object(role,'commit',side_effect=slow),self.assertRaises(NativeUIError):role.read(0)
            old=role.stored(1)['public'];self.assertLess(old['capturedEpochMs'],m.epoch-1500)
            reopened=PhoneEmoteRole(run,'primary',POLICY);value=reopened.read(1)
            self.assertEqual(2,value['sequence']);self.assertGreater(value['capturedEpochMs'],old['capturedEpochMs'])

    def publication_server(self):
        reader,actor=secrets.token_hex(32),secrets.token_hex(32)
        server=make_server(reader,actor);server.journal=self.model.journal
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def close():
            server.shutdown();server.server_close();thread.join(2);self.assertFalse(thread.is_alive())
        self.addCleanup(close)
        base='http://127.0.0.1:'+str(server.server_port)+'/feature-fixture/v1'
        self.model.client.url=base
        return server,Client(base,reader),Client(base,actor)

    def actor_run(self,client):
        run=self.owner();m=self.model
        run.phase=PhaseFixtureReader(client,RUN,'emotes',epoch_ms=lambda:m.epoch,monotonic=lambda:m.clock)
        return run

    def test_actor_projection_posts_with_its_own_credential_after_releasing_source_lock(self):
        server,reader,actor=self.publication_server();run=self.prepared()
        with run.lock.held():
            primary=PhoneEmoteRole(run,'primary',POLICY);value=primary.read(0)
            with self.assertRaises(NativeUIError):primary.publication()
        run=self.actor_run(actor)
        with run.lock.held():
            run.load();role=PhoneEmoteRole(run,'actor',POLICY);packet=role.publication()
            self.assertGreater(packet['capturedEpochMs'],value['capturedEpochMs'])
            row=role.stored(1);self.assertEqual('actor',row['sourceHeader']['role'])
            self.assertEqual(row['public']['capturedEpochMs'],packet['capturedEpochMs'])
        actor.request('/runs/'+RUN+'/samples',packet)
        received=reader.request('/runs/'+RUN)['entries']
        self.assertEqual(1,len(received));self.assertEqual(packet['facts'],received[0]['facts'])
        self.assertEqual(packet['capturedEpochMs'],received[0]['capturedEpochMs']);self.assertEqual(0,server.internal_errors)
        with self.assertRaises(ValueError):actor.request('/runs/'+RUN+'/samples',packet)
        self.assertEqual(1,len(reader.request('/runs/'+RUN)['entries']))

    def test_reader_credential_cannot_publish_or_force_reuse_of_a_failed_actor_packet(self):
        server,reader,actor=self.publication_server();self.prepared();run=self.actor_run(actor)
        with run.lock.held():
            run.load();role=PhoneEmoteRole(run,'actor',POLICY);packet=role.publication()
        with self.assertRaises(ValueError):reader.request('/runs/'+RUN+'/samples',packet)
        self.assertEqual([],reader.request('/runs/'+RUN)['entries'])
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY);next_packet=role.publication()
        self.assertGreater(next_packet['actorSequence'],packet['actorSequence'])
        self.assertGreater(next_packet['capturedEpochMs'],packet['capturedEpochMs'])
        actor.request('/runs/'+RUN+'/samples',next_packet)
        self.assertEqual(2,reader.request('/runs/'+RUN)['entries'][0]['actorSequence']);self.assertEqual(0,server.internal_errors)

    def test_slow_publication_projection_cannot_hide_old_measurement_behind_frozen_host_clock(self):
        m=self.model;run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'actor',POLICY);stored=role.stored
            def slow(index):
                value=stored(index);m.clock+=2.;return value
            with patch.object(role,'stored',side_effect=slow),self.assertRaises(NativeUIError):role.publication()
            self.assertEqual(1,role.state['sequence']);self.assertEqual('ready',role.state['phase'])

    def test_private_metadata_rejects_false_sequence_aliases_unowned_scope_and_malformed_play_references(self):
        run=self.prepared()
        with run.lock.held():
            role=PhoneEmoteRole(run,'primary',POLICY);role.read(0);header=deepcopy(role.previous)
            for fault in ('last','index','played','scope'):
                value=deepcopy(header);state=unpack(value['payload'])[0]
                if fault=='last':state['last']=True
                elif fault=='index':state['index']=0
                elif fault=='played':state['played']=dict(segment=0,reference=dict(inputTicket='e'*32,frame=dict(revision=True,sha256='e'*64)))
                else:
                    state.update(phase='acquiring',pending=dict(ticket='e'*32,image=False,index=2,scopeId='f'*32,
                        motion=None,original=None,manifest=None))
                value['payload']=pack([state])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):role.decode(value)
            self.assertEqual(header,role.store.read())


if __name__=='__main__':unittest.main()
