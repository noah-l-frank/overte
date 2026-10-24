"""Private fresh Lifecycle primary observations from the existing live owners.

No action, peer, image or finalization authority lives here. Every acquisition
still appends to the same capped World journal; archives never become samples.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.chat_journey import source_bundles
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node,state as file_state
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
from adapters.pico4.lifecycle_editor import PicoLifecycleEditor
from adapters.pico4.lifecycle_pending import PicoLifecyclePending
from adapters.pico4.lifecycle_process import native as validate_native
from adapters.pico4.lifecycle_restore import PicoLifecycleRestore
from adapters.pico4.lifecycle_world import MAX_FRAMES
from adapters.pico4 import lifecycle_source as ui
from adapters.script_journey.history import canonical
from feature_journeys.contract import VERSION as CONTRACT_VERSION,result as feature_result

VERSION=1


class PicoLifecycleObservation:
    """One live primary cursor, bound to the existing original owner graph.

    Constructing another reader over retained files does not resurrect this
    cursor. A failed acquisition, lost CAS or failed real lock exit is terminal.
    The still-owned originals remain available to later explicit finalization.
    """
    def __init__(self,restore,editor,chat,pending,path):
        need(type(restore) is PicoLifecycleRestore and type(editor) is PicoLifecycleEditor
            and type(chat) is PicoLifecycleChatDraft and type(pending) is PicoLifecyclePending)
        self.restore,self.editor,self.chat,self.pending=restore,editor,chat,pending
        self.world,self.native,self.reader=restore.world,restore.native,pending.pending
        self.run,self.binding,self.lock,self.pid=self.world.run,deepcopy(self.world.binding),self.world.lock,self.world.pid
        need(chat.joined is restore.joined and pending.world is self.world and editor.lock is self.lock
            and editor.session is self.world.session and editor.source.source_lock is self.lock
            and chat.lock is self.lock and pending.lock is self.lock
            and all(owner.run==self.run and owner.binding==self.binding for owner in (restore,editor,chat,pending)))
        need(editor.store.path==self.world.store.path.with_name('lifecycle-editor-owner.json')
            and chat.store.path==self.world.store.path.with_name('lifecycle-chat-owner.json')
            and pending.store.path==self.world.store.path.with_name('lifecycle-pending-owner.json'))
        self.store=PrivateFeatureState(path)
        need(self.store.path==self.world.store.path.with_name('lifecycle-primary-observation.json'))
        self.scope=dict(lifecyclePrimaryObservationVersion=VERSION,runId=self.run,binding=self.binding,role='primary')
        self.scope_sha=json_digest(self.scope);self.owners=(restore,editor,chat,pending)
        self.history=ChatSourceChunks(self.store,self.scope);self.parent=parent_node(self.store)
        self.chunk_identities=();self.chunk_raw_bytes=2
        self.disk=self.stamp=None;self.pin=None;self.failed=False;self.anchor=None;self.last_clock=None
        # Historical records are deliberately not adopted as a live cursor.
        with self.lock.held():
            need(self.store.read() is None);self.history.inventory(0);self.bound()

    def bound(self):
        need(not self.failed and self.world.run==self.run and self.world.binding==self.binding
            and self.restore.world is self.pending.world is self.world
            and self.chat.joined is self.restore.joined and self.world.lock is self.lock
            and self.native.pid==self.reader.pid==self.pid and self.restore.native is self.native
            and self.pending.pending is self.reader and self.editor.session is self.world.session
            and all(owner is original for owner,original in zip(
                (self.restore,self.editor,self.chat,self.pending),self.owners))
            and all(owner.run==self.run and owner.binding==self.binding and owner.lock is self.lock for owner in self.owners)
            and json_digest(self.scope)==self.scope_sha==self.history.scope)
        need(parent_node(self.store)==self.parent and self.store.read()==self.disk)
        if self.disk is not None:
            need(json_digest(self.disk)==self.pin)
            value,_raw,physical=file_state(self.store);need(value==self.disk and tuple(physical)==self.stamp)
        self.history.verify()
        need(tuple(self.history.identities)==self.chunk_identities and self.history.raw_bytes==self.chunk_raw_bytes
            and type(self.history.raw_bytes) is int)
        for owner in (self.editor,self.chat,self.pending,self.restore):
            need(owner.store.read()==owner.disk)
        need(self.world.store.read()==self.world.disk and self.world.guard() is not False
            and self.native.guard() is not False and self.reader.guard() is not False)

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
            identifier=owner.state.get(field) if owner.state is not None else None
            if identifier is not None:
                need(ui.nonce(identifier) and identifier not in identities)
                identities[identifier]=(generation,kind)
        generation=0
        if current is not None:
            need(current['id'] in identities);generation,kind=identities[current['id']];need(current['kind']==kind)
        commit=pending['commit'];stale=0
        if commit:
            need(self.pending.state is not None and self.pending.state['eventId']==commit['observation']['eventId'])
            # Count original terminal native events, never the requested attempt.
            stale=sum(event['kind']=='rejected' and event['reason']=='context-retired'
                for event in commit['observation']['events'])
            need(stale<=1)
        else:need(self.pending.state is None or self.pending.state['eventId'] is None)
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

    def read(self,*,after_sequence):
        need(integer(after_sequence) and not self.failed)
        try:
            with self.lock.held():
                self.bound();self.world.load()
                need(self.world.state is not None and len(self.world.state['frames'])<MAX_FRAMES)
                need(self.restore.state is not None and self.restore.state['phase'] in ('begun','navigating','prepared'))
                # Revalidate physical owner grammars before using their actual
                # object IDs. Mutable in-memory states are not identity proof.
                for owner in (self.editor,self.chat,self.pending,self.restore):owner.load()
                references=[] if self.disk is None else self.disk['records']
                need(after_sequence==len(references) and (self.disk is None or self.disk['pending'] is None))
                started=self.world.monotonic();requested=self.world.axes.clock_ms()
                need(number(started,0,1e15) and integer(requested,1))
                value=dict(self.scope,phase='reading',chunks=[] if self.disk is None else self.disk['chunks'],
                    records=deepcopy(references),bundles=[] if self.disk is None else deepcopy(self.disk['bundles']),
                    pending=dict(sequence=after_sequence+1,worldFrameIndex=len(self.world.state['frames']),pendingBundle=None,nativeBundle=None))
                self.save(value) # Durable read intent precedes any source query.
                packets=self.world.current();index=len(self.world.state['frames'])-1
                event=self.pending.state['eventId'] if self.pending.state is not None else ''
                pending=self.reader.read(self.run,event or '')
                pending_raw=self.reader.last_raw
                need(decode(pending_raw)==pending)
                pending_index=self.append_original(dict(pending=frame(pending_raw),request=deepcopy(self.reader.last_request)))
                updated=deepcopy(self.disk);updated['pending']['pendingBundle']=pending_index;self.save(updated)
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
                    owners={owner.store.path.name:json_digest(owner.disk) for owner in (self.editor,self.chat,self.pending,self.restore)},
                    result=deepcopy(result))
                row_index=self.append_original(row)
                completed=deepcopy(self.disk);completed['records'].append(row_index);completed['pending']=None;self.save(completed)
                delivered=deepcopy(result);self.fresh()
            # Includes the actual context-manager exit, physical originals,
            # installation/PID guards and both original clock domains.
            self.fresh();return delivered
        except Exception:
            self.failed=True
            raise NativeUIError('Lifecycle primary observation unresolved; original reads retained, none replayed') from None
