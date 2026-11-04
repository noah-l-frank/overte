"""Two-phase Source4 capture on the same original Parent and render owners.

Acquire/complete share one durable component clock. The caller lets native
autonomous production advance outside both locks between them. No frame
request, new source, replayed GPU acquire or fresh Parent deadline exists.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_fd_owner import require_directory
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.emote_capture import PicoEmoteCapture
from adapters.pico4.emote_model_draws import validate as draw_packet,ACTION
from adapters.pico4.emote_stream_archive import PicoEmoteStreamArchive
from adapters.pico4.emote_stream_cycle import PicoEmoteStreamCycle
from adapters.pico4.emote_stream_draws import remote_draws
from adapters.pico4.emote_stream_model_raw import PicoEmoteStreamModelRaw
from adapters.pico4.emote_stream_world_raw import PicoEmoteStreamWorldRaw
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical,same,pack,unpack
from adapters.world_render_evidence import original_pixels,validate as capture_packet
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=3
FIELDS={'phase','started','providerBefore','providerAfter','primary','avatarBefore','avatarAfter',
    'captureIntent','capture','modelRequest','draws','image','storage','inventory','retirement','failure'}
UNRESOLVED=[]
OWNED=[]


class PicoEmoteStreamCapture(PicoEmoteCapture):
    def __init__(self,cycle,index,world,models):
        need(type(cycle) is PicoEmoteStreamCycle and integer(index,1,256) and callable(world) and callable(models))
        cycle.locks();cycle.identity();need(cycle.phase=='armed' and set(cycle.streams)=={'primary','actor'})
        from adapters.pico4.emote_stream_capacity import PicoEmoteStreamCapacity
        need(type(cycle.capacity) is PicoEmoteStreamCapacity and cycle.policy.capacity is cycle.capacity
            and cycle.originals.capacity is cycle.capacity and cycle.capacity.archive is cycle.originals.archive
            and cycle.policy.version==(2 if cycle.capacity.source_profile is None else 3)
            and cycle.originals.archive.scope['picoEmoteStreamOriginalsVersion']==cycle.policy.version)
        self.cycle=self._cycle=cycle;self.parent=cycle.parent;self.primary=cycle.streams['primary'];self.source=cycle.streams['actor']
        self.lock,self.monotonic=self.source.lock,self.parent.source.monotonic;self._monotonic=self.monotonic
        self.binding,self.pid=deepcopy(self.source.binding),self.source.pid;self.run,self.role=self.source.run,'actor'
        self.root=self._root=Path(self.parent.source.artifact_root);self.index=self._index=index
        self.world=self._world=world;self.models=self._models=models
        self.guard=self.bound;self.failed=False;self.recovering=False;self.started=self.clock=None
        self.model_originals=None;self.file=self._file=object.__new__(LifecycleProcessFile);self.previous=None
        self._component_started=None
        self.world_originals=[]
        need(self.parent.state is not None and self.parent.state['phase']=='ready' and len(self.parent.state['steps'])==2
            and self.parent.state['steps'][1]['frame'] is not None and self.parent.state['steps'][1]['call']['verb']=='play')
        self.parent_prefix=self._parent_prefix=deepcopy(self.parent.previous);self.parent_pin=self._parent_pin=canonical(self.parent_prefix)
        key=hashlib.sha256(canonical(self.binding)).hexdigest()[:16]
        self.store=self._store=PrivateFeatureState(self.parent.store.path.with_name(self.parent.store.path.name+'.child-remote-capture-'+key+'-'+str(index)+'.json'))
        self._path=self.store.path
        need(self.store.read() is None and not any(path.name.startswith(self.store.path.name+'.') for path in self.store.path.parent.iterdir()))
        self.identity=dict(picoEmoteCaptureVersion=VERSION,mode='remote-avatar-source4',runId=self.run,index=index,
            binding=deepcopy(self.binding),artifactRoot=str(self.root),parentIdentity=deepcopy(self.parent.identity),
            parentPrefixSha256=hashlib.sha256(self.parent_pin).hexdigest(),
            primaryIdentity=deepcopy(self.primary.identity),actorIdentity=deepcopy(self.source.identity),
            rawScopeSha256=cycle.originals.archive.scope_sha)
        self.identity_sha=json_digest(self.identity);self.state={key:None for key in FIELDS};self.state['phase']='ready'
        self._state=self.state;self._state_bytes=canonical(self.state)
        OWNED.append(self) # Actual descriptor ownership outlives caller/traceback loss.
        try:LifecycleProcessFile.__init__(self.file,self.store);self.bound()
        except BaseException:UNRESOLVED.append(self);raise

    def locks(self):self.cycle.locks()

    def candidate(self):
        self.locks();need(not self.failed and self.cycle is self._cycle and json_digest(self.identity)==self.identity_sha
            and self.parent_prefix is self._parent_prefix and self.parent_pin is self._parent_pin
            and canonical(self.parent_prefix)==self.parent_pin and self.monotonic is self._monotonic
            and self.parent is self.cycle.parent and self.primary is self.cycle.streams['primary'] and self.source is self.cycle.streams['actor']
            and self.lock is self.source.lock and self.role=='actor' and self.index==self._index and self.root==self._root
            and self.world is self._world and self.models is self._models and self.file is self._file
            and self.store is self._store and self.store.path==self._path
            and json_digest(self.binding)==json_digest(self.source.binding) and self.pid==self.source.pid
            and self.state is self._state and canonical(self.state)==self._state_bytes
            and (self.state['started']==self._component_started or (self.previous is None and self.state['started'] is None)))
        self.cycle.identity();self.parent.bound();self.file.guard();require_directory(self.file.parent,self.store.path.parent)
        need(same(self.store.read(),self.previous))
        current=self.parent.previous;old=self.parent_prefix
        need(all(same(current[key],old[key]) for key in self.parent.identity)
            and all(same(current['state'][key],old['state'][key]) for key in ('started','epochMs','hostEpochMs','baseline'))
            and same(current['state']['steps'][:2],old['state']['steps']))
        return True

    def bound(self):
        self.candidate()
        for source in (self.primary,self.source):
            if self.recovering:
                source.file.guard();source.chunks.verify();need(same(source.store.read(),source.previous));source.policy.bound()
            else:source.guard()
        now=self.monotonic();need(number(now,0 if self.clock is None else self.clock,1e15)
            and (self._component_started is None or now-self._component_started<5))
        self.clock=now;return now

    def update(self,**changes):
        # Validate the OLD admitted graph before staging a new candidate. No
        # callback may turn a caller-mutated graph into admitted authority.
        self.bound();need(set(changes)<=FIELDS)
        state=deepcopy(self.state);state.update(deepcopy(changes))
        value=dict(self.identity,parentPrefix=deepcopy(self.parent_prefix),payload=pack([state]))
        try:
            self.file.write(value,self.previous)
            need(same(self.store.read(),value))
            self.previous=deepcopy(value);self.state=self._state=state;self._state_bytes=canonical(state)
            self.bound()
        except BaseException:self.failed=True;UNRESOLVED.append(self);raise

    def remember(self,key,value):self.update(**{key:value})

    def phase_ticket(self,packet):
        phase_packet(packet,run=self.run,area='emotes',request=packet['requestId'],epoch=packet['capturedEpochMs'])
        need(packet['active'] and packet['activations']);return packet['activations'][-1]['ticket']

    def source_original(self,role,reference):
        exact(reference,{'picoEmoteStreamCaptureSourceVersion','role','record','rawReference'})
        need(type(reference['picoEmoteStreamCaptureSourceVersion']) is int and reference['picoEmoteStreamCaptureSourceVersion']==1
            and reference['role']==role and role in ('primary','actor'))
        source=self.primary if role=='primary' else self.source
        reader=PicoEmoteStreamArchive(source.store,self.cycle.originals.path,guard=self.candidate)
        try:
            # A different already-issued raw read may be uncertain. This exact
            # confirmed role range must still replay; it never turns that
            # unrelated pending tail into acquisition/input authority.
            record,packet=reader.original(reference['record'])
            need(record['kind']=='sample' and same(record['rawReference'],reference['rawReference']))
            ticket=self.parent_prefix['state']['steps'][1]['call']['ticket']
            need(self.phase_ticket(record['phaseBefore'])==self.phase_ticket(record['phaseAfter'])==ticket)
            return packet
        finally:need(reader.close())

    def sample(self,role):
        source=self.primary if role=='primary' else self.source
        value=source.read();record,original=source.original(source.last_sample_record);need(same(value,original))
        reference=dict(picoEmoteStreamCaptureSourceVersion=1,role=role,record=source.last_sample_record,
            rawReference=deepcopy(record['rawReference']))
        need(same(self.source_original(role,reference),value));return reference

    def image_root(self):
        key=hashlib.sha256(canonical(self.binding)).hexdigest()[:16]
        return self.root/('emote-remote-images-'+self.run+'-'+key+'-'+str(self.index))

    def owned(self,*,raw=True):
        value=super().owned()
        for obj in (value.owner,value.capture,value.storage,value.receipts.cleanup):
            old=obj.guard
            def guard(old=old):self.bound();need(old() is not False);self.bound();return True
            obj.guard=guard
        if getattr(self.cycle,'capacity',None) is not None:
            original_read=value.storage.read
            def png_read(name):
                self.bound();self.cycle.capacity.png(self.role,value.storage.capture);self.bound()
                return original_read(name)
            value.storage.read=png_read
        if raw:self.bind_world_originals(value)
        return value

    def bind_world_originals(self,value):
        originals=PicoEmoteStreamWorldRaw(self)
        for obj,label,limit in ((value.capture,'world',262144),(value.storage,'storage',100000),(value.receipts.cleanup,'inventory',262144)):
            originals.bind(obj,label,limit)
        self.world_originals.append(originals)

    def validate_retirement(self,proof,owner):
        super().validate_retirement(proof,owner)
        before=self.source_original('actor',self.state['avatarBefore'])
        need(proof['memory']['instance']==before['source']['worldRenderInstance']
            and proof['memory']['instance']==self.state['capture']['instance']
            and same(owner['capture'],self.state['captureIntent']) and same(proof['memory'],self.state['storage'])
            and same(proof['files']['absent'],self.state['inventory']))

    def frame(self):
        need(self.model_originals is not None and self.state['draws'] is not None)
        return dict(ticket=self.parent_prefix['state']['steps'][1]['call']['ticket'],
            primary=self.source_original('primary',self.state['primary']),
            avatarBefore=self.source_original('actor',self.state['avatarBefore']),
            avatarAfter=self.source_original('actor',self.state['avatarAfter']),
            capture=deepcopy(self.state['capture']),draws=self.model_originals.original(self.state['draws']))

    def validate_frame(self,frame,raw):
        draw_packet(frame['draws'],self.state['modelRequest'],self.pid,self.source.clock_ms(),capture=frame['capture'])
        row=remote_draws(frame['primary'],frame['avatarBefore'],frame['avatarAfter'],frame['capture'],frame['draws'],self.pid,self.source.clock_ms())
        original_pixels(frame['capture'],raw);return row

    def acquire(self,ticket):
        identifier(ticket);self.bound();need(self.previous is None and self.state['phase']=='ready'
            and self.parent.state['phase']=='ready' and len(self.parent.state['steps'])==2
            and self.parent.state['steps'][1]['call']['ticket']==ticket)
        self._component_started=self.clock;self.update(phase='reading',started=self._component_started)
        try:
            floor=self.parent.effects.current_original(self.parent_prefix['state']['steps'][1]['frame'])['phaseAfter']
            status=self.parent.source.phase.status(floor);need(self.phase_ticket(status)==ticket);self.remember('providerBefore',status)
            self.remember('primary',self.sample('primary'));self.remember('avatarBefore',self.sample('actor'))
            owned=self.owned(raw=False);need(owned.owner.store.read() is None)
            intent,send=owned.capture.intent,owned.capture.send
            def reserve(command):
                need(self.state['captureIntent'] is None);WorldRenderOwner.acquisition(command)
                self.remember('captureIntent',command);intent(command);self.bound()
            def publish(command):
                need(same(command,self.state['captureIntent']) and same(owned.owner.owned()['capture'],command));self.bound();send(command)
            owned.capture.intent,owned.capture.send=reserve,publish
            self.bind_world_originals(owned) # Final callbacks attach once, before first send/get.
            packet,raw=owned.read(0);self.remember('capture',packet)
            images=self.images(create=True);image=images.write(ticket,packet,raw)
            if getattr(self.cycle,'capacity',None) is not None:self.cycle.capacity.png_accounted(self.role,images,image)
            self.model_originals=PicoEmoteStreamModelRaw(self,self.models())
            draws=self.model_originals.reader.read(packet);need(self.model_originals.last is not None)
            reference=deepcopy(self.model_originals.last);need(same(draws,self.model_originals.original(reference)))
            self.update(draws=reference,phase='awaiting-after')
            return dict(picoEmoteStreamCaptureVersion=VERSION,awaitingAutonomousNativeSample=True,
                issuedCaptureRequest=packet['requestId'],wholeFeatureComplete=False,stereoQualified=False,independentActorQualified=False)
        except BaseException:
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            try:self.update(failure='acquisition-refused')
            except BaseException:pass
            raise NativeUIError('Original passive Emote capture remains owned') from None

    def complete(self):
        self.bound();need(self.previous is not None and self.state['phase']=='awaiting-after')
        try:
            self.remember('avatarAfter',self.sample('actor'));raw=self.images().read(self.state['image'])
            frame=self.frame();self.validate_frame(frame,raw);owned=self.owned()
            need(same(owned.owner.owned()['capture'],self.state['captureIntent']));self.release(owned)
            status=self.parent.source.phase.status(self.state['providerBefore'])
            need(self.phase_ticket(status)==frame['ticket']);self.remember('providerAfter',status)
            self.update(phase='complete');frame=self.frame();self.validate_frame(frame,raw);self.bound()
            if getattr(self.cycle,'capacity',None) is not None:self.cycle.capacity.retired(self)
            return frame
        except BaseException:
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            try:self.update(failure='completion-refused')
            except BaseException:pass
            raise NativeUIError('Original passive Emote capture completion remains owned') from None

    def original(self):
        self.bound();need(self.state['phase']=='complete' and self.previous is not None)
        rows=unpack(self.previous['payload']);need(len(rows)==1 and json_digest(rows[0])==json_digest(self.state))
        frame=self.frame();raw=self.images().read(self.state['image']);self.validate_frame(frame,raw)
        self.validate_retirement(self.state['retirement'],self.state['retirement']['owner']);self.bound();return frame,raw

    def recover(self):
        self.recovering=True
        try:
            self.bound();need(self.state['captureIntent'] is not None and self.state['phase']!='complete')
            owned=self.owned();need(owned.owner.store.read() is not None);self.release(owned)
            self.bound();return deepcopy(self.state['retirement'])
        except BaseException:
            if self not in UNRESOLVED:UNRESOLVED.append(self)
            raise
        finally:self.recovering=False

    def close_host(self):
        result=self._file.close_host()
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        if result and self in OWNED:OWNED.remove(self)
        return result
