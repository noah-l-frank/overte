"""Actual loopback SDK and process-separated observers over native host models.

The normal Feature/Runtime/InstalledCodeBinding/readers are used unchanged.
Only selector metadata, WDA/UIKit/native producers and their separate boundary
clock are models. This fixture cannot qualify native execution or device time.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.self_tests.tablet_web_host_clock import advance
import base64
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import multiprocessing
import os
import time
import traceback
from pathlib import Path
from threading import Thread
from urllib.request import Request,urlopen
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from ios.adapters import appium_adapter,feature_observation,normal_input
from ios.adapters.installed_code import InstalledCodeBinding
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.self_tests.tablet_web_page_fixture import TabletPageBoundary
from ios.self_tests.test_ios_tablet_web_sources import RUN

READER='a'*64
ACTOR='b'*64
ADAPTER='c'*64
SELECTOR='existing-tablet-host-sdk'
REAL_NATIVE_POST=feature_observation.post_request
REAL_NATIVE_URLOPEN=normal_input.urlopen


class SharedBoundary(TabletPageBoundary):
    def __init__(self,test,clock,**options):
        self.shared_clock=clock
        super().__init__(test,**options)
    def sleep(self,duration):advance(self.shared_clock,duration)
    @property
    def elapsed(self):return self.shared_clock.value
    @elapsed.setter
    def elapsed(self,value):self.shared_clock.value=value


class SDKBridge:
    def __init__(self,test):
        self.boundary=None;self.calls=[];self.errors=[];self.error_tracebacks=[];self.present=True;self.lose_delete_return=False;owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):pass
            def response(self,status,value):
                raw=json.dumps(value).encode();self.send_response(status)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
            def route(self):
                try:
                    need(owner.boundary is not None);b=owner.boundary
                    size=int(self.headers.get('Content-Length','0'));need(0<=size<=2097152)
                    body=None if size==0 else json.loads(self.rfile.read(size))
                    owner.calls.append((self.command,self.path))
                    if self.path=='/e2e-client-command.json':
                        need(self.command=='POST')
                        if body['action']=='ios-bundle-observe':
                            native=b.context_test.admission.fixture.native;native.send(body)
                            original=json.loads(native.original());original['capturedEpochMs']=b.epoch()
                            b.raw['ios-installed-bundle-observation.json']=json.dumps(original)
                        else:b.post(type('NativeRequest',(),dict(data=json.dumps(body).encode()))(),5)
                        return self.response(200,body)
                    if self.path=='/session/'+b.binding['sessionId'] and self.command=='GET':
                        return self.response(200 if owner.present else 404,dict(value={} if owner.present else dict(error='invalid session id')))
                    if self.path=='/session/'+b.binding['sessionId'] and self.command=='DELETE':
                        if not owner.present:return self.response(404,dict(value=dict(error='invalid session id')))
                        owner.present=False
                        if owner.lose_delete_return:
                            owner.lose_delete_return=False;raise OSError('Actual SDK DELETE response return lost after removal')
                        return self.response(200,dict(value=None))
                    need(owner.present and self.path.startswith('/session/'+b.binding['sessionId']+'/'))
                    if self.command=='GET' and self.path.endswith('/screenshot'):
                        from ios.self_tests.tablet_web_render_fixture import screenshot
                        result=base64.b64encode(screenshot(b)).decode()
                    elif self.path.endswith('/execute/sync'):
                        need(self.command=='POST' and type(body) is dict)
                        operation,arguments=body['script'],body['args'][0]
                        if operation=='mobile: overteProcessInfo':result=b.process()
                        elif operation=='mobile: overteProcessSourceInfo':result=deepcopy(b.context_test.admission.fixture.source)
                        elif getattr(b,'lifecycle',None) is not None and b.lifecycle.handles(operation):result=b.lifecycle.execute(operation,arguments)
                        else:result=b.execute(b.binding['sessionId'],operation,arguments)
                    else:result=b.ui.call(self.command,self.path,body)
                    return self.response(200,dict(value=result))
                except Exception as error:
                    owner.errors.append(error);owner.error_tracebacks.append(traceback.format_exc())
                    return self.response(500,dict(value=dict(error='host boundary rejected')))
            do_GET=do_POST=do_DELETE=route
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start();test.addCleanup(self.close)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        if self.error_tracebacks:print('Actual host SDK boundary exceptions:\n'+'\n'.join(self.error_tracebacks),flush=True)


class ExistingAdapter:
    """Test selector boundary; actual installed-code admission stays strict."""
    def __init__(self,root,metadata):
        self.root=Path(root);self.metadata=deepcopy(metadata)
    def _candidate_guard(self,*,complete=False):
        need(type(complete) is bool)
        need(PrivateFeatureState(self.root/'paired-input-metadata.json').read()==self.metadata)
    def state_path(self,selector):need(selector==SELECTOR);return self.root/'session.json'
    def read_session(self,selector):return PrivateFeatureState(self.state_path(selector)).read()
    def _target(self,selector):need(selector==SELECTOR);return deepcopy(self.metadata['target'])
    def _scope(self,selector,session,state,target):
        self._candidate_guard();need(selector==SELECTOR and session==self.metadata['scope']['sessionId']
            and state==self.read_session(selector) and target==self.metadata['target'])
        need(all(state.get(key)==value for key,value in self.metadata['session'].items()
            if key in ('sessionId','generation','targetFingerprint')))
        need(set(state)<=set(self.metadata['session'])|{'processIdentity','iosE2ELaunchCompleted','iosE2ESceneUrl'})
        return deepcopy(self.metadata['scope'])
    def _binding(self,selector,client,session,state,target):
        scope=self._scope(selector,session,state,target)
        return InstalledCodeBinding(PrivateFeatureState(self.metadata['installedPath']),scope,self.metadata['bundle'],
            lambda:client.execute(session,'mobile: overteProcessInfo'),lambda:client.execute(session,'mobile: overteProcessSourceInfo'),
            lambda:need(False))  # Observers cannot verify/write installed code.


class PairedTabletFixture:
    def __init__(self,test):
        self.test=test;self.clock=multiprocessing.get_context('spawn').Value('d',0.)
        self.sdk=SDKBridge(test)
        self.fixture=make_server(READER,ACTOR,adapter_token=ADAPTER)
        self.foreign=make_server(READER,ACTOR,browser_peer_of=self.fixture)
        self.threads=[]
        for server in (self.fixture,self.foreign):
            thread=Thread(target=server.serve_forever,daemon=True);thread.start();self.threads.append(thread)
        test.addCleanup(self.close)
        def address(server):return 'http://127.0.0.1:'+str(server.server_port)
        self.fixture_url=address(self.fixture)+'/feature-fixture/v1'
        self.origins=dict(primary=address(self.fixture),foreign=address(self.foreign))
        b=self.boundary=SharedBoundary(test,self.clock,fixture_url=self.fixture_url+'/runs/'+RUN+'/',origins=self.origins)
        self.sdk.boundary=b
        b.live_marker=True
        # Existing model inputs are installed before either actual observer
        # acquires a source. The real shared fixture keeps its auth/route code.
        self.fixture.journal=b.journal;self.foreign.journal=b.journal
        self.fixture.browser_resources=b.browser;self.foreign.browser_resources=b.browser
        self.fixture.journal.clock=b.host;self.fixture.browser_resources.clock_ms=b.epoch
        b.target.update(serverUrl=self.sdk.url)
        b.target['testBuild']['fixtureOrigin']=self.sdk.url
        installed=b.context_test.admission.fixture
        b.target['appId']=installed.native.bundle['bundleId']
        self.session=dict(sessionId=b.binding['sessionId'],generation=b.binding['generation'],targetFingerprint=b.binding['targetFingerprint'])
        PrivateFeatureState(b.root/'session.json').write(self.session,None)
        # The real adapter keeps installed-code metadata in its existing SDK
        # directory. Keep this prepared model record there too, before either
        # observer admits it; unrelated helper teardown must not remove its
        # namespace after a complete SDK end/archive.
        installed_store=PrivateFeatureState(b.root/'paired-installed-code.json')
        installed_store.write(installed.store.read(),None)
        self.metadata=dict(target=deepcopy(b.target),scope=deepcopy(installed.scope),session=deepcopy(self.session),
            installedPath=str(installed_store.path),bundle=deepcopy(installed.native.bundle))
        PrivateFeatureState(b.root/'paired-input-metadata.json').write(self.metadata,None)
        self.settings=dict(artifactRoot=str(b.root),imagePolicy=dict(source='native-screen',marker=[334,56,462,88],subject=[150,50,320,80]),
            physicalBinding=deepcopy(b.binding),setupNative=deepcopy(b.context_test.setup),origins=deepcopy(self.origins))
        self.controller=Client(self.fixture_url,READER,monotonic=b.mono,sleep=b.sleep)
        # End the real helper's initial lock context through its own normal
        # __exit__; never clear lock flags or share a held foreign descriptor.
        entries=b.context_test._cleanups
        matches=[(index,entry) for index,entry in enumerate(entries) if getattr(entry[0],'__name__','')=='__exit__'
            and getattr(getattr(entry[0],'__self__',None),'gen',None) is not None
            and entry[0].__self__.gen.gi_code.co_name=='held']
        need(len(matches)==1);index,(function,args,kwargs)=matches[0];function(*args,**kwargs);entries.pop(index)
        self.child_transports()
        self.primary=self.feature('primary')
    def feature(self,role):
        b=self.boundary
        runtime=IOSTabletWebRuntime(ExistingAdapter(b.root,self.metadata))
        client=Client(self.fixture_url,ACTOR if role=='actor' else ADAPTER,monotonic=b.mono,sleep=b.sleep)
        feature=runtime._tablet_web_feature(SELECTOR,RUN,role=role,client=client,settings=self.settings)
        # Explicit test boundary clocks, shared only for model event delivery.
        # No claim is made about real CPU/native-device freshness.
        def operation_sleep(duration):
            b.sleep(duration)
            # Give real independent OS processes the same actual scheduling
            # opportunity supplied by the production sleep callback.
            time.sleep(duration)
        feature.monotonic,feature.epoch_ms,feature.sleep=b.mono,b.host,operation_sleep
        return feature
    def close(self):
        for server in (self.foreign,self.fixture):server.shutdown();server.server_close()
        for thread in self.threads:thread.join()
    def child_transports(self):
        # Forking must not inherit the parent's test-only in-memory transport
        # patches. The child uses the actual unchanged HTTP/AFC implementations.
        feature_observation.post_request=REAL_NATIVE_POST
        normal_input.urlopen=REAL_NATIVE_URLOPEN


def actor_baseline(inputs,clock,pipe):
    try:
        root,metadata,settings,fixture_url,base=inputs
        def monotonic():return clock.value
        def epoch():return base+round(clock.value*1000)+10000
        def sleep(duration):advance(clock,duration)
        runtime=IOSTabletWebRuntime(ExistingAdapter(root,metadata))
        client=Client(fixture_url,ACTOR,monotonic=monotonic,sleep=sleep)
        feature=runtime._tablet_web_feature(SELECTOR,RUN,role='actor',client=client,settings=settings)
        feature.monotonic,feature.epoch_ms,feature.sleep=monotonic,epoch,sleep
        sequence=feature.publish()
        pipe.send(dict(hostProcessId=os.getpid(),sequence=sequence))
    except Exception as error:
        import traceback
        pipe.send(dict(hostProcessId=os.getpid(),error=type(error).__name__,traceback=traceback.format_exc()))
    finally:pipe.close()
