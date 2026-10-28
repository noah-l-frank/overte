"""Real local tasks/FDs/files; explicit display/HID/RSD producer model only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio,socket
from pathlib import Path
from types import SimpleNamespace
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner

BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,sessionId='owned-source-session',generation=1,targetFingerprint='c'*64,processIdentity='31')
RUN='d'*32


class RSD:
    def __init__(self):self.service=SimpleNamespace(address=('fd00::2',1))


class Receiver:
    def __init__(self):self.sockets=socket.socketpair();self.bound=None;self.pending=asyncio.Event();self.fail=False
    def bind(self,value):self.bound=value
    def getsockname(self):return self.bound[0],54321
    async def recv(self,limit):
        await self.pending.wait()
        if self.fail:raise RuntimeError('Declared media drain failure')
        return b''
    def close(self):
        for fd in self.sockets:fd.close()


class Display:
    def __init__(self):self.starts=[];self.stops=[];self.fail_start=False;self.fail_stop=False;self.exits=0;self.stop_gate=asyncio.Event();self.stop_gate.set();self.stop_started=asyncio.Event()
    async def __aenter__(self):return self
    async def __aexit__(self,*args):self.exits+=1
    async def start_video_stream(self,**values):
        self.starts.append(values['client_session_id'])
        if self.fail_start:raise RuntimeError('Declared stream-start return lost')
    async def stop_media_stream(self,stream):
        self.stops.append(stream);self.stop_started.set();await self.stop_gate.wait()
        if self.fail_stop:raise RuntimeError('Declared stream-stop failure')


class HID:
    def __init__(self,store):self.store=store;self.reports=[];self.down_gate=asyncio.Event();self.down_gate.set();self.down_started=asyncio.Event();self.exits=0
    async def __aenter__(self):return self
    async def __aexit__(self,*args):self.exits+=1
    async def send_touchscreen(self,state,x,y):
        phase=self.store.read()['phase'];assert phase==('down-issued' if state==0xC2 else 'up-issued')
        self.reports.append(state)
        if state==0xC2:self.down_started.set();await self.down_gate.wait()


class Fixture:
    def __init__(self,root):
        self.root=Path(root);self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__()
        self.current=True;self.rsd=RSD();self.receiver=Receiver();self.display=Display()
        self.lease_store=PrivateFeatureState(self.root/('ios-lifecycle-touch-lease-'+RUN+'.json'));self.hid=HID(self.lease_store)
        self.owner=self.restore();self.lease=self.owner.make_lease(self.lease_store,self.rsd,'fd00::1',check=lambda:self.current,
            options=dict(socket_factory=lambda:self.receiver,display_factory=lambda _:self.display,hid_factory=lambda _:self.hid))
    def restore(self):return LifecycleTouchResourceOwner(PrivateFeatureState(self.root/('ios-lifecycle-touch-resources-'+RUN+'.json')),BINDING,RUN,self.lock,lambda:self.current)
    async def begin(self,seconds=2):return await self.lease.begin(100,50,25,10,seconds=seconds)
    async def close(self):
        self.hid.down_gate.set();self.display.stop_gate.set();self.lease.request_release.set()
        if self.lease.worker is not None:await asyncio.wait_for(asyncio.shield(self.lease.worker),6)
        self.receiver.close();self.held.__exit__(None,None,None)
