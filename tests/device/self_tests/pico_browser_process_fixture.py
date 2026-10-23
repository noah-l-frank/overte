"""Existing analytical browser producers over an owned loopback channel.

Only original source requests cross this boundary. No scenario expectations,
browser input, live flow/Actor object or observer-owned image crosses it.
All product/GPU/Qt/native clocks remain declared analytical host seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import secrets
import socket
import socketserver
import threading
from types import SimpleNamespace

from adapters.native_feature_observation import NativeFeatureObservation,need
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_object_lifetimes import NativeScriptObjectLifetimes
from adapters.native_web_runtime import NativeWebRuntime
from adapters.navigation_arrival import NavigationArrival
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.browser_stereo import PicoBrowserStereo,original_name
from adapters.pico4.browser_vm import PicoBrowserVm
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.pico4.graphics_source import PicoGraphicsSource,COMMAND as UI_COMMAND,FILE as UI_FILE
from adapters.pico4.tablet_browser_source import PicoTabletBrowserIO
from adapters.script_journey.lock import ScriptSourceLock
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles

LIMIT=2*1024*1024


class ProductSources:
    """The original fixture target/model live in the actual Parent process."""
    def __init__(self,fixture,model):
        self.f,self.model=fixture,model;self.token=secrets.token_hex(32);self.calls=[]
        self.mutex=threading.RLock()
        service=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                while True:
                    raw=self.rfile.readline(LIMIT+1)
                    if not raw:return
                    need(0<len(raw)<=LIMIT)
                    request=json.loads(raw);need(type(request) is dict and set(request)=={'token','action','value'}
                        and request['token']==service.token)
                    with service.mutex:result=service.dispatch(request['action'],request['value'])
                    response=json.dumps(result,separators=(',',':'),allow_nan=False).encode()+b'\n'
                    need(len(response)<=LIMIT);self.wfile.write(response);self.wfile.flush()
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads=True
            allow_reuse_address=False
        self.server=Server(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()

    def configuration(self):
        f=self.f
        return dict(port=self.server.server_address[1],token=self.token,path=str(f.path),modelRoot=str(self.model.root),
            artifacts=str(f.artifacts),nativeRoot=str(self.model.native_root),binding=deepcopy(f.target.binding),
            run=f.run,fixture=f.fixture_url,foreign=f.foreign,scene=f.target.scene_url)

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);need(not self.thread.is_alive())

    def dispatch(self,action,value):
        target,model,clock=self.f.target,self.model,self.f.clock
        self.calls.append(action)
        if action=='epoch':return clock.epoch()
        if action=='host':return clock.now()
        if action=='sleep':need(type(value) in (int,float) and 0<=value<=1);clock.sleep(value);return None
        if action=='candidate':return dict(binding=deepcopy(target.binding),foreground=target.foreground)
        if action=='diagnostic':return target.normal_feature_runtime('target',read_only=True)[1](value)
        if action=='probe':return model.probe(value)
        if action=='feature':model.features.send(value);return model.features.original()
        if action=='browser':
            need(value['operation']=='observe');target.send(value);return target.raw
        if action=='runtime':
            reader=target._web_runtime_observer('target',read_only=True);reader.send(value);return target.runtime_raw
        if action=='scripts':target.vm.script.send(value);return target.vm.script.original()
        if action=='objects':target.vm.objects.send(value);return json.dumps(target.vm.objects.packet)
        if action=='subject':model.update_subject();model.subject.send(value);return model.subject.original()
        if action=='ui':
            model.ui.write('synthetic','org.overte.pico',UI_COMMAND,json.dumps(value))
            return model.ui.read('synthetic','org.overte.pico','files/overte-e2e/'+UI_FILE,attempts=1)
        if action=='capture':
            owner=PrivateFeatureState(model.owner_store('actor').path).read()
            need(owner is not None and owner['capture']==value and owner['role']=='actor')
            model.active=self.f.actor.source.read()['ticket']
            model.gpu.intents.append(deepcopy(value));model.gpu.advance();model.storage.present=True
            model.gpu.send(value);return model.gpu.original()
        if action=='storage':
            model.storage.intents.append(deepcopy(value));model.storage.send(value)
            name=receipt_file(value['commandId']);path=model.native_root/name
            path.write_text(model.storage.files[name]);path.chmod(0o600)
            model.inventory.issued[value['commandId']]=(value['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            model.inventory.owner=deepcopy(model.owner_store('actor').read())
            model.inventory.retired=not model.storage.present;model.inventory.present=model.storage.present
            model.inventory.callbacks=model.storage.callbacks;model.inventory.png_bytes=len(model.storage.raw) if model.storage.present else 0
            return model.storage.files[name]
        if action=='inventory':model.inventory.send(value);return model.inventory.original()
        need(False)


class Rpc:
    def __init__(self,config):
        self.config=config;self.socket=socket.create_connection(('127.0.0.1',config['port']),timeout=5)
        self.socket.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);self.stream=self.socket.makefile('rwb')
    def call(self,action,value=None):
        raw=json.dumps(dict(token=self.config['token'],action=action,value=value),separators=(',',':')).encode()+b'\n'
        need(len(raw)<=LIMIT);self.stream.write(raw);self.stream.flush();raw=self.stream.readline(LIMIT+1)
        need(0<len(raw)<=LIMIT);return json.loads(raw)
    def close(self):self.stream.close();self.socket.close()


class Clock:
    def __init__(self,rpc):self.rpc=rpc
    def epoch(self):return self.rpc.call('epoch')
    def now(self):return self.rpc.call('host')
    def sleep(self,seconds):return self.rpc.call('sleep',seconds)


class IndependentBrowserSources:
    """Host-side ordinary readers; the independent process creates its own Actor."""
    def __init__(self,config):
        self.config=config;self.rpc=Rpc(config);self.clock=Clock(self.rpc)
        self.path=Path(config['path']);self.artifacts=Path(config['artifacts']);self.model_root=Path(config['modelRoot'])
        self.native_root=Path(config['nativeRoot']);self.binding=deepcopy(config['binding']);self.scene_url=config['scene']
        self.lock=ScriptSourceLock(self.path/'script-sources.lock');self.pid=int(self.binding['processIdentity'].split(':',1)[0])
    def close(self):self.rpc.close()
    def state_path(self,_selector):return self.path/'session.json'
    def _lock(self,_selector):return self.lock
    def existing_input_session(self,_selector):return nullcontext()
    def guard(self):
        self.lock.assert_held();value=self.rpc.call('candidate')
        need(value['binding']==self.binding and value['foreground'] is True);return True
    def _graphics_lifecycle_status(self,_selector,binding):
        value=self.rpc.call('candidate');need(value['binding']==binding);return dict(foreground=value['foreground'],binding=binding)
    def _world_web_clock(self,_selector):return self.clock.epoch()
    def tablet_web_manager_store(self,_selector):return PrivateFeatureState(self.path/'pico-tablet-web-manager.json')
    def normal_feature_runtime(self,_selector,**_kwargs):
        return None,lambda after:tuple(self.rpc.call('diagnostic',after)),deepcopy(self.binding),self.guard,None
    def channel(self,name):
        original=[None]
        def send(request):original[0]=self.rpc.call(name,request)
        return send,lambda:original[0]
    def _native_feature_observer(self,_selector,**_kwargs):
        return NativeFeatureObservation(*self.channel('feature'),self.clock.epoch,self.guard,self.pid,
            monotonic=self.clock.now,sleep=self.clock.sleep)
    def _tablet_web_io(self,_selector,_flow,**_kwargs):
        return PicoTabletBrowserIO(*self.channel('browser'),self.clock.epoch,self.guard,self.pid,source_lock=self.lock,read_only=True,
            monotonic=self.clock.now,sleep=self.clock.sleep)
    def _web_runtime_observer(self,_selector,**_kwargs):
        return NativeWebRuntime(*self.channel('runtime'),self.clock.epoch,self.guard,self.pid,require_renderers=True,
            monotonic=self.clock.now,sleep=self.clock.sleep)
    def _tablet_web_vm(self,_selector,flow):
        scripts=NativeScriptObservation(*self.channel('scripts'),self.clock.epoch,self.guard,self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
        objects=NativeScriptObjectLifetimes(*self.channel('objects'),self.clock.epoch,self.guard,self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
        return PicoBrowserVm(flow.run,flow.fixture_url,flow.live_owner['scriptUrl'],'actor',self.binding,scripts,objects,
            PrivateFeatureState(self.path/'pico-tablet-web-actor-vm.json'),self.lock,
            lambda:flow.source.client.request('/runs/'+flow.run+'/browser'))
    def owner_store(self):return PrivateFeatureState(self.model_root/'capture-actor.json')
    def world_capture(self):
        self.guard()
        def guard():
            self.guard();need(PrivateFeatureState(self.model_root/'capture-primary.json').read() is None);return True
        owner=WorldRenderOwner(self.owner_store(),self.binding,guard,role='actor')
        storage_channel=self.channel('storage');storage_replies={}
        def storage_send(command):storage_channel[0](command);storage_replies[receipt_file(command['commandId'])]=storage_channel[1]()
        storage=NativeWorldRenderStorage(storage_send,lambda name:storage_replies.get(name,''),self.clock.epoch,guard,self.pid,
            receipt_intent=owner.receipt_intent,monotonic=self.clock.now,sleep=self.clock.sleep)
        capture=NativeWorldRenderCapture(*self.channel('capture'),storage,self.clock.epoch,guard,self.pid,intent=owner.intent,
            stereo=True,require_cameras=True,monotonic=self.clock.now,sleep=self.clock.sleep)
        inventory=NativeWorldReceiptInventory(*self.channel('inventory'),self.clock.epoch,guard,self.pid,owner.owned,
            lambda:storage.instance,monotonic=self.clock.now,sleep=self.clock.sleep)
        receipts=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.native_root/name).read_text()),inventory)
        return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=self.lock)
    def _tablet_web_stereo(self,_selector,flow,journal,role):
        need(role=='actor');self.guard()
        subject=NativeGraphicsSubject(*self.channel('subject'),self.clock.epoch,self.guard,self.pid,require_framework=True,
            monotonic=self.clock.now,sleep=self.clock.sleep)
        arrival=NavigationArrival(lambda after:self.rpc.call('probe',after),subject,self.clock.epoch,self.guard,
            flow.run,self.binding,self.scene_url,monotonic=self.clock.now)
        ui_channel=self.channel('ui')
        def write(_target,_package,_path,raw):ui_channel[0](json.loads(raw))
        ui_adapter=SimpleNamespace(adb=SimpleNamespace(write_debug_app_file=write,read_debug_app_file=lambda *_args,**_kwargs:ui_channel[1]()))
        native=SimpleNamespace(clock_ms=self.clock.epoch,guard=self.guard,pid=self.pid,monotonic=self.clock.now,sleep=self.clock.sleep)
        ui=PicoGraphicsSource(ui_adapter,'synthetic',native)
        return PicoBrowserStereo(arrival,self.world_capture,self.artifacts/original_name(flow.run,role,journal),self.artifacts,
            flow.run,self.binding,self.lock,self.guard,fixture_url=flow.fixture_url,foreign_fixture_url=flow.foreign_url,
            owner_token=flow.live_owner['ownerToken'],script_url=flow.live_owner['scriptUrl'],
            browser_factory=lambda:self._tablet_web_io('target',flow),runtime_factory=lambda:self._web_runtime_observer('target'),
            scripts=self.normal_feature_runtime('target')[1],http=lambda:flow.source.client.request('/runs/'+flow.run+'/browser'),
            role=role,journal_id=journal,ui_factory=lambda:ui,native_factory=lambda:self._native_feature_observer('target'),monotonic=self.clock.now)
