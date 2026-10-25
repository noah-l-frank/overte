"""Composed whole preparation; only native/Qt/GPU boundaries are modeled.

OAuth/profile/protected replies use an actual loopback HTTPS service. The actual
normal staged marker Script executes in Node, and source/peer/PNG owners retain
original private files. No adapter verdict or decoder is replaced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import hashlib
import json
import secrets
import threading
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import build_opener,HTTPSHandler,ProxyHandler
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.native_avatar_receive import NativeAvatarReceive
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from feature_journeys import witness
from feature_journeys.account_provider import AccountProvider
from feature_journeys.avatar_social_http import account_authenticator
from feature_journeys.avatar_social_provider import AvatarSocialProvider
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.server import make_server
from ios.adapters import authentication_runtime,script_runtime,normal_input,feature_observation,avatar_feature
from ios.adapters.authentication_runtime import IOSLoginControls
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner
from ios.adapters.avatar_marker_files import OwnedAvatarMarkerFiles
from ios.adapters.avatar_originals import IOSAvatarOriginals
from ios.adapters.avatar_peer import session_sha
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.self_tests import authentication_native_boundary as auth
from ios.self_tests import test_ios_installed_code as installed
from ios.self_tests.test_ios_emote_peer import acquisition as peer_template
from ios.self_tests.avatar_scene_fixture import SceneDomain
from self_tests.test_native_avatar_receive import Boundary as Receiver
from self_tests import test_account_provider as tls

from ios.self_tests.test_ios_emote_sources import RUN
TICKET='b'*32
SESSIONS=dict(primary='00000000-0000-4000-8000-000000000001',actor='00000000-0000-4000-8000-000000000002')


class PrepareDomain:
    HELD_MARKER=True
    def __init__(self,test):
        self.test=test;self.clock=[1.];self.scenes={};self.natives={};self.installed={};self.receivers={};self.peer_sequences={};self.role_by_url={}
        self.provider=AccountProvider(epoch_ms=self.host)
        self.social=AvatarSocialProvider(account_authenticator(self.provider),epoch_ms=self.host,monotonic=lambda:self.clock[0])
        self.reader,self.actor,self.adapter=[secrets.token_hex(32) for _ in range(3)]
        self.server=make_server(self.reader,self.actor,account_provider=self.provider,avatar_social_provider=self.social,
            adapter_token=self.adapter,tls_context=tls.AccountProviderTests.server_context)
        self.server.journal.clock=self.host;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        test.addCleanup(self.stop);self.origin='https://localhost:'+str(self.server.server_port)
        self.opener=build_opener(ProxyHandler({}),HTTPSHandler(context=tls.AccountProviderTests.client_context),witness.NoRedirect())
        # Direct fixture-owner registration separates the closed run ID from
        # its independently generated child credentials, before any SDK data.
        with patch.object(secrets,'token_hex',return_value=RUN):self.server.journal.register('avatar-people')
        self.server.avatar_accounts.provision(RUN)
        self.client=witness.Client(self.origin+'/feature-fixture/v1',self.reader);self.client.run=RUN
        self.primary_client=AdapterFixtureClient(self.client.url,self.adapter)
        opener=patch.object(witness,'build_opener',return_value=self.opener);opener.start();test.addCleanup(opener.stop)
        self.client.activate(TICKET)
        outer=self
        for role in ('primary','actor'):
            scene=SceneDomain(test,held=self.HELD_MARKER);self.scenes[role]=scene;d,s=scene.domain,scene.scope
            from contextlib import nullcontext
            scene.setup.fixture.held.__exit__(None,None,None);scene.setup.fixture.held=nullcontext()
            class Native(auth.Native):
                @property
                def clock(_self):return outer.clock[0]
                @clock.setter
                def clock(_self,value):outer.clock[0]=value
                @property
                def shown(_self):return _self.scene.domain.io.qt.opened if hasattr(_self,'scene') else False
                @shown.setter
                def shown(_self,value):
                    if hasattr(_self,'scene'):_self.scene.domain.io.qt.opened=value
                def scope(_self):
                    result=super().scope();result['sessionId']=_self.state['sessionId'];return result
                def execute(_self,session,operation,values):
                    test.assertEqual(_self.state['sessionId'],session);return super().execute('owned-session',operation,values)
                def call(_self,method,path,body=None):return super().call(method,path.replace('/session/'+_self.state['sessionId'],'/session/owned-session'),body)
            admitted_clock=self.clock[0];n=Native(s.root,self.origin,self.opener);self.clock[0]=admitted_clock;n.scene=scene;n.pid=31;n.birth=('b' if role=='primary' else 'd')*32;n.state.update(processIdentity='31',sessionId='sdk-'+role)
            n.target['serverUrl']='http://'+role+'.sdk.invalid:4723';n.target['testBuild']['fixtureOrigin']='http://'+role+'.transport.invalid:49121'
            n.state['targetFingerprint']=n.fingerprint();self.natives[role]=n;self.role_by_url[n.target['serverUrl']]=role
            class SharedDomain(type(d)):
                @property
                def time(_self):return outer.clock[0]
                @time.setter
                def time(_self,value):outer.clock[0]=value
            d.__class__=SharedDomain;d.epoch=n.epoch
            # Source-native offsets are assigned to modeled producers before
            # their first original. No retained packet is rewritten or retimed.
            scene.native_epoch_offset=n.epoch()-round(n.clock*1000)
            binding=dict(n.scope(),processIdentity='31');s.binding=binding;s.pid=31;s.role=role
            s.run=RUN;s.ticket=TICKET;s.fixture_url=self.client.url+'/runs/'+RUN+'/'
            s.store=PrivateFeatureState(s.root/('ios-avatar-'+role+'-marker.json'))
            s.files=OwnedAvatarMarkerFiles(d.files,PrivateFeatureState(s.root/('ios-avatar-'+role+'-marker-files.json')),binding)
            s.originals=IOSAvatarOriginals(s.root,binding,RUN,role,s.guard,s.storage_intent,kind='inputs')
            s.epoch_ms=self.host;s.monotonic=lambda:self.clock[0];s.sleep=n.sleep
            # All native feature packets share the actual account producer and
            # the original marker-domain evaluated-frame history.
            base=n.feature.send
            wrapper_type=type('NativeFeatureFor'+role,(),{'send':lambda _self,q,base=base:base(q),
                'sample':property(lambda _self,n=n:n.feature.sample),'original':lambda _self,n=n:n.feature.original()})
            d.boundary=wrapper_type();n.feature.send=d.native_send
            def native(bound=True,n=n,d=d):return NativeFeatureObservation(d.native_send,n.feature.original,n.epoch,lambda:True,31,ios=True,
                native_clock_bound=bound,monotonic=lambda:self.clock[0],sleep=n.sleep)
            scene.native=native;scene.f.native=native;s.native=native();scene.f.now=n.epoch;scene.f.host=self.host;scene.f.run=RUN
            # Retained history timestamps precede this process' first emitted
            # capture. Every subsequent current timestamp comes from the source.
            def epochs(v):
                if type(v) is dict:
                    for key,item in v.items():
                        if key.endswith('EpochMs') and type(item) in (int,float) and item>0:yield item
                        yield from epochs(item)
                elif type(v) is list:
                    for item in v:yield from epochs(item)
            offset=scene.native_epoch_offset-100000-max(epochs(scene.f.prototypes))
            def seed(v):
                if type(v) is dict:return {k:item+offset if k.endswith('EpochMs') and type(item) in (int,float) and item>0 else seed(item) for k,item in v.items()}
                if type(v) is list:return [seed(item) for item in v]
                return v
            scene.f.prototypes=seed(scene.f.prototypes);scene.f.prototypes['state']['source']['sessionId']=SESSIONS[role]
            d.identity=SESSIONS[role];d.world_template['source']['domain']['selfSha256']=session_sha(SESSIONS[role])
            for row in scene.f.prototypes['renderers']['source']['avatars']:row['self']=row['sessionId']==SESSIONS[role]
            old_web=d.web
            def web(run,url,d=d,old=old_web):
                if d.running and d.context is None:d.paint()
                return old(run,url)
            d.web=web;s.web.read=web
            gate=installed.InstalledCodeTests();gate.setUp();test.addCleanup(gate.doCleanups)
            gate.scope=deepcopy(n.scope());gate.process['pid']=31
            gate.native.clock_source=dict(processId=31,capturedEpochMs=n.epoch())
            gate.native.mutate=lambda value,n=n,offset=scene.native_epoch_offset:value.update(processId=31,capturedEpochMs=n.epoch(),preparedEpochMs=offset-1000)
            gate.reader.pid=31;gate.reader.native_clock=lambda n=n:dict(processId=31,capturedEpochMs=n.epoch())
            gate.binding=gate.make();gate.active();self.installed[role]=gate
            self.receivers[role]=Receiver();self.peer_sequences[role]=0
        # One adapter resolves only already existing independent SDK sessions.
        def native_for(selector):return self.natives[selector]
        def call(name):return lambda selector,*args,**kwargs:getattr(native_for(selector).base(),name)(selector,*args,**kwargs)
        adapter=SimpleNamespace(_candidate_guard=lambda **_:None,_operation=None,_session_recreation_forbidden=False,
            _binding=lambda selector,*_args:self.installed[selector].make(),_target=call('_target'),_scope=call('_scope'),read_session=call('read_session'),
            state_path=call('state_path'))
        for name in ('script_store','script_files_store','script_restart_store','script_restart_inputs_store'):setattr(adapter,name,call(name))
        class Runtime(IOSAvatarRuntime):
            def _sources(_self,selector):
                actual=super()._sources(selector);scene=outer.scenes[selector];clock=actual['clock_source']
                actual['observer'].avatar_world=lambda _clock:SimpleNamespace(last=None,read=scene.domain.world)
                actual['observer'].emote_world=lambda _clock:SimpleNamespace(last=None,read=lambda run:outer.peer_world(selector,run))
                actual['observer'].avatar_renderers=lambda _clock:scene.f.reader('renderers',__import__('ios.adapters.avatar_renderers',fromlist=['IOSAvatarRenderers']).IOSAvatarRenderers)
                actual['observer'].pointer_state=scene.pointer_reader;actual['observer'].script_fixture_files=scene.sources()['observer'].script_fixture_files
                actual['observer'].vulkan_world_frame=scene.vulkan
                return actual
            def _avatar_receive(_self,selector):
                receiver=outer.receivers[selector];n=outer.natives[selector]
                def send(query):
                    outer.clock[0]+=.001;receiver.send(query);value=receiver.current
                    value.update(processId=31,requestedEpochMs=n.epoch(),capturedEpochMs=n.epoch())
                    value['source'].update(processId=31,selfSha256=session_sha(SESSIONS[selector]))
                return NativeAvatarReceive(send,lambda:json.dumps(receiver.current),n.epoch,lambda:True,31,ios=True,
                    monotonic=lambda:outer.clock[0],sleep=outer.sleep)
            def _avatar_peer_sources(_self,selector,client,run,role,root,lock):
                return IOSAvatarPeerSources(PrivateFeatureState(_self.state_path(selector).with_name('ios-avatar-'+role+'-peer-sources.json')),root,
                    dict(outer.natives[selector].scope(),processIdentity='31'),run,
                    PhaseFixtureReader(client,run,'avatar-people',epoch_ms=outer.host,monotonic=lambda:outer.clock[0]),lock,lambda:True,
                    runtime=_self,selector=selector,role=role,epoch_ms=outer.host,monotonic=lambda:outer.clock[0])
            def _avatar_sources(_self,selector,client,run,role,root,lock):
                scene=outer.scenes[selector]
                return IOSAvatarSources(PrivateFeatureState(_self.state_path(selector).with_name('ios-avatar-'+role+'-sources.json')),root,
                    dict(outer.natives[selector].scope(),processIdentity='31'),run,role,lock,lambda:True,
                    PhaseFixtureReader(client,run,'avatar-people',epoch_ms=outer.host,monotonic=lambda:outer.clock[0]),readers=scene.readers(),
                    epoch_ms=outer.host,monotonic=lambda:outer.clock[0])
            def _avatar_marker_scope(_self,selector,client,run,role,root,ticket,lock):
                scene=outer.scenes[selector];s=scene.scope;s.lock=lock;return s
            def _avatar_held_marker_scope(_self,selector,client,run,role,root,ticket,lock):
                scene=outer.scenes[selector];s=scene.scope;s.lock=lock;return s
            def _avatar_marker_entities(_self,selector,scope,root,lock):
                owner=outer.scenes[selector].entity.owner();owner.lock=lock;return owner
            def _avatar_samples(_self,selector,scope,client,root,policy,lock):
                Samples=IOSAvatarSamples
                if outer.HELD_MARKER:
                    from ios.adapters.avatar_held_samples import IOSAvatarHeldSamples
                    Samples=IOSAvatarHeldSamples
                return Samples(_self,selector,scope,root,policy,
                    PhaseFixtureReader(client,run=RUN,area='avatar-people',epoch_ms=outer.host,monotonic=lambda:outer.clock[0]),lock,
                    epoch_ms=outer.host,monotonic=lambda:outer.clock[0],sleep=outer.sleep)
        self.runtime=Runtime(adapter)
        for boundary in (patch.object(script_runtime.backend,'WebDriver',side_effect=lambda url:self.natives[self.role_by_url[url]]),
            # These are the original boundary clocks for this explicit host
            # model, fixed before either unbound or bound native reader exists.
            # Production FeatureObservation defaults and saved DTOs stay intact.
            patch.object(script_runtime,'FeatureObservation',partial(feature_observation.FeatureObservation,
                monotonic=lambda:self.clock[0],sleep=self.sleep,epoch_ms=self.host)),
            patch.object(normal_input,'urlopen',side_effect=self.post),patch.object(feature_observation,'post_request',side_effect=self.post),
            patch.object(authentication_runtime,'NativeUI',partial(NativeUI,monotonic=lambda:self.clock[0],sleep=self.sleep)),
            patch.object(avatar_feature,'NativeUI',partial(NativeUI,monotonic=lambda:self.clock[0],sleep=self.sleep)),
            patch.object(authentication_runtime,'IOSLoginControls',partial(IOSLoginControls,monotonic=lambda:self.clock[0],sleep=self.sleep))):
            boundary.start();test.addCleanup(boundary.stop)
        self.owners={}
        for role in ('primary','actor'):
            config=dict(artifactRoot=str(self.scenes[role].root),imagePolicy=dict(source='world-render-target',marker=[0,0,32,32],subject=[64,64,96,96]),
                **{('actorTarget' if role=='primary' else 'primaryTarget'):('actor' if role=='primary' else 'primary')})
            if role=='actor':config['authorityRead']=dict(mode='adapter',token=self.adapter)
            client=self.client if role=='primary' else witness.Client(self.client.url,self.actor)
            self.owners[role]=IOSAvatarFeature(self.runtime,role,client,RUN,role,config,epoch_ms=self.host,monotonic=lambda:self.clock[0],sleep=self.sleep)
    def peer_world(self,selector,run):
        import uuid
        self.test.assertEqual(RUN,run);n=self.natives[selector];self.clock[0]+=.001
        sequence=self.peer_sequences[selector]+1;self.peer_sequences[selector]=sequence
        value=deepcopy(peer_template()['world']);value.update(runId=run,processId=31,requestId='ios-'+uuid.uuid4().hex,sequence=sequence)
        value['source']['scriptOriginal'].update(processId=31,requestedEpochMs=n.epoch(),capturedEpochMs=n.epoch())
        value['source']['domain'].update(selfSha256=session_sha(SESSIONS[selector]),avatarMixerSha256='c'*64)
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=n.epoch(),monotonicMs=round(self.clock[0]*1000))
        return value
    def host(self):return 1700000000000+round(self.clock[0]*1000)
    def sleep(self,seconds):
        self.clock[0]+=seconds
        for n in self.natives.values():n.poll()
        import time;time.sleep(.005)
    def post(self,request,timeout):
        role=request.full_url.split('://',1)[1].split('.',1)[0];return self.natives[role].post(request,timeout)
    def stop(self):
        self.provider.shutdown();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        for n in self.natives.values():n.close()
        self.test.assertFalse(self.thread.is_alive());self.test.assertEqual(0,self.server.internal_errors)
