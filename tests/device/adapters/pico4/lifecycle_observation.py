"""Private fresh Lifecycle primary observations from the existing live owners.

No action, peer, image or finalization authority lives here. Every acquisition
still appends to the same capped World journal; archives never become samples.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.chat_journey import source_bundles
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pending_commit_owner import NativePendingCommitOwner,accept as pending_accept,validate as pending_validate
from adapters.observer_return import parent_node,state as file_state
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
from adapters.pico4.lifecycle_close import PicoLifecycleClose
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_editor import PicoLifecycleEditor
from adapters.pico4.lifecycle_pending import PicoLifecyclePending
from adapters.pico4.lifecycle_process import native as validate_native
from adapters.pico4.lifecycle_restore import PicoLifecycleRestore
from adapters.pico4.lifecycle_world import MAX_FRAMES
from adapters.pico4 import lifecycle_source as ui
from adapters.script_journey.history import canonical
from feature_journeys.contract import VERSION as CONTRACT_VERSION,result as feature_result
from feature_journeys.contract import arguments as feature_arguments

VERSION=2
FAMILIES={
    'chat':('lifecycle-chat-owner.json',),
    'background':('lifecycle-background-owner.json','lifecycle-background-originals.json'),
    'pending':('lifecycle-pending-owner.json','lifecycle-pending-originals.json'),
    'close':('lifecycle-close-owner.json','lifecycle-close-originals.json'),
}


class PicoLifecycleObservation:
    """One live primary cursor, bound to the existing original owner graph.

    Constructing another reader over retained files does not resurrect this
    cursor. A failed acquisition, lost CAS or failed real lock exit is terminal.
    The still-owned originals remain available to later explicit finalization.
    """
    def __init__(self,restore,editor,chat,pending,path):
        # The existing complete-graph entry retains its exact v1 wire profile.
        need(type(restore) is PicoLifecycleRestore and type(editor) is PicoLifecycleEditor
            and type(chat) is PicoLifecycleChatDraft and type(pending) is PicoLifecyclePending)
        self._initialize(restore,editor,chat,pending,path,version=1,reader=pending.pending)

    @classmethod
    def before_inputs(cls,restore,editor,reader,path):
        need(cls is PicoLifecycleObservation and type(restore) is PicoLifecycleRestore and type(editor) is PicoLifecycleEditor
            and type(reader) is NativePendingCommitOwner and reader.intent is None and reader._before_send is None
            and reader.last is None and reader.last_raw is None and reader.last_request is None)
        need(restore.state is not None and restore.state['phase']=='begun' and not restore.world.state['attempts']
            and (editor.state is None or editor.state['phase']=='prepared' and editor.state['tablet'] is None
                and not editor.state['inputs'] and editor.state['originalId'] is None))
        owner=cls.__new__(cls)
        owner._initialize(restore,editor,None,None,path,version=2,reader=reader)
        return owner

    def _initialize(self,restore,editor,chat,pending,path,*,version,reader):
        self.version=version
        self.restore,self.editor,self.chat,self.pending=restore,editor,chat,pending
        self.background=self.close=None
        self.world,self.native,self.reader=restore.world,restore.native,reader
        self.original_reader=reader
        self.run,self.binding,self.lock,self.pid=self.world.run,deepcopy(self.world.binding),self.world.lock,self.world.pid
        need(editor.lock is self.lock and editor.session is self.world.session and editor.source.source_lock is self.lock)
        need(editor.store.path==self.world.store.path.with_name('lifecycle-editor-owner.json'))
        if version==1:
            need(chat.joined is restore.joined and pending.world is self.world
                and chat.store.path==self.world.store.path.with_name('lifecycle-chat-owner.json')
                and pending.store.path==self.world.store.path.with_name('lifecycle-pending-owner.json'))
        self.store=PrivateFeatureState(path)
        need(self.store.path==self.world.store.path.with_name('lifecycle-primary-observation.json'))
        self.scope=dict(lifecyclePrimaryObservationVersion=version,runId=self.run,binding=self.binding,role='primary')
        self.scope_sha=json_digest(self.scope)
        self.owners=tuple(owner for owner in (restore,editor,chat,pending) if owner is not None)
        self.missing=set(FAMILIES) if version==2 else set()
        self.attached={}
        self.history=ChatSourceChunks(self.store,self.scope);self.parent=parent_node(self.store)
        self.chunk_identities=();self.chunk_raw_bytes=2
        self.disk=self.stamp=None;self.pin=None;self.failed=False;self.anchor=None;self.last_clock=None
        # Historical records are deliberately not adopted as a live cursor.
        with self.lock.held():
            need(self.store.read() is None);self.history.inventory(0);self.bound()

    def family_inventory(self,role):
        roots=FAMILIES[role]
        with os.scandir(self.store.path.parent) as entries:
            return {entry.name for entry in entries if any(entry.name==name or entry.name.startswith(name+'.frame-') for name in roots)}

    def absent(self,*,except_role=None):
        for role in self.missing:
            if role!=except_role:need(not self.family_inventory(role))

    def bound(self,*,except_role=None):
        need(not self.failed and self.world.run==self.run and self.world.binding==self.binding
            and self.restore.world is self.world and self.world.lock is self.lock
            and self.native.pid==self.reader.pid==self.pid and self.restore.native is self.native
            and self.reader is self.original_reader and self.editor.session is self.world.session
            and self.owners==tuple(owner for owner in (self.restore,self.editor,self.chat,self.pending,self.background,self.close) if owner is not None)
            and all(owner.run==self.run and owner.binding==self.binding and owner.lock is self.lock for owner in self.owners)
            and json_digest(self.scope)==self.scope_sha==self.history.scope)
        if self.version==1:need(self.pending.world is self.world and self.pending.pending is self.reader and self.chat.joined is self.restore.joined)
        else:
            need(self.version==2 and self.reader.intent is None and self.reader._before_send is None)
            self.absent(except_role=except_role)
            for role,owner in self.attached.items():
                need(getattr(self,role) is owner)
                if role=='chat':need(owner.joined is self.restore.joined)
                elif role=='background':need(owner.runtime is not None and owner.runtime[0] is self.world)
                elif role=='pending':need(owner.world is self.world and owner.background is self.background)
                else:need(owner.world is self.world and owner.pending is self.pending)
                expected={owner.store.path.name}
                if hasattr(owner,'originals') and owner.originals.disk is not None:
                    expected.add(owner.originals.root.path.name)
                    expected.update(owner.originals.history.names[:len(owner.originals.manifest)])
                need(self.family_inventory(role)==expected)
        need(parent_node(self.store)==self.parent and self.store.read()==self.disk)
        if self.disk is not None:
            need(json_digest(self.disk)==self.pin)
            value,_raw,physical=file_state(self.store);need(value==self.disk and tuple(physical)==self.stamp)
        self.history.verify()
        need(tuple(self.history.identities)==self.chunk_identities and self.history.raw_bytes==self.chunk_raw_bytes
            and type(self.history.raw_bytes) is int)
        for owner in self.owners:
            need(owner.store.read()==owner.disk)
        need(self.world.store.read()==self.world.disk and self.world.guard() is not False
            and self.native.guard() is not False and self.reader.guard() is not False)

    def attach_chat(self,owner):return self.attach('chat',owner)
    def attach_background(self,owner):return self.attach('background',owner)
    def attach_pending(self,owner):return self.attach('pending',owner)
    def attach_close(self,owner):return self.attach('close',owner)

    def attach(self,role,owner):
        # The caller holds this same lock continuously across the original
        # participant prepare and this binding. A publisher must never observe
        # a newly acquired family in the gap between those two operations.
        self.lock.assert_held()
        try:
            with self.lock.held():
                need(self.version==2 and role in self.missing and self.disk is not None and self.disk['records']
                    and self.disk['pending'] is None)
                self.bound(except_role=role)
                need(type(owner) is dict(chat=PicoLifecycleChatDraft,background=PicoLifecycleBackground,
                    pending=PicoLifecyclePending,close=PicoLifecycleClose)[role]
                    and owner.run==self.run and owner.binding==self.binding and owner.lock is self.lock
                    and owner.store.path==self.world.store.path.with_name(FAMILIES[role][0]))
                owner.load();need(owner.state is not None)
                if role=='chat':need(owner.joined is self.restore.joined and owner.state['phase']=='prepared')
                elif role=='background':need(self.chat is not None and owner.state['phase']=='prepared' and owner.runtime[0] is self.world)
                elif role=='pending':
                    need(self.background is not None and owner.background is self.background and owner.world is self.world
                        and owner.state['phase']=='prepared' and owner.state['eventId'] is None
                        and self.reader.last is not None and owner.pending.last is not None
                        and self.reader.last['instance']==owner.pending.last['instance'])
                    previous=self.previous_pending()
                    need(previous is not None)
                    old=self.live_pending(self.reader,[previous])
                    saved=self.owner_pending(owner)
                    new=self.live_pending(owner.pending,[saved])
                    pending_accept(old,new)
                else:need(self.pending is not None and owner.pending is self.pending and owner.state['phase']=='prepared')
                setattr(self,role,owner);self.attached[role]=owner;self.missing.remove(role)
                self.owners=tuple(item for item in (self.restore,self.editor,self.chat,self.pending,self.background,self.close) if item is not None)
                value=deepcopy(self.disk);value['attached'][role]=json_digest(owner.disk);value['absentRoles']=sorted(self.missing)
                self.save(value)
            self.bound()
        except Exception:
            self.failed=True
            raise NativeUIError('Lifecycle original participant attachment unresolved; no input issued') from None

    def previous_pending(self):
        """The previous immutable original is a continuity floor only."""
        if self.disk is None or not self.disk['records']:return None
        row,_=source_bundles.original(self.history,self.disk['chunks'],self.disk['bundles'],self.disk['records'][-1])
        pending,_=source_bundles.original(self.history,self.disk['chunks'],self.disk['bundles'],row['pendingBundle'])
        return dict(original=pending['pending'],request=pending['request'])

    def owner_pending(self,owner):
        need(owner.state is not None)
        row=owner.state['frames'][-1]['pending'] if owner.state['cleanup'] is None else owner.state['cleanup']['frames'][-1]
        owner.pending_packet(row) # Existing full historical grammar, no clock refresh.
        return row

    def live_pending(self,reader,originals):
        need(type(reader) is NativePendingCommitOwner and reader.last is not None)
        value=decode(reader.last_raw);pending_validate(value,reader.last_request,self.pid,value['capturedEpochMs'])
        need(value['runId']==self.run and json_digest(value)==json_digest(reader.last))
        original=dict(original=frame(reader.last_raw),request=deepcopy(reader.last_request))
        need(any(candidate is not None and json_digest(candidate)==json_digest(original) for candidate in originals))
        return value

    def save(self,value):
        self.bound();self.store.write(value,self.disk)
        actual,_raw,physical=file_state(self.store);need(actual==value)
        self.disk=deepcopy(value);self.pin=json_digest(self.disk);self.stamp=tuple(physical)

    def append_original(self,value):
        references=self.disk['bundles'];index=len(references)
        reference,parts=source_bundles.prepare(value,index,references)
        for part in parts:
            manifest=self.history.append(part,self.disk['chunks'])
            need(tuple(self.history.identities[:-1])==self.chunk_identities
                and len(self.history.identities)==len(self.chunk_identities)+1)
            self.chunk_identities=tuple(self.history.identities);self.chunk_raw_bytes=self.history.raw_bytes
            updated=deepcopy(self.disk);updated['chunks']=manifest
            self.save(updated)
        updated=deepcopy(self.disk);updated['bundles'].append(reference);self.save(updated)
        return index

    def source_state(self,packets,pending):
        current=ui.current_editor(packets['ui']);identities={}
        for owner,field,generation,kind in ((self.editor,'originalId',1,'create'),(self.chat,'originalId',2,'chat'),
                (self.pending,'scriptId',3,'scripts'),(self.pending,'replacementId',4,'scripts')):
            identifier=owner.state.get(field) if owner is not None and owner.state is not None else None
            if identifier is not None:
                need(ui.nonce(identifier) and identifier not in identities)
                identities[identifier]=(generation,kind)
        generation=0
        if current is not None:
            need(current['id'] in identities);generation,kind=identities[current['id']];need(current['kind']==kind)
        commit=pending['commit'];stale=0
        if commit:
            need(self.pending is not None and self.pending.state is not None
                and self.pending.state['eventId']==commit['observation']['eventId'])
            # Count original terminal native events, never the requested attempt.
            stale=sum(event['kind']=='rejected' and event['reason']=='context-retired'
                for event in commit['observation']['events'])
            need(stale<=1)
        else:need(self.pending is None or self.pending.state is None or self.pending.state['eventId'] is None)
        if self.version==2 and self.pending is None:
            need(not commit and not pending['resources']['pendingRuns'] and pending['resources']['archivedEvents']==0
                and pending['lastIntentSequence']==0 and pending['current']['status']=='none')
        actual=self.world.anchor.measure(packets['drive'])
        return dict(editor=current['kind'] if current else 'none',text=current['text'] if current else '',
            focused=bool(current and current['focused']),keyboard=measured_keyboard(packets['ui']['source']['keyboard']),
            generation=generation,deferredInputs=len(pending['resources']['pendingRuns']),staleAttempts=stale,
            worldAttempts=len(self.world.attempts(self.world.state,packets['gesture'])),heldInputs=actual['heldInputs'],
            worldDisplacement=actual['worldDisplacement'],positionDelta=dict(zip(('x','y','z'),actual['positionDelta'])))

    def resources(self,packets,pending):
        # This is the actual product inventory used by the common baseline.
        # Host evidence journals remain owned separately until post-baseline
        # archival; their existence is not a product-created file or panel.
        # A missing current editor cannot hide retained original Qt contexts.
        resources=['panel:lifecycle-'+row['id'] for row in packets['ui']['source']['editors'] if row['alive']]
        resources.extend('input:lifecycle-'+run for run in pending['resources']['pendingRuns'])
        return resources

    def fresh(self):
        self.bound();need(self.anchor is not None)
        started,requested,oldest=self.anchor
        epochs=(self.world.axes.clock_ms(),self.reader.clock_ms(),self.native.clock_ms())
        completed=self.world.monotonic()
        need(number(completed,0,1e15) and (self.last_clock is None or completed>=self.last_clock)
            and completed-started<20 and all(integer(epoch,1) and -250<=epoch-oldest
                and max(epoch-oldest,requested-oldest+(completed-started)*1000)<=1500 for epoch in epochs))
        self.last_clock=completed

    def observe_operation(self,operation,arguments):
        """Private observation-only OverteSession seam; no capability grant.

        No action, cleanup, expected state, peer or image can be supplied here.
        The normal session validates the same portable request/result again.
        """
        need(operation=='feature.lifecycle-input.observe')
        feature_arguments(operation,arguments);need(arguments['runId']==self.run)
        return self.read(after_sequence=arguments['afterSequence'])

    def read(self,*,after_sequence):
        need(integer(after_sequence) and not self.failed)
        started=self.world.monotonic();need(number(started,0,1e15))
        try:
            with self.lock.held():
                self.bound();self.world.load()
                need(self.world.state is not None and len(self.world.state['frames'])<MAX_FRAMES)
                need(self.restore.state is not None and self.restore.state['phase'] in ('begun','navigating','prepared'))
                # Revalidate physical owner grammars before using their actual
                # object IDs. Mutable in-memory states are not identity proof.
                for owner in (self.editor,self.chat,self.pending,self.restore,self.background,self.close):
                    if owner is not None:owner.load()
                references=[] if self.disk is None else self.disk['records']
                need(after_sequence==len(references) and (self.disk is None or self.disk['pending'] is None))
                previous=self.previous_pending()
                owner_floor=None
                if self.pending is not None:
                    saved=self.owner_pending(self.pending)
                    owner_floor=deepcopy(self.live_pending(self.pending.pending,[saved,previous]))
                readonly_floor=None
                if self.version==2:
                    if previous is None:need(self.reader.last is None and self.reader.last_raw is None and self.reader.last_request is None)
                    else:readonly_floor=deepcopy(self.live_pending(self.reader,[previous]))
                requested=self.world.axes.clock_ms();need(integer(requested,1))
                value=dict(self.scope,phase='reading',chunks=[] if self.disk is None else self.disk['chunks'],
                    records=deepcopy(references),bundles=[] if self.disk is None else deepcopy(self.disk['bundles']),
                    pending=dict(sequence=after_sequence+1,worldFrameIndex=len(self.world.state['frames']),pendingBundle=None,nativeBundle=None))
                if self.version==2:
                    value.update(attached={} if self.disk is None else deepcopy(self.disk['attached']),absentRoles=sorted(self.missing),
                        absenceParent=list(self.parent))
                self.save(value) # Durable read intent precedes any source query.
                packets=self.world.current();index=len(self.world.state['frames'])-1
                event=self.pending.state['eventId'] if self.pending is not None and self.pending.state is not None else ''
                pending=self.reader.read(self.run,event or '')
                pending_raw=self.reader.last_raw
                need(decode(pending_raw)==pending)
                pending_index=self.append_original(dict(pending=frame(pending_raw),request=deepcopy(self.reader.last_request)))
                updated=deepcopy(self.disk);updated['pending']['pendingBundle']=pending_index;self.save(updated)
                # Snapshot both original floors BEFORE read() advanced .last.
                # In v1 this is the same reader object as the mutating owner;
                # comparing its new .last with itself would reject every read.
                if readonly_floor is not None:pending_accept(readonly_floor,pending)
                if owner_floor is not None:pending_accept(owner_floor,pending)
                if self.version==2 and self.pending is None:
                    need(not pending['commit'] and not pending['resources']['pendingRuns']
                        and pending['resources']['archivedEvents']==0 and pending['lastIntentSequence']==0
                        and pending['current']['status']=='none')
                native=self.native.read(self.native.sequence);validate_native(native,self.pid)
                native_raw=self.native.original();need(decode(native_raw)==native)
                native_index=self.append_original(dict(native=frame(native_raw)))
                updated=deepcopy(self.disk);updated['pending']['nativeBundle']=native_index;self.save(updated)
                oldest=min(*(packet['capturedEpochMs'] for packet in packets.values()),pending['capturedEpochMs'],native['capturedEpochMs'])
                self.anchor=(started,requested,oldest)
                state=self.source_state(packets,pending)
                result=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=after_sequence+1,
                    capturedEpochMs=oldest,state=state,resources=self.resources(packets,pending),lifecycle=deepcopy(native['lifecycle']),artifacts=[])
                feature_result('feature.lifecycle-input.observe',result)
                row=dict(worldFrameIndex=index,worldSha256=hashlib.sha256(canonical(self.world.state['frames'][index])).hexdigest(),
                    nativeBundle=native_index,pendingBundle=pending_index,
                    owners={owner.store.path.name:json_digest(owner.disk) for owner in self.owners},
                    result=deepcopy(result))
                if self.version==2:row.update(absentRoles=sorted(self.missing),absenceParent=list(self.parent))
                row_index=self.append_original(row)
                completed=deepcopy(self.disk);completed['records'].append(row_index);completed['pending']=None;self.save(completed)
                delivered=deepcopy(result);self.fresh()
            # Includes the actual context-manager exit, physical originals,
            # installation/PID guards and both original clock domains.
            self.fresh();return delivered
        except Exception:
            self.failed=True
            raise NativeUIError('Lifecycle primary observation unresolved; original reads retained, none replayed') from None
