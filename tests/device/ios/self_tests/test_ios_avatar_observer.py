"""Actual composed acquisition/archive owner with explicit native producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import json
import unittest
from unittest.mock import patch
from PIL import Image
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_observer import IOSAvatarObserver
from ios.adapters.avatar_surface import IOSAvatarSurface
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.self_tests import test_ios_avatar_facts as fixture


class AvatarObserverTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarFactsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.baseline_proof();self.surfaces={};self.calls=[]
        for role in ('primary','actor'):
            source=self.f.sources[role];surface=object.__new__(IOSAvatarSurface)
            surface.sources,surface.subject_role,surface.observer_role=source,role,'primary'
            surface.previous=dict(explicitSyntheticQtSurface=True,subjectRole=role)
            def prepare(ticket,subject=role):
                self.assertEqual(fixture.TICKET,ticket);self.calls.append('surface-'+subject)
                old=len(self.f.logic.http[subject]['events'])
                self.f.logic.response(subject,'GET','/api/v1/users/connections','page=1&per_page=1000&sort=username%2CASC')
                for event in self.f.logic.http[subject]['events'][old:]:
                    self.f.clock[0]+=.001;event['clock']=dict(epochMs=fixture.NATIVE+round(self.f.clock[0]*1000),monotonicMs=round(self.f.clock[0]*1000))
                return self.f.sources[subject].read()
            surface.prepare=prepare;self.surfaces[role]=surface
            def read(subject=role):
                self.calls.append('peer-'+subject);return self.f.read_peer(subject,received=subject=='actor')
            self.f.peers[role].read=read
        self.path=self.f.g.root/'ios-avatar-primary-observer.json'
        self.role='primary'
    def owner(self):
        return IOSAvatarObserver(PrivateFeatureState(self.path),self.f.sources,self.f.peers,self.surfaces,self.f.samples,
            self.f.authority,self.f.fixtures[self.role].phase,role=self.role,guard=lambda:True,
            expected_code=self.f.logic.expected,epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
    def test_complete_acquisition_survives_reconstruction_and_file_only_decode(self):
        owner=self.owner();actual=owner.observe();self.assertEqual('none',actual['state']['connection'])
        self.assertEqual(9,len(actual['state']));self.assertEqual(1,actual['sequence'])
        self.assertEqual(['surface-primary','surface-actor','peer-primary','peer-actor','peer-actor'],self.calls)
        restored=self.owner();row=deepcopy(restored.state['rows'][-1]);before=len(self.calls)
        def forbidden(*_args,**_kwargs):raise AssertionError('Historical decoder used a current transport')
        self.f.client.request=forbidden
        self.assertEqual(actual,restored.validate_original(row)['public']);self.assertEqual(before,len(self.calls))
        self.assertEqual(0o600,self.path.stat().st_mode&0o777)

    def test_lost_passive_peer_return_retains_complete_actual_prefix_and_uses_distinct_new_reads(self):
        owner=self.owner();peer=self.f.peers['primary'];read=peer.read
        def lost():
            read();raise OSError('Synthetic lost complete passive peer return')
        peer.read=lost
        with self.assertRaises(OSError):owner.observe()
        actual=deepcopy(peer.frames[-1]);self.assertEqual(1,owner.state['pending']['index'])
        peer.read=read;restored=self.owner();before=len(self.calls);row=restored.recover()
        self.assertEqual('abandoned',row['status']);self.assertEqual(before,len(self.calls))
        record=restored.read_record(row);self.assertEqual(peer.previous,record['components']['peers']['primary']['owner'])
        with self.assertRaises(NativeUIError):restored.validate_original(row)
        public=restored.observe(after_sequence=1);self.assertEqual(2,public['sequence'])
        self.assertEqual(actual,peer.frames[-2]);self.assertGreater(peer.frames[-1]['peer']['receive']['sequence'],actual['peer']['receive']['sequence'])

    def test_lost_saved_original_return_is_adopted_without_sdk_or_second_file_write(self):
        owner=self.owner();intent=owner.originals.intent
        def lost(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':raise OSError('Synthetic lost saved-file return')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.observe()
        self.assertEqual('saved',owner.state['pending']['original']['phase']);before=list(self.calls)
        restored=self.owner();row=restored.recover();self.assertEqual('observed',row['status']);self.assertEqual(before,self.calls)
        self.assertEqual(1,restored.validate_original(row)['public']['sequence'])
        self.assertEqual(1,len(list(self.f.g.root.glob('avatar-observation-frame-*.json'))))

    def test_delayed_saved_callback_refuses_fresh_return_but_keeps_historical_original(self):
        owner=self.owner();intent=owner.originals.intent
        def delayed(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='saved':self.f.clock[0]+=1.501
        owner.originals.intent=delayed
        with self.assertRaises(NativeUIError):owner.observe()
        self.assertIsNone(owner.state['pending']);self.assertEqual(1,len(owner.state['rows']))
        before=list(self.calls);restored=self.owner();row=restored.state['rows'][0]
        proof=restored.validate_original(row)
        self.assertEqual(1,proof['public']['sequence']);self.assertEqual(before,self.calls)
        self.assertLess(proof['acquisition']['hostAfterMonotonic'],self.f.clock[0]-1.5)
        self.assertEqual(1,len(list(self.f.g.root.glob('avatar-observation-frame-*.json'))))

    def test_peer_lock_is_reasserted_after_construction_for_bound_and_snapshot(self):
        from types import SimpleNamespace
        owner=self.owner();peer=self.f.peers['actor'];old=peer.lock
        def unlocked():raise NativeUIError('Synthetic peer serialization has ended')
        peer.lock=SimpleNamespace(assert_held=unlocked)
        try:
            with self.assertRaises(NativeUIError):owner.bound()
            with self.assertRaises(NativeUIError):owner.snapshot()
        finally:peer.lock=old

    def test_opened_failed_writer_inode_and_bytes_survive_abandonment_and_cannot_be_replaced(self):
        owner=self.owner();intent=owner.originals.intent
        def lost(kind,value):
            intent(kind,value)
            if kind=='original' and value['phase']=='opened':raise OSError('Synthetic lost opened-file return')
        owner.originals.intent=lost
        with self.assertRaises(OSError):owner.observe()
        partial=deepcopy(owner.state['pending']['original']);path=owner.originals.path(partial);identity=path.stat().st_ino
        self.assertEqual(b'',path.read_bytes());before=list(self.calls);restored=self.owner();row=restored.recover()
        self.assertEqual('abandoned',row['status']);self.assertEqual(identity,path.stat().st_ino);self.assertEqual(before,self.calls)
        old=path.read_bytes();path.unlink();path.write_bytes(old);path.chmod(0o600)
        with self.assertRaises(NativeUIError):restored.read_record(row)

    def test_observation_proof_cannot_replace_actual_saved_provider_or_native_reference_prefix(self):
        owner=self.owner();owner.observe();original=owner.read_record(owner.state['rows'][-1])
        for fault in ('provider','image','source','sequence','start'):
            altered=deepcopy(original)
            if fault=='provider':altered['facts']['provider']['status']['socialInstance']='9'*32
            elif fault=='image':altered['facts']['image']['requestId']='ios-'+'9'*32
            elif fault=='source':altered['facts']['current']['primary']['index']=1
            elif fault=='sequence':altered['facts']['sequence']+=1
            else:altered['facts']['acquisition']['hostBeforeEpochMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.record(altered)

    def actor_view(self):
        """Take distinct role-owned source reads; never reuse primary answers."""
        from ios.self_tests.test_ios_avatar_images import bundle,NONCE,MARKER_URL
        from ios.adapters.avatar_marker_measurements import image_body_preserved
        from ios.adapters.avatar_world import owned_marker
        previous=self.f.sources;root=self.f.g.root/'actor-observer';root.mkdir(mode=0o700)
        self.role='actor';binding=deepcopy(previous['actor'].binding)
        for subject in ('primary','actor'):
            original=previous[subject];directory=root/subject;directory.mkdir(mode=0o700);metadata=original.store.path.parent
            source=IOSAvatarSources(PrivateFeatureState(metadata/'ios-avatar-actor-sources.json'),directory,original.binding,fixture.RUN,'actor',
                original.lock,lambda:True,self.f.fixtures[subject].phase,readers=self.f.fixtures[subject].readers(),
                epoch_ms=self.f.host,monotonic=lambda:self.f.clock[0])
            self.f.sources[subject]=source
            peer=IOSAvatarPeerSources(PrivateFeatureState(metadata/'ios-avatar-actor-peer-sources.json'),directory,original.binding,fixture.RUN,None,
                original.lock,lambda:True,historical=True,role='actor');peer.historical=False;peer.save();self.f.peers[subject]=peer
            peer.read=lambda subject=subject:self.f.read_peer(subject,received=subject=='actor')
            self.surfaces[subject].sources=source;self.surfaces[subject].observer_role='actor'
        g=self.f.g;g.root=root;g.lock=self.f.sources['actor'].lock;g.scope.lock=g.lock;g.scope.binding=binding;g.scope.role='actor'
        g.native_boundary=self.f.fixtures['actor'].core
        template,raw,_=bundle(remote=True)
        # The modeled remote-primary placement keeps the actual native rows
        # and body UUIDs, rather than changing a normalized result's subject.
        for key in ('worldBefore','worldAfter'):
            world=template[key];world['source']['domain'].update(selfSha256=fixture.session_sha(fixture.PEER),avatarMixerSha256='c'*64)
            for body in world['source']['bodies']['avatars']:
                body['sessionId']=fixture.PEER if body['sessionId']==fixture.SELF else fixture.SELF
            world['source']['bodies']['avatars'].sort(key=lambda row:row['sessionId'])
        url=self.f.fixtures['primary'].prototypes['state']['source']['requestedUrl']
        for key in ('renderersBefore','renderersAfter'):
            for row in template[key]['source']['avatars']:
                row.update(sessionId=fixture.PEER if row['sessionId']==fixture.SELF else fixture.SELF,requestedUrl=url,resourceUrl=url)
            template[key]['source']['avatars'].sort(key=lambda row:row['sessionId'])
        g.template=template;g.gpu.png=raw;g.gpu.raw_pixels=Image.open(BytesIO(raw)).convert('RGBA').tobytes()
        baseline=deepcopy(template['worldBefore'])
        def bind_world(value):
            image_body_preserved(baseline,value);marker=owned_marker(value,NONCE,MARKER_URL);return dict(nonce=NONCE,url=marker['sourceUrl'])
        g.scope.bind_image_world=bind_world
        g.scope.snapshot=lambda:dict(syntheticMarkerAdmission=True,runId=fixture.RUN,binding=deepcopy(binding))
        sources=g.sources
        g.runtime._sources=lambda selector:sources(selector)|dict(binding=deepcopy(binding))
        g.runtime.state_path=lambda _selector:previous['actor'].store.path.parent/'session.json'
        self.f.samples=g.owner();self.path=previous['actor'].store.path.parent/'ios-avatar-actor-observer.json';self.calls=[]

    def test_independent_actor_sources_remote_primary_png_and_lost_publication_return_never_resend_POST(self):
        self.actor_view();owner=self.owner();actual=owner.observe()
        self.assertEqual('actor',owner.role);record=owner.read_record(owner.state['rows'][-1])
        self.assertEqual(fixture.SELF,record['facts']['image']['avatarId'])
        self.assertTrue(all(owner.sources[role].role=='actor' for role in ('primary','actor')))
        previous=self.f.client.request;posts=[]
        def request(path,value=None,**kwargs):
            if path.endswith('/samples'):
                posts.append(deepcopy(value));self.f.journal.publish(fixture.RUN,value)
                raise OSError('Synthetic socket loss after actual actor journal commit')
            if path=='/runs/'+fixture.RUN:return self.f.journal.snapshot(fixture.RUN)
            return previous(path,**kwargs)
        self.f.client.request=request
        with self.assertRaises(OSError):owner.publish_latest()
        self.assertEqual(1,len(posts));restored=self.owner();publisher=restored.publisher();self.assertTrue(publisher.resolve())
        self.assertEqual(1,restored.publish_latest());self.assertEqual(1,len(posts))
        self.assertEqual(actual['state']['requestedAvatar'],posts[0]['facts']['requestedAvatar'])


if __name__=='__main__':unittest.main()
