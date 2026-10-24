"""Independent readonly initial/Create observations from original target queries.

This first closed source stage has no input, G1 handoff, image or public feature
authority. A separate worker must own it; Primary results are not constructor
arguments. Later recipe stages require their own reviewed source admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import NativeFeatureObservation,decode,integer,need,number
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node,state as file_state,host
from adapters.pending_commit_owner import NativePendingCommitOwner
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_process import identity
from adapters.pico4.lifecycle_readonly import LifecycleReadOnlyAcquisition
from adapters.pico4.lifecycle_world import PicoLifecycleWorld
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import state as validate_state,typed_equal
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import projection

VERSION=1


class ActorReadOnlyTriple:
    originals=PicoLifecycleWorld.originals
    now=PicoLifecycleWorld.now
    fresh_current=PicoLifecycleWorld.fresh_current
    advance=staticmethod(LifecycleReadOnlyAcquisition.advance)

    def __init__(self,owner,source,axes,avatar):
        self.owner,self.source,self.axes,self.avatar=owner,source,axes,avatar
        self.pid,self.run,self.guard=owner.pid,owner.run,owner.guard
        self.monotonic=owner.monotonic
        self.last_clock=self.acquired_start=self.fresh_anchor=None

    def acquire(self):
        # Keep the unchanged complete World acquisition grammar, but retain
        # each actual response before its reader validates it or the next
        # producer is queried. No new query, reader or World journal exists.
        callbacks=[]
        try:
            for key,reader in (('gesture',self.axes),('drive',self.avatar),('ui',self.source)):
                original=reader.original;callbacks.append((reader,original))
                def received(key=key,original=original):
                    raw=original();self.owner.retain(key,dict(original=frame(raw)));return raw
                reader.original=received
            return PicoLifecycleWorld.acquire(self)
        finally:
            for reader,original in callbacks:reader.original=original


class PicoLifecycleActorSource:
    def __init__(self,path,run,binding,source,axes,avatar,pending,native,subject,phases,guard,
            source_lock,parent_host,*,monotonic):
        need(ui.nonce(run) and type(source) is ui.PicoLifecycleSource
            and type(axes) is gesture.PicoLifecycleGesture and type(avatar) is drive.PicoLifecycleDrive
            and type(pending) is NativePendingCommitOwner and type(native) is NativeFeatureObservation
            and type(subject) is NativeGraphicsSubject and type(phases) is PhaseFixtureReader
            and type(source_lock) is ScriptSourceLock and callable(guard) and callable(monotonic))
        self.binding=deepcopy(context(binding));self.pid,_start=identity(binding)
        self.run,self.lock,self.phases,self.guard,self.monotonic=run,source_lock,phases,guard,monotonic
        self.readers=(source,axes,avatar,pending,native,subject)
        need(all(reader.pid==self.pid for reader in self.readers)
            and phases.run==run and phases.area=='lifecycle-input'
            and pending.intent is None and pending._before_send is None
            and pending.last_raw is None and pending.last_request is None)
        for reader in (source,axes,avatar):
            need(reader.source_lock is None or reader.source_lock is self.lock);reader.source_lock=self.lock
            need(reader.previous is None and reader.last_raw is None)
        need(pending.last is None and native.sequence==0 and native.instance is None and subject.last is None)
        self.parent_host,self.host=parent_host,host_identity();host(parent_host)
        need(parent_host!=self.host)
        self.store=PrivateFeatureState(path);need(self.store.path.name=='lifecycle-actor-originals.json'
            and self.lock.path==self.store.path.with_name('script-sources.lock'))
        self.scope=dict(picoLifecycleActorSourceVersion=VERSION,runId=run,binding=self.binding,
            role='actor',stage='before-input-create',producerHostProcessIdentity=self.host,
            parentHostProcessIdentity=parent_host,fixtureUrl=phases.fixture_url)
        self.scope_sha=json_digest(self.scope);self.parent=parent_node(self.store)
        self.history=ChatSourceChunks(self.store,self.scope);self.disk=self.stamp=None
        self.parts=();self.raw_bytes=2;self.failed=False;self.anchor=None
        self.last_world=None;self.origin=None;self.baseline=None
        self.last_world_sha=json_digest(None);self.baseline_sha=json_digest(None)
        self.pending_floor=self.native_floor=self.subject_floor=None
        self.original_phases,self.original_client=phases,phases.client
        self.triple=ActorReadOnlyTriple(self,source,axes,avatar)
        with self.lock.held():
            need(self.store.read() is None);self.history.load([])
            self.disk=dict(self.scope,phase='reading',chunks=[],bundles=[],records=[],pending=None,publication=None)
            self.store.write(self.disk,None);self.pin()
        self.bound()

    def pin(self):
        value,_raw,stamp=file_state(self.store);need(typed_equal(value,self.disk))
        self.stamp=tuple(stamp);self.disk_sha=json_digest(self.disk)

    def bound(self):
        need(not self.failed and self.host==host_identity() and self.host!=self.parent_host)
        host(self.parent_host);host(self.host,current=True)
        need(json_digest(self.scope)==self.scope_sha==self.history.scope
            and self.scope['binding']==self.binding and self.scope['runId']==self.run
            and self.phases is self.original_phases and self.phases.client is self.original_client
            and self.phases.fixture_url==self.scope['fixtureUrl'] and parent_node(self.store)==self.parent
            and json_digest(self.baseline)==self.baseline_sha and json_digest(self.last_world)==self.last_world_sha
            and (self.origin is None if self.baseline is None else
                json_digest(self.origin.original)==json_digest(self.baseline['drive']))
            and self.lock.path==self.store.path.with_name('script-sources.lock')
            and all(reader.pid==self.pid for reader in self.readers)
            and all(reader.source_lock is self.lock for reader in self.readers[:3])
            and self.readers[3].intent is None and self.readers[3]._before_send is None)
        value,_raw,stamp=file_state(self.store)
        need(json_digest(value)==json_digest(self.disk)==self.disk_sha and tuple(stamp)==self.stamp)
        self.history.verify();need(tuple(self.history.identities)==self.parts and self.history.raw_bytes==self.raw_bytes)
        need(self.guard() is not False)
        for reader in self.readers:need(reader.guard() is not False)

    def previous(self):
        for key,reader in zip(('ui','gesture','drive'),self.readers[:3]):
            if self.last_world is None:need(reader.previous is None and reader.last_raw is None and reader.last_sha256 is None)
            else:
                packet=self.triple.originals(self.last_world)[key]
                previous=ui.summary(packet) if key=='ui' else packet
                need(json_digest(reader.previous)==json_digest(previous)
                    and reader.last_raw==self.last_world[key]['raw'] and reader.last_sha256==self.last_world[key]['sha256'])
        pending,native,subject=self.readers[3:]
        if self.pending_floor is None:need(pending.last is None and pending.last_raw is None and pending.last_request is None)
        else:need(json_digest(pending.last)==self.pending_floor['sha256'] and pending.last_raw==self.pending_floor['raw']
            and json_digest(pending.last_request)==self.pending_floor['requestSha256'])
        need((native.instance,native.sequence)==((None,0) if self.native_floor is None else self.native_floor))
        need(json_digest(subject.last)==json_digest(self.subject_floor))

    def save(self,value):
        self.lock.assert_held();self.bound();self.store.write(value,self.disk)
        self.disk=deepcopy(value);self.pin()

    def archive(self,value):
        reference,parts=source_bundles.prepare(value,len(self.disk['bundles']),self.disk['bundles'])
        for part in parts:
            self.bound();manifest=self.history.append(part,self.disk['chunks'])
            self.parts=tuple(self.history.identities);self.raw_bytes=self.history.raw_bytes
            updated=deepcopy(self.disk);updated['chunks']=manifest;self.save(updated)
        index=len(self.disk['bundles']);updated=deepcopy(self.disk);updated['bundles'].append(reference);self.save(updated)
        return index

    def fresh(self):
        self.bound();need(self.anchor is not None)
        started,requested,oldest=self.anchor;epoch=self.readers[4].clock_ms();ended=self.monotonic()
        need(integer(epoch,1) and number(ended,started,started+1.5) and -250<=epoch-oldest
            and max(epoch-oldest,requested-oldest+(ended-started)*1000)<=1500)

    def measurement(self,packets,pending,subject):
        actual=packets['ui']['source'];current=ui.current_editor(packets['ui'])
        if self.baseline is None:
            need(current is None and not actual['tabletShown'] and not any(row['alive'] for row in actual['editors']))
            self.baseline=deepcopy(packets)
            self.baseline_sha=json_digest(self.baseline)
            self.origin=drive.AvatarDisplacement(packets['drive'])
        prior={row['id'] for row in self.baseline['ui']['source']['editors']}
        new=[row for row in actual['editors'] if row['id'] not in prior]
        need(len(new)<=1 and all(row['kind']=='create' for row in new))
        ids=[row['id'] for row in new];generation=0 if current is None else ids.index(current['id'])+1
        before=self.baseline['gesture']['source']['events'];events=packets['gesture']['source']['events']
        need(events[:len(before)]==before)
        attempts=[row for row in events[len(before):] if row['kind']=='started']
        # This first Actor source stage cannot grant later world/retained-event
        # ownership by guessing an input envelope or a requested phase.
        need(not attempts and not pending['commit'] and not pending['resources']['pendingRuns']
            and pending['resources']['archivedEvents']==0 and pending['lastIntentSequence']==0
            and pending['current']['status']=='none')
        measured=self.origin.measure(packets['drive']);pose=subject['source']['avatarPose']
        source=packets['drive']['source']
        need(subject['source']['sceneUrl']==source['sceneUrl'] and abs(pose['modelScale']-source['modelScale'])<=1e-6
            and math.dist(pose['feetPosition'],source['feetPosition'])<=.025
            and abs(sum(a*b for a,b in zip(pose['orientation'],source['orientation'])))>=.999)
        facts=dict(editor=current['kind'] if current else 'none',text=current['text'] if current else '',
            keyboard=measured_keyboard(actual['keyboard']),focused=bool(current and current['focused']),
            heldInputs=measured['heldInputs'],worldDisplacement=measured['worldDisplacement'],
            positionDelta=dict(zip(('x','y','z'),measured['positionDelta'])),generation=generation,
            deferredInputs=len(pending['resources']['pendingRuns']),worldAttempts=len(attempts),staleAttempts=0)
        validate_state('lifecycle-input',facts,self.run);return facts

    def read(self):
        try:
            with self.lock.held():
                self.bound();need(self.disk['pending'] is None and len(self.disk['records'])<128)
                need(self.disk['publication'] is None or self.disk['publication']['phase']=='delivered')
                self.previous()
                before=self.phases.read();need(before['verb']=='baseline' if self.baseline is None else
                    before['verb']=='baseline' or before['verb']=='open-editor' and before['inputs']=={'editor':'create'})
                started=self.monotonic();requested=self.readers[4].clock_ms()
                updated=deepcopy(self.disk);updated['pending']=dict(phase=None,gesture=None,drive=None,ui=None,
                    world=None,pending=None,native=None,subject=None);self.save(updated)
                self.retain('phase',before['status'])
                world,packets,_start=self.triple.acquire();self.retain('world',dict(world=world))
                pending_reader,native_reader,subject_reader=self.readers[3:]
                pending=pending_reader.read(self.run)
                self.retain('pending',dict(pending=frame(pending_reader.last_raw),request=pending_reader.last_request))
                native=native_reader.read(native_reader.sequence);raw=native_reader.original();need(decode(raw)==native)
                self.retain('native',dict(native=frame(raw)))
                subject=subject_reader.read(self.run,require_avatar=True);raw=subject_reader.original();need(decode(raw)==subject)
                self.retain('subject',dict(subject=frame(raw)))
                need(native['instance']==subject['instance'])
                if self.last_world is not None:self.triple.advance(self.triple.originals(self.last_world),packets)
                facts=self.measurement(packets,pending,subject)
                after=self.phases.read(before['status']);need(typed_equal(after['status']['activations'],before['status']['activations']))
                phase=self.archive(after['status'])
                oldest=min(*(packet['capturedEpochMs'] for packet in packets.values()),pending['capturedEpochMs'],native['capturedEpochMs'],subject['capturedEpochMs'])
                self.anchor=started,requested,oldest
                value=dict(ticket=before['ticket'],actor='owned-observer',actorSequence=len(self.disk['records'])+1,
                    capturedEpochMs=oldest,facts=projection('lifecycle-input',facts))
                updated=deepcopy(self.disk);updated['records'].append(dict(originals=deepcopy(updated['pending']),phase=phase,publication=deepcopy(value)))
                updated['pending']=None;self.save(updated)
                self.last_world=deepcopy(world);self.last_world_sha=json_digest(self.last_world)
                self.pending_floor=dict(sha256=json_digest(pending),raw=pending_reader.last_raw,
                    requestSha256=json_digest(pending_reader.last_request))
                self.native_floor=(native_reader.instance,native_reader.sequence);self.subject_floor=deepcopy(subject_reader.last)
                returned=deepcopy(value);self.fresh()
            self.fresh();return returned
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Lifecycle initial source unresolved; originals retained, no query replayed') from None

    def retain(self,key,value):
        index=self.archive(value);updated=deepcopy(self.disk);updated['pending'][key]=index;self.save(updated)

    def before_publication(self,value):
        try:
            with self.lock.held():
                self.bound();need(self.disk['records'] and typed_equal(value,self.disk['records'][-1]['publication'])
                    and (self.disk['publication'] is None or self.disk['publication']['phase']=='delivered'))
                index=len(self.disk['records'])-1
                need(self.disk['publication'] is None or self.disk['publication']['record']<index)
                updated=deepcopy(self.disk);updated['publication']=dict(phase='issued',record=index,valueSha256=json_digest(value),fixture=None,reply=None)
                self.save(updated)
                expected,_=source_bundles.original(self.history,self.disk['chunks'],self.disk['bundles'],self.disk['records'][-1]['phase'])
                current=self.phases.read(expected);need(typed_equal(current['status']['activations'],expected['activations']))
                phase=self.archive(current['status']);updated=deepcopy(self.disk);updated['publication']['fixture']=phase;self.save(updated)
                self.fresh()
            self.fresh()
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Lifecycle publication unresolved; no publication replayed') from None

    def delivered(self,reply):
        try:
            with self.lock.held():
                self.bound();need(self.disk['publication'] is not None and self.disk['publication']['phase']=='issued')
                original=self.archive(dict(transportReply=deepcopy(reply)))
                updated=deepcopy(self.disk);updated['publication'].update(phase='delivered',reply=original);self.save(updated)
                self.fresh()
            self.fresh()
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Lifecycle publication receipt unresolved; originals retained') from None
