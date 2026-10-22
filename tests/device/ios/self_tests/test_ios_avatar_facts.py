"""Composed real archives/provider/PNG with explicit synthetic SDK boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import secrets
import unittest
import uuid
from io import BytesIO
from urllib.parse import urlencode
from unittest.mock import patch
from PIL import Image
from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_accounts import AvatarAccountScopes
from feature_journeys.avatar_social_provider import AvatarSocialProvider
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_facts import IOSAvatarFacts
from ios.adapters.avatar_observation import source_history
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_peer import session_sha
from ios.self_tests.test_ios_avatar_sources import SourcesFixture
from ios.self_tests.test_ios_avatar_social import SocialFixture,NODES,ORIGIN
from ios.self_tests import test_ios_avatar_samples as samples_fixture
from ios.self_tests.test_ios_avatar_renderers import SELF,PEER
from ios.self_tests.test_ios_emote_peer import acquisition as peer_template
from ios.self_tests.test_ios_graphics_measurements import RUN,TICKET,NATIVE,HOST,BINDING
from self_tests.test_native_avatar_receive import Boundary as Receiver,record


class AvatarFactsTests(unittest.TestCase):
    def setUp(self):
        self.g=samples_fixture.AvatarSamplesTests();self.g.setUp();self.addCleanup(self.g.doCleanups);self.clock=[self.g.gpu.clock]
        shared=self.clock
        class SharedGPU(type(self.g.gpu)):
            @property
            def clock(_self):return shared[0]
            @clock.setter
            def clock(_self,value):shared[0]=value
        self.g.gpu.__class__=SharedGPU
        self.logic=SocialFixture();self.account=AccountProvider(epoch_ms=lambda:round(self.host()))
        self.social=AvatarSocialProvider(account_authenticator(self.account),epoch_ms=lambda:round(self.host()),monotonic=lambda:self.clock[0])
        self.scopes=AvatarAccountScopes(self.account,self.social);self.scopes.provision(RUN);self.scopes.activate(RUN,TICKET)
        self.principals={};self.tokens={}
        for role in ('primary','actor'):
            credentials=self.scopes.credentials(RUN,role);self.principals[role]=credentials['username']
            status,grant=self.account.grant(urlencode(dict(grant_type='password',scope='owner',**credentials)).encode())
            self.assertEqual(200,status);self.tokens[role]='Bearer '+grant['access_token']
        self.scopes.bind_sessions(RUN,NODES,'11111111-1111-4111-8111-111111111111')
        self.logic.logic.account,self.logic.logic.provider,self.logic.logic.principals,self.logic.logic.tokens=self.account,self.social,self.principals,self.tokens
        self.client=Client(ORIGIN+'/feature-fixture/v1','reader-'+'a'*32)
        self.journal=Journal(clock=self.host)
        with patch.object(secrets,'token_hex',return_value=RUN):self.assertEqual(RUN,self.journal.register('avatar-people'))
        self.journal.activate(RUN,TICKET)
        self.client.request=lambda _path,**kwargs:self.journal.phase(RUN,kwargs['phase_nonce']) if 'phase_nonce' in kwargs else self.scopes.snapshot(RUN)
        self.authority=AvatarAuthorityReader(self.client,RUN,epoch_ms=self.host,monotonic=lambda:self.clock[0])
        self.fixtures={};self.sources={};self.peers={};self.baseline={};self.receivers={};self.peer_sequence={}
        for role in ('primary','actor'):
            fixture=SourcesFixture()
            class SharedSources(SourcesFixture):
                @property
                def clock(_self):return shared[0]
                @clock.setter
                def clock(_self,value):shared[0]=value
            fixture.__class__=SharedSources;fixture.run=RUN;fixture.journal=self.journal
            fixture.now=lambda:NATIVE+round(self.clock[0]*1000);fixture.host=self.host
            fixture.phase=PhaseFixtureReader(self.client,RUN,'avatar-people',epoch_ms=self.host,monotonic=lambda:self.clock[0])
            source=deepcopy(self.logic.frames[role]['originals'])
            source['scripts']=self.retime(source['scripts'],NATIVE-9000001000)
            fixture.prototypes.update(scripts=source['scripts'],http=self.logic.http[role],people=source['people'])
            fixture.prototypes['entities']['source']['events']=[]
            for packet in fixture.prototypes.values():packet['processId']=42
            fixture.prototypes['http']['runId']=RUN;fixture.prototypes['http']['events']=[]
            source_account=self.retime(source['native']['account'],NATIVE-9000001000)
            source_account['principalSha256']=hashlib.sha256(self.principals[role].encode()).hexdigest()
            base_send=fixture.core.send
            def send(query,f=fixture,original_send=base_send,account=source_account):
                original_send(query);value=deepcopy(account);value['observation']['capturedEpochMs']=f.now();f.core.sample['account']=value
            fixture.core.send=send
            widget=fixture.widget;widget.screen='people';widget.shown=True;widget.phase='idle'
            original_rows=widget.rows
            def rows(original=original_rows):
                result=original()
                for row in result:
                    if row['id']=='people.page':row['activeTab']='connectionsTab'
                return result
            widget.rows=rows
            model=fixture.prototypes['people']['source']['roots'][0]
            model.update(rootId=widget.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml',myData=dict(userName=self.principals[role]))
            fixture.prototypes['state']['source']['sessionId']=NODES[role]
            original_url=fixture.prototypes['state']['source']['requestedUrl']
            for row in fixture.prototypes['renderers']['source']['avatars']:
                row.update(self=row['sessionId']==NODES[role],replicated=False,requestedUrl=original_url,resourceUrl=original_url)
                if row['self']:
                    row['rigPose']=deepcopy(fixture.prototypes['renderers']['source']['avatars'][0]['rigPose']);row['externalPose']=None
                else:
                    row['rigPose']=None;row['externalPose']=dict(externalPoseVersion=1,instance='d'*32,rigId=124,capturedEpochMs=NATIVE,
                        evaluationSequence=10,totalJoints=3,joints=[[0,0,0,1,0,0,0] for _ in range(3)])
            # Set true current capture clocks at the modeled native source.
            def mutate(name,value,f=fixture):
                if name=='people':
                    value['source']['tabletShown']=True
                    for root in value['source']['roots']:root.update(active=True,visible=True)
                elif name=='renderers':
                    for row in value['source']['avatars']:
                        for key in ('rigPose','externalPose'):
                            if row[key]:row[key].update(capturedEpochMs=f.now(),evaluationSequence=100+f.sources.get('renderers',0))
            fixture.mutate=mutate
            binding=BINDING if role=='primary' else BINDING|dict(sessionId='actor-sdk',targetFingerprint='e'*64)
            directory=self.g.root/role;directory.mkdir(mode=0o700)
            lock=self.g.lock if role=='primary' else ScriptSourceLock(directory/'script-feature-sources.lock')
            if role=='actor':held=lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
            metadata=self.g.root if role=='primary' else directory
            owner=IOSAvatarSources(PrivateFeatureState(metadata/'ios-avatar-primary-sources.json'),directory,binding,RUN,'primary',lock,lambda:True,
                fixture.phase,readers=fixture.readers(),epoch_ms=self.host,monotonic=lambda:self.clock[0])
            self.fixtures[role],self.sources[role]=fixture,owner
            self.logic.frames[role]['originals']['scripts']=deepcopy(fixture.prototypes['scripts'])
            self.receivers[role]=Receiver();self.peer_sequence[role]=0
            self.peers[role]=IOSAvatarPeerSources(PrivateFeatureState(metadata/'ios-avatar-primary-peer-sources.json'),directory,binding,RUN,None,lock,
                lambda:True,historical=True,role='primary',epoch_ms=self.host,monotonic=lambda:self.clock[0])
            self.peers[role].historical=False;self.peers[role].save()
        self.g.native_boundary=self.fixtures['primary'].core
        self.g.scope.run=RUN;self.g.scope.binding=deepcopy(BINDING);self.g.scope.fixture_url=self.client.url+'/runs/'+RUN+'/'
        self.g.phase.run=RUN;self.g.phase.fixture_url=self.g.scope.fixture_url
        self.g.scope.snapshot=lambda:dict(syntheticMarkerAdmission=True,runId=RUN,binding=deepcopy(BINDING))
        self.g.activations=[dict(sequence=1,ticket=TICKET,activatedEpochMs=self.host()-100,stimulus=dict(verb='baseline',inputs={}))]
        original_phase=self.g.phase_status
        self.g.phase_status=lambda *_args:original_phase()|dict(instance=self.journal.phase_instance,
            activations=deepcopy(self.journal.runs[RUN]['phaseActivations']))
        self.g.phase.status=self.g.phase_status
        self.g.template['worldBefore']['source']['domain'].update(selfSha256=session_sha(SELF),avatarMixerSha256='c'*64)
        marker_baseline=deepcopy(self.g.template['worldBefore'])
        def bind_world(value):
            from ios.adapters.avatar_marker_measurements import image_body_preserved
            from ios.adapters.avatar_world import owned_marker
            from ios.self_tests.test_ios_avatar_images import NONCE,MARKER_URL
            image_body_preserved(marker_baseline,value);marker=owned_marker(value,NONCE,MARKER_URL)
            return dict(nonce=NONCE,url=marker['sourceUrl'])
        self.g.scope.bind_image_world=bind_world
        for key in ('renderersBefore','renderersAfter'):
            for row in self.g.template[key]['source']['avatars']:row.update(requestedUrl=original_url,resourceUrl=original_url)
        self.samples=self.g.owner()
    def host(self):return HOST+round(self.clock[0]*1000)
    @staticmethod
    def retime(value,offset):
        if type(value) is dict:return {key:item+offset if key.endswith('EpochMs') and type(item) in (int,float) else AvatarFactsTests.retime(item,offset) for key,item in value.items()}
        if type(value) is list:return [AvatarFactsTests.retime(item,offset) for item in value]
        return value
    def read_peer(self,role,*,received=False):
        owner=self.peers[role];fixture=self.fixtures[role];phase=fixture.phase.read()
        window=NativeClockAcquisition(fixture.native(),epoch_ms=self.host,monotonic=lambda:self.clock[0]);window.begin(phase['afterEpochMs'])
        self.clock[0]+=.001;packet=deepcopy(peer_template()['world']);sequence=self.peer_sequence[role]+1;self.peer_sequence[role]=sequence
        packet=self.retime(packet,fixture.now()-20000);packet.update(runId=RUN,processId=42,requestId='ios-'+uuid.uuid4().hex,sequence=sequence)
        packet['source']['scriptOriginal']['processId']=42
        for row in packet['source']['markers']+packet['source']['scriptOriginal']['source']['effects']['entities']:
            data=json.loads(row['userData']);data['runId']=RUN;row['userData']=json.dumps(data);row['name']='e2e-'+RUN+'-script'
        packet['source']['domain'].update(selfSha256=session_sha(NODES[role]),avatarMixerSha256='c'*64)
        for key in ('clockBefore','clockAfter'):packet[key]=dict(epochMs=fixture.now(),monotonicMs=round(self.clock[0]*1000))
        receiver=self.receivers[role]
        if received:
            item=record(len(receiver.records)+1,.1);item.update(capturedEpochMs=fixture.now(),avatarSha256=session_sha(SELF),jointCount=3,
                advertisedModelUrl=fixture.prototypes['state']['source']['requestedUrl'])
            item['joints']=[dict(index=i,rotation=[0,0,0,1],translation=[0,0,0]) for i in range(3)];receiver.records.append(item)
        receiver.send(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='feature-avatar-receive-observe'))
        receive=deepcopy(receiver.current);receive.update(processId=42,requestedEpochMs=fixture.now(),capturedEpochMs=fixture.now())
        receive['source'].update(processId=42,selfSha256=session_sha(NODES[role]))
        renderer=fixture.reader('renderers',__import__('ios.adapters.avatar_renderers',fromlist=['IOSAvatarRenderers']).IOSAvatarRenderers).read(RUN)
        originals=dict(world=packet,receive=receive,renderers=renderer)
        peer=dict(originals,clockJoin=window.finish(originals,[('receive','capturedEpochMs')]))
        after=fixture.phase.status(phase['status']);frame=dict(peer=peer,phaseBefore=phase['status'],phaseAfter=after)
        owner.validate_frame(frame,owner.frames[-1] if owner.frames else None)
        owner.state['pending']=dict(original=None,manifest=None,partial={});owner.save()
        original=owner.originals.write(len(owner.frames)+1,frame);refs=owner.originals.append(owner.state['manifests'],original)
        owner.frames.append(deepcopy(frame));owner.state.update(revision=len(owner.frames),manifests=refs,pending=None);owner.save()
        return owner.reference()
    def baseline_proof(self):
        for role in ('primary','actor'):
            self.sources[role].read();self.baseline[role]=dict(index=1,sha256=digest(self.sources[role].frames[0]))
        barriers={role:dict(nativeEpochMs=self.sources[role].frames[0]['clockJoin']['nativeAfter']['capturedEpochMs'],
            providerEpochMs=self.host(),httpEvent=0) for role in ('primary','actor')}
        before=self.host();started=self.clock[0]
        for role in ('primary','actor'):
            old=len(self.logic.http[role]['events']);self.logic.response(role,'GET','/api/v1/users/connections','page=1&per_page=1000&sort=username%2CASC')
            for event in self.logic.http[role]['events'][old:]:
                self.clock[0]+=.001;event['clock']=dict(epochMs=NATIVE+round(self.clock[0]*1000),monotonicMs=round(self.clock[0]*1000))
            self.fixtures[role].prototypes['people']['source']['roots'][0]['connectionRows']=[]
            self.fixtures[role].prototypes['people']['source']['roots'][0]['pagination']['totalEntries']=0
        primary_peer=self.read_peer('primary');self.sources['primary'].read()
        actor_before=self.read_peer('actor');self.sources['actor'].read();actor_after=self.read_peer('actor',received=True)
        provider=dict(status=self.authority.read(),acquisition=dict(hostBeforeEpochMs=self.host(),hostAfterEpochMs=self.host(),
            hostBeforeMonotonic=self.clock[0],hostAfterMonotonic=self.clock[0]))
        row=self.samples.capture(TICKET)
        historical={role:source_history(owner.previous,None,store=owner.store,root=owner.root,binding=owner.binding,run=RUN,
            role='primary',lock=owner.lock) for role,owner in self.sources.items()}
        peers={role:IOSAvatarPeerSources(owner.store,owner.root,owner.binding,RUN,None,owner.lock,lambda:True,historical=True,role='primary')
            for role,owner in self.peers.items()}
        images=IOSAvatarSamples.history(self.samples.previous,store=self.samples.store,root=self.samples.root,binding=BINDING,run=RUN,
            role='primary',policy=self.samples.policy,lock=self.g.lock)
        facts=IOSAvatarFacts(historical,peers,images,self.authority,role='primary',phase_instance=self.journal.phase_instance,expected_code=self.logic.expected)
        current={role:dict(index=len(owner.frames),sha256=digest(owner.frames[-1])) for role,owner in self.sources.items()}
        original=dict(iosAvatarFactsOriginalVersion=1,runId=RUN,role='primary',sequence=1,ticket=TICKET,phaseInstance=self.journal.phase_instance,
            baseline=self.baseline,current=current,primaryPeer=primary_peer,actorBefore=actor_before,actorAfter=actor_after,
            provider=provider,barriers=barriers,image=row,imageBefore=None,acquisition=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.host(),
                hostBeforeMonotonic=started,hostAfterMonotonic=self.clock[0]))
        return facts,original
    def test_positive_nine_fact_composition_keeps_actual_two_sdk_http_peer_and_original_png(self):
        facts,original=self.baseline_proof();value=facts.derive(original)
        self.assertEqual(dict(avatar='original',requestedAvatar='original',modelLoaded=True,loadFailed=False,
            scale=1.,wearable=False,bookmarked=False,connection='none',dialog=False),value['public']['state'])
        self.assertEqual(facts.samples.archive(original['image'])[2]['image']['sha256'],value['originals']['image']['image']['sha256'])
        self.assertEqual(SELF,value['originals']['peer']['remoteSessionId'])
        changed=deepcopy(original);changed['provider']['status']['sessionBinding']['sessions']=dict(primary=PEER,actor=SELF)
        with self.assertRaises(NativeUIError):facts.derive(changed)

    def test_historical_full_join_never_uses_sdk_provider_request_or_action_owner(self):
        facts,original=self.baseline_proof();before=facts.derive(original)
        files={str(path):path.read_bytes() for path in self.g.root.rglob('*.json')}
        def forbidden(*_args,**_kwargs):raise AssertionError('Historical join attempted live work')
        self.client.request=forbidden
        for owner in list(facts.sources.values())+list(facts.peers.values()):owner.guard=forbidden
        facts.samples.guard=forbidden
        self.assertEqual(before,facts.derive(original));self.assertEqual(files,{str(path):path.read_bytes() for path in self.g.root.rglob('*.json')})

    def test_current_ticket_http_reads_source_identity_and_image_reference_cannot_be_substituted(self):
        facts,original=self.baseline_proof()
        for fault in ('scope','providerReceipts','barrier','source','image','role','window'):
            altered=deepcopy(original)
            if fault=='scope':altered['provider']['status']['accounts']['primary']['runId']='9'*32
            elif fault=='providerReceipts':altered['provider']['status']['social']['history']=[]
            elif fault=='barrier':altered['barriers']['primary']['httpEvent']=100000
            elif fault=='source':altered['current']['primary']=deepcopy(altered['baseline']['primary'])
            elif fault=='image':altered['image']['avatarId']=PEER
            elif fault=='role':altered['role']='actor'
            else:
                clock=facts.peers['primary'].original(original['primaryPeer'])['peer']['clockJoin']
                altered['acquisition']['hostBeforeEpochMs']=clock['hostAfterEpochMs']+1
                altered['acquisition']['hostBeforeMonotonic']=clock['hostAfterMonotonic']+.001
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,KeyError)):facts.derive(altered)

    def wearable_proof(self,*,image_present):
        from ios.self_tests.test_ios_avatar_renderers import attach
        from ios.self_tests.test_ios_avatar_images import bundle
        old_facts,old=self.baseline_proof();ticket='f'*32
        self.journal.activate(RUN,ticket,'wearable-add',dict(resource='gltf-bundle/main.gltf'));self.scopes.activate(RUN,ticket)
        self.g.ticket=ticket;self.g.activations=deepcopy(self.journal.runs[RUN]['phaseActivations'])
        before,started=self.host(),self.clock[0];self.clock[0]+=.001
        identity=str(uuid.uuid4());resource=self.client.url+'/runs/'+RUN+'/tickets/'+ticket+'/gltf-bundle/main.gltf'
        from ios.self_tests.test_ios_avatar_entities import packet as entity_packet
        primary=self.fixtures['primary'];events=primary.prototypes['entities']['source']['events'];event=deepcopy(entity_packet()[0]['source']['events'][0])
        worker=primary.prototypes['scripts']['source']['workers'][0];event.update(sequence=len(events)+1,eventId=uuid.uuid4().hex)
        event['clock']=dict(epochMs=primary.now(),monotonicMs=round(self.clock[0]*1000))
        event['caller'].update(sequence=len(events)+1,invokedEpochMs=primary.now(),
            manager=deepcopy(worker['membership']),code=deepcopy(worker['code']),
            avatarCode={key:deepcopy(worker['avatar'][key]) for key in ('avatarScriptVersion','instance','complete','code')})
        event['entity'].update(entityId=identity,modelUrl=resource,lastEditedEpochUs=str(primary.now()*1000))
        events.append(event)
        for role in ('primary','actor'):
            renderer=self.fixtures[role].prototypes['renderers'];attach(renderer,SELF)
            row=renderer['source']['avatarEntities'][-1];row.update(id=identity,modelUrl=resource,resourceUrl=resource)
            renderer['source']['tree']['entities'][-1]['id']=identity
            renderer['source']['tree'].update(revisionBefore=2,revisionAfter=2)
            old_events=len(self.logic.http[role]['events'])
            self.logic.response(role,'GET','/api/v1/users/connections','page=1&per_page=1000&sort=username%2CASC')
            for event in self.logic.http[role]['events'][old_events:]:
                self.clock[0]+=.001;event['clock']=dict(epochMs=NATIVE+round(self.clock[0]*1000),monotonicMs=round(self.clock[0]*1000))
        primary_peer=self.read_peer('primary');self.sources['primary'].read()
        actor_before=self.read_peer('actor');self.sources['actor'].read();actor_after=self.read_peer('actor',received=True)
        provider=dict(status=self.authority.read(),acquisition=dict(hostBeforeEpochMs=self.host(),hostAfterEpochMs=self.host(),
            hostBeforeMonotonic=self.clock[0],hostAfterMonotonic=self.clock[0]))
        _template,raw,_policy=bundle(ticket=ticket,change=True);self.g.gpu.png=raw
        self.g.gpu.raw_pixels=Image.open(BytesIO(raw)).convert('RGBA').tobytes()
        if image_present:
            for side in ('renderersBefore','renderersAfter'):
                renderer=self.g.template[side];attach(renderer,SELF)
                renderer['source']['avatarEntities'][-1].update(id=identity,modelUrl=resource,resourceUrl=resource)
                renderer['source']['tree']['entities'][-1]['id']=identity
                renderer['source']['tree'].update(revisionBefore=2,revisionAfter=2)
        row=self.samples.capture(ticket)
        sources={role:source_history(owner.previous,None,store=owner.store,root=owner.root,binding=owner.binding,run=RUN,
            role='primary',lock=owner.lock) for role,owner in self.sources.items()}
        peers={role:IOSAvatarPeerSources(owner.store,owner.root,owner.binding,RUN,None,owner.lock,lambda:True,historical=True,role='primary')
            for role,owner in self.peers.items()}
        samples=IOSAvatarSamples.history(self.samples.previous,store=self.samples.store,root=self.samples.root,binding=BINDING,run=RUN,
            role='primary',policy=self.samples.policy,lock=self.g.lock)
        facts=IOSAvatarFacts(sources,peers,samples,self.authority,role='primary',phase_instance=self.journal.phase_instance,expected_code=self.logic.expected)
        original=deepcopy(old);original.update(sequence=2,ticket=ticket,current={role:dict(index=len(owner.frames),sha256=digest(owner.frames[-1]))
            for role,owner in self.sources.items()},primaryPeer=primary_peer,actorBefore=actor_before,actorAfter=actor_after,
            provider=provider,image=row,imageBefore=old['image'],acquisition=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.host(),
                hostBeforeMonotonic=started,hostAfterMonotonic=self.clock[0]))
        return facts,original

    def test_positive_owned_wearable_full_join_keeps_remote_actor_self_and_requires_actual_changed_pixels(self):
        facts,original=self.wearable_proof(image_present=True);value=facts.derive(original)
        self.assertTrue(value['public']['state']['wearable']);self.assertGreater(value['originals']['changed']['subjectChangedFraction'],.5)
        self.assertEqual(1,len(value['originals']['peer']['wearables']))

    def test_owned_wearable_missing_from_actual_image_renderers_cannot_inherit_earlier_source_and_peer_presence(self):
        facts,original=self.wearable_proof(image_present=False)
        # Both earlier independent source and real peer joins establish the
        # wearable; the image's own native mesh inventory honestly lacks it.
        self.assertTrue(facts.sources['primary'].frames[-1]['originals']['renderers']['source']['avatarEntities'])
        self.assertTrue(facts.peers['actor'].frames[-1]['peer']['renderers']['source']['avatarEntities'])
        with self.assertRaises(NativeUIError):facts.derive(original)

    def test_derive_rechecks_each_original_owner_lock_after_construction(self):
        facts,original=self.baseline_proof();actor=facts.sources['actor'].lock;held=actor._owner;actor._owner=None
        try:
            with self.assertRaises(NativeUIError):facts.derive(original)
        finally:actor._owner=held


if __name__=='__main__':unittest.main()
