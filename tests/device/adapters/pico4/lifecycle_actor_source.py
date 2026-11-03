"""Independent readonly initial/Create/draft observations from target queries.

This first closed source stage has no input, G1 handoff, image or public feature
authority. A separate worker must own it; Primary results are not constructor
arguments. Later recipe stages require their own reviewed source admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import math

from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import NativeFeatureObservation,decode,integer,need,number,LIMIT
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node,raw_file,host
from adapters.pending_commit_owner import NativePendingCommitOwner
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_process import identity
from adapters.pico4.lifecycle_actor_storage import LifecycleActorStorage,VERSION
from adapters.pico4 import lifecycle_actor_world as world_ownership
from adapters.script_journey.history import canonical
from adapters.pico4.lifecycle_readonly import LifecycleReadOnlyAcquisition
from adapters.pico4.lifecycle_world import PicoLifecycleWorld
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import state as validate_state,typed_equal
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.witness import projection


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
                original,send=reader.original,reader.send;callbacks.append((reader,original,send))
                def issued(value,key=key,send=send):
                    self.owner.bound();self.owner.reserve_original()
                    self.owner.retain(key,dict(request=deepcopy(value)));return send(value)
                def received(key=key,original=original):
                    self.owner.reserve_original()
                    raw=original();self.owner.retain(key,dict(original=frame(raw)));return raw
                reader.send,reader.original=issued,received
            return PicoLifecycleWorld.acquire(self)
        finally:
            for reader,original,send in callbacks:reader.original,reader.send=original,send


class PicoLifecycleActorSource:
    def __init__(self,path,run,binding,source,axes,avatar,pending,native,subject,phases,guard,
            source_lock,parent_host,*,monotonic,world_profile=None):
        need(ui.nonce(run) and type(source) is ui.PicoLifecycleSource
            and type(axes) is gesture.PicoLifecycleGesture and type(avatar) is drive.PicoLifecycleDrive
            and type(pending) is NativePendingCommitOwner and type(native) is NativeFeatureObservation
            and type(subject) is NativeGraphicsSubject and type(phases) is PhaseFixtureReader
            and type(source_lock) is ScriptSourceLock and callable(guard) and callable(monotonic))
        self.binding=deepcopy(context(binding));self.pid,_start=identity(binding)
        self.run,self.lock,self.phases,self.guard,self.monotonic=run,source_lock,phases,guard,monotonic
        need(world_profile is None or type(world_profile) is dict)
        self.world_profile=deepcopy(world_profile);self.world_profile_sha=json_digest(self.world_profile)
        self.world_envelopes=[];self.world_envelopes_sha=json_digest(self.world_envelopes)
        self.world_original_sequence=None
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
            role='actor',stage='before-input-create' if world_profile is None else 'before-input-create-world',producerHostProcessIdentity=self.host,
            parentHostProcessIdentity=parent_host,fixtureUrl=phases.fixture_url)
        self.scope_sha=json_digest(self.scope);self.parent=parent_node(self.store)
        self.failed=False;self.anchor=None
        self.last_world=None;self.origin=None;self.baseline=None
        self.last_world_sha=json_digest(None);self.baseline_sha=json_digest(None)
        self.pending_floor=self.native_floor=self.subject_floor=None
        self.original_phases,self.original_client=phases,phases.client
        self.triple=ActorReadOnlyTriple(self,source,axes,avatar)
        with self.lock.held():
            self.storage=LifecycleActorStorage(self.store,self.scope,self.lock,self.ownership,self.storage_fresh)
        self.history=self.storage.history
        self.bound()

    @property
    def disk(self):return self.storage.disk

    def ownership(self):
        # Archiving an already acquired literal must not query the candidate
        # again. This original warm host/scope/namespace owns only storage.
        need(not self.failed and self.host==host_identity() and self.host!=self.parent_host)
        host(self.parent_host);host(self.host,current=True)
        need(json_digest(self.scope)==self.scope_sha
            and self.scope['binding']==self.binding and self.scope['runId']==self.run
            and self.phases is self.original_phases and self.phases.client is self.original_client
            and self.phases.fixture_url==self.scope['fixtureUrl'] and parent_node(self.store)==self.parent
            and json_digest(self.baseline)==self.baseline_sha and json_digest(self.last_world)==self.last_world_sha
            and json_digest(self.world_profile)==self.world_profile_sha
            and json_digest(self.world_envelopes)==self.world_envelopes_sha
            and (self.world_original_sequence is None if not self.world_envelopes else
                integer(self.world_original_sequence,1,128))
            and (self.origin is None if self.baseline is None else
                json_digest(self.origin.original)==json_digest(self.baseline['drive']))
            and self.lock.path==self.store.path.with_name('script-sources.lock')
            and all(reader.pid==self.pid for reader in self.readers)
            and all(reader.source_lock is self.lock for reader in self.readers[:3])
            and self.readers[3].intent is None and self.readers[3]._before_send is None)

    def identity(self):
        self.ownership()
        need(self.guard() is not False)
        for reader in self.readers:need(reader.guard() is not False)

    def bound(self):
        self.identity();self.storage.verify()

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

    def fresh(self):
        self.bound();self.clock_fresh()

    def storage_fresh(self):
        self.storage.verify();self.clock_fresh()

    def clock_fresh(self):
        need(self.anchor is not None)
        started,requested,oldest=self.anchor;epoch=self.readers[4].clock_ms();ended=self.monotonic()
        need(integer(epoch,1) and number(ended,started,started+1.5) and -250<=epoch-oldest
            and max(epoch-oldest,requested-oldest+(ended-started)*1000)<=1500)

    def query(self,key,reader,operation):
        # These readers belong exclusively to this readonly Actor. Preserve
        # even an unavailable/rejected literal response before validation;
        # Pending's input intent and before-send ownership remain untouched.
        send,original=reader.send,reader.original;request=[None];received=[]
        def issued(value):
            self.bound();self.reserve_original()
            request[0]=deepcopy(value)
            self.retain(key,dict(request=deepcopy(value)))
            return send(value)
        def response():
            self.reserve_original()
            raw=original();self.retain(key,{key:frame(raw),'request':deepcopy(request[0])})
            received.append(raw);return raw
        try:
            reader.send,reader.original=issued,response
            value=operation();need(received)
            return value,received[-1]
        finally:reader.send,reader.original=send,original

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
        count=world_ownership.measured_attempts(attempts,self.world_envelopes)
        need(not pending['commit'] and not pending['resources']['pendingRuns']
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
            deferredInputs=len(pending['resources']['pendingRuns']),worldAttempts=count,staleAttempts=0)
        validate_state('lifecycle-input',facts,self.run);return facts

    def admitted_phase(self,value):
        # Phase rows restrict which already-owned normal inputs this bounded
        # source may observe. They never provide editor/text/generation facts.
        # Multiple independent acquisitions under the SAME phase remain valid.
        rows=value['status']['activations'];limit=2 if self.world_profile is None else 3
        need(1<=len(rows)<=limit+1)
        expected=[dict(verb='baseline',inputs={})]
        expected.extend(dict(verb=row['verb'],inputs=expand(row['inputs'],fixture_context(self.run)))
            for row in SCENARIOS['lifecycle-input']['steps'][:limit])
        need(all(typed_equal(row['stimulus'],stimulus) for row,stimulus in zip(rows,expected)))
        if self.baseline is None:need(len(rows)==1)

    def world_restrictions(self,phase):
        if len(phase['status']['activations'])<4:return
        need(self.world_profile is not None)
        authorized=sum(row['stimulus']['verb']=='world-input' for row in phase['status']['activations'])
        if len(self.world_envelopes)==authorized:return
        need(len(self.world_envelopes)<authorized<=2)
        self.bound();self.storage.reserve(2*65536+len(canonical(self.world_profile))+4096)
        store=PrivateFeatureState(self.store.path.with_name('lifecycle-world-owner.json'))
        raw,physical=raw_file(store)
        def original(raw,physical):
            return dict(rawBase64=base64.b64encode(raw).decode('ascii'),sha256=hashlib.sha256(raw).hexdigest(),
                physical=list(physical),profile=deepcopy(self.world_profile),profileSha256=self.world_profile_sha)
        self.retain('world-owner',original(raw,physical))
        value=decode(raw.decode('utf-8'))
        # Persist the complete nested ownership decode charge before decoding
        # that history or querying another independent target source.
        self.storage.reserve_nested(world_ownership.decoded_bytes(value))
        envelopes=world_ownership.restrictions(value,self.run,self.binding,self.pid,self.world_profile)
        need(len(envelopes)==authorized and envelopes[:len(self.world_envelopes)]==self.world_envelopes)
        self.storage.reserve(2*65536+len(canonical(self.world_profile))+4096)
        again,stamp=raw_file(store)
        if again!=raw or list(stamp)!=list(physical):
            self.retain('world-owner-changed',original(again,stamp));need(False)
        self.world_envelopes=deepcopy(envelopes);self.world_envelopes_sha=json_digest(self.world_envelopes)
        self.world_original_sequence=len(self.disk['records'])+1

    def phase(self,key,previous=None,*,publication=False):
        # Retain each decoded endpoint response before the shared reader can
        # reject it. Phase metadata carries no native/editor facts.
        # Client caps the actual HTTP body at1MiB; canonical JSON can expand
        # UTF8 astral codepoints threefold. Literal native frames below use
        # sixfold escaping of the original262144-byte reader bound.
        self.bound();self.storage.reserve(3*1024*1024+4096)
        client=self.phases.client;request=client.request
        path='/runs/'+self.run+'/phase'
        def received(actual,*args,**kwargs):
            value=request(actual,*args,**kwargs)
            if actual==path and 'phase_nonce' in kwargs:
                if publication:self.storage.publication_phase(deepcopy(value))
                else:self.retain(key,deepcopy(value))
            return value
        try:
            client.request=received;return self.phases.read(previous)
        finally:client.request=request

    def read(self):
        try:
            with self.lock.held():
                self.bound();need(self.disk['pending'] is None and len(self.disk['records'])<128)
                need(self.disk['publication'] is None or self.disk['publication']['phase']=='delivered')
                self.previous()
                self.storage.begin()
                before=self.phase('phase-before')
                # Retain the actual input metadata even when its stage cannot
                # be admitted. A rejected phase must survive worker exit, but
                # it does not issue a native source intent or another input.
                self.admitted_phase(before)
                started=self.monotonic();requested=self.readers[4].clock_ms()
                self.world_restrictions(before)
                world,packets,_start=self.triple.acquire();self.retain('world',dict(world=world))
                pending_reader,native_reader,subject_reader=self.readers[3:]
                pending,_raw=self.query('pending',pending_reader,lambda:pending_reader.read(self.run))
                native,received=self.query('native',native_reader,lambda:native_reader.read(native_reader.sequence))
                self.bound();self.reserve_original();raw=native_reader.original()
                if raw!=received:self.retain('native',dict(native=frame(raw)))
                need(raw==received and decode(raw)==native)
                subject,received=self.query('subject',subject_reader,lambda:subject_reader.read(self.run,require_avatar=True))
                self.bound();self.reserve_original();raw=subject_reader.original()
                if raw!=received:self.retain('subject',dict(subject=frame(raw)))
                need(raw==received and decode(raw)==subject)
                need(native['instance']==subject['instance'])
                if self.last_world is not None:self.triple.advance(self.triple.originals(self.last_world),packets)
                facts=self.measurement(packets,pending,subject)
                after=self.phase('phase-after',before['status']);need(typed_equal(after['status']['activations'],before['status']['activations']))
                epochs=[packet['capturedEpochMs'] for packet in packets.values()]
                if packets['gesture']['source']['known']:epochs.append(packets['gesture']['source']['frameEpochMs'])
                for packet in (pending,native,subject):
                    epochs.append(packet['capturedEpochMs'])
                    if 'requestedEpochMs' in packet:epochs.append(packet['requestedEpochMs'])
                oldest=min(epochs)
                self.anchor=started,requested,oldest
                value=dict(ticket=before['ticket'],actor='owned-observer',actorSequence=len(self.disk['records'])+1,
                    capturedEpochMs=oldest,facts=projection('lifecycle-input',facts))
                self.storage.native_record(dict(phase=deepcopy(after['status']),publication=deepcopy(value),
                    worldOwnershipActorSequence=self.world_original_sequence))
                self.last_world=deepcopy(world);self.last_world_sha=json_digest(self.last_world)
                self.pending_floor=dict(sha256=json_digest(pending),raw=pending_reader.last_raw,
                    requestSha256=json_digest(pending_reader.last_request))
                self.native_floor=(native_reader.instance,native_reader.sequence);self.subject_floor=deepcopy(subject_reader.last)
                returned=deepcopy(value);self.fresh()
            self.fresh();return returned
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Lifecycle initial source unresolved; originals retained, no query replayed') from None

    def retain(self,key,value):self.storage.retain(key,value)

    def reserve_original(self):self.storage.reserve(6*LIMIT+4096)

    def before_publication(self,value):
        try:
            with self.lock.held():
                self.bound();self.storage.issue_publication(value)
                expected=self.storage.latest()['phase']
                current=self.phase('publication-phase',expected,publication=True)
                need(typed_equal(current['status']['activations'],expected['activations']))
                self.fresh();self.storage.retire_stage();self.fresh()
                self.storage.reserve(3*1024*1024+4096)
            self.fresh()
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Lifecycle publication unresolved; no publication replayed') from None

    def delivered(self,reply):
        try:
            with self.lock.held():
                # The actual returned transport literal precedes any current
                # candidate rejection. Its durable receipt grants no verdict.
                self.storage.retain_reply(reply);self.bound();self.storage.delivered(reply);self.fresh()
            self.fresh()
        except Exception:
            self.failed=True
            raise NativeUIError('Independent Lifecycle publication receipt unresolved; originals retained') from None

    def close_host(self):return self.storage.close_host()
