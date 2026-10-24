"""Full feature/runtime assembly over explicit SDK/native/OS/GPU host models.

The existing owners/factories are real. Native resource/input producers and OS
processes are models with consistent model clocks. Local fixture and SDK HTTP,
actual staged Node Script, actual file bytes and rendered host PNGs are real.
This fixture makes no physical/native or real-CPU deadline qualification claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from types import SimpleNamespace
import threading
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.appium_adapter import WebDriver
from ios.adapters.installed_code import InstalledCodeBinding,SDK
from ios.adapters.world_web_feature import IOSWorldWebFeature
from ios.adapters.world_web_runtime import IOSWorldWebRuntime
from ios.adapters.retired_process import IOSRetiredProcess
from ios.self_tests.world_web_network_fixture import NetworkWorldWeb
from ios.self_tests.world_web_actor_fixture import IndependentActor
from ios.self_tests.world_web_gpu_fixture import Pool
from ios.self_tests.test_ios_world_web_retirement import Files
from ios.self_tests.test_ios_world_web_sample import POLICY
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus


class InstalledModel:
    def __init__(self,sdk,store):
        self.sdk,self.store=sdk,store;self.running=True;self.bundle=dict(bundleContractVersion=1,bundleId='org.example.overte',
            executableSha256='a'*64,bundleSha256='b'*64,nodeCount=3,fileCount=2,totalBytes=1000)
        self.source=dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance=uuid.uuid4().hex,available=True,cleanupPending=False,sdk=dict(SDK))
        self.native_instance=uuid.uuid4().hex;self.sequence=0;self.os_sequence=0;self.anchor=None;self.native_calls=0;self.sdk_live=True
    def process(self):return dict(bundleId=self.bundle['bundleId'],pid=self.sdk.pid,foreground=self.sdk.foreground) if self.running else None
    def native(self):
        assert self.running,'No native original after modeled process death'
        self.sequence+=1;self.native_calls+=1;self.sdk.tick()
        return dict(bundleObservationVersion=1,commandId='ios-'+uuid.uuid4().hex,instance=self.native_instance,sequence=self.sequence,processId=self.sdk.pid,
            capturedEpochMs=self.sdk.epoch(),status='ready',preparedEpochMs=19000,bundle=deepcopy(self.bundle))
    def gate(self):
        return InstalledCodeBinding(self.store,{k:v for k,v in self.sdk.binding.items() if k!='processIdentity'},self.bundle,
            self.process,lambda:deepcopy(self.source),self.native)
    def install(self):
        gate=self.gate();gate.begin();gate.bind()
    def now(self):self.sdk.tick();return dict(epochMs=round(self.sdk.host_epoch()),monotonicMs=self.sdk.time*1000)
    def arm_os(self):
        assert self.running
        if self.anchor is None:
            before=self.now();self.os_sequence+=1
            self.anchor=dict(sequence=self.os_sequence,pid=self.sdk.pid,appStates=[4,4],bundlePids=[self.sdk.pid,self.sdk.pid],clockBefore=before,clockAfter=self.now())
    def os_original(self,query):
        assert self.anchor is not None and query['bundleId']==self.bundle['bundleId'];before=self.now();self.os_sequence+=1
        return dict(iosRetiredProcessVersion=1,commandId=query['commandId'],instance=self.source['instance'],sequence=self.os_sequence,
            source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',clockBefore=before,clockAfter=self.now(),anchor=deepcopy(self.anchor),
            appStates=[4,4] if self.running else [0,0],bundlePids=[self.sdk.pid]*2 if self.running else [0,0],pidChecks=[dict(pid=self.sdk.pid,running=self.running) for _ in range(2)])


class FeatureWorldWeb:
    def __init__(self):
        try:self.initialize()
        except BaseException:self.close();raise
    def initialize(self):
        self.network=NetworkWorldWeb(use_whole_snapshot=True);self.whole=self.network.whole;self.sdk=self.whole.sdk
        self.actor=IndependentActor(self.whole);self.paths=dict(primary=self.whole.scope.root/'session.json',actor=self.actor.root/'session.json')
        self.actor.sdk.foreground=True
        self.sdks=dict(primary=self.sdk,actor=self.actor.sdk);self.models={};self.requests=[];self.own=[]
        self.root_census={};self.retained_roots={};self.widget_sources={}
        original_widgets=self.whole.domain.widgets
        for selector,sdk in self.sdks.items():
            outer=self
            class ClockedRoots(RootCensus):
                def tick(census):
                    outer.sdk.time+=.001;census.elapsed=round(outer.sdk.time*1000);return outer.sdk.epoch()
            self.root_census[selector]=ClockedRoots();self.retained_roots[selector]={}
            def widget_source(selector=selector):
                sdk=self.sdks[selector];census=self.root_census[selector];roots=self.retained_roots[selector]
                if selector=='primary':
                    value=original_widgets();inventory=value['scriptInventory']
                else:
                    sdk.tick();value=dict(schemaVersion=1,instance='00000000-0000-4000-8000-000000000002',frameSpace='qt-window-logical',processId=sdk.pid,
                        sampleEpochMs=sdk.epoch(),elapsedMs=round(sdk.time*1000),lastSequence=0,tabletShown=False,ready=True,controls=[],
                        scriptObservationVersion=1,scriptSourceSequence=census.sequence+1)
                    inventory=dict(inventoryVersion=1,complete=True,managers=[],pickers=[],tabletPresent=True,tabletShown=False);value['scriptInventory']=inventory
                members=dict(managers=[],pickers=[])
                for group,kind in (('managers','manager'),('pickers','picker')):
                    if inventory[group] and kind not in roots:roots[kind]=Root(kind)
                    if inventory[group]:
                        root=roots[kind];identity=census.observe(root);members[group]=[identity]
                    # A detached cached root remains a live original in the
                    # census. It is not a member of this actual tree walk.
                    # Visibility alone never removes a current member.
                source=census.source();source['processId']=sdk.pid
                # This is a newly produced model original, never an older
                # packet being relabeled. Independent actor's source has its
                # own actual census and distinct PID before exposure.
                inventory.update(inventoryVersion=2,rootOwnership=source,rootMembership=members)
                value['sampleEpochMs']=sdk.epoch();return value
            def native_widget(native,selector=selector,widget_source=widget_source):
                from ios.adapters.normal_input import NativeInput,observation
                boundary=object.__new__(NativeInput);sdk=self.sdks[selector]
                def capture(*,native_epoch_ms=None):
                    query=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='normal-ui-input',operation='observe')
                    sdk.widget_intents.append(deepcopy(query));hook=getattr(boundary,'observe_intent',None)
                    if hook is not None:hook(deepcopy(query))
                    original=widget_source();boundary.last_receipt=dict(schemaVersion=1,commandId=query['commandId'],observation=deepcopy(original))
                    epoch=(native_epoch_ms or (lambda:native.read(native.sequence)['capturedEpochMs']))()
                    return observation(original,sdk.pid,epoch)
                boundary.capture=capture;return boundary
            sdk.native_widget=native_widget;self.widget_sources[selector]=widget_source
        self.whole.domain.widgets=self.widget_sources['primary']
        self.whole.scope.live['native'].capture=self.widget_sources['primary']
        self.gpu=Pool(self.sdk);self.files=Files(self.whole)
        for selector,sdk in self.sdks.items():
            model=InstalledModel(sdk,PrivateFeatureState(self.paths[selector].with_name('installed-code.json')));model.install();self.models[selector]=model
            PrivateFeatureState(self.paths[selector]).write({k:sdk.binding[k] for k in ('sessionId','generation','targetFingerprint')},None)
        outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(_self,*_args):pass
            def handle_request(_self,method):
                path=_self.path;pieces=path.split('/');selector=next(key for key,sdk in outer.sdks.items() if len(pieces)>2 and pieces[2]==sdk.binding['sessionId'])
                model=outer.models[selector];tail='/'+'/'.join(pieces[3:]);body=None
                if method=='POST':body=json.loads(_self.rfile.read(int(_self.headers.get('Content-Length','0'))))
                outer.requests.append((selector,method,path,deepcopy(body)));status=200;value=None
                if len(pieces)==3:
                    if method=='DELETE':model.sdk_live=False
                    elif not model.sdk_live:status=404
                elif method=='DELETE' and tail=='/actions':outer.sdks[selector].release()
                else:value=outer.sdks[selector].request(method,tail,body)
                _self.send_response(status);_self.end_headers();_self.wfile.write(json.dumps(dict(value=value)).encode())
            def do_GET(_self):_self.handle_request('GET')
            def do_POST(_self):_self.handle_request('POST')
            def do_DELETE(_self):_self.handle_request('DELETE')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port);self.clients={key:WebDriver(self.url) for key in self.sdks}
        base=SimpleNamespace(state_path=self.paths.__getitem__,_operation=None,_candidate_guard=lambda **_kwargs:True)
        base.target=lambda _selector:dict(appId='org.example.overte',serverUrl=self.url)
        base._binding_store=lambda selector:self.models[selector].store
        base._binding=lambda selector,*_args:self.models[selector].gate()
        base.read_session=lambda selector:PrivateFeatureState(self.paths[selector]).read()
        base._scope=lambda selector,*_args:{k:v for k,v in self.sdks[selector].binding.items() if k!='processIdentity'}
        base.query_app_state=lambda _client,session,_target:4 if self.sdks[next(k for k,v in self.sdks.items() if v.binding['sessionId']==session)].foreground else 3
        def invoke(selector,operation,values):
            sdk=self.sdks[selector];assert values=={};self.own.append((selector,operation))
            if operation=='app.stop':self.models[selector].gate().begin_retirement();self.models[selector].running=False;sdk.foreground=False
            elif operation=='lifecycle.background':sdk.foreground=False;sdk.lifecycle['backgrounds']+=1;sdk.close_document()
            else:
                assert operation=='app.launch';sdk.foreground=True;sdk.lifecycle['activations']+=1;sdk.history=[];sdk.open_document(sdk.domain.marker['sourceUrl'],new_view=True)
            return dict(performed=True)
        base.invoke=invoke
        def retired_scope(selector,scope):
            assert scope==base._scope(selector);return base.target(selector)
        base._retired_candidate_scope=retired_scope;base.reset_launch_state=lambda *_args:None
        self.runtime=IOSWorldWebRuntime(base);self.runtime._existing=self.existing;self.runtime.existing_input_session=lambda _selector:nullcontext()
        self.runtime._sources=self.sources;self.runtime._world_web_source_owner=self.source_owner
        self.runtime._world_web_marker=lambda *_args:self.whole.scope
        self.runtime._world_web_feature=lambda selector,run,*,role,client,settings:IOSWorldWebFeature(self.runtime,selector,client,run,role,settings,
            epoch_ms=self.sdk.host_epoch,monotonic=lambda:self.sdk.time,sleep=self.sdk.sleep)
        def process_source(selector,_binding):self.models[selector].arm_os();return deepcopy(self.models[selector].source)
        self.runtime._graphics_final_source=process_source
        self.runtime._retired_process_observer=lambda selector,*_args:IOSRetiredProcess(self.models[selector].os_original,lambda:True,
            self.models[selector].bundle['bundleId'],self.sdks[selector].pid,self.models[selector].source,epoch_ms=self.sdk.host_epoch,monotonic=lambda:self.sdk.time)
        config=dict(artifactRoot=str(self.whole.scope.root),imagePolicy=deepcopy(POLICY),origins=deepcopy(self.sdk.origins))
        self.primary=self.runtime._world_web_feature('primary',self.network.run,role='primary',client=self.network.adapter,settings=config|dict(actorTarget='actor'))
        self.secondary=self.runtime._world_web_feature('actor',self.network.run,role='actor',client=self.network.actor,settings=config|dict(primaryTarget='primary'))
        self.primary.lock=self.primary.primary_lock=self.whole.scope.lock;self.secondary.lock=self.actor.lock;self.secondary.primary_lock=self.whole.scope.lock
    def existing(self,selector):
        state=PrivateFeatureState(self.paths[selector]).read();assert state is not None
        return self.clients[selector],state['sessionId'],state,self.runtime.adapter.target(selector),self.runtime.adapter._scope(selector)
    def sources(self,selector):
        sdk=self.sdks[selector]
        def send(query):
            if query.get('action')=='feature-vulkan-world-frame':return self.gpu.send(query)
            return self.files.send(query)
        def original(*,remote,limit):
            if remote.endswith('feature-vulkan-world-frame.json'):return self.gpu.original()
            return self.files.read()
        observer=SimpleNamespace(remote='@org.example.overte:documents/results/native-feature-observation.json',send=send,original=original)
        return dict(binding=deepcopy(sdk.binding),client=self.clients[selector],session=sdk.binding['sessionId'],check=lambda:True,observer=observer)
    def source_owner(self,selector,run,role,phase,lock):
        sdk=self.sdks[selector];old=getattr(sdk,'role',None);sdk.role=role
        try:return sdk.owner(PrivateFeatureState(self.paths[selector].with_name('ios-world-web-'+role+'-sources.json')),lock)
        finally:
            if old is None:del sdk.role
            else:sdk.role=old
    def allow_role_threads(self):
        # End the actual single-threaded component setup lock. No lock owner
        # field or thread assertion is changed; subsequent APIs use real flock.
        scaffolding=self.whole.fixture.fixture
        if self.primary.lock._owner is not None:
            self.primary.lock.assert_held();scaffolding.held.__exit__(None,None,None)
            scaffolding.held=nullcontext()
        if self.actor.lock._owner is not None:
            self.actor.lock.assert_held();self.actor.held.__exit__(None,None,None)
            self.actor.held=nullcontext()

    def paired_cleanup(self):
        """Run real role APIs with an explicit cooperative model scheduler.

        While Primary waits for Actor, the actual Actor API owns execution;
        an idle polling thread must not advance the shared logical clock past
        an in-flight acquisition. Its requested sleep is applied on resumption.
        Production sleep functions and original packet times are unchanged.
        """
        # The component scaffolding originally held this lock for its entire
        # single-threaded test lifetime. End that real setup context normally;
        # role APIs now acquire/release the same actual OS lock themselves.
        self.allow_role_threads()
        self.sdk.activate('cleanup',{});ready=threading.Event();done=threading.Event();errors=[];values=[]
        original_sleep=self.primary.sleep
        def sleep(delay):
            if self.primary.state['phase']=='cleaned' and self.primary.state['retirement'] is None and not done.is_set():
                ready.set()
                if not done.wait(600):raise RuntimeError('Independent modeled Actor did not finish')
            original_sleep(delay)
        def primary():
            try:values.append(self.primary.cleanup(dict(contractVersion=16,runId=self.network.run)))
            except BaseException as error:errors.append(error)
            finally:ready.set()
        self.primary.sleep=sleep;worker=threading.Thread(target=primary,daemon=True);worker.start()
        try:
            if not ready.wait(600):raise RuntimeError('Primary did not reach original peer receipt wait')
            if errors:raise errors[0]
            if self.primary.state['phase']!='cleaned':raise RuntimeError('Primary wait lacked actual local-cleaned metadata')
            actor=self.secondary.cleanup(dict(contractVersion=16,runId=self.network.run))
            if actor!=dict(performed=True):raise RuntimeError('Independent Actor cleanup is still pending')
        finally:
            done.set();worker.join(600);self.primary.sleep=original_sleep
        if worker.is_alive():raise RuntimeError('Actual Primary cleanup did not return')
        if errors:raise errors[0]
        if values!=[dict(performed=True)]:raise RuntimeError('Actual Primary cleanup is still pending')
    def close(self):
        if hasattr(self,'server'):
            self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);assert not self.thread.is_alive()
        if hasattr(self,'actor'):self.actor.close()
        if hasattr(self,'network'):self.network.close()
