"""Durable one-send Snapshot control input and original lost-return recovery.

This owner proves input delivery only. Capture/cancel/export outcomes, images,
files, independently witnessed effects and resource retirement remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.normal_input import NativeInput
from ios.adapters import snapshot_capture_controls as capture,snapshot_export_controls as export,snapshot_inputs as inputs

VERSION=1


class SnapshotInputPending(NativeUIError):pass


def reference(value,control):
    need(control in inputs.IDS and type(value) is dict)
    module=capture if control in capture.IDS else export;key='iosSnapshotCaptureControlsVersion' if module is capture else 'iosSnapshotExportControlsVersion'
    exact(value,{key,'scope','open','controls'});scope=value['scope']
    exact(scope,{'processId','instance','sampleEpochMs','elapsedMs','sequence'})
    raw=dict(processId=scope['processId'],instance=scope['instance'],sampleEpochMs=scope['sampleEpochMs'],elapsedMs=scope['elapsedMs'],
        lastSequence=scope['sequence'],tabletShown=value['open'],controls=deepcopy(value['controls']),
        **{('snapshotCaptureControlsVersion' if module is capture else 'snapshotExportControlsVersion'):value[key]})
    need(same(module.project(raw),value));rows=[row for row in value['controls'] if row['id']==control]
    need(value['open'] and len(rows)==1 and rows[0]['enabled'] and rows[0]['inputReady']);return rows[0]


def receipt(value,command,pid,after):
    exact(value,{'schemaVersion','commandId','status'});need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
    status=value['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
    need(type(status['schemaVersion']) is int and status['schemaVersion']==1 and status['performed'] is True
        and type(status['processId']) is int and status['processId']==pid and integer(status['sampleEpochMs'],after)
        and all(status[k]==command[k] for k in ('commandId','instance','sequence')) and type(status['sequence']) is int)
    return value


class SnapshotInputOwner:
    _owner_key='iosSnapshotInputOwnerVersion'
    _proof_namespace='snapshot-input-proof'
    _proof_schema='snapshotInputProof'
    _reference=staticmethod(reference)
    _input_source=inputs
    _root_is_stable=True

    @staticmethod
    def store_name(role):return 'ios-snapshot-'+role+'-inputs.json'

    @classmethod
    def history(cls,store,lock,binding,run,role):
        """Original-file reader after native/SDK retirement; no transport."""
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor'))
        context(binding);identifier(run);need(re.fullmatch('[1-9][0-9]*',binding['processIdentity'])
            and store.path.parent==lock.path.parent and store.path.name==cls.store_name(role))
        reader=cls.__new__(cls);reader.store,reader.lock,reader.binding,reader.run,reader.role=store,lock,deepcopy(binding),run,role
        reader.pid=int(binding['processIdentity']);reader.native=None
        def unavailable():raise NativeUIError('Historical Snapshot input owner cannot issue live operations')
        reader.guard=unavailable;lock.assert_held();reader.previous=store.read();need(reader.previous is not None)
        reader.state=reader.decode(reader.previous);return reader

    def __init__(self,store,lock,binding,run,role,native,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and isinstance(native,NativeInput)
            and callable(guard) and role in ('primary','actor'));context(binding);identifier(run)
        self.store,self.lock,self.binding,self.run,self.role,self.native,self.guard=store,lock,deepcopy(binding),run,role,native,guard
        need(store.path.parent==lock.path.parent and store.path.name==self.store_name(role)
            and re.fullmatch('[1-9][0-9]*',binding['processIdentity']))
        self.pid=int(binding['processIdentity']);need(native.process is None or self.pid==native.process['pid'])
        lock.assert_held();self.previous=store.read();self.state=dict(events=[],storage={}) if self.previous is None else self.decode(self.previous)

    def proof_store(self,live=False):
        return OriginalFrameStore(self.store.path.parent,self.binding,self.run,self.role,self.guard if live else lambda:True,
            self.storage if live else lambda *_:need(False),namespace=self._proof_namespace,schema_prefix=self._proof_schema)

    def envelope(self):
        return {self._owner_key:VERSION,'binding':self.binding,'runId':self.run,'role':self.role,'payload':pack([self.state])}

    def decode(self,value):
        exact(value,{self._owner_key,'binding','runId','role','payload'});need(type(value[self._owner_key]) is int
            and value[self._owner_key]==VERSION and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'events','storage'})
        need(type(state['events']) is list and len(state['events'])<=128 and type(state['storage']) is dict)
        commands=set();previous=None;original_root=None
        for index,event in enumerate(state['events'],1):
            exact(event,{'index','phase','controlId','reference','command','receipt','proof'})
            need(type(event['index']) is int and event['index']==index and event['phase'] in ('reserved','issued','delivered'))
            row=self._reference(event['reference'],event['controlId']);scope=event['reference']['scope'];command=event['command']
            current_root=self.root(event)
            if original_root is None:original_root=current_root
            elif self._root_is_stable:need(same(original_root,current_root))
            self._input_source.native_command(command,event['controlId']);need(scope['processId']==self.pid and command['commandId'] not in commands);commands.add(command['commandId'])
            expected=dict(schemaVersion=1,commandId=command['commandId'],instance=scope['instance'],sequence=scope['sequence']+1,
                observedElapsedMs=scope['elapsedMs'],fieldToken=row['token'],operation=command['operation'])
            if command['operation']=='replace':
                self.replace_reference(event,row);expected['text']=command['text']
            need(same(command,expected))
            if previous is not None:need(scope['instance']==previous['instance'] and scope['sequence']>=previous['sequence']
                and scope['elapsedMs']>=previous['elapsedMs'] and scope['sampleEpochMs']>=previous['sampleEpochMs'])
            previous=dict(scope,sequence=command['sequence'])
            if event['phase']=='delivered':receipt(event['receipt'],command,self.pid,scope['sampleEpochMs'])
            else:need(event['receipt'] is None and event['proof'] is None and index==len(state['events']))
            if event['proof'] is not None:
                proof=self.proof_store();frame=proof.read(proof.expand(event['proof']));exact(frame,{'packet'})
                actual=self._input_source.delivered(frame['packet'],command,event['controlId'],self.root(event));need(same(actual['originalReceipt'],event['receipt']))
        for key,value in state['storage'].items():
            need(type(key) is str and key.isdigit() and 1<=int(key)<=len(state['events']));self.proof_store().original(value);need(value['index']==int(key))
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.previous)
        need(same(value,self.store.read()));self.previous=deepcopy(value)

    @staticmethod
    def root(event):
        row=reference(event['reference'],event['controlId']);return dict(rootId=row['snapshotRootId'],qmlSource=row['snapshotQmlSource'])

    def replace_reference(self,event,row):
        need(row['focused'] and (row['snapshotNameOwned'] or row['snapshotNameSha256']==capture.EMPTY))
        text=event['command']['text'];need(text=='' or text.startswith('parity-'+self.run[:16]+'-'))

    def check_current(self,event):
        module=capture if event['controlId'] in capture.IDS else export
        module.same_reference(event['reference'],module.project(self.native.capture()),event['controlId'])

    def current(self):
        self.bound();need(self.state['events']);return self.state['events'][-1]

    def validate_original(self,index):
        self.lock.assert_held();need(same(self.store.read(),self.previous));state=self.decode(self.previous)
        need(integer(index,1,len(state['events'])));event=state['events'][index-1];need(event['phase']=='delivered')
        return dict(command=deepcopy(event['command']),originalReceipt=deepcopy(event['receipt']),root=self.root(event),productOutcomeRequired=True)

    def reserve(self,control,original,*,operation='activate',text=None):
        self.bound();need(not self.state['events'] or self.state['events'][-1]['phase']=='delivered');need(len(self.state['events'])<128)
        row=self._reference(original,control);scope=original['scope'];command=dict(schemaVersion=1,commandId=str(uuid.uuid4()),instance=scope['instance'],
            sequence=scope['sequence']+1,observedElapsedMs=scope['elapsedMs'],fieldToken=row['token'],operation=operation)
        if operation=='replace':command['text']=text
        else:need(text is None)
        self._input_source.native_command(command,control)
        self.state['events'].append(dict(index=len(self.state['events'])+1,phase='reserved',controlId=control,reference=deepcopy(original),
            command=command,receipt=None,proof=None));self.save();return deepcopy(command)

    def send(self):
        event=self.current()
        if event['phase']!='reserved':raise SnapshotInputPending('Retained Snapshot input cannot be sent again')
        self.check_current(event)
        # Persist issued before crossing the existing ordinary Qt transport.
        event['phase']='issued';self.save();self.native.deliver(deepcopy(event['command']))
        actual=deepcopy(self.native.last_receipt);receipt(actual,event['command'],self.pid,event['reference']['scope']['sampleEpochMs'])
        event.update(phase='delivered',receipt=actual);self.save();return dict(productOutcomeRequired=True)

    def storage(self,kind,value):
        self.bound();event=self.current();need(event['phase']=='issued' and kind=='original' and value['index']==event['index'])
        key=str(value['index']);old=self.state['storage'].get(key);self.proof_store().original(value)
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(old[k],value[k]) for k in old if k not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        self.state['storage'][key]=deepcopy(value);self.save()

    def recover(self,packet=None):
        """Read/adopt original reception; never deliver an input again."""
        event=self.current();need(event['phase']=='issued');store=self.proof_store();saved=self.state['storage'].get(str(event['index']))
        if saved is not None:
            need(saved['phase'] in ('opened','saved'));frame=store.read(saved);exact(frame,{'packet'});packet=frame['packet']
            if saved['phase']=='opened':saved=dict(saved,phase='saved');self.storage('original',saved)
            proof=store.compact(saved)
        else:
            actual=self._input_source.delivered(packet,event['command'],event['controlId'],self.root(event))
            proof=self.proof_store(live=True).write(event['index'],dict(packet=deepcopy(packet)))
        actual=self._input_source.delivered(packet,event['command'],event['controlId'],self.root(event))
        event.update(phase='delivered',receipt=deepcopy(actual['originalReceipt']),proof=proof);self.save()
        return dict(productOutcomeRequired=True)
