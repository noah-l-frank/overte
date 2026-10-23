"""Real SDK/fixture HTTP and installed-code ownership, modeled live seal/OS.

This isolates final lifecycle mechanics. The full Navigation source/PNG seal is
explicitly a model here; its separate connected journey must qualify that graph.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import secrets
import threading
from types import SimpleNamespace
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import terminal as protocol
from feature_journeys.navigation_fixture import NavigationResources
from feature_journeys.navigation_scene import PROFILE
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.witness import projection
from ios.adapters import appium_adapter as backend
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.navigation_feature import IOSNavigationFeature
from ios.adapters.navigation_fixture import NavigationFixtureReader
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_terminal import NavigationTerminal
from ios.adapters.navigation_terminal_resources import binding as public_binding
from ios.self_tests.test_ios_installed_code import InstalledCodeTests
from ios.self_tests.test_ios_retired_process import Boundary
from self_tests.test_navigation_resources import INPUTS


class EndBoundary:
    def __init__(self,test):
        self.test=test;self.installed=InstalledCodeTests();self.installed.setUp();test.addCleanup(self.installed.doCleanups)
        self.installed.active();self.root=self.installed.store.path.parent;self.os=Boundary()
        self.good=self.exists=True;self.stop_lost=self.delete_lost=self.delete_ignored=False
        self.stops=0;self.requests=[];self.get_lost=False
        self.binding=dict(self.installed.scope,processIdentity='42');self.scope=deepcopy(self.installed.scope)
        self.sdk=PrivateFeatureState(self.root/'sdk-session.json');self.sdk.write(deepcopy(self.scope),None)
        self.payload=self.root/'modeled-navigation-original.json';self.payload.write_text('{"modeledLiveSeal":true}')
        self.payload.chmod(0o600);self.payload_bytes=self.payload.read_bytes()
        reader,actor=secrets.token_hex(32),secrets.token_hex(32)
        server=make_server(reader,actor);server.journal.clock=self.os.epoch
        origin='http://127.0.0.1:'+str(server.server_port)
        server.navigation_resources=NavigationResources(INPUTS|dict(sceneUrl=origin+'/navigation/scene.json'),clock_ms=self.os.epoch,scene_profile=PROFILE)
        self.start_server(server,test);self.controller=Client(origin+'/feature-fixture/v1',reader)
        self.run,_=self.controller.register('world-navigation');self.ticket='c'*32;self.controller.activate(self.ticket,'cleanup',{})
        self.fixture=NavigationFixtureReader(self.controller,self.run,epoch_ms=self.os.epoch,monotonic=lambda:self.os.clock);self.fixture.attach()
        outer=self
        class SDKHandler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def reply(self,status,value):
                raw=json.dumps(dict(value=value)).encode();self.send_response(status);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                outer.requests.append(('GET',self.path));test.assertEqual('/session/'+outer.binding['sessionId'],self.path)
                if outer.get_lost:outer.get_lost=False;self.connection.close();return
                self.reply(200 if outer.exists else 404,{} if outer.exists else dict(error='invalid session id',message='Gone'))
            def do_DELETE(self):
                outer.requests.append(('DELETE',self.path));test.assertEqual('/session/'+outer.binding['sessionId'],self.path)
                if not outer.delete_ignored:outer.exists=False
                if outer.delete_lost:self.connection.close();return
                self.reply(200,{})
            def do_POST(self):
                outer.requests.append(('POST',self.path));test.assertEqual('/session/'+outer.binding['sessionId']+'/execute/sync',self.path)
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if data['script']=='mobile: terminateApp':
                    test.assertEqual([dict(bundleId=outer.installed.native.bundle['bundleId'])],data['args']);outer.stops+=1
                    outer.installed.process=None
                    if outer.stop_lost:self.connection.close();return
                    self.reply(200,True)
                else:
                    test.assertEqual('mobile: overteRetiredProcessInfo',data['script']);self.reply(200,outer.os.send(data['args'][0]))
        sdk_server=ThreadingHTTPServer(('127.0.0.1',0),SDKHandler);self.start_server(sdk_server,test)
        self.target=dict(serverUrl='http://127.0.0.1:'+str(sdk_server.server_port),appId=self.installed.native.bundle['bundleId'])
        class Base:
            _operation=None;_session_recreation_forbidden=False
            def _candidate_guard(base,**_kwargs):need(outer.good)
            def state_path(base,_selector):return outer.sdk.path
            def read_session(base,_selector):return outer.sdk.read()
            def _target(base,_selector):return deepcopy(outer.target)
            def _scope(base,_selector,session,state,_target):
                need(session==outer.binding['sessionId'] and all(state[key]==value for key,value in outer.scope.items()));return deepcopy(outer.scope)
            def _binding(base,*_args):return outer.installed.make()
            def _binding_store(base,_selector):return outer.installed.store
            def _retired_candidate_scope(base,_selector,scope):need(same_scope(scope));return deepcopy(outer.target)
            def reset_launch_state(base,_selector,_state):pass
            def invoke(base,_selector,operation,values):
                test.assertEqual(('app.stop',{}),(operation,values));test.assertIsNone(base._operation);test.assertTrue(base._session_recreation_forbidden)
                gate=outer.installed.make();gate.begin_retirement()
                backend.WebDriver(outer.target['serverUrl']).execute(outer.binding['sessionId'],'mobile: terminateApp',dict(bundleId=outer.target['appId']))
                gate.finish_retirement();return dict(stopped=True)
        def same_scope(value):return value==outer.scope
        self.base=Base();self.runtime=IOSNavigationRuntime(self.base)
        flow=object.__new__(IOSNavigationFeature);flow.runtime=self.runtime;flow.selector='owned';flow.root=self.root;flow.run=self.run;flow.role='primary'
        flow.store=PrivateFeatureState(self.root/'modeled-navigation-parent.json');flow.fixture=self.fixture;flow.client=self.controller
        state=dict(stage=1,binding=self.binding,providerInstance=self.fixture.instance,providerInputs=self.fixture.inputs)
        flow.store.write(state,None)
        def load():flow.previous=flow.store.read();flow.state=deepcopy(flow.previous)
        flow.load=load;flow.load();flow.epoch_ms=self.os.epoch;flow.monotonic=lambda:self.os.clock;flow.sleep=lambda seconds:setattr(self.os,'clock',self.os.clock+seconds)
        flow.deadline=flow.last_clock=flow.operation_clock=None;flow.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.flow=flow
        terminal=object.__new__(NavigationTerminal);terminal.flow=flow;terminal.lock=flow.lock
        descriptor=dict(featureTerminalVersion=1,profile=protocol.PROFILE,area='world-navigation',runId=self.run,ticket=self.ticket,
            roles={role:dict(binding=public_binding(self.binding),originalSha256=digest(dict(modeledRole=role)),
                heldResources=[dict(resource='panel:modeled-navigation-address',kind='qt-root',originalSha256=digest(dict(modeledRoot=role)))]) for role in protocol.ROLES})
        samples=[]
        for index in range(1,4):
            if index>1:flow.sleep(1.6)
            facts=dict(location='A',bookmark=False,bookmarkName='',searchQuery='',searchResults=[],error='none',panel=False,addressDialog=False)
            epoch=flow.epoch_ms();public=dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=index,capturedEpochMs=epoch,
                state=facts,resources=['panel:modeled-navigation-address'],artifacts=[],lifecycle=dict(backgrounds=0,activations=1,launches=1))
            samples.append(dict(primary=public,actor=dict(ticket=self.ticket,actor='owned-observer',actorSequence=index,
                capturedEpochMs=epoch,facts=projection('world-navigation',facts),sequence=index,receivedEpochMs=epoch)))
        seal=dict(featureTerminalSealVersion=1,description=descriptor,windowSha256=digest(samples),liveOriginalSha256='b'*64)
        terminal.state=dict(description=descriptor,seal=seal,samples=samples)
        terminal.store=PrivateFeatureState(self.root/'modeled-navigation-terminal.json');terminal.store.write(terminal.state,None);terminal.previous=terminal.store.read()
        def replay():test.assertEqual(self.payload_bytes,self.payload.read_bytes());return deepcopy(seal)
        terminal.replay=replay
        terminal.roles=lambda:dict(primary=SimpleNamespace(admission=SimpleNamespace(archive=lambda:dict(providerInstance=self.fixture.instance,providerInputs=self.fixture.inputs))))
        self.terminal=terminal;self.controller.close()
        original=IOSGraphicsRuntime._retired_process_observer
        def reader(*args):
            value=original(*args);value.epoch_ms=self.os.epoch;value.monotonic=lambda:self.os.clock;return value
        clock=patch.object(IOSGraphicsRuntime,'_retired_process_observer',side_effect=reader);clock.start();test.addCleanup(clock.stop)

    @staticmethod
    def start_server(server,test):
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        test.addCleanup(thread.join,2);test.addCleanup(server.server_close);test.addCleanup(server.shutdown)
