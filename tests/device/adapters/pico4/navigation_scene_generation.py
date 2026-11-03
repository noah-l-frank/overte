"""Initial normal G1 IO construction for the same original scene owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.pico4 import normal_scripts
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.navigation_scene_prefix import NavigationScenePrefix,NavigationSceneIO
from adapters.token_script_ui import TokenScriptUI
from adapters.pico4.navigation_originals import read_original
from adapters.script_journey.history import same


def scene_owner(parent):
    guard=getattr(parent,'outer_guard',None)
    if guard is None:return None
    owner=getattr(guard,'__self__',None)
    need(type(owner) is NavigationScenePrefix and guard is owner.outer_guard
        and parent.original_outer_guard is guard and parent in owner.parents.values())
    return owner


def outer(parent):
    owner=scene_owner(parent)
    if owner is not None:parent.outer_publish_fence()


def normal_runtime(adapter,target,parent,scene,installed,identity,ui_path,controller):
    """Same PicoNavigation/PicoScriptIO/TokenScriptUI and observer producers.

    The opt-in transport is selected BEFORE ordinary callback binding. Sealed
    callbacks are never replaced. Existing G0/G1 callers use the exact default
    normal_scripts runtime when the original Parent has no scene owner.
    """
    owner=scene_owner(parent)
    if owner is None:return normal_scripts.runtime(adapter,target,scene,installed,identity,ui_path,controller)
    owner.bound()
    native=NavigationSceneIO(adapter,target,identity,controller,owner)
    navigation=PicoNavigation(native,ui_path,installed,identity,scene,monotonic=owner.monotonic,sleep=parent.source.normal.sleep)
    io=normal_scripts.PicoScriptIO(navigation)
    observer=adapter._feature_observer(target)
    def observe(after):
        owner.bound();value=observer.read(after);owner.bound()
        return value,adapter.adb.epoch_milliseconds(target)
    binding={key:installed[key] for key in ('sourceRevision','artifactSha256')}
    binding.update(processIdentity=identity,sessionId=io.bridge,generation=0,
        targetFingerprint=hashlib.sha256((target+'\0'+str(adapter.pico_configuration)).encode()).hexdigest())
    owner.bound();return TokenScriptUI(io,monotonic=owner.monotonic,sleep=parent.source.normal.sleep),observe,binding


class NavigationSceneEnvironment:
    """One original request/raw channel, bound before its first acquisition."""
    def __init__(self,owner,source,binding,observer,*,before_io=None):
        need(type(owner) is NavigationScenePrefix and isinstance(source,NativeNavigationEnvironment)
            and callable(observer) and (before_io is None or callable(before_io)) and source.pid==int(binding['processIdentity'].split(':',1)[0])
            and source.last is None and not source.requests and not hasattr(source,'_navigation_scene_channel'))
        self.owner,self.source,self.binding,self.observer=owner,source,deepcopy(binding),observer
        self.before_io=self.original_before_io=before_io
        self.binding_sha=json_digest(binding);self.pending=self.request=None
        self.original_send,self.original_read,self.original_guard=source.send,source.original,source.guard
        self.send_callback=self.send;self.read_callback=self.read;self.guard_callback=self.guard
        source._navigation_scene_channel=self;source.send=self.send_callback;source.original=self.read_callback;source.guard=self.guard_callback

    def control(self):
        need(self.source._navigation_scene_channel is self and self.source.send is self.send_callback
            and self.source.original is self.read_callback and self.source.guard is self.guard_callback
            and self.before_io is self.original_before_io
            and json_digest(self.binding)==self.binding_sha and self.source.pid==int(self.binding['processIdentity'].split(':',1)[0]))

    def child_io(self):
        if self.before_io is not None:self.before_io();self.owner.bound()

    def guard(self):
        self.control();self.owner.bound();value=self.original_guard();self.owner.bound();return value

    def reserve(self,request):
        self.control();self.owner.bound();self.child_io()
        return self.owner.raw.reserve('navigation-g1-primary',dict(source='navigation-restoration-environment',
            binding=deepcopy(self.binding),request=deepcopy(request)),262144,side_bytes=0)

    def send(self,request):
        self.control();self.owner.bound();need(self.pending is None)
        self.pending=self.reserve(request);self.request=deepcopy(request);self.owner.bound();self.child_io()
        return self.original_send(request)

    def read(self):
        self.control();self.owner.bound();self.child_io();need(self.request is not None)
        token=self.pending if self.pending is not None else self.reserve(self.request);self.pending=None
        self.owner.bound();self.child_io();raw=self.original_read()
        # Archival identity/return clock is independent from lost business
        # authority. No parser, schema fence or JSON expansion precedes retain.
        reference=self.owner.raw.retain(token,raw)
        need(self.owner.raw.literal(reference)==raw)
        self.owner.bound();self.observer(reference,self.request)
        self.owner.bound();return raw


class NavigationSceneGeneration:
    """Gap ledger around the SAME original Continuation and G1 Flow.

    It records no substitute completion, reset, new restart or desired fact.
    Origin3's normal directory restoration is only one part of final cleanup;
    the actually observed pre-setup world and resource/host retirement remain
    explicitly outstanding until their separate original proofs are joined.
    """
    def __init__(self,owner,primary,actor):
        from adapters.pico4.navigation_continuation import NavigationContinuation
        need(type(owner) is NavigationScenePrefix and isinstance(primary,NavigationContinuation) and isinstance(actor,NavigationContinuation)
            and primary.prefix is owner.parents.get('primary') and actor.prefix is owner.parents.get('actor')
            and primary.prefix.role=='primary' and actor.prefix.role=='actor' and primary.prefix is not actor.prefix
            and primary.generation_factory is not None and actor.generation_factory is not None)
        self.owner,self.primary,self.actor=owner,primary,actor;self.handles=(owner,primary,actor)
        with owner.lock.held():
            owner.publish_bound();need(owner.state['phase']=='ready' and owner.state['restoration'] is None
                and len(primary.prefix.state['completed'])==11)
            restart=None if primary.continuation_disk is None else read_original(primary.continuation_store.path)
            generation=None if primary.generation_owner is None else read_original(primary.generation_owner.store.path)
            owner.change(phase='generation',restoration=dict(navigationSceneGenerationVersion=1,pending=None,
                restart=restart,generation=generation,frames=[],directory=None,userWorldRestored=False,rolesRetired=False,hostRetired=False))

    def control(self):
        need((self.owner,self.primary,self.actor)==self.handles);self.owner.publish_bound()
        need(self.primary.prefix is self.owner.parents['primary'] and self.actor.prefix is self.owner.parents['actor'])

    def pending(self,value):
        with self.owner.lock.held():
            self.control();state=self.owner.state['restoration'];need(state['pending'] is None)
            value_state=deepcopy(state);value_state['pending']=deepcopy(value);self.owner.change(restoration=value_state)

    def completed(self,**updates):
        with self.owner.lock.held():
            self.control();value=deepcopy(self.owner.state['restoration']);value.update(updates,pending=None)
            self.owner.change(restoration=value);self.owner.bill()
        self.control()

    def act(self,call):
        self.control();need(self.owner.state['phase']=='generation')
        self.pending(dict(kind='act',arguments=deepcopy(call)))
        result=self.primary.act(call);self.control()
        restart=read_original(self.primary.continuation_store.path)
        generation=None if self.primary.generation_owner is None else read_original(self.primary.generation_owner.store.path)
        self.completed(restart=restart,generation=generation);return result

    def observe(self,role):
        self.control();need(role in ('primary','actor') and self.owner.state['phase']=='generation')
        self.pending(dict(kind='observe',role=role));handle=self.primary if role=='primary' else self.actor
        result=handle.observe();self.completed();return result

    def frames(self,role,after_sequence):
        self.control();need(role in ('primary','actor') and self.owner.state['phase']=='generation')
        handle=self.primary if role=='primary' else self.actor
        self.pending(dict(kind='frames',role=role,afterSequence=after_sequence));result=handle.frames(after_sequence)
        self.control();rows=[*self.owner.state['restoration']['frames'],dict(role=role,sha256=json_digest(result))]
        self.completed(frames=rows);return result

    def restore_directory(self,call):
        self.control();need(self.owner.state['phase']=='generation')
        self.pending(dict(kind='directory-restoration',arguments=deepcopy(call)))
        with self.owner.lock.held():self.owner.change(phase='restoring')
        result=self.primary.restore(call);self.control()
        original=self.primary.generation_owner.restoration_owner
        need(original.state['phase']=='complete')
        reference=read_original(original.store.path)
        self.completed(directory=reference)
        with self.owner.lock.held():self.owner.change(phase='directory-restored')
        return result

    def report(self):
        self.control();state=deepcopy(self.owner.state['restoration'])
        return dict(navigationSceneGenerationVersion=1,phase=self.owner.state['phase'],journal=state,
            fullNavigationRecipe=False,deviceAcceptance=False,originalUserWorldRestorationPending=not state['userWorldRestored'],
            roleRetirementPending=not state['rolesRetired'],hostRetirementPending=not state['hostRetired'])

    def restore_world(self,call):
        self.control();need(self.owner.state['phase']=='directory-restored')
        self.pending(dict(kind='original-world-restoration',arguments=deepcopy(call)))
        from adapters.pico4.navigation_scene_original_world import NavigationSceneOriginalWorld
        with self.owner.lock.held():
            need(not hasattr(self,'user_world'))
            self.user_world=NavigationSceneOriginalWorld(self)
        result=self.user_world.restore(call)
        self.completed(userWorld=read_original(self.user_world.path),userWorldRestored=True)
        self.user_world.finalize();return result
