"""Actual peer codecs and immutable anchor files; native producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters import emote_peer_continuation as continuation
from ios.adapters.emote_observation import IOSEmoteObservationDecoder,ORIGINAL_FIELDS
from ios.adapters.emote_peer import movement
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObservationDecoder,IOSEmoteRootedObserver
from ios.self_tests import test_ios_emote_peer as fixture
from ios.self_tests.test_ios_emote_sources import RUN,phase


def late_pair():
    """Two fresh producer cuts born after the earlier receive ring has expired."""
    rows=[]
    for sequence in range(9,43):
        row=deepcopy(fixture.acquisition(True)['receive']['source']['records'][0])
        row.update(receiveSequence=sequence,capturedEpochMs=22000+sequence*10 if sequence<=40 else 24500+sequence-40)
        for joint in row['joints']:joint['translation']=[sequence*.01,0,0]
        rows.append(row)
    cuts=[]
    for index,(start,base,end,total) in enumerate(((23000,23000,24000,40),(25000,25000,26000,42)),3):
        value=fixture.acquisition(True)
        value['world'].update(sequence=index,requestId='ios-'+format(100+index,'032x'))
        for key in ('clockBefore','clockAfter'):
            value['world'][key].update(epochMs=base,monotonicMs=base-18000)
        value['world']['source']['scriptOriginal'].update(requestedEpochMs=base,capturedEpochMs=base)
        renderer=value['renderers'];renderer.update(sequence=index,requestId='ios-'+format(200+index,'032x'))
        for key in ('clockBefore','clockAfter'):renderer[key].update(epochMs=base,monotonicMs=base-18000)
        for avatar in renderer['source']['avatars']:
            if avatar['rigPose']:avatar['rigPose'].update(capturedEpochMs=base,evaluationSequence=100+index)
            if avatar['externalPose']:
                avatar['externalPose'].update(capturedEpochMs=base,evaluationSequence=10+index)
                avatar['externalPose']['joints'][0][4]=index*.1
        receive=value['receive'];receive.update(sequence=index,commandId='ios-'+format(300+index,'032x'),
            requestedEpochMs=base,capturedEpochMs=base)
        receive['source'].update(receiveSequence=total,droppedRecords=total-32,
            records=deepcopy([row for row in rows if total-32<row['receiveSequence']<=total]))
        value['clockJoin'].update(hostBeforeEpochMs=95000+(index-3)*2000,hostAfterEpochMs=96000+(index-3)*2000,
            hostBeforeMonotonic=6+(index-3)*2,hostAfterMonotonic=7+(index-3)*2,
            nativeBefore=fixture.native(start,index*2-1),nativeAfter=fixture.native(end,index*2),
            sourceTimes=[dict(source='receive',field='capturedEpochMs',epochMs=base)])
        fixture.reseal(value);cuts.append(value)
    return cuts


class PeerContinuationTests(unittest.TestCase):
    def test_expired_initial_ring_requires_original_anchor_and_new_strict_motion(self):
        primary,initial,anchor=fixture.setup();before,after=late_pair()
        movement(primary,fixture.PRIMARY,initial,anchor,fixture.ACTOR)
        with self.assertRaises(NativeUIError):movement(primary,fixture.PRIMARY,initial,after,fixture.ACTOR)
        continuation.peer_follows(anchor,before,fixture.ACTOR)
        actual=movement(primary,fixture.PRIMARY,before,after,fixture.ACTOR)
        self.assertEqual([41,42],actual['receivedSequences'])

    def test_later_cut_still_rejects_frozen_pose_missing_packets_and_wrong_mixer(self):
        primary,_,_=fixture.setup()
        for fault in ('pose','packets','mixer','layout','receive-instance'):
            before,after=late_pair()
            if fault=='pose':after['renderers']['source']['avatars'][1]['externalPose']['joints']=deepcopy(before['renderers']['source']['avatars'][1]['externalPose']['joints'])
            elif fault=='packets':
                after['receive']['source'].update(receiveSequence=40,droppedRecords=8,records=deepcopy(before['receive']['source']['records']))
            elif fault=='mixer':after['receive']['source']['records'][-1]['mixerSha256']='f'*64
            elif fault=='layout':after['renderers']['source']['avatars'][1]['jointIndices']['Hips']=3
            else:after['receive']['source']['instance']='f'*32
            fixture.reseal(after)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):movement(primary,fixture.PRIMARY,before,after,fixture.ACTOR)

    def test_bridge_rejects_foreign_renderer_receiver_domain_and_regressed_clock(self):
        _,_,anchor=fixture.setup()
        for fault in ('renderer','clock','domain','receive'):
            before,_=late_pair()
            if fault=='renderer':before['renderers']['source']['avatars'][1]['externalPose']['instance']='f'*32
            elif fault=='clock':before['clockJoin']['hostBeforeMonotonic']=1
            elif fault=='domain':before['world']['source']['domain']['avatarMixerSha256']='f'*64
            else:before['receive']['source']['instance']='f'*32
            fixture.reseal(before)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):continuation.peer_follows(anchor,before,fixture.ACTOR)

    def test_phase_prefix_cannot_change_birth_input_or_fixture(self):
        before=phase(1,90000);after=phase(2,91000);continuation.phase_follows(before,after)
        for field in ('instance','createdEpochMs','activations','capturedEpochMs','requestId'):
            bad=deepcopy(after)
            if field=='instance':bad[field]='e'*32
            elif field=='createdEpochMs':bad[field]-=1
            elif field=='activations':bad[field][0]['ticket']='e'*32
            elif field=='capturedEpochMs':bad[field]=89999
            else:bad[field]=before[field]
            with self.subTest(field=field),self.assertRaises(NativeUIError):continuation.phase_follows(before,bad)

    def test_a_retained_receive_counter_cannot_be_rewritten_across_bridge_cuts(self):
        before,after=late_pair();continuation.peer_follows(before,after,fixture.ACTOR)
        after['receive']['source']['records'][0]['recordSha256']='e'*64
        fixture.reseal(after)
        with self.assertRaises(NativeUIError):continuation.peer_follows(before,after,fixture.ACTOR)

    def test_actual_anchor_hash_scope_and_acyclic_literal_original_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700);calls=[]
            decoder=SimpleNamespace(root=root,run=RUN,role='actor',binding=fixture.ACTOR,primary_binding=fixture.PRIMARY,
                phase_instance='3'*32,derive=lambda value:calls.append(deepcopy(value)))
            original=dict(iosEmoteObservationOriginalVersion=1,sequence=2)
            raw=dict(iosEmoteObserverRecordVersion=1,runId=RUN,role='actor',binding=fixture.ACTOR,primaryBinding=fixture.PRIMARY,
                fixtureUrl='http://127.0.0.1:1/runs/'+RUN+'/',phaseInstance='3'*32,payload=pack([original]))
            store=PrivateFeatureState(root/('emote-observation-'+RUN+'-actor-2.json'));store.write(raw,None)
            reference=dict(index=2,sha256=digest(raw))
            self.assertEqual(original,continuation.anchor_original(decoder,reference,3));self.assertEqual([original],calls)
            for fault in ('hash','self','future','cycle','binding','missing'):
                value=deepcopy(raw);ref=deepcopy(reference)
                if fault=='hash':ref['sha256']='f'*64
                elif fault=='self':ref['index']=3
                elif fault=='future':ref['index']=4
                elif fault=='cycle':value['payload']=pack([dict(original,iosEmoteObservationOriginalVersion=2)])
                elif fault=='binding':value['binding']=fixture.PRIMARY
                else:store.discard(raw)
                if fault in ('cycle','binding'):
                    store.write(value,raw);ref['sha256']=digest(value)
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):continuation.anchor_original(decoder,ref,3)
                current=store.read()
                if current!=raw:store.write(raw,current)
            self.assertEqual([original],calls)

    def test_default_decoder_cannot_admit_rooted_original_two(self):
        value={key:None for key in ORIGINAL_FIELDS}
        value.update(iosEmoteObservationOriginalVersion=2,proof=dict(kind='playback'),peerContinuation=dict(index=1,sha256='a'*64))
        root=object.__new__(IOSEmoteRootedObservationDecoder);root.role='actor';root.original_shape(value)
        for decoder in (object.__new__(IOSEmoteObservationDecoder),object.__new__(IOSEmoteRootedObservationDecoder)):
            decoder.role='primary'
            with self.assertRaises(NativeUIError):decoder.original_shape(value)
        value['iosEmoteObservationOriginalVersion']=True
        with self.assertRaises(NativeUIError):root.original_shape(value)

    def test_rooted_selection_requires_a_real_previous_literal_episode(self):
        proof=dict(kind='playback',baseline=dict(index=1),before=dict(index=2),played=dict(index=3),inputBarrier=None)
        value=dict(iosEmoteObservationOriginalVersion=1,proof=proof,peerBefore=dict(index=1),peerAfter=dict(index=9))
        owner=object.__new__(IOSEmoteRootedObserver);owner.role='actor'
        owner.decoder=SimpleNamespace(retained=lambda _owner,ref:dict(peer=dict(receive=dict(source=
            dict(receiveSequence=0,droppedRecords=0) if ref['index']==1 else dict(receiveSequence=40,droppedRecords=8)))))
        owner.peers=object();owner.state=dict(records=[],lastPeer=dict(index=8))
        self.assertEqual(value,owner.prepare_original(deepcopy(value)))
        reference=dict(index=2,sha256='a'*64);owner.state['records']=[reference]
        owner.original=lambda ref:dict(iosEmoteObservationOriginalVersion=1,proof=proof,peerAfter=dict(index=2))
        actual=owner.prepare_original(deepcopy(value));self.assertEqual(2,actual['iosEmoteObservationOriginalVersion'])
        self.assertEqual(reference,actual['peerContinuation']);self.assertEqual(dict(index=8),actual['peerBefore'])
        owner.original=lambda ref:dict(iosEmoteObservationOriginalVersion=2,proof=proof,peerAfter=dict(index=2))
        self.assertEqual(value,owner.prepare_original(deepcopy(value)))


class RootedPeerContinuationConnectedTests(unittest.TestCase):
    def test_normal_actor_publication_continues_from_original_motion_after_receive_ring_expires(self):
        from ios.self_tests.emote_rooted_whole_fixture import paired
        from ios.adapters.emote_sources import IOSEmoteSources
        from ios.adapters.emote_peer_sources import IOSEmotePeerSources
        from feature_journeys.phase_fixture import PhaseFixtureReader

        f=paired(self,retain_originals=True);primary,actor=f.flow,f.actor.flow;target=f.actor.target
        call=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        primary.observe(call);actor.observe(call)
        # Retain deterministic, independently selected model clocks while
        # avoiding the fixture's unrelated inter-role cleanup scheduler.
        actor.sleep=target.domain.sleep
        primary.act(f.call('play',name='Crying'));f.target.native.sleep(.25)
        first=actor.observe(call)
        self.assertTrue(first['state']['override']);self.assertEqual('Crying',first['state']['animation'])
        owner=target.observer;reference=deepcopy(owner.state['records'][-1]);anchor=owner.original(reference)
        self.assertEqual(1,anchor['iosEmoteObservationOriginalVersion'])
        # Fresh producer evaluations occur before their first receive capture;
        # neither old receive bytes nor old acquisition clocks are changed.
        reader=f.target.rig.reader()
        for _ in range(36):reader.read(reader.sequence)
        normal_inputs=deepcopy(f.target.vm.state['events'])
        later=actor.observe(dict(call,afterSequence=first['sequence']))
        original=owner.original(owner.state['records'][-1])
        self.assertEqual(2,original['iosEmoteObservationOriginalVersion'])
        self.assertEqual(reference,original['peerContinuation'])
        self.assertTrue(later['state']['override']);self.assertEqual('Crying',later['state']['animation'])
        self.assertEqual(normal_inputs,f.target.vm.state['events'])
        self.assertTrue(later['artifacts']);self.assertTrue(target.packet_bytes)
        entries=f.target.server.journal.snapshot(primary.run)['entries']
        self.assertTrue(any(row['actorSequence']==later['sequence'] for row in entries))

        with actor.held(30):
            sources=IOSEmoteSources(owner.sources.store,owner.sources.root,owner.sources.binding,owner.run,'actor',
                owner.sources.lock,lambda:True,None,historical=True)
            peers=IOSEmotePeerSources(owner.peers.store,owner.peers.root,owner.binding,owner.run,None,owner.lock,lambda:True,historical=True)
            decoder=IOSEmoteRootedObservationDecoder(sources,owner.binding,'actor',owner.root,owner.policy,owner.lock,
                phase_instance=owner.decoder.phase_instance,peers=peers)
            paths=[path for root in (f.target.root,target.root) for path in root.rglob('*') if path.is_file()]
            def pins(path):
                stat=path.stat()
                return tuple(getattr(stat,key) for key in ('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink',
                    'st_size','st_mtime_ns','st_ctime_ns'))+(path.read_bytes(),)
            before={path:pins(path) for path in paths}
            def forbidden(*_args,**_kwargs):raise AssertionError('Historical continuation must not acquire, write or resend')
            with (patch.object(PrivateFeatureState,'write',side_effect=forbidden),
                  patch.object(PrivateFeatureState,'discard',side_effect=forbidden),
                  patch.object(PhaseFixtureReader,'read',side_effect=forbidden),
                  patch.object(PhaseFixtureReader,'status',side_effect=forbidden),
                  patch.object(f.target.rig,'send',side_effect=forbidden),
                  patch.object(target.runtime,'_sources',side_effect=forbidden),
                  patch.object(target,'receive_reader',side_effect=forbidden)):
                self.assertEqual(later,decoder.derive(original)['public'])
                for fault in ('missing-anchor','self-anchor','old-cut','new-episode'):
                    bad=deepcopy(original)
                    if fault=='missing-anchor':bad['peerContinuation']['sha256']='f'*64
                    elif fault=='self-anchor':bad['peerContinuation']['index']=bad['sequence']
                    elif fault=='old-cut':bad['peerBefore']=anchor['peerBefore']
                    else:bad['proof']['played']=bad['source']
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):decoder.derive(bad)
            self.assertEqual(before,{path:pins(path) for path in paths})


if __name__=='__main__':unittest.main()
