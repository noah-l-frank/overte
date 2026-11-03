"""Once-only original Assets UI/Create/UIKit source acquisitions.

The original Upload journal owns normal UI queries. New passive Create, native
clock and geometry responses are retained verbatim before interpretation. A
partial capture remains owned and blocks another source acquisition; no input,
Model adoption, PNG verdict or native qualification is inferred here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import time
from types import SimpleNamespace
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,need,integer
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same,pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.assets_upload import OwnedAssetsUpload
from ios.adapters.assets_tree_controls import ROW
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_image_basis import marker_original
from ios.adapters.assets_model_raw_sources import ModelRawSources
from ios.adapters.assets_budget import operation
from ios.adapters.create_state import IOSCreateState,original as create_original
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters.assets_ui_measurements import frame as ui_frame

VERSION=1


class UiRawSources(ModelRawSources):
    NAMESPACE='assets-ui-native'
    SCHEMA_PREFIX='iosAssetsUiRawSource'
    MIGRATION_PREFIX='assets-ui-native-migration-'
    RECORD_KEY='iosAssetsUiRawSourceRecordVersion'
    MIGRATION_KEY='iosAssetsUiRawSourceMigrationVersion'


def returned(record):
    try:return decode(record['raw'],limit=262144)
    except json.JSONDecodeError:return None


class AssetsUiSource:
    @classmethod
    def from_archive(cls,value,store,upload,marker,lock,*,subject,checkpoint):
        """Independent actual owner paths and locks, without SDK construction."""
        need(isinstance(upload,OwnedAssetsUpload) and isinstance(marker,OwnedAssetsMarker)
            and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and upload.lock is lock
            and upload.role=='primary' and marker.role=='primary' and marker.run==upload.files.run
            and same(marker.scope.binding,upload.binding) and checkpoint in ('browse','baking-on') and type(subject) is str)
        need(subject=='assets.baking' if checkpoint=='baking-on' else ROW.fullmatch(subject) is not None)
        lock.assert_held();marker.lock.assert_held();need(same(store.read(),value))
        owner=object.__new__(cls)
        owner.upload,owner.marker,owner.store,owner.lock=upload,marker,store,lock
        owner.binding,owner.run,owner.role=deepcopy(upload.binding),upload.files.run,'primary'
        owner.root,owner.checkpoint,owner.subject=store.path.parent,checkpoint,subject
        need(store.path.name=='ios-assets-ui-sources-'+owner.run+'-'+checkpoint+'.json' and store.path.parent==upload.store.path.parent)
        def forbidden(*_args,**_kwargs):need(False)
        owner.guard,owner.epoch_ms,owner.monotonic=forbidden,forbidden,time.monotonic
        owner.native=SimpleNamespace(monotonic=time.monotonic);owner.create=owner.geometry=None
        owner.historical=True;owner.previous=deepcopy(value);owner.state=None;owner.active=False
        owner.raws=UiRawSources(owner,'primary',owner.bound,owner.save)
        owner.originals=OriginalFrameStore(owner.root,owner.binding,owner.run,owner.role,owner.bound,owner.intent,
            namespace='assets-ui-'+checkpoint+'-sources',schema_prefix='iosAssetsUiSource',monotonic=time.monotonic)
        owner.state=owner.decode(value);return owner
    def __init__(self,upload,marker,native,create,geometry,store,lock,guard,*,subject,checkpoint,epoch_ms,monotonic,historical=False):
        need(isinstance(upload,OwnedAssetsUpload) and isinstance(marker,OwnedAssetsMarker)
            and isinstance(native,NativeFeatureObservation) and native.ios and native.native_clock_bound
            and isinstance(create,IOSCreateState) and isinstance(geometry,OriginalGeometry)
            and isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and lock is upload.lock and callable(guard) and callable(epoch_ms) and callable(monotonic)
            and checkpoint in ('browse','baking-on') and type(subject) is str and upload.role=='primary' and type(historical) is bool)
        need(subject=='assets.baking' if checkpoint=='baking-on' else ROW.fullmatch(subject) is not None)
        self.upload,self.marker,self.native,self.create,self.geometry=upload,marker,native,create,geometry
        self.store,self.lock,self.guard=store,lock,guard
        self.binding,self.run,self.role=deepcopy(upload.binding),upload.files.run,'primary'
        self.root,self.epoch_ms,self.monotonic=store.path.parent,epoch_ms,monotonic
        self.checkpoint,self.subject=checkpoint,subject
        need(store.path.name=='ios-assets-ui-sources-'+self.run+'-'+checkpoint+'.json'
            and store.path.parent==upload.store.path.parent and native.pid==create.pid==int(self.binding['processIdentity'])
            and marker.run==self.run and marker.role=='primary' and same(marker.scope.binding,self.binding))
        self.historical=historical;self.previous=store.read();self.state=None;self.active=False
        self.raws=UiRawSources(self,'primary',self.bound,self.save)
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.bound,self.intent,
            namespace='assets-ui-'+checkpoint+'-sources',schema_prefix='iosAssetsUiSource',monotonic=monotonic)
        if self.previous is None:
            need(not historical);self.state=dict(records=[],pending=None,rawSources=self.raws.manifest());self.save()
        else:self.state=self.decode(self.previous)
    def bound(self):
        self.lock.assert_held();self.marker.lock.assert_held();PrivateFeatureState(self.store.path)._parent()
        if not self.historical:need(self.guard() is not False)
        return True
    def envelope(self):
        self.state['rawSources']=self.raws.manifest()
        return dict(iosAssetsUiSourcesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            checkpoint=self.checkpoint,subjectControl=self.subject,payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.bound();need(same(self.store.read(),self.previous));value=self.envelope();self.store.write(value,self.previous);self.previous=deepcopy(value)
    def intent(self,kind,value):
        need(kind=='original' and self.state['pending'] is not None);self.state['pending']['original']=deepcopy(value);self.save()
    def record_references(self):return self.state['records']
    def record(self,row,index):
        exact(row,{'assetsUiAcquisitionVersion','index','page','marker','uploadReference','frame','queries','rawRefs'})
        need(row['assetsUiAcquisitionVersion']==VERSION and type(row['assetsUiAcquisitionVersion']) is int and type(row['index']) is int and row['index']==index)
        need(row['page']==self.upload.state['page']);marker_original(self.marker,row['marker'])
        ref=row['uploadReference'];self.upload.originals.expand(ref)
        need(any(same(ref,current) for current in self.upload.state['frames']))
        original=self.upload.originals.read(self.upload.originals.expand(ref));self.upload.frame(original)
        need(same(original,row['frame']['uiFrame']) and same(original['ui'],row['frame']['ui']))
        need(type(row['queries']) is list and type(row['rawRefs']) is list and len(row['queries'])<=24 and len(row['rawRefs'])<=24)
        seen=set()
        for entry in row['queries']:
            exact(entry,{'kind','command'});command=entry['command'];need(entry['kind'] in ('clock','create','geometry'))
            if entry['kind']=='create':
                from ios.adapters.create_state import command as create_command
                create_command(command)
            else:
                exact(command,{'schemaVersion','commandId','action'})
                need(type(command['schemaVersion']) is int and command['schemaVersion']==1
                    and command['action']==('feature-native-observe' if entry['kind']=='clock' else 'native-geometry-snapshot'))
            need(command['commandId'] not in seen);seen.add(command['commandId'])
        records=[self.raws.read_record(ref) for ref in row['rawRefs']]
        need(all(entry['kind']=='native' and any(same(entry['query'],query['command']) for query in row['queries']) for entry in records))
        need(all(ref in self.raws.refs for ref in row['rawRefs']))
        for field,kind in (('create','create'),('geometry','geometry')):
            packet=row['frame'][field];command_id=packet.get('requestId') if kind=='create' else packet.get('commandId')
            queries=[entry['command'] for entry in row['queries'] if entry['kind']==kind and entry['command'].get('commandId')==command_id]
            need(len(queries)==1)
            originals=[returned(entry) for entry in records if same(entry['query'],queries[0]) and type(returned(entry)) is dict
                and returned(entry).get('requestId' if kind=='create' else 'commandId')==command_id]
            need(originals and all(same(packet,entry) for entry in originals))
        clock=row['frame']['clockJoin']
        for packet in (clock['nativeBefore'],clock['nativeAfter']):
            commands=[entry['command'] for entry in row['queries'] if entry['kind']=='clock' and entry['command'].get('commandId')==packet['requestId']]
            need(len(commands)==1 and any(same(returned(entry),packet) and same(entry['query'],commands[0]) for entry in records))
        ui_frame(row['frame'],self.binding,self.run,row['page'],self.subject,self.checkpoint);return row
    def decode(self,value):
        exact(value,{'iosAssetsUiSourcesVersion','binding','runId','role','checkpoint','subjectControl','payload'})
        need(type(value['iosAssetsUiSourcesVersion']) is int and value['iosAssetsUiSourcesVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
            and value['checkpoint']==self.checkpoint and value['subjectControl']==self.subject)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'records','pending','rawSources'})
        need(type(state['records']) is list and len(state['records'])<=8);self.raws.load(state['rawSources'])
        previous=None
        for index,ref in enumerate(state['records'],1):
            row=self.record(self.originals.read(self.originals.expand(ref)),index);frame=row['frame']
            if previous is not None:
                from ios.adapters.graphics_history import follow_native
                from ios.adapters.create_state import validate as create_validate,ACTION
                follow_native(previous['clockJoin']['nativeAfter'],frame['clockJoin']['nativeBefore'])
                create_validate(frame['create'],dict(schemaVersion=1,action=ACTION,commandId=frame['create']['requestId'],runId=self.run),
                    int(self.binding['processIdentity']),frame['clockJoin']['nativeAfter']['capturedEpochMs'],previous['create'])
                need(frame['geometry']['observation']['sampleSequence']>previous['geometry']['observation']['sampleSequence'])
            previous=frame
        if state['pending'] is not None:
            row=state['pending'];exact(row,{'index','page','marker','uploadReference','frame','queries','rawRefs','original'})
            need(row['index']==len(state['records'])+1 and type(row['frame']) is dict and type(row['queries']) is list and len(row['queries'])<=24
                and type(row['rawRefs']) is list and all(ref in self.raws.refs for ref in row['rawRefs']))
            if row['original'] is not None:self.originals.original(row['original'])
        return state
    def validate(self,reference):
        self.lock.assert_held();need(same(self.store.read(),self.previous));self.decode(self.previous)
        matches=[(index,ref) for index,ref in enumerate(self.state['records'],1) if same(ref,reference)];need(len(matches)==1)
        index,ref=matches[0];return deepcopy(self.record(self.originals.read(self.originals.expand(ref)),index)['frame'])
    def marker_identity(self,frame):
        rows=[self.originals.read(self.originals.expand(ref)) for ref in self.state['records']]
        matches=[row for row in rows if same(row['frame'],frame)];need(len(matches)==1)
        self.record(matches[0],matches[0]['index']);return marker_original(self.marker,matches[0]['marker'])
    def current(self,reference):
        self.bound();need(self.state['pending'] is None and self.raws.pending is None and self.state['records']
            and same(reference,self.state['records'][-1]) and self.upload.state['pending'] is None)
        row=self.originals.read(self.originals.expand(reference));need(same(row['uploadReference'],self.upload.state['frames'][-1]));return self.validate(reference)
    @operation
    def capture(self):
        self.bound();need(not self.historical and not self.active and self.state['pending'] is None and self.raws.pending is None and len(self.state['records'])<8)
        self.upload.guard();self.marker.guard();need(self.marker.state['phase']=='ready' and self.upload.state['phase']=='uploaded')
        row=dict(index=len(self.state['records'])+1,page=self.upload.state['page'],marker=deepcopy(self.marker.previous),uploadReference=None,frame={},queries=[],rawRefs=[],original=None)
        self.state['pending']=row;self.save();wrappers=[];self.active=True
        for kind,reader in (('clock',self.native),('create',self.create),('geometry',self.geometry)):
            old_send,old_original=reader.send,reader.original;wrappers.append((reader,old_send,old_original))
            def send(command,kind=kind,old_send=old_send):
                need(len(row['queries'])<24);row['queries'].append(dict(kind=kind,command=deepcopy(command)));self.save();return old_send(command)
            def original(kind=kind,old_original=old_original):
                raw=old_original()
                if raw:
                    commands=[entry['command'] for entry in row['queries'] if entry['kind']==kind];need(commands and len(row['rawRefs'])<24)
                    self.raws.capture(commands[-1],raw);self.raws.accept_capture();row['rawRefs'].append(deepcopy(self.raws.refs[-1]));self.save()
                return raw
            reader.send,reader.original=send,original
        def remember(name,value):row['frame'][name]=deepcopy(value);self.save();return value
        try:
            clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(self.epoch_ms())
            packet=self.upload.capture();row['uploadReference']=deepcopy(self.upload.state['frames'][-1]);self.save()
            remember('ui',packet);remember('uiFrame',self.upload.originals.read(self.upload.originals.expand(row['uploadReference'])))
            remember('create',self.create.read(self.run));remember('geometry',self.geometry.capture())
            parts=dict(ui=packet,create=row['frame']['create'],geometry=row['frame']['geometry']['observation'])
            remember('clockJoin',clock.finish(parts,[('ui','sampleEpochMs'),('geometry','sampleEpochMs')]))
            remember('assetsUiSourceFrameVersion',VERSION)
            body=dict(assetsUiAcquisitionVersion=VERSION,**{key:deepcopy(row[key]) for key in row if key!='original'})
            self.record(body,row['index']);ref=self.originals.write(row['index'],body)
            self.state['records'].append(ref);self.state['pending']=None;self.save();return deepcopy(ref)
        finally:
            self.active=False
            for reader,send,original in wrappers:reader.send,reader.original=send,original
