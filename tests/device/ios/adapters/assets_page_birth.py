"""Original normal page birth before any picker/file episode is staged.

The existing Upload source carrier supplies exactly the same bracketed native
UI/clock frame grammar. No upload/files object or future input is fabricated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import re
import time
from types import SimpleNamespace
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_action_phase import AssetsActionScope,AssetsActionPhases
from ios.adapters.assets_budget import operation
from ios.adapters.assets_controls import project,identity
from ios.adapters.assets_end_graph import AssetsFinalArchive
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_picker import root
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.normal_input import NativeInput

VERSION=1
SLOTS={'open-edit-menu':'assets.menu','open-assets':'assets.open'}


class AssetsPageBirth:
    @classmethod
    def from_archive(cls,selected,store,lock,actions,*,monotonic=time.monotonic):
        need(type(selected) is AssetsFinalArchive and type(actions) is AssetsActionPhases and actions.selected is selected
            and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock))
        completed=actions.read(1);need(completed['input']==dict(verb='open',inputs={}))
        return cls._archive(selected,store,lock,actions,completed['ticket'],monotonic)
    @classmethod
    def from_prefix(cls,selected,store,lock,actions,*,monotonic=time.monotonic):
        # A pending first action authorizes historical ownership only. It is
        # never a completed action, a current native fact, or end eligibility.
        need(type(selected) is AssetsFinalArchive and type(actions) is AssetsActionPhases and actions.selected is selected)
        actions.guard();need(actions.state is not None and same(actions.store.read(),actions.previous)
            and same(actions.envelope(),actions.previous))
        if actions.state['records']:return cls.from_archive(selected,store,lock,actions,monotonic=monotonic)
        pending=actions.state['pending'];need(pending is not None and pending['index']==1)
        actions.phase_packet(pending['before'],1,pending['ticket'])
        return cls._archive(selected,store,lock,actions,pending['ticket'],monotonic)
    @classmethod
    def _archive(cls,selected,store,lock,actions,ticket,monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock))
        owner=object.__new__(cls);owner.selected,owner.store,owner.lock,owner.actions=selected,store,lock,actions
        owner.action=None;owner.ticket=ticket;owner.binding=deepcopy(selected.context['roles']['primary']['binding'])
        owner.run,owner.role,owner.monotonic,owner.historical=selected.run,'primary',monotonic,True
        owner.clock=SimpleNamespace(pid=int(owner.binding['processIdentity']));owner.native=None;owner._cached=[]
        owner.previous=store.read();owner.state=None;owner.boundary()
        owner.originals=OriginalFrameStore(store.path.parent,owner.binding,owner.run,'primary',owner.guard,owner.frame_intent,
            namespace='assets-page-birth',schema_prefix='iosAssetsPageBirthSource',monotonic=monotonic)
        need(owner.previous is not None);owner.state=owner.decode(owner.previous);return owner
    # Only the existing actual frame carrier is reused. It neither requires a
    # file owner nor interprets upload success; normal page inputs remain here.
    capture=OwnedAssetsUpload.capture
    frame=OwnedAssetsUpload.frame
    frame_intent=OwnedAssetsUpload.frame_intent

    def __init__(self,selected,store,lock,action,native,clock,*,monotonic=time.monotonic):
        need(type(selected) is AssetsFinalArchive and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and type(action) is AssetsActionScope and action.owner.selected is selected and action.index==1
            and isinstance(native,NativeInput) and isinstance(clock,NativeFeatureObservation) and clock.ios and not clock.native_clock_bound)
        self.selected,self.store,self.lock,self.action,self.actions=selected,store,lock,action,action.owner
        self.binding=deepcopy(selected.context['roles']['primary']['binding']);self.run,self.role,self.ticket=selected.run,'primary',action.ticket
        self.native,self.clock,self.monotonic=native,clock,monotonic;self._native_capture=native.capture;self.historical=False
        self._cached=[];self.previous=store.read();self.state=None;self.boundary()
        self.originals=OriginalFrameStore(store.path.parent,self.binding,self.run,'primary',self.guard,self.frame_intent,
            namespace='assets-page-birth',schema_prefix='iosAssetsPageBirthSource',monotonic=monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
    def boundary(self):
        need(self.store.path==Path(self.selected.context['roles']['primary']['stateRoot'])/('ios-assets-page-birth-'+self.run+'-primary.json')
            and self.lock.path==self.store.path.with_name('script-feature-sources.lock')
            and self.clock.pid==int(self.binding['processIdentity']))
        self.lock.assert_held();self.selected.selected_guard()
    def guard(self):
        self.boundary();need(same(self.store.read(),self.previous))
        if not self.historical:self.action.guard()
        return True
    def link(self):
        self.guard();need(self.state is not None)
        return dict(iosAssetsPageBirthLinkVersion=1,path=str(self.store.path),ticket=self.ticket)
    def envelope(self):
        return dict(iosAssetsPageBirthVersion=VERSION,binding=self.binding,runId=self.run,role='primary',selectedPair=self.selected.link(),
            action=dict(path=str(self.actions.store.path),index=1,ticket=self.ticket),payload=pack([self.state]))
    def save(self):
        self.guard();need(not self.historical);value=self.envelope();self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)
    def frame_read(self,index):
        need(integer(index,1,len(self.state['frames'])));ref=self.originals.expand(self.state['frames'][index-1]);need(ref['index']==index)
        value=self.originals.read(ref);self.frame(value);return value
    def page(self):
        self.guard();need(self.state is not None and self.state['phase']=='opened')
        packet=self.frame_read(self.state['openedBy'])['ui'];page=root(project(packet),'page')
        need(page['visible'] and not page['busy'] and not page['bundleRequest'] and not page['pendingBundle'] and not page['destinationOpen']);return deepcopy(page)
    def decode(self,value):
        exact(value,{'iosAssetsPageBirthVersion','binding','runId','role','selectedPair','action','payload'})
        need(type(value['iosAssetsPageBirthVersion']) is int and value['iosAssetsPageBirthVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']=='primary'
            and same(value['selectedPair'],self.selected.link()) and same(value['action'],dict(path=str(self.actions.store.path),index=1,ticket=self.ticket)))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'phase','frames','pending','inputs','openedBy'})
        need(state['phase'] in ('reserved','opening','opened') and type(state['frames']) is list and len(state['frames'])<=32
            and type(state['inputs']) is list and len(state['inputs'])<=2)
        frames=[];prior=None
        for index,ref in enumerate(state['frames'],1):
            full=self.originals.expand(ref);need(full['index']==index);frame=self.originals.read(full);self.frame(frame,prior);frames.append(frame);prior=frame
        slots=set()
        for entry in state['inputs']:
            exact(entry,{'slot','before','command','receipt','resolvedBy'});slot=entry['slot'];need(slot in SLOTS and slot not in slots);slots.add(slot)
            need(integer(entry['before'],1,len(frames)));packet=frames[entry['before']-1]['ui'];reference=project(packet)
            targets=[row for row in reference['controls'] if row['id']==SLOTS[slot]];need(len(targets)==1)
            command=entry['command'];receipt=entry['receipt']
            if command is None:need(receipt is None and entry['resolvedBy'] is None);continue
            exact(command,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'});identity(command['commandId'])
            need(type(command['schemaVersion']) is int and command['schemaVersion']==1 and command['instance']==packet['instance']
                and type(command['sequence']) is int and command['sequence']==packet['lastSequence']+1 and command['observedElapsedMs']==packet['elapsedMs']
                and type(command['observedElapsedMs']) is int and command['fieldToken']==targets[0]['token'] and command['operation']=='activate')
            if receipt is not None:
                exact(receipt,{'schemaVersion','commandId','status'});status=receipt['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
                need(receipt['schemaVersion']==status['schemaVersion']==1 and type(receipt['schemaVersion']) is type(status['schemaVersion']) is int
                    and status['commandId']==command['commandId'] and status['instance']==command['instance'] and status['sequence']==command['sequence']
                    and type(status['sequence']) is int and status['performed'] is True and type(status['processId']) is int and status['processId']==self.clock.pid
                    and number(status['sampleEpochMs'],packet['sampleEpochMs'],packet['sampleEpochMs']+1500));need(type(receipt['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',receipt['commandId']) is not None)
            if entry['resolvedBy'] is not None:
                need(integer(entry['resolvedBy'],entry['before']+1,len(frames)));self.effect(entry,frames[entry['resolvedBy']-1]['ui'])
        pending=state['pending']
        if pending is not None:
            exact(pending,{'hostBefore','hostAfter','queries','clocks','ui','uiReceipt','original'})
            need(number(pending['hostBefore'],0,1e15) and type(pending['queries']) is list and type(pending['clocks']) is list)
            if pending['original'] is not None:self.originals.original(pending['original']);AssetsModelSources.prefix(self,pending['original'])
        if state['phase']=='opened':
            need(pending is None and 'open-assets' in slots and all(entry['resolvedBy'] is not None for entry in state['inputs'])
                and integer(state['openedBy'],1,len(frames)));page=root(project(frames[state['openedBy']-1]['ui']),'page')
            need(page['visible'] and not page['busy'] and not page['bundleRequest'] and not page['pendingBundle'] and not page['destinationOpen'])
        else:need(state['openedBy'] is None)
        self._cached=frames;return state
    def effect(self,entry,packet):
        need(entry['command'] is not None and packet['instance']==entry['command']['instance'] and packet['lastSequence']==entry['command']['sequence'])
        current=project(packet)
        if entry['slot']=='open-edit-menu':need(any(row['id']=='assets.open' for row in current['controls']))
        else:
            page=root(current,'page');need(page['visible'] and not page['busy'] and not page['pendingBundle'] and not page['destinationOpen'])
    @operation
    def reserve(self):
        self.guard();need(self.state is None);self.state=dict(phase='reserved',frames=[],pending=None,inputs=[],openedBy=None);self.save()
    def resolve(self,entry):
        need(entry['command'] is not None and entry['resolvedBy'] is None);packet=self.capture();self.effect(entry,packet)
        entry['resolvedBy']=len(self.state['frames']);self.save();return packet
    def input(self,slot):
        need(slot in SLOTS and not any(entry['slot']==slot or entry['resolvedBy'] is None for entry in self.state['inputs']))
        packet=self.capture();entry=dict(slot=slot,before=len(self.state['frames']),command=None,receipt=None,resolvedBy=None)
        self.state['inputs'].append(entry);self.save()
        def intent(command):need(entry['command'] is None);entry['command']=deepcopy(command);self.save();return True
        original=self.native.capture;self.native.capture=self.capture
        try:self.native.assets_input(SLOTS[slot],'activate',reference=project(packet),before_send=intent)
        finally:self.native.capture=original
        entry['receipt']=deepcopy(self.native.last_receipt);self.save();return self.resolve(entry)
    def prepare_slot(self,slot):
        entries=[entry for entry in self.state['inputs'] if entry['slot']==slot];need(len(entries)<=1)
        if not entries:return self.input(slot)
        entry=entries[0];need(entry['command'] is not None)
        if entry['resolvedBy'] is None:return self.resolve(entry)
    @operation
    def open(self):
        self.guard();need(self.state is not None and self.state['phase'] in ('reserved','opening','opened'))
        if self.state['phase']=='opened':return self.page()
        if self.state['phase']=='reserved':
            packet=self.capture();need(not any(row['alive'] and row['role'] in ('page','picker') for row in project(packet)['inventory']['roots']))
            self.state['phase']='opening';self.save()
        if not any(entry['slot']=='open-edit-menu' for entry in self.state['inputs']):
            current=project(self.capture())
            if not any(row['id']=='assets.open' for row in current['controls']):self.prepare_slot('open-edit-menu')
        else:self.prepare_slot('open-edit-menu')
        self.prepare_slot('open-assets');packet=self.capture();page=root(project(packet),'page')
        need(page['visible'] and not page['busy'] and not page['bundleRequest'] and not page['pendingBundle'] and not page['destinationOpen'])
        self.state.update(phase='opened',openedBy=len(self.state['frames']));self.save();return self.page()
