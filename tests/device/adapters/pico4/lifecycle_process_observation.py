"""Fresh G1 Lifecycle observations from the actual warm Process readers.

Old originals are continuity/history only. No old-PID reader is rebound and no
mutating World or new observer sequence is reconstructed from retained files.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.chat_journey import source_bundles
from adapters.native_feature_observation import decode,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node,state as file_state
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_world import PicoLifecycleWorld,MAX_FRAMES
from adapters.pico4.lifecycle_readonly import LifecycleReadOnlyAcquisition
from adapters.pico4 import lifecycle_source as ui,lifecycle_drive as drive
from feature_journeys.contract import VERSION as CONTRACT,result as feature_result

VERSION=4


class ProcessReadOnlyAcquisition:
    acquire=PicoLifecycleWorld.acquire
    originals=PicoLifecycleWorld.originals
    now=PicoLifecycleWorld.now
    fresh_current=PicoLifecycleWorld.fresh_current
    advance=staticmethod(LifecycleReadOnlyAcquisition.advance)

    def __init__(self,owner):
        self.owner=owner;runtime=owner.runtime
        self.source,self.axes,self.avatar=runtime.readers[3:]
        self.pid,self.run=owner.pid,owner.run
        self.monotonic=owner.monotonic
        self.guard=owner.current_guard
        self.last_clock=self.acquired_start=self.fresh_anchor=None

    def previous(self,original):
        packets=self.originals(original)
        for name,reader in (('ui',self.source),('gesture',self.axes),('drive',self.avatar)):
            prior=ui.summary(packets[name]) if name=='ui' else packets[name]
            need(json_digest(reader.previous)==json_digest(prior)
                and reader.last_raw==original[name]['raw'] and reader.last_sha256==original[name]['sha256'])


class PicoLifecycleProcessObservation:
    def __init__(self,operations,runtime,pending,path):
        from adapters.pico4.lifecycle_operations import PicoLifecycleOperations
        from adapters.pico4.lifecycle_restart_runtime import PicoLifecycleRestartRuntime
        from adapters.pending_commit_owner import NativePendingCommitOwner
        need(type(operations) is PicoLifecycleOperations and type(runtime) is PicoLifecycleRestartRuntime
            and runtime.operations is operations and runtime.handoff is not None
            and type(pending) is NativePendingCommitOwner and pending.intent is None and pending._before_send is None
            and pending.last is None and pending.last_raw is None and pending.last_request is None)
        self.operations,self.runtime,self.pending=operations,runtime,pending
        self.process,self.memo,self.readers=runtime.process,runtime.memo,runtime.readers
        self.binding=deepcopy(runtime.handoff['binding']);self.pid=int(self.binding['processIdentity'].split(':')[0])
        self.run,self.lock=operations.source.run,operations.lock
        self.monotonic=self.process.monotonic
        need(pending.pid==self.pid and self.readers is self.memo['readers'] and self.process._final_delivery is self.memo)
        self.old_source=operations.source;self.old_disk=deepcopy(self.old_source.disk);self.old_stamp=self.old_source.stamp
        self.boundary=deepcopy(operations.state['cleanup']['sourceBoundary']);self.initial=self.boundary['sequence']
        self.boundary_sha=json_digest(self.boundary)
        last,_=source_bundles.original(self.old_source.history,self.old_disk['chunks'],self.old_disk['bundles'],self.old_disk['records'][-1])
        need(type(self.initial) is int and self.initial==len(self.old_disk['records'])
            and json_digest(last['result'])==self.boundary_sha
            and self.boundary['state']['worldAttempts']==len(self.old_source.world.state['attempts']))
        self.store=PrivateFeatureState(path);need(self.store.path==self.old_source.store.path.with_name('lifecycle-primary-process-observation.json'))
        self.scope=dict(lifecyclePrimaryObservationVersion=VERSION,contractVersion=CONTRACT,runId=self.run,
            binding=self.binding,originalBinding=deepcopy(self.old_source.binding),initialSequence=self.initial,role='primary-process')
        self.scope_sha=json_digest(self.scope);self.history=ChatSourceChunks(self.store,self.scope)
        self.parent=parent_node(self.store);self.disk=self.stamp=self.anchor=None;self.failed=False
        self.last_world=None;self.last_pending=None
        self.process_state_sha=json_digest(self.process.state)
        self.floor={key:deepcopy(self.process.state['next']['frames'][-1][key]) for key in ('ui','gesture','drive','hostMonotonic')}
        first=self.process.state['next']['frames'][0]
        self.drive_anchor=drive.AvatarDisplacement(decode(first['drive']['raw']))
        self.drive_anchor_sha=json_digest(self.drive_anchor.original)
        original=self.process.history(self.process.state['originalWorld'],self.old_source.binding)
        self.original_drive=original.originals(original.state['frames'][0])['drive']
        self.original_drive_sha=json_digest(self.original_drive)
        self.acquisition=ProcessReadOnlyAcquisition(self)
        with self.lock.held():
            need(self.store.read() is None);self.history.load([])
            self.disk=dict(self.scope,phase='reading',chunks=[],bundles=[],records=[],pending=None)
            self.store.write(self.disk,None);self.pin()
        self.current_guard();runtime.final()

    def current_guard(self):
        need(self.process.guard() is not False)
        for reader in self.readers:need(reader.guard() is not False)
        need(self.pending.guard() is not False);return True

    def pin(self):
        value,_raw,physical=file_state(self.store);need(value==self.disk)
        self.disk_sha=json_digest(self.disk)
        self.stamp=tuple(physical);self.chunks=tuple(self.history.identities);self.raw_bytes=self.history.raw_bytes

    def control(self):
        self.lock.assert_held();self.original_control();self.current_guard()

    def original_control(self):
        self.operations.final_identity()
        need(not self.failed and self.runtime.memo is self.memo and self.process._final_delivery is self.memo
            and self.runtime.readers is self.readers and self.memo['readers'] is self.readers
            and self.process.state['next']['binding']==self.binding and self.process.state['phase']=='process-retired'
            and json_digest(self.process.state)==self.process_state_sha
            and json_digest(self.process.disk)==self.memo['diskSha256']
            and json_digest(self.drive_anchor.original)==self.drive_anchor_sha
            and json_digest(self.original_drive)==self.original_drive_sha
            and self.scope_sha==json_digest(self.scope)==self.history.scope and parent_node(self.store)==self.parent
            and json_digest(self.boundary)==self.boundary_sha
            and json_digest(self.old_disk)==self.old_source.pin==json_digest(self.old_source.disk)
            and type(self.initial) is int and self.initial==self.scope['initialSequence']==self.boundary['sequence']==len(self.old_disk['records'])
            and self.process.physical is self.memo['physical'] and self.process.physical.file is self.memo['file']
            and self.process.physical.stamp==self.memo['stamp']
            and self.process.lock is self.lock and self.readers[2].source_lock is self.lock
            and all(reader.pid==self.pid for reader in self.readers)
            and all(reader.source_lock is self.lock for reader in self.readers[3:])
            and all(current is saved for current,saved in zip(
                (self.acquisition.source,self.acquisition.axes,self.acquisition.avatar),self.readers[3:]))
            and self.pending.pid==self.pid and self.pending.intent is None and self.pending._before_send is None)
        self.process.physical.guard()
        value,_raw,physical=file_state(self.old_source.store)
        need(value==self.old_disk==self.old_source.disk and tuple(physical)==self.old_stamp)
        self.old_source.history.verify()
        need(tuple(self.old_source.history.identities)==self.old_source.chunk_identities
            and self.old_source.history.raw_bytes==self.old_source.chunk_raw_bytes)
        value,_raw,physical=file_state(self.store)
        need(json_digest(value)==json_digest(self.disk)==self.disk_sha and tuple(physical)==self.stamp)
        self.history.verify();need(tuple(self.history.identities)==self.chunks and self.history.raw_bytes==self.raw_bytes)

    def save(self,value):
        self.control();self.store.write(value,self.disk);self.disk=deepcopy(value);self.pin()

    def archive(self,value):
        reference,parts=source_bundles.prepare(value,len(self.disk['bundles']),self.disk['bundles'])
        for part in parts:
            self.control();manifest=self.history.append(part,self.disk['chunks'])
            self.chunks=tuple(self.history.identities);self.raw_bytes=self.history.raw_bytes
            updated=deepcopy(self.disk);updated['chunks']=manifest;self.save(updated)
        updated=deepcopy(self.disk);updated['bundles'].append(reference);self.save(updated)
        return len(self.disk['bundles'])-1

    def fresh(self,*,after_guard=None):
        self.original_control();self.current_guard()
        if after_guard is not None:after_guard()
        need(self.anchor is not None);started,requested,oldest=self.anchor
        epoch=self.readers[0].clock_ms();completed=self.monotonic()
        need(integer(epoch,1) and number(completed,started,started+1.5) and -250<=epoch-oldest
            and max(epoch-oldest,requested-oldest+(completed-started)*1000)<=1500)

    def quiet_originals(self,first):
        """Validate the fresh readonly window already consumed by this owner.

        No sample, input, timer or Process-window mutation occurs. This is a
        primary original-window proof, not independent Actor/Common execution.
        """
        try:
            with self.lock.held():
                self.control();self.fresh()
                need(type(first) is int and 0<=first<len(self.disk['records']))
                rows=deepcopy(self.disk['records'][first:]);need(len(rows)>=3)
                window=drive.AvatarReleaseWindow(self.drive_anchor)
                start=end=None;prior=None
                from adapters.pending_commit_owner import validate as pending_validate
                from adapters.pico4.lifecycle_process import closed
                for index,row in enumerate(rows,first):
                    need(row['result']['sequence']==self.initial+index+1 and row['result']['resources']==[])
                    original,_=source_bundles.original(self.history,self.disk['chunks'],self.disk['bundles'],row['originals']['world'])
                    current=self.acquisition.originals(original['world']);closed(current['ui'])
                    need(not any(item['alive'] for item in current['ui']['source']['editors']))
                    pending,_=source_bundles.original(self.history,self.disk['chunks'],self.disk['bundles'],row['originals']['pending'])
                    need(frame(pending['pending']['raw'])==pending['pending'])
                    packet=decode(pending['pending']['raw'])
                    pending_validate(packet,pending['request'],self.pid,packet['capturedEpochMs'])
                    from adapters.pending_commit_owner import accept
                    accept(prior,packet);prior=packet
                    need(not packet['commit'] and packet['current']['status']=='none' and packet['lastIntentSequence']==0
                        and not packet['resources']['pendingRuns'] and packet['resources']['archivedEvents']==0)
                    measured=self.drive_anchor.measure(current['drive']);need(not measured['heldInputs'])
                    point=current['drive']['source']['feetPosition'];old=self.original_drive['source']['feetPosition']
                    need(math.sqrt(sum((value-origin)**2 for value,origin in zip(point,old)))<=.025)
                    observed=window.observe(current['drive'],original['world']['hostMonotonic'])
                    if start is None:start=(current['drive']['capturedEpochMs'],original['world']['hostMonotonic'])
                    end=(current['drive']['capturedEpochMs'],original['world']['hostMonotonic'])
                need(observed and end[0]-start[0]>=3000 and end[1]-start[1]>=3)
                result=dict(firstSequence=rows[0]['result']['sequence'],lastSequence=rows[-1]['result']['sequence'],
                    advancingSamples=len(rows),nativeMilliseconds=end[0]-start[0],hostSeconds=end[1]-start[1],
                    recordsSha256=json_digest(rows),callbackScope='native-pending-owner-and-observed-Qt-contexts')
                returned=deepcopy(result);self.fresh()
            self.fresh();return returned
        except Exception:
            self.failed=True
            raise NativeUIError('Lifecycle fresh primary quiet window unresolved; originals retained') from None

    def read(self,*,after_sequence):
        need(type(after_sequence) is int and not self.failed)
        try:
            with self.lock.held():
                self.control();need(after_sequence==self.initial+len(self.disk['records'])
                    and self.disk['pending'] is None and len(self.disk['records'])<MAX_FRAMES)
                started=self.monotonic();requested=self.readers[0].clock_ms()
                self.acquisition.previous(self.floor if self.last_world is None else self.last_world)
                updated=deepcopy(self.disk);updated['pending']=dict(world=None,pending=None,native=None,presence=None,domain=None)
                self.save(updated)
                original,packets,_start=self.acquisition.acquire()
                world_index=self.archive(dict(world=original));updated=deepcopy(self.disk);updated['pending']['world']=world_index;self.save(updated)
                self.pending.read(self.run);pending=deepcopy(self.pending.last)
                pending_index=self.archive(dict(pending=frame(self.pending.last_raw),request=self.pending.last_request))
                updated=deepcopy(self.disk);updated['pending']['pending']=pending_index;self.save(updated)
                from adapters.pending_commit_owner import accept
                accept(self.last_pending,pending)
                need(not pending['commit'] and not pending['resources']['pendingRuns'] and pending['lastIntentSequence']==0
                    and pending['resources']['archivedEvents']==0 and pending['current']['status']=='none')
                native,presence,domain=self.readers[:3]
                receipt=native.read(native.sequence);raw=native.original();need(decode(raw)==receipt)
                native_index=self.archive(dict(native=frame(raw)));updated=deepcopy(self.disk);updated['pending']['native']=native_index;self.save(updated)
                absent=presence.read(self.old_source.pid);raw=presence.original();need(decode(raw)==absent)
                absence_index=self.archive(dict(presence=frame(raw)));updated=deepcopy(self.disk);updated['pending']['presence']=absence_index;self.save(updated)
                need(absent['presence']=='absent')
                connected=domain.read(self.run)
                raw=domain.native.original();need(decode(raw)==connected)
                domain_index=self.archive(dict(domain=frame(raw)));updated=deepcopy(self.disk);updated['pending']['domain']=domain_index;self.save(updated)
                now=self.monotonic();row=dict(original,native=receipt,presence=absent,domain=connected,
                    requestedEpochMs=requested,durationSeconds=now-started)
                old=self.process.history(self.process.state['shutdown']['world'],self.old_source.binding)
                self.process.new_frame(row,self.process.state,self.binding,old.originals(old.state['frames'][-1]))
                self.acquisition.advance(self.acquisition.originals(self.floor if self.last_world is None else self.last_world),packets)
                # Same-PID continuity comes from the actual returned G1 window.
                # The absolute restore delta still uses the original frozen
                # G0 feet; new_frame above independently verifies that restore.
                actual=self.drive_anchor.measure(packets['drive'])
                delta=[value-origin for value,origin in zip(packets['drive']['source']['feetPosition'],self.original_drive['source']['feetPosition'])]
                actual.update(positionDelta=delta,worldDisplacement=math.sqrt(sum(value*value for value in delta)))
                current=ui.current_editor(packets['ui'])
                need(current is None and not any(item['focused'] for item in packets['ui']['source']['editors']))
                state=dict(editor='none',text='',generation=0,focused=False,keyboard=measured_keyboard(packets['ui']['source']['keyboard']),
                    heldInputs=actual['heldInputs'],worldDisplacement=actual['worldDisplacement'],positionDelta=dict(zip(('x','y','z'),actual['positionDelta'])),
                    deferredInputs=len(pending['resources']['pendingRuns']),worldAttempts=self.boundary['state']['worldAttempts'],staleAttempts=self.boundary['state']['staleAttempts'])
                resources=['panel:lifecycle-'+item['id'] for item in packets['ui']['source']['editors'] if item['alive']]
                oldest=min(*(value['capturedEpochMs'] for value in packets.values()),pending['capturedEpochMs'],receipt['capturedEpochMs'],absent['capturedEpochMs'],connected['capturedEpochMs'])
                self.anchor=started,requested,oldest
                result=dict(schemaVersion=1,contractVersion=CONTRACT,runId=self.run,sequence=after_sequence+1,capturedEpochMs=oldest,
                    state=state,resources=resources,lifecycle=deepcopy(receipt['lifecycle']),artifacts=[])
                feature_result('feature.lifecycle-input.observe',result)
                updated=deepcopy(self.disk);updated['records'].append(dict(originals=deepcopy(updated['pending']),result=deepcopy(result)))
                updated['pending']=None;self.save(updated)
                self.last_world,self.last_pending=deepcopy(original),deepcopy(pending)
                returned=deepcopy(result);self.fresh()
            self.fresh();return returned
        except Exception:
            self.failed=True
            raise NativeUIError('Lifecycle new-process observation unresolved; originals retained, no source replayed') from None
