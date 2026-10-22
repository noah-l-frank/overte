"""Real paired owners/locks/receipts; unavailable app/device SDKs are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.retirement_receipts import PhaseRetirementJournal
from feature_journeys.witness import Client
from ios.adapters.create_actor_facts import CreateActorFacts
from ios.adapters.create_feature import IOSCreateFeature
from ios.adapters.create_runtime import IOSCreateRuntime
from ios.adapters.create_sources import CreateSources
from ios.adapters.peer_admission import admit_existing_peer
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.self_tests.create_whole_fixture import ComposedCreate
from ios.self_tests import test_ios_create_retirement as actors
from ios.self_tests import test_ios_create_primary_images as image_fixture
from ios.self_tests import test_ios_installed_code as installed
from ios.self_tests.test_ios_create_files import BINDING,URL
from ios.self_tests.test_ios_create_state import RUN


class CreateFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f=ComposedCreate(self);self.a=actors.CreateRetirementTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
        f,a=self.f,self.a;self.posts=[];self.lose=False;self.receipts=PhaseRetirementJournal(f.journal)
        for harness in (a.h.primary_h,a.h.peer_h):
            harness.sdk.shared=f.clock;harness.sdk.__class__=image_fixture.ClockedSDK
        for source,harness in ((a.h.primary,a.h.primary_h),(a.h.peer,a.h.peer_h)):
            source.epoch_ms=harness.sdk.epoch;source.phase.epoch_ms=harness.sdk.epoch
            for reader in source.readers.values():reader.clock_ms=harness.sdk.tick
        a.pointer.clock_ms=a.h.peer_h.sdk.tick
        def request(path,value=None,method=None,**kwargs):
            f.domain.time+=.001
            if path.endswith('/phase'):return f.journal.phase(RUN,kwargs['phase_nonce'])
            if path.endswith('/retirements'):
                if value is not None:
                    self.posts.append(deepcopy(value));self.receipts.publish(RUN,value)
                    if self.lose:raise OSError('Lost genuine committed Actor retirement reply')
                    return {}
                return self.receipts.snapshot(RUN)
            if path.endswith('/samples'):
                if value is not None:f.journal.publish(RUN,value);return {}
                return f.journal.snapshot(RUN)
            raise AssertionError('Unexpected fixture route')
        self.client=Client(URL.split('/runs/')[0],'r'*64);self.client.request=request
        f.source.phase.client=self.client
        primary_phase=PhaseFixtureReader(self.client,RUN,'create',epoch_ms=f.clock.epoch,monotonic=lambda:f.clock.clock)
        self.actor_primary=CreateSources(PrivateFeatureState(f.root/'ios-create-actor-primary-sources.json'),f.lock,BINDING,RUN,'actor-primary',f.source.scripts_root,
            lambda:True,phase=primary_phase,readers=f.source.readers,epoch_ms=f.clock.epoch,monotonic=lambda:f.clock.clock)
        a.h.peer.phase.client=self.client
        class Runtime(IOSCreateRuntime):
            def state_path(_self,selector):return (f.root if selector=='primary' else a.h.peer_h.root)/'session.json'
            @contextmanager
            def existing_input_session(_self,_selector):yield
        self.runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True))
        self.primary=self.flow('primary');self.actor=self.flow('actor');self.primary.lock=f.lock;self.primary.primary_lock=f.lock
        self.actor.lock=a.h.peer_h.lock;self.actor.primary_lock=f.lock
        self.f.held.__exit__(None,None,None)
        # Installed-code/process originals are admitted before any marker setup;
        # this seam models already prepared SDKs, never a new session or install.
        prepared=installed.InstalledCodeTests();prepared.setUp();self.addCleanup(prepared.doCleanups)
        prepared.scope={key:value for key,value in a.h.peer_binding.items() if key!='processIdentity'}
        prepared.process['pid']=43;prepared.native.clock_source['processId']=43;prepared.reader.pid=43
        prepared.native.mutate=lambda packet:packet.update(processId=43);prepared.binding=prepared.make();prepared.active()
        sdk=object.__new__(IOSScriptRuntime);sdk._existing=lambda _: (None,prepared.scope['sessionId'],{}, {},deepcopy(prepared.scope))
        sdk.adapter=SimpleNamespace(_binding=lambda *_args:prepared.make())
        admission=admit_existing_peer(sdk,'actor',BINDING,epoch_ms=f.clock.epoch,monotonic=lambda:f.clock.clock)
        self.parts_primary=dict(own=dict(check=lambda:True),source=f.source,history=f.history,scope=f.scope,retirement=f.retirement)
        error=None
        with self.actor.held():
            try:
                self.facts=CreateActorFacts(a.h.store,a.h.peer_h.lock,RUN,self.actor_primary,a.h.peer,lambda:True);self.facts.capture()
                self.whole_actor=a.owner(self.facts);self.whole_actor.admit()
            except Exception as caught:error=caught
        if error is not None:raise error
        self.parts_actor=dict(own=dict(check=lambda:True),source=a.h.peer,history=self.facts,retirement=self.whole_actor)
        for flow,parts,binding in ((self.primary,self.parts_primary,BINDING),(self.actor,self.parts_actor,a.h.peer_binding)):
            flow.phase=parts['source'].phase;flow.phase.client=self.client
            flow.parts=lambda parts=parts:parts
            with flow.held():
                flow.state=dict(phase='ready',binding=deepcopy(binding),primaryBinding=deepcopy(BINDING),phaseInstance=f.journal.phase_instance,
                    initialTicket='1'*32,actorAdmission=admission if flow.role=='primary' else None,
                    beforeImage=f.before.request if flow.role=='primary' else None,images=[],exports=[],retirement=None);flow.save()
            def ensure(flow=flow,parts=parts):flow.load();return parts,flow.phase.read()
            flow.ensure=ensure
        with f.lock.held():f.scope.prepare();f.domain.paint();f.scope.admit_rendered()
        f.journal.activate(RUN,'2'*32,'cleanup',{})
    def flow(self,role):
        f=self.f;config=dict(artifactRoot=str(f.root),imagePolicy=dict(source='world-render-target',marker=[0,0,128,64],subject=[128,64,640,400]))
        if role=='primary':config.update(actorTarget='actor',rezAuthority=dict(controlUrl='http://127.0.0.1:43210/v1/create-rez',token='t'*64,
            domainId='00000000-0000-4000-8000-000000000001'))
        else:config['primaryTarget']='primary'
        return IOSCreateFeature(self.runtime,role,self.client,RUN,role,config,epoch_ms=f.clock.epoch,monotonic=lambda:f.clock.clock,sleep=f.domain.sleep)
    def call(self):return dict(contractVersion=16,runId=RUN)
    def pair(self):
        f=self.f;actor=self.actor
        def independent(_seconds):
            # A different lock instance must acquire Primary's real OS inode.
            # If cleanup still held it, this would be genuine contention.
            from adapters.script_feature.lock import ScriptSourceLock
            probe=ScriptSourceLock(f.lock.path,timeout=.05)
            with probe.held():pass
            actor.cleanup(self.call());f.domain.sleep(.15)
        self.primary.sleep=independent;self.primary.cleanup(self.call())
    def test_actual_two_role_retirement_repeats_read_only_then_inactive_final_archive_uses_no_sdk(self):
        self.pair();self.assertEqual(1,len(self.posts));self.assertFalse(self.f.domain.running)
        self.assertEqual(1,self.f.domain.io.actions.count('scripts.stop.0'))
        with self.primary.held():self.primary.load();first=deepcopy(self.primary.state['retirement'])
        self.actor.cleanup(self.call());self.primary.cleanup(self.call());self.assertEqual(2,len(self.posts))
        with self.primary.held():
            self.primary.load();second=deepcopy(self.primary.state['retirement']);self.assertEqual('paired',self.primary.state['phase'])
        self.assertGreater(second['peerReceipt']['entry']['actorSequence'],first['peerReceipt']['entry']['actorSequence'])
        self.assertEqual(1,self.f.domain.io.actions.count('scripts.stop.0'))
        # A different, genuine normal Facts publication loses its committed
        # reply. It remains issued until the inactive original retires it;
        # no old sample POST may be replayed by finalization.
        request=self.client.request;sample_posts=[]
        def lost_sample(path,value=None,method=None,**kwargs):
            result=request(path,value,method,**kwargs)
            if path.endswith('/samples') and value is not None:
                sample_posts.append(deepcopy(value));raise OSError('Lost actual committed normal sample reply')
            return result
        self.client.request=lost_sample
        with self.actor.held(),self.assertRaises(OSError):self.facts.publish(marker_active=False)
        self.assertEqual(1,len(sample_posts))
        self.f.journal.close(RUN);self.primary.cleanup(self.call());self.actor.publish()
        self.assertEqual(1,len(sample_posts))
        from ios.adapters.create_finalization import finalize_existing
        checked=[];self.runtime.adapter._retired_candidate_scope=lambda selector,scope:checked.append((selector,deepcopy(scope)))
        for selector in ('primary','actor'):self.assertTrue(finalize_existing(self.runtime,selector,None,None))
        self.assertEqual(2,len(checked))
        with self.actor.held():
            self.actor.load()
            from ios.adapters.create_final_archive import CreateFinalArchive
            archive=CreateFinalArchive(PrivateFeatureState(self.actor.store.path.with_name('ios-create-actor-'+RUN+'-final.json')),
                self.actor.root,self.actor.state['binding'],RUN,'actor',self.actor.lock)
            self.assertTrue(any('/phase-publication-create-' in row['path'] for row in archive.verify()['files']))

        def forbidden(*_args,**_kwargs):raise AssertionError('Finalized Create flow queried an SDK or fixture')
        self.primary.parts=self.actor.parts=forbidden;self.client.request=forbidden
        self.assertEqual({'performed':True},self.primary.cleanup(self.call()));self.assertEqual({'performed':True},self.actor.publish())
        # A valid-shaped mutation of another actual coordinator field cannot
        # borrow the already sealed cleanup proof, including the direct flow.
        with self.primary.held():
            self.primary.load();original=deepcopy(self.primary.state)
            self.primary.state['images'].append('ios-'+'f'*32);self.primary.save()
        with self.assertRaises(NativeUIError):self.primary.cleanup(self.call())
        with self.primary.held():self.primary.load();self.primary.state=original;self.primary.save()
        genuine=self.primary.store.read()
        for key,changed in (('fixtureUrl','https://other.invalid/runs/'+RUN+'/'),
                            ('imagePolicy',dict(self.primary.policy,subject=[0,64,128,128]))):
            altered=dict(genuine,**{key:changed});self.primary.store.write(altered,genuine)
            with self.subTest(header=key),self.assertRaises(NativeUIError):finalize_existing(self.runtime,'primary',None,None)
            self.primary.store.write(genuine,altered)
    def test_lost_committed_actor_retirement_is_resolved_without_another_input_or_post(self):
        self.lose=True
        with self.assertRaises((OSError,NativeUIError)):self.actor.cleanup(self.call())
        self.assertEqual(1,len(self.posts));self.lose=False
        # Explicit readonly resolution of the original durable issued POST.
        with self.actor.held():
            self.actor.load();parts=self.actor.parts();original=self.whole_actor.original()
            self.actor.publish_retirement(parts,original)
        self.assertEqual(1,len(self.posts))


if __name__=='__main__':unittest.main()
