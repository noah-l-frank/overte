"""Declared existing-SDK/installed/OS boundaries for the real Assets end owners.

Only SDK/device/process responses are models. Existing InstalledCodeBinding,
normal Assets files/QML/Create/Marker/PNG, source codecs, original WALs and
once-only process/SDK/CAS owners execute. This is no physical/candidate/public
InstalledAdapter acceptance and cannot open a whole Assets capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import check as transport_check
from adapters.script_feature.history import same
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters import assets_image_reader as reader1,assets_image_reader_queue as queue,assets_image_reader_processing as processing
from ios.adapters import assets_image_reader_storage as storage,assets_image_reader_pool as pool
from ios.adapters.assets_session_owners import installed_entry
from ios.adapters.bundle_observation import NativeBundleObservation
from ios.self_tests.test_ios_installed_code import InstalledCodeTests
from ios.self_tests.test_ios_retired_process import Boundary as OSBoundary
from ios.self_tests.assets_picker_fixture import BINDING,EPOCH


class RoleOS(OSBoundary):
    def __init__(self,host,pid):
        self.host=None;super().__init__();self.host=host;self.pid=pid
        self.anchor.update(pid=pid,bundlePids=[pid,pid],clockBefore=dict(epochMs=self.node_epoch()-5000,monotonicMs=1000),
            clockAfter=dict(epochMs=self.node_epoch()-4990,monotonicMs=1010))
    @property
    def clock(self):return self.initial if self.host is None else self.host.monotonic()
    @clock.setter
    def clock(self,value):
        if self.host is None:self.initial=value
        else:self.host.set_time(value)
    def epoch(self):return EPOCH+round(self.clock*1000)


class SDKModels:
    def __init__(self,test,roots,locks):
        self.test,self.roots,self.locks=test,dict(roots),dict(locks);self.boundary=None;self.initial_time=0.
        self.alive=dict(primary=True,actor=True);self.deleted=set();self.stops=[];self.calls=[];self.native_queries=[];self.native_raw={};self.documents={role:{} for role in ('primary','actor')}
        self.fault='';self.fired=False;self.installations={};self.targets={};self.clients={}
        self.bindings=dict(primary=deepcopy(BINDING),actor=dict(BINDING,processIdentity='43',targetFingerprint='9'*64,sessionId='actual-peer-boundary'))
        self.os={role:RoleOS(self,int(info['processIdentity'])) for role,info in self.bindings.items()}
        host=self
        class SDK:
            def __init__(self,role):self.role=role
            def call(self,method,path,body=None):
                transport_check();role=self.role;host.calls.append((role,method,path));need(path=='/session/'+host.bindings[role]['sessionId'])
                if role in host.deleted:raise WebDriverRequestError(404,'Original modeled SDK absence')
                need(method in ('GET','DELETE'))
                if method=='DELETE':
                    if host.fault!='ignored-delete':host.deleted.add(role)
                    if host.fault=='lost-delete' and not host.fired:host.fired=True;raise OSError('Original modeled lost SDK DELETE return')
                return {}
            def execute(self,session,operation,values):
                transport_check();role=self.role;host.calls.append((role,operation,deepcopy(values)))
                need(session==host.bindings[role]['sessionId'] and role not in host.deleted)
                if operation=='mobile: overteRetiredProcessInfo':
                    source=host.os[role];alive=host.alive[role]
                    source.states=[4 if alive else 1]*2;source.pids=[source.pid if alive else 0]*2;source.running=[alive]*2
                    return source.send(values)
                if operation=='mobile: terminateApp':
                    need(role not in host.stops);host.stops.append(role)
                    if host.fault!='ignored-stop':host.alive[role]=False
                    if host.fault=='lost-stop' and not host.fired:host.fired=True;raise OSError('Original modeled lost Stop return')
                    return True
                if operation=='mobile: pullFile':
                    need(host.alive[role]);filename=values['remotePath'].rsplit('/',1)[-1]
                    need(filename in host.documents[role]);return base64.b64encode(host.documents[role][filename].encode()).decode()
                raise AssertionError('Unexpected modeled Assets SDK operation')
        for role,bound in self.bindings.items():
            installed=InstalledCodeTests();installed.setUp();test.addCleanup(installed.doCleanups)
            installed.store.path=roots[role]/'installed-code-binding.json';installed.scope={k:v for k,v in bound.items() if k!='processIdentity'}
            installed.process['pid']=int(bound['processIdentity']);installed.native.clock_source['processId']=int(bound['processIdentity'])
            installed.native.mutate=lambda value,pid=int(bound['processIdentity']):value.update(processId=pid)
            n=installed.native;installed.reader=NativeBundleObservation(n.send,n.original,lambda:True,int(bound['processIdentity']),lambda n=n:dict(n.clock_source),
                monotonic=lambda n=n:n.clock,sleep=n.sleep)
            installed.binding=installed.make();installed.active();self.installations[role]=installed
            self.targets[role]=dict(platform='ios',physical=True,probe={'kind':'ios-documents'},appId='org.example.overte',serverUrl='http://declared-sdk.invalid/'+role,
                normalScripts=dict(contractVersion=1,profile='ios-native-qt-scripts-v1'),nativeUiObservation=dict(kind='uikit-documents',version=1),testBuild=dict(resultsDirectory='owned-results',fixtureOrigin='http://declared-native.invalid:'+str(49121 if role=='primary' else 49122)))
            PrivateFeatureState(roots[role]/'session.json').write(dict(sessionId=bound['sessionId'],generation=bound['generation'],targetFingerprint=bound['targetFingerprint'],iosE2ELaunchCompleted=True,iosE2ESceneUrl='declared-owned-scene'),None)
            self.clients[role]=SDK(role)
        class Adapter:
            _operation=None
            def _candidate_guard(self,**kwargs):
                # Declared metadata seam only; real typed binding decoder below
                # still consumes original bundle/nonce/process observations.
                need(all(roots[role].is_dir() for role in ('primary','actor')));return True
            def state_path(self,selector):need(selector in roots);return roots[selector]/'session.json'
            def read_session(self,selector):return PrivateFeatureState(self.state_path(selector)).read()
            def _target(self,selector):return deepcopy(host.targets[selector])
            def target(self,selector):return self._target(selector)
            def _scope(self,selector,session,state,target):
                expected=host.bindings[selector];need(session==expected['sessionId'] and same(target,host.targets[selector]))
                need(all(state.get(key)==expected[key] for key in ('sessionId','generation','targetFingerprint')))
                return {key:value for key,value in expected.items() if key!='processIdentity'}
            def _binding_store(self,selector):return host.installations[selector].store
            def _binding(self,selector,*args):return host.installations[selector].make()
            def _retired_candidate_scope(self,selector,scope):
                self._candidate_guard();need(same(scope,{k:v for k,v in host.bindings[selector].items() if k!='processIdentity'}));return self._target(selector)
            def reset_launch_state(self,selector,state):
                store=PrivateFeatureState(self.state_path(selector));actual=store.read();need(same(actual,state))
                if actual.get('iosE2ELaunchCompleted'):
                    value=deepcopy(actual);value['iosE2ELaunchCompleted']=False;value.pop('iosE2ESceneUrl',None);store.write(value,actual)
            @installed_entry
            def invoke(self,selector,operation,values):
                need(operation=='app.stop' and values=={});gate=self._binding(selector);gate.begin_retirement()
                value=host.clients[selector].execute(host.bindings[selector]['sessionId'],'mobile: terminateApp',dict(bundleId='org.example.overte'))
                gate.finish_retirement();return value
        self.adapter=Adapter()
        # Install source callbacks BEFORE the first normal owner/query. They
        # observe each role's selected live process model independently.
        for role,item in self.installations.items():
            item.binding.process=lambda role=role:dict(bundleId='org.example.overte',pid=int(host.bindings[role]['processIdentity']),foreground=True) if host.alive[role] else None
            item.make=lambda role=role,item=item: type(item.binding)(item.store,item.scope,item.native.bundle,
                lambda role=role:dict(bundleId='org.example.overte',pid=int(host.bindings[role]['processIdentity']),foreground=True) if host.alive[role] else None,
                lambda item=item:deepcopy(item.source),item.reader.read)
        self.runtime=IOSAssetsRuntime(self.adapter,monotonic=self.monotonic,epoch_ms=self.epoch)
    def monotonic(self):return self.initial_time if self.boundary is None else self.boundary.monotonic()
    def set_time(self,value):
        if self.boundary is None:self.initial_time=value
        else:self.boundary.elapsed=round(value*1000)
    def epoch(self):return EPOCH+5000+round(self.monotonic()*1000)
    def sleep(self,seconds):self.set_time(self.monotonic()+seconds)
    def post(self,request,timeout):
        from fixture.serve import FixtureState
        need(timeout==5);query=json.loads(request.data);FixtureState().set_client_command(query)
        role=next((r for r,t in self.targets.items() if request.full_url.startswith(t['testBuild']['fixtureOrigin']+'/')),None)
        need(role is not None and self.alive[role] and self.boundary is not None)
        self.native_queries.append((role,deepcopy(query)));action=query['action']
        if action=='feature-native-observe':
            if role=='primary':self.boundary.tick();self.boundary.native_clock.send(query);value=self.boundary.native_clock.original()
            else:self.actor_endpoint.send('clock',query);value=self.actor_endpoint.raw['clock']
            self.native_raw[role]=value;self.documents[role]['feature-native-observation.json']=value
        else:
            need(role=='primary')
            producers={reader1.ACTION:(reader1,self.boundary.images.parent),queue.ACTION:(queue,self.boundary.images),
                processing.ACTION:(processing,self.boundary.processing),storage.ACTION:(storage,self.boundary.storage),pool.ACTION:(pool,self.boundary.pool)}
            need(action in producers);module,producer=producers[action];producer.send(query)
            self.documents[role][module.FILE]=producer.raw
        raw=json.dumps(query).encode()
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,limit):return raw[:limit]
        return Response()
    def install_transport(self,test):
        # Choose both native HTTP reader acquisition clocks before the first
        # canonical source/owner birth. The native packets keep their actual
        # modeled producer offset; no retained clock is rewritten.
        from ios.adapters import feature_observation
        original_init=feature_observation.FeatureObservation.__init__;host=self
        def selected(observer,*args,**kwargs):
            kwargs['monotonic']=host.monotonic;kwargs['sleep']=host.sleep
            kwargs.setdefault('epoch_ms',host.epoch)
            return original_init(observer,*args,**kwargs)
        test.enterContext(patch.object(feature_observation.FeatureObservation,'__init__',selected))
        test.enterContext(patch('ios.adapters.feature_observation.post_request',side_effect=self.post))
        def driver(url):return self.clients[next(role for role,value in self.targets.items() if value['serverUrl']==url)]
        test.enterContext(patch('ios.adapters.appium_adapter.WebDriver',side_effect=driver))
