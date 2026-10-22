"""Private browser owner and original source protocols; SDK/DOM/Java effects are explicit seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_web_runtime import NativeWebRuntime
from adapters.normal_ui import NativeUIError
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.pico4.tablet_web_binding import PicoTabletWebBinding
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.scenarios import VERSION
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.witness import Client,Journal
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary

RUN='b'*32;TICKET='c'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
FOREIGN='http://foreign.invalid/feature-fixture/v1'
SCENE='http://controlled.invalid/scene.json'


class Original:
    def __init__(self,path):
        self.root=path;self.pico_configuration=('explicit-host-test',path);self.host=0.;self.epoch=20000
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:456',sessionId='session',generation=1,targetFingerprint='c'*64)
        self.lock=ScriptSourceLock(path/'script-sources.lock');self.owner=None;self.sequence=0;self.packet=None;self.commands=[]
        self.features=FeatureBoundary();self.features.mutate=lambda value:value.update(processId=31)
        self.feature_sequence=0;self.service_sequence=0;self.runtime_sequence=0;self.runtime_packet=None;self.fail_reserve=False
        self.installed={key:self.binding[key] for key in ('sourceRevision','artifactSha256')}
        self.adb=SimpleNamespace(foreground_package=lambda target:'org.overte.pico')
    def _script_journey(self):return SimpleNamespace(_lock=self.source_lock)
    def source_lock(self,target,provided=None):
        if provided is not None:need(provided is self.lock)
        return self.lock
    def _installation(self,target):return deepcopy(self.installed)
    def require_controlled_debug_identity(self,target):return self.binding['processIdentity']
    def require_pico_session_identity(self,target):return self.binding['processIdentity']
    def _script_runtime(self,target):return None,self.service,deepcopy(self.binding)
    def service(self,after):
        self.service_sequence=max(after+1,self.service_sequence+1)
        return dict(schemaVersion=1,instance='a'*32,sampleSequence=self.service_sequence,sampleEpochMs=self.epoch,complete=True,scripts=[]),self.epoch
    def guard(self):return True
    def sleep(self,seconds):self.host+=seconds;self.epoch+=round(seconds*1000)
    def _native_feature_observer(self,target):
        return NativeFeatureObservation(self.features.send,self.features.original,lambda:self.epoch,self.guard,31,
            monotonic=lambda:self.host,sleep=self.sleep)
    def _browser_originals(self,target,*,source_lock,tablet,read_only):
        need(tablet and source_lock is self.lock)
        return PicoTabletBrowserIO(self.send,lambda:json.dumps(self.packet),lambda:self.epoch,self.guard,31,
            source_lock=self.lock,read_only=read_only,monotonic=lambda:self.host,sleep=self.sleep)
    def send(self,command):
        self.commands.append(deepcopy(command));self.sequence+=1
        if command['operation']=='reserve':
            need(self.owner is None);self.owner=command['ownerToken'];source={'reserved':True}
            if self.fail_reserve:raise NativeUIError('Original reserve delivery return lost')
        elif command['operation']=='observe':
            need(self.owner==command['ownerToken'])
            source=dict(retired=False,documents=[],requests=[],replies=[],inputs=[],domHistory={},current={},
                deferred=dict(armed=False,pending=False,held=None,deliveries=[]))
        else:raise NativeUIError('Explicit original baseline producer has no product input implementation')
        self.packet=dict(picoBrowserVersion=2,commandId=command['commandId'],runId=RUN,ownerToken=self.owner,instance='d'*32,
            sequence=self.sequence,processId=31,capturedEpochMs=self.epoch,status='ready',source=source)
    def _web_runtime_observer(self,target):
        def send(command):
            self.runtime_sequence+=1
            native=dict(capturedEpochMs=self.epoch,complete=True,knownHandles=[],views=[])
            java=dict(javaWebRuntimeVersion=2,commandId=command['commandId'],instance='e'*32,sequence=self.runtime_sequence,
                processId=31,capturedEpochMs=self.epoch,complete=True,views=[],creations=[],renderers=[])
            self.runtime_packet=dict(webRuntimeVersion=2,commandId=command['commandId'],runId=RUN,instance='f'*32,
                sequence=self.runtime_sequence,processId=31,capturedEpochMs=self.epoch,status='ready',
                source=dict(nativeBefore=deepcopy(native),nativeAfter=deepcopy(native),java=java))
        return NativeWebRuntime(send,lambda:json.dumps(self.runtime_packet),lambda:self.epoch,self.guard,31,
            require_renderers=True,monotonic=lambda:self.host,sleep=self.sleep)


def need(value):
    if not value:raise NativeUIError('Explicit original boundary mismatch')


class PicoTabletWebFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700);self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.original=Original(self.root);self.journal=Journal(lambda:self.original.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('tablet-web')
        self.journal.activate(RUN,TICKET);self.publications=[];self.lose_pub=False
        with patch('adapters.pico4.tablet_web_binding.configuration',return_value=SCENE):self.binding=PicoTabletWebBinding(self.original)
    def client(self,*,actor=False):
        client=Client(URL.rsplit('/runs/',1)[0],('p' if actor else 'r')*64)
        def request(path,value=None,**kwargs):
            if path.endswith('/phase'):return self.journal.phase(RUN,kwargs['phase_nonce'])
            if path.endswith('/browser'):return dict(browserFixtureVersion=1,instance='1'*32,ready=False,sequence=0,responses=[])
            if path.endswith('/samples'):
                need(actor);self.publications.append(deepcopy(value));self.journal.publish(RUN,value)
                if self.lose_pub:raise NativeUIError('Original publisher reply lost')
                return {}
            raise AssertionError(path)
        client.request=request;return client
    def flow(self,*,actor=False):
        source=PhaseFixtureReader(self.client(actor=actor),RUN,'tablet-web',epoch_ms=lambda:self.original.epoch,
            monotonic=lambda:self.original.host)
        return self.binding.feature('owned',source,self.artifacts,FOREIGN,role='actor' if actor else 'primary')
    def test_original_reservation_baseline_and_independent_actor_use_distinct_role_files(self):
        primary=self.flow();owner=primary.prepare();self.assertTrue(owner['reserved'])
        self.assertEqual(1,len(owner['inputs']));self.assertTrue(owner['inputs'][0]['complete'])
        value=primary.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0));self.assertFalse(value['state']['open']);self.assertEqual([],value['resources'])
        actor=self.flow(actor=True);observed=actor.publish();self.assertFalse(observed['state']['open'])
        self.assertEqual(1,len(self.publications));self.assertNotEqual(primary.role_store.path,actor.role_store.path)
        self.assertEqual(1,len([row for row in self.original.commands if row['operation']=='reserve']))
        self.assertIs(primary.lock,self.original.lock);self.assertEqual('tablet-web',primary.adapter.state_area)
    def test_lost_original_reservation_is_retained_across_cold_reconstruction_without_resend(self):
        self.original.fail_reserve=True
        with self.assertRaises((ValueError,RuntimeError)):self.flow().prepare()
        self.original.fail_reserve=False;before=len(self.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):self.flow().prepare()
        self.assertEqual(before,len(self.original.commands))
        flow=self.flow()
        with flow.lock.held():
            owner=flow.owner();self.assertFalse(owner['reserved']);self.assertFalse(owner['inputs'][0]['complete'])

    def test_rootless_vm_quiet_or_actor_originals_refuse_before_new_reservation(self):
        from adapters.normal_feature_state import PrivateFeatureState
        for index,name in enumerate(('pico-tablet-web-primary-vm.json.frame-000.json',
                'pico-tablet-web-cleanup-quiet.json.frame-000.json','pico-tablet-web-actor.json')):
            source=PhaseFixtureReader(self.client(),RUN,'tablet-web',epoch_ms=lambda:self.original.epoch,monotonic=lambda:self.original.host)
            flow=self.binding.feature('orphan-'+str(index),source,self.artifacts,FOREIGN)
            child=PrivateFeatureState(flow.store.path.with_name(name));child.write(dict(original='unresolved'),None)
            before=len(self.original.commands)
            with self.subTest(name=name),self.assertRaises((ValueError,RuntimeError)):flow.prepare()
            self.assertEqual(before,len(self.original.commands));self.assertEqual(dict(original='unresolved'),child.read())
    def test_lost_original_publication_is_durable_and_not_resent_after_reconstruction(self):
        primary=self.flow();primary.prepare();self.lose_pub=True
        with self.assertRaises((ValueError,RuntimeError)):self.flow(actor=True).publish()
        before=len(self.original.commands);self.lose_pub=False
        with self.assertRaises((ValueError,RuntimeError)):self.flow(actor=True).publish()
        self.assertEqual(before,len(self.original.commands));self.assertEqual(1,len(self.publications))
        actor=self.flow(actor=True)
        with actor.lock.held():self.assertEqual('issued',actor.role_state()['publication']['phase'])

    def test_last_owner_cas_cannot_age_fixture_admission_before_original_source_writer(self):
        for native in (False,True):
            with self.subTest(native=native):
                # A fresh target namespace keeps the original pending scope
                # independent; no source or replay cursor is reset.
                target='native-jump' if native else 'host-gap'
                source=PhaseFixtureReader(self.client(),RUN,'tablet-web',epoch_ms=lambda:self.original.epoch,monotonic=lambda:self.original.host)
                flow=self.binding.feature(target,source,self.artifacts,FOREIGN)
                original_write=flow.store.write
                def write(value,previous):
                    original_write(value,previous)
                    if value['kind']=='owner' and value['payload']:
                        if native:self.original.epoch+=2000
                        else:self.original.host+=2
                before=len(self.original.commands)
                with patch.object(flow.store,'write',side_effect=write),self.assertRaises((ValueError,RuntimeError)):flow.prepare()
                self.assertEqual(before,len(self.original.commands));self.assertIsNotNone(flow.store.read())

    def test_actor_ticket_and_payload_cannot_be_relabelled_after_original_publication(self):
        primary=self.flow();primary.prepare();actor=self.flow(actor=True);actor.publish()
        with actor.lock.held():
            state=actor.role_state();state['publication']['payload']['ticket']='9'*32
            actor.write(actor.role_store,'actor',state)
            with self.assertRaises((ValueError,RuntimeError)):self.flow(actor=True).role_state()

    def stalled_observation(self,*,actor,native):
        primary=self.flow();primary.prepare();flow=self.flow(actor=actor)
        original_write=flow.role_store.write
        def write(value,previous):
            original_write(value,previous)
            from adapters.script_journey.history import unpack
            state=unpack(value['payload'])[0]
            if not actor or state['publication'] is not None:
                if native:self.original.epoch+=2000
                else:self.original.host+=2
        with patch.object(flow.role_store,'write',side_effect=write),self.assertRaises((ValueError,RuntimeError)):
            if actor:flow.publish()
            else:flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertIsNotNone(flow.role_store.read());self.assertEqual([],self.publications)
        if actor:
            with flow.lock.held():self.assertEqual('issued',flow.role_state()['publication']['phase'])
            before=len(self.original.commands)
            with self.assertRaises((ValueError,RuntimeError)):self.flow(actor=True).publish()
            self.assertEqual(before,len(self.original.commands))

    def test_final_primary_cas_cannot_renew_observations_after_host_delay(self):
        self.stalled_observation(actor=False,native=False)

    def test_final_primary_cas_cannot_renew_observations_after_native_jump(self):
        self.stalled_observation(actor=False,native=True)

    def test_actor_intent_cas_cannot_publish_stale_sources_after_host_delay(self):
        self.stalled_observation(actor=True,native=False)

    def test_actor_intent_cas_cannot_publish_stale_sources_after_native_jump(self):
        self.stalled_observation(actor=True,native=True)

    def test_fixture_activation_after_final_cas_cannot_release_previous_ticket_sample(self):
        flow=self.flow();flow.prepare();original_write=flow.role_store.write
        def write(value,previous):
            original_write(value,previous);self.journal.activate(RUN,'2'*32)
        with patch.object(flow.role_store,'write',side_effect=write),self.assertRaises((ValueError,RuntimeError)):
            flow.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
        self.assertIsNotNone(flow.role_store.read());self.assertEqual([],self.publications)

    def test_private_composition_cannot_finalize_without_original_vm_and_capture_join(self):
        flow=self.flow();flow.prepare();before=flow.store.read();commands=len(self.original.commands)
        with self.assertRaises((ValueError,RuntimeError)):flow.finalize()
        self.assertEqual(before,flow.store.read());self.assertEqual(commands,len(self.original.commands))

    def test_replaced_identical_metadata_bytes_cannot_adopt_original_inode(self):
        flow=self.flow();path=self.artifacts/'original.native.json';path.write_bytes(b'{}');path.chmod(0o600)
        raw,tag=flow.metadata(path.name);self.assertEqual(b'{}',raw)
        replacement=self.artifacts/'replacement';replacement.write_bytes(raw);replacement.chmod(0o600)
        os.replace(replacement,path)
        with self.assertRaises((ValueError,RuntimeError)):flow.metadata(path.name,tag)

    def test_same_inode_rewrite_cannot_adopt_original_metadata_stamp(self):
        flow=self.flow();path=self.artifacts/'original.native.json';path.write_bytes(b'{}');path.chmod(0o600)
        raw,tag=flow.metadata(path.name);path.write_bytes(raw)
        os.utime(path,ns=(tag['mtimeNs']+1000000,tag['mtimeNs']+1000000))
        with self.assertRaises((ValueError,RuntimeError)):flow.metadata(path.name,tag)

    def window(self,*,step=.1,frozen=False):
        from adapters.pico4.browser_quiet import append
        flow=self.flow();flow.prepare();window=None
        reader=self.original._web_runtime_observer('owned');native=None
        with flow.lock.held():
            owner=flow.owner()
            for index in range(31):
                if index:
                    self.original.host+=step
                    if not frozen:self.original.epoch+=round(step*1000)
                native=flow.sample_native(owner,native);runtime=reader.read(RUN,URL)
                window=append(window,native,runtime,self.original.host,RUN,URL,owner['ownerToken'],31,retired=False)
        return window

    def test_quiet_requires_all_original_clocks_and_continuous_cadence_for_three_seconds(self):
        self.assertTrue(self.window()['complete'])

    def test_frozen_native_clocks_or_actual_long_observation_gap_cannot_complete_host_quiet(self):
        for frozen in (False,True):
            with self.subTest(frozen=frozen),self.assertRaises((ValueError,RuntimeError)):
                self.window(step=.1 if frozen else .6,frozen=frozen)

    def test_never_observed_native_scope_cannot_hide_a_still_owned_java_renderer(self):
        from adapters.pico4.browser_quiet import frame
        flow=self.flow();flow.prepare()
        with flow.lock.held():
            owner=flow.owner();native=flow.sample_native(owner);runtime=self.original._web_runtime_observer('owned').read(RUN,URL)
        runtime['source']['java']['renderers']=[dict(id='2'*32,handle='42',creation=1,sourceOwned=True,sourceSha256='3'*64,
            objectAlive=True,threadAlive=True,mainCallbacks=0,glCallbacks=0,retainedCallbacks=0,closed=False,released=False,releaseSucceeded=True)]
        with self.assertRaises((ValueError,RuntimeError)):frame(dict(host=0.,browser=native,runtime=runtime),RUN,URL,owner['ownerToken'],31,retired=False)

    def test_actor_cannot_issue_original_input_and_pending_parent_prevents_publication(self):
        primary=self.flow();primary.prepare();actor=self.flow(actor=True)
        with actor.lock.held():
            actor.owner()
            with self.assertRaises((ValueError,RuntimeError)):actor.io(actor.live_owner,read_only=False)
        with primary.lock.held():
            owner=primary.owner();owner['phase']='acting';primary.save(owner)
        before=len(self.original.commands)
        with self.assertRaises(PhasePending):actor.publish()
        self.assertEqual(before,len(self.original.commands));self.assertEqual([],self.publications)


if __name__=='__main__':unittest.main()
