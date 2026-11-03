"""Per-read raw admission on the existing Navigation literal archive.

The original reader still performs every real guard/query/parser/continuation.
An earlier same-clock read anchor can only shorten its five-second window.
Returned bytes are retained before any business/history callback or parser.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import need,number
from adapters.pico4.navigation_scene_prefix import NavigationScenePrefix
from adapters.pico4.navigation_scene_metadata import NavigationMetadataSeal


class NavigationSceneRawReader:
    def __init__(self,scene,reader,binding,role,authority,observer,*,method='read',limit=262144):
        need(type(scene) is NavigationScenePrefix and method in ('read','capture')
            and callable(authority) and callable(observer) and callable(getattr(reader,method,None))
            and callable(reader.send) and callable(reader.original) and reader.pid==int(binding['processIdentity'].split(':',1)[0])
            and (not hasattr(reader,'before_io') or reader.before_io is None))
        self.scene,self.reader,self.binding,self.role=scene,reader,deepcopy(binding),role
        self.authority,self.observer,self.method,self.limit=authority,observer,method,limit
        self.dependencies=(scene,reader,role,authority,observer,method,limit)
        self.binding_seal=NavigationMetadataSeal(self.binding)
        self.originals=(reader.send,reader.original,getattr(reader,method),reader.guard,reader.monotonic,reader.clock_ms)
        self.original_callbacks=self.originals
        self.failed=False;self.active=False;self.anchor=self.original_anchor=None;self.command=self.command_seal=None;self.pending=None
        self.send_callback=self.send;self.get_callback=self.get;self.read_callback=self.read
        reader.send=self.send_callback;reader.original=self.get_callback;setattr(reader,method,self.read_callback)
        self.before_callback=None
        if hasattr(reader,'before_io'):
            self.before_callback=self.before_io;reader.before_io=self.before_callback

    def control(self):
        r=self.reader;need(not self.failed and r.send is self.send_callback and r.original is self.get_callback
            and getattr(r,self.method) is self.read_callback and r.guard is self.originals[3]
            and r.monotonic is self.originals[4] and r.clock_ms is self.originals[5]
            and self.originals is self.original_callbacks
            and (self.scene,self.reader,self.role,self.authority,self.observer,self.method,self.limit)==self.dependencies
            and (not hasattr(r,'before_io') or r.before_io is self.before_callback))
        self.binding_seal.require(self.binding,self.binding_seal.digest)
        if self.command_seal is not None:self.command_seal.require(self.command,self.command_seal.digest)

    def before_io(self,started,requested,stage):
        self.control();need(self.active and stage in ('send','get') and self.anchor is not None
            and number(started,self.anchor[0],self.anchor[0]+5) and number(requested,1,1e15))

    def gate(self):
        self.control();need(self.active and self.anchor is self.original_anchor and self.anchor is not None)
        self.authority();need(self.originals[3]() is not False);self.scene.bound()
        now=self.originals[4]();host=self.scene.now()
        need(number(now,self.anchor[0],self.anchor[0]+5) and now-self.anchor[0]<5
            and host-self.anchor[1]<5)

    def reserve(self):
        self.gate()
        return self.scene.raw.reserve(self.role,dict(source=self.role,binding=self.binding,request=deepcopy(self.command)),self.limit,side_bytes=0)

    def send(self,command):
        try:
            self.control();need(self.active and self.pending is None)
            self.command=deepcopy(command);self.command_seal=NavigationMetadataSeal(self.command)
            self.pending=self.reserve();self.gate()
            return self.originals[0](command)
        except BaseException:self.failed=True;raise

    def get(self):
        try:
            self.control();need(self.active and self.command is not None)
            if self.pending is None:self.pending=self.reserve()
            self.gate();raw=self.originals[1]()
            # No business guard/native clock between return and durable retain.
            reference=self.scene.raw.retain(self.pending,raw);self.pending=None
            self.observer(reference,dict(source=self.role,request=deepcopy(self.command)))
            self.gate();return raw
        except BaseException:self.failed=True;raise

    def read(self,*args,**kwargs):
        try:
            self.control();need(not self.active and self.pending is None)
            self.authority();self.anchor=self.original_anchor=(self.originals[4](),self.scene.now());self.active=True
            result=self.originals[2](*args,**kwargs);self.gate();return result
        except BaseException:self.failed=True;raise
        finally:self.active=False
