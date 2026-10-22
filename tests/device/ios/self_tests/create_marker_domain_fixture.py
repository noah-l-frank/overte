"""Create-specific native DTOs around the reviewed host Script UI/Node model.

The actual staged Create JS/companion runs in Node. Qt/native/SDK/Web renderer
remain modeled. No device, compiler, installed Overte VM or camera setter runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import uuid
import weakref
from unittest.mock import patch

from ios.self_tests import emote_marker_domain_fixture as shared
from ios.self_tests.test_ios_create_state import packet,version2,SESSION


class EntityItem:pass


class RunningDomain(shared.RunningDomain):
    def __init__(self,scope):
        super().__init__(scope);self.sequences.update(create=0,entities=0);self.entity_items={};self.entity_rows=[];self.entity_events=[];self.entity_calls=[];self.entity_call_sequence=0
        self.entity_return_delay=0;self.pending_entity_return=None;self.entity_complete=True;self.entity_tree_birth=self.world_template['source']['tree']['treeInstance'];self.ignore_entity_delete=False
        scope.entities=SimpleNamespace(last=None,read=self.entities)
        scope.create=SimpleNamespace(last=None,read=self.create)
        self.original_request=self.files.request
        self.files.last_packet=None;self.file_sequence=0
        self.files.request=self.file_request
    def attach(self,scope):
        super().attach(scope);scope.create=SimpleNamespace(last=deepcopy(scope.frames[-1]['create']),read=self.create)
        scope.entities=SimpleNamespace(last=deepcopy(scope.frames[-1]['entities']),read=self.entities)
    def start(self):
        view=self.world_template['source']['view'];camera=dict(position=dict(zip('xyz',view['position'])),orientation=dict(zip('xyzw',view['rotation'])))
        program=shared.PROGRAM.replace('MyAvatar:{','Camera:'+json.dumps(camera)+',MyAvatar:{')
        with patch.object(shared,'PROGRAM',program):super().start()
        self.entity_add(self.vm['added'][0]['id'])
    def entity_caller(self,method):
        self.time+=.001;self.entity_call_sequence+=1
        return dict(callerVersion=1,method=method,sequence=self.entity_call_sequence,invokedEpochMs=self.epoch(),
            manager=deepcopy(self.worker),code=deepcopy(self.engine['code']))
    def entity_event(self,kind,row):
        self.time+=.001;stamp=self.epoch();mono=round(self.time*1000)
        event=dict(sequence=len(self.entity_events)+1,kind=kind,id=row['id'],birth=row['birth'],epochMs=stamp,monotonicMs=mono)
        self.entity_events.append(event)
        if kind=='inserted':row.update(insertedSequence=event['sequence'],bornEpochMs=stamp,bornMonotonicMs=mono)
        else:row.update(removedSequence=event['sequence'],removedEpochMs=stamp,removedMonotonicMs=mono)
    def entity_return(self,kind,id_,caller):
        if kind=='add-returned' and self.entity_return_delay>0:
            self.pending_entity_return=(kind,id_,deepcopy(caller));return
        self.time+=.001;self.entity_calls.append(dict(sequence=len(self.entity_calls)+1,eventId=uuid.uuid4().hex,kind=kind,
            clock=dict(epochMs=self.epoch(),monotonicMs=round(self.time*1000)),caller=caller,entityId=id_,localTreeAvailable=True))
    def entity_add(self,id_):
        caller=self.entity_caller('addEntity');item=EntityItem();self.entity_items[id_]=item
        row=dict(id=id_,birth=uuid.uuid4().hex,insertedSequence=0,bornEpochMs=0,bornMonotonicMs=0,
            removedSequence=0,removedEpochMs=0,removedMonotonicMs=0,destroyed=False,destructionObservedEpochMs=0,destructionObservedMonotonicMs=0)
        self.entity_rows.append((weakref.ref(item),row));self.entity_event('inserted',row);self.entity_return('add-returned',id_,caller)
    def stop(self):
        # The Node execution returns the actual ScriptEnding delete operand.
        # This model performs the separate actual object-map removal now.
        id_=self.vm['deleted'][0];caller=self.entity_caller('deleteEntity')
        if not self.ignore_entity_delete:
            item=self.entity_items.pop(id_,None)
            for weak,row in self.entity_rows:
                if weak() is item and row['removedSequence']==0:self.entity_event('removed',row)
            del item
        self.entity_return('delete-returned',id_,caller);super().stop()
    def entities(self,run):
        if self.pending_entity_return is not None:
            self.entity_return_delay-=1
            if self.entity_return_delay<=0:
                value=self.pending_entity_return;self.pending_entity_return=None;self.entity_return(*value)
        sequence=self.tick('entities');stamp=self.epoch();mono=round(self.time*1000);rows=[]
        for weak,row in self.entity_rows:
            if weak() is None and not row['destroyed']:row.update(destroyed=True,destructionObservedEpochMs=stamp,destructionObservedMonotonicMs=mono)
            rows.append(deepcopy(row))
        value=dict(iosCreateEntitiesVersion=1,requestId='ios-'+format(8000+sequence,'032x'),runId=run,instance='8'*32,sequence=sequence,processId=31,
            clockDomain='native-main-create-entities',clockBefore=dict(epochMs=stamp,monotonicMs=mono),clockAfter=dict(epochMs=stamp,monotonicMs=mono),
            source=dict(calls=dict(createEntityCallsVersion=1,instance='7'*32,complete=self.entity_complete,events=deepcopy(self.entity_calls)),
            tree=dict(entityTreeLifetimesVersion=1,treeInstance=self.entity_tree_birth,treeBornEpochMs=19000,complete=self.entity_complete,
            eventSequence=len(self.entity_events),observedEpochMs=stamp,observedMonotonicMs=mono,events=deepcopy(self.entity_events),entities=rows)))
        self.scope.entities.last=deepcopy(value);return value
    def world(self,run):
        value=super().world(run)
        # The native Emote domain DTO intentionally filters only Emote markers;
        # its complete EntityTree and Script originals still include Create.
        value['source']['markers']=[]
        value['source']['domain']['selfSha256']=hashlib.sha256(uuid.UUID(SESSION).bytes).hexdigest()
        return value
    def create(self,run):
        sequence=self.tick('create');value=version2(packet());value.update(iosCreateStateVersion=3,runId=run,processId=31,instance='6'*32,
            requestId='ios-'+format(7000+sequence,'032x'),sequence=sequence)
        for key in ('clockBefore','clockAfter'):value[key]=dict(epochMs=self.epoch(),monotonicMs=round(self.time*1000))
        source=value['source'];domain=self.world_template['source'];source.update(domainId=domain['domain']['domainId'],localSessionId=SESSION)
        source['view'].update({key:deepcopy(domain['view'][key]) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')})
        source['entities']=[];tree=source['tree'];tree.update(treeInstance=domain['tree']['treeInstance'],revisionBefore=1 if self.worker is None else 2 if self.running else 3,
            revisionAfter=1 if self.worker is None else 2 if self.running else 3,totalEntities=0,entities=[])
        if self.running:
            row=deepcopy(self.marker);stamp=row['lastEditedEpochUs']
            row.update(createdEpochUs=stamp,name=self.marker['name'],shape='',modelURL='',textures='',lastEditedBy=SESSION,locked=False,model={},voxels={})
            source['entities']=[row];tree.update(totalEntities=1,entities=[dict(id=row['id'],hostType=row['hostType'],ready=True,createdEpochUs=stamp,
                lastEditedEpochUs=stamp,lastEditedAfterEpochUs=stamp,semanticBytes=100,semanticSha256='d'*64)])
        self.scope.create.last=deepcopy(value);return value
    def widgets(self):
        value=super().widgets();value.update(createControlsVersion=2,createGeneration=str(uuid.UUID('4'*32)))
        return value
    def manager(self):
        manager=super().manager();manager.store.path=manager.store.path.with_name('ios-create-'+self.scope.role+'-marker-script.json')
        # Construct the real manager directly at its Create ownership path.
        from adapters.normal_script_manager import NormalScriptManager
        return NormalScriptManager(manager.ui,manager.observe,manager.store,self.scope.binding,source_kind='script-file-bundle',file_owner=self.scope.files,
            file_picker=manager.file_picker,monotonic=lambda:self.time,sleep=self.io.sleep)
    def paint(self):
        super().paint();self.context['descriptor']['identitySha256']=hashlib.sha256(('web-entity:'+self.marker['id']).encode()).hexdigest()
    def file_request(self,operation,run,owner,files=None):
        result=self.original_request(operation,run,owner,files);self.file_sequence+=1
        self.files.last_packet=dict(schemaVersion=1,requestId='ios-'+uuid.uuid4().hex,instance='9'*32,sequence=self.file_sequence,
            requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),processId=31,runId=run,operation=operation,source=deepcopy(result))
        return result
