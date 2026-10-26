"""Real durable original archives with explicit synthetic native source boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.witness import Client,Journal
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.avatar_sources import IOSAvatarSources,AvatarSourcePending,CHANNELS
from ios.adapters.avatar_controls import IOSAvatarIO
from ios.adapters import avatar_state,avatar_renderers,avatar_social_http,people_model,avatar_scripts,avatar_entities
from ios.self_tests import test_ios_avatar_state as state_tests
from ios.self_tests import test_ios_avatar_renderers as renderer_tests
from ios.self_tests import test_ios_avatar_social_http as http_tests
from ios.self_tests import test_ios_people_model as people_tests
from ios.self_tests import test_ios_avatar_scripts as script_tests
from ios.self_tests import test_ios_avatar_entities as entity_tests
from ios.self_tests.test_ios_avatar_controls import Boundary as WidgetBoundary
from ios.self_tests.test_ios_avatar_input_owner import BINDING
from self_tests.test_native_feature_observation import Boundary as CoreBoundary


class SourcesFixture:
    def __init__(self):
        self.clock=1.;self.sequence=0;self.tickets=0;self.sources={};self.mutate=None
        self.journal=Journal(clock=self.host);self.run=self.journal.register('avatar-people')
        self.journal.activate(self.run,'1'*32)
        client=Client('http://controlled.invalid/feature-fixture/v1','reader-'+'a'*32)
        client.request=lambda _path,phase_nonce:self.journal.phase(self.run,phase_nonce)
        self.phase=PhaseFixtureReader(client,self.run,'avatar-people',epoch_ms=self.host,monotonic=lambda:self.clock)
        http=http_tests.SocialHttpTests();http.setUp()
        state=state_tests.packet();state['iosAvatarStateVersion']=2
        state['source']['bookmarkFile']=dict(source='avatar-bookmarks-persistence',status='ready',reason='',bytes=2,
            sha256=hashlib.sha256(b'{}').hexdigest(),contentBase64=base64.b64encode(b'{}').decode(),identity=dict(device='1',inode='2'))
        people=people_tests.packet();people['source']['roots'][0].update(visible=False,active=False)
        self.prototypes=dict(state=state,renderers=renderer_tests.packet(),http=http.value,people=people,scripts=script_tests.packet(),entities=entity_tests.packet()[0])
        self.widget=WidgetBoundary();self.core=CoreBoundary();self.proto_core=None
    def now(self):return 1700000000000+round(self.clock*1000)
    def host(self):return 1800000000000+self.clock*1000
    def tick(self):self.clock+=.001
    def sleep(self,seconds):self.clock+=seconds
    def native(self):
        def send(query):
            self.tick();self.core.send(query);value=self.core.sample
            value.update(processId=42,requestedEpochMs=self.now(),capturedEpochMs=self.now(),animation={},animationFence={})
            self.proto_core=deepcopy(value)
        return NativeFeatureObservation(send,self.core.original,self.now,lambda:True,42,ios=True,native_clock_bound=True,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def reader(self,name,kind):
        def send(query):
            self.tick();index=self.sources.get(name,0)+1;self.sources[name]=index
            value=deepcopy(self.prototypes[name]);value.update(requestId=query['commandId'],runId=self.run,sequence=index)
            value['clockBefore']=dict(epochMs=self.now(),monotonicMs=round(self.clock*1000));self.tick()
            value['clockAfter']=dict(epochMs=self.now(),monotonicMs=round(self.clock*1000))
            if self.mutate:self.mutate(name,value)
            self.sources[name+'-last']=value
        return kind(send,lambda:json.dumps(self.sources[name+'-last']),self.now,lambda:True,42,
                    monotonic=lambda:self.clock,sleep=self.sleep)
    def readers(self):
        result=dict(state=self.reader('state',avatar_state.IOSAvatarState),renderers=self.reader('renderers',avatar_renderers.IOSAvatarRenderers),
            http=self.reader('http',avatar_social_http.IOSAvatarSocialHttp),people=self.reader('people',people_model.IOSPeopleModel),
            scripts=self.reader('scripts',avatar_scripts.IOSAvatarScripts),entities=self.reader('entities',avatar_entities.IOSAvatarEntities),native=self.native())
        def capture():
            self.tick();raw=self.widget.observed();raw.update(sampleEpochMs=self.now(),elapsedMs=round(self.clock*1000));return raw
        class NativeWidgets:
            def capture(_self):return capture()
            def deliver(_self,_query):raise AssertionError('Original acquisition must not deliver input')
        result['ui']=IOSAvatarIO(NativeWidgets());return result


class AvatarSourcesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);os.chmod(self.path,0o700)
        self.artifacts=self.path/'originals';self.artifacts.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(self.path/'script-feature-sources.lock');self.fixture=SourcesFixture()
    def owner(self,historical=False,binding=BINDING):
        return IOSAvatarSources(PrivateFeatureState(self.path/'ios-avatar-primary-sources.json'),self.artifacts,binding,
            self.fixture.run,'primary',self.lock,lambda:True,self.fixture.phase,
            readers=None if historical else self.fixture.readers(),historical=historical,
            monotonic=lambda:self.fixture.clock,epoch_ms=self.fixture.host)
    def test_actual_immutable_archive_retains_all_native_originals_and_separate_host_clock(self):
        with self.lock.held():
            owner=self.owner();first=owner.read()
            self.assertNotEqual(first['clockJoin']['hostBeforeEpochMs'],first['clockJoin']['nativeBefore']['capturedEpochMs'])
            self.assertEqual(set(CHANNELS)|{'native','widgets'},set(first['originals']))
            second=owner.read();self.assertEqual(2,owner.state['revision'])
            restored=self.owner(historical=True);self.assertEqual([first,second],restored.frames)
            self.assertEqual(0o600,owner.store.path.stat().st_mode&0o777)
        self.assertEqual(2,len(list(self.artifacts.glob('avatar-frame-*.json'))))
    def test_reconstruction_restores_source_floors_and_uses_new_actual_queries(self):
        with self.lock.held():
            first=self.owner().read();restored=self.owner();second=restored.read()
            self.assertGreater(second['originals']['scripts']['sequence'],first['originals']['scripts']['sequence'])
            self.assertNotEqual(first['originals']['state']['requestId'],second['originals']['state']['requestId'])
            self.assertGreater(second['ui']['scope']['sourceSequence'],first['ui']['scope']['sourceSequence'])
    def test_decoded_state_and_frames_are_isolated_from_owner_metadata_and_later_decodes(self):
        with self.lock.held():
            owner=self.owner();owner.read();owner.read()
            state,frames=deepcopy(owner.state),deepcopy(owner.frames)
            previous=deepcopy(owner.previous);queries=dict(self.fixture.sources)
            original_files={path:(path.stat().st_ino,path.read_bytes()) for path in self.artifacts.iterdir()}
            decoded,originals=owner.decode(previous)
            decoded['manifests'][0]['sha256']='caller-modified-manifest'
            originals[0]['originals']['native']['processId']=0
            originals[1]['clockJoin']['nativeAfter']['requestId']='caller-modified-clock'
            originals.clear()
            self.assertEqual(state,owner.state);self.assertEqual(frames,owner.frames)
            self.assertEqual((state,frames),owner.decode(previous))
            self.assertEqual(previous,owner.previous);self.assertEqual(previous,owner.store.read())
            self.assertEqual(queries,self.fixture.sources)
            self.assertEqual(original_files,{path:(path.stat().st_ino,path.read_bytes()) for path in self.artifacts.iterdir()})
    def test_frozen_v1_group_stays_original_and_first_v2_read_adds_new_channel_without_inventing_old_returns(self):
        from adapters.native_clock_join import digest
        with self.lock.held():frame=self.owner().read()
        legacy=deepcopy(frame);del legacy['avatarSourceGroupVersion'];del legacy['originals']['entities'];del legacy['acquisitions']['entities']
        legacy['clockJoin']['originalsSha256']=digest(legacy['originals'])
        directory=self.path/'legacy';directory.mkdir(mode=0o700);artifacts=directory/'originals';artifacts.mkdir(mode=0o700)
        store=PrivateFeatureState(directory/'ios-avatar-primary-sources.json');lock=ScriptSourceLock(directory/'script-feature-sources.lock')
        def make():return IOSAvatarSources(store,artifacts,BINDING,self.fixture.run,'primary',lock,lambda:True,self.fixture.phase,
            readers=self.fixture.readers(),monotonic=lambda:self.fixture.clock,epoch_ms=self.fixture.host)
        with lock.held():
            writer=make();writer.state.update(phase='reading',pending=dict(original=None,manifest=None,partial={}));writer.save()
            original=writer.originals.write(1,legacy);manifests=writer.originals.append([],original)
            frozen=dict(phase='ready',revision=1,manifests=manifests,pending=None)
            store.write(writer.envelope(frozen,version=1),writer.previous)
            restored=make();self.assertNotIn('entities',restored.frames[0]['originals'])
            self.assertIsNone(restored.readers['entities'].last)
            current=restored.read();self.assertEqual(2,current['avatarSourceGroupVersion'])
            self.assertIn('entities',current['originals']);self.assertNotIn('entities',restored.frames[0]['originals'])
            self.assertEqual(2,store.read()['iosAvatarSourcesVersion'])
            with self.assertRaises(NativeUIError):restored.validate_frame(legacy,current)
    def test_lost_source_or_partial_storage_remains_owned_and_cannot_replay_as_new_group(self):
        with self.lock.held():
            owner=self.owner()
            self.fixture.mutate=lambda name,value:value.update(processId=43) if name=='people' else None
            with self.assertRaises(NativeUIError):owner.read()
            restored=self.owner();self.assertEqual('reading',restored.state['phase'])
            self.assertIn('state',restored.state['pending']['partial'])
            before=dict(self.fixture.sources)
            with self.assertRaises(AvatarSourcePending):restored.read()
            self.assertEqual(before,self.fixture.sources)
    def test_original_file_replacement_or_foreign_candidate_binding_cannot_be_adopted(self):
        with self.lock.held():
            owner=self.owner();owner.read();frame=next(self.artifacts.glob('avatar-frame-*.json'))
            with self.assertRaises(NativeUIError):self.owner(historical=True,binding=BINDING|dict(artifactSha256='0'*64))
            original=frame.read_bytes();frame.unlink();frame.write_bytes(original);os.chmod(frame,0o600)
            with self.assertRaises(NativeUIError):self.owner(historical=True)
    def test_inconsistent_current_Pal_root_and_widget_or_retired_source_cannot_supply_frame(self):
        with self.lock.held():
            owner=self.owner();frame=owner.read()
            for fault in ('people-active','source-version','clock','source-hash'):
                changed=deepcopy(frame)
                if fault=='people-active':changed['originals']['people']['source']['roots'][0].update(visible=True,active=True)
                elif fault=='source-version':changed['originals']['state']['iosAvatarStateVersion']=1;del changed['originals']['state']['source']['bookmarkFile']
                elif fault=='clock':changed['originals']['state']['clockBefore']['epochMs']=1
                else:changed['acquisitions']['state']['originalSha256']='0'*64
                if fault!='source-hash':
                    from adapters.native_clock_join import digest
                    changed['clockJoin']['originalsSha256']=digest(changed['originals'])
                    for name in CHANNELS:changed['acquisitions'][name]['originalSha256']=digest(changed['originals'][name])
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.validate_frame(changed)


if __name__=='__main__':unittest.main()
