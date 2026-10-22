"""Existing parent plus real Runner/Settings leases, declared native/UI actors."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_create_rez_owner as rez
import test_create_journey as parent
from test_create_models import ModelBackend
from test_create_model_resource_join import ResourceActor
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import same_reference
from adapters.pico4.create_recovery import DENIED


class CreateRecoveryTests(unittest.TestCase):
    make=rez.CreateRezOwnerTests.make
    act=rez.CreateRezOwnerTests.act
    def setUp(self):rez.CreateRezOwnerTests.setUp(self)
    def _before_prepare(self):
        b=self.b;b.recovery_events=getattr(b,'local_creations',[]);b.recovery_births=getattr(b,'creation_times',{});b.recovery_signals=0;b.recovery_error=False;b.shape=0
        b.actual_shape='Cube';b.ignore_shape=False;b.create_count=0
        root=Path(__file__).resolve().parents[5]
        for identifier,name in ((120,'nativeCreateBridge.js'),(121,'picoQmlMessageValidation.js')):
            relative='system/create/modules/'+name;code=(root/'scripts'/relative).read_text().encode('utf-16le')
            b.callback['source']['managers'][0]['compiled']['compilations'].append(dict(scriptId=identifier,
                resourceName='file:///original/scripts/'+relative,encoding='utf-16le-code-units',codeUnits=len(code)//2,
                sha256=hashlib.sha256(code).hexdigest(),compiledEpochMs=12000))
        original_reader=ModelBackend.reader;original_work=ModelBackend.work_reader
        original_capture=parent.UnifiedIO.capture;original_command=parent.UnifiedIO.command;original_resources=ResourceActor.resource_reader
        def reader(b,kind):
            native=original_reader(b,kind);send=native.send
            def deliver(command):
                send(command)
                if kind=='entities':
                    packet=json.loads(b.frames[kind]);source=packet['source'];source['createEntitySourceVersion']=6
                    source['localCreations']=dict(createLocalCreationsVersion=1,armedAfterSequence=0,lastSequence=len(b.recovery_events),events=deepcopy(b.recovery_events))
                    source['avatarRotation']=[0,0,0,1]
                    source.setdefault('polyvoxResources',dict(createPolyvoxResourcesVersion=1,instance='7'*32,sourceSequence=packet['sequence'],bindings=[],meshes=[],renderers=[],textures=[]))
                    for row in source['entities']:
                        row.setdefault('createdEpochUs',b.recovery_births.setdefault(row['id'],row['lastEditedEpochUs']))
                        row.setdefault('lastEditedBy',source['sessionId']);row.setdefault('voxels',None);row.setdefault('shape',None)
                    b.frames[kind]=json.dumps(packet,indent=2)+'\n'
            native.send=deliver;return native
        def work(b):
            native=original_work(b);send=native.send
            def deliver(command):
                send(command);packet=json.loads(b.work_raw);rows=packet['source']['work']['activity']
                # Sampling is not a callback. Only the explicit original UI
                # actor's actual create/edit/delete receive increments this.
                own=next((row for row in rows if row['scriptId']==17),dict(scriptId=17,signalCallbacks=0,timerCallbacks=0,timerInvocations=0,timerRegistrations=0))
                own['signalInvocations']=b.recovery_signals
                rows[:]=[row for row in rows if row['scriptId']!=17]
                if any(own[k] for k in own if k!='scriptId'):rows.insert(0,own)
                packet['source']['work']['activityEntries']=len(rows);b.work_raw=json.dumps(packet,indent=2)+'\n'
            native.send=deliver;return native
        def capture(io):
            value=original_capture(io);b=io.b
            if not b.editor or not b.opened:return value
            for row in value['controls']:
                if row['id']=='create.page':row['statusError']=b.recovery_error;row['statusText']=b.status
            for identifier,extra in [('create.shape',dict(count=6,currentIndex=b.shape)),('create.new-shape',{})]:
                value['controls'].append(dict(id=identifier,enabled=True,focused=b.focus==identifier,inputReady=True,
                    token=uuid.uuid5(uuid.NAMESPACE_URL,identifier+str(extra)).hex,**extra))
            return value
        def command(io,identifier,action,reference,value=None):
            b=io.b
            if identifier not in ('create.shape','create.new-shape'):
                result=original_command(io,identifier,action,reference,value)
                if identifier in ('create.apply','create.delete'):
                    b.recovery_signals+=1;b.recovery_error=False;b.status='Properties applied.' if identifier=='create.apply' else 'Entities deleted.'
                return result
            same_reference(reference,io.capture(),identifier);b.before_input();b.ui.command_sequence+=1
            b.inputs.append(dict(controlId=identifier,action=action,value=value))
            if identifier=='create.shape':
                if action=='select-index':b.shape=value
                else:b.focus=identifier
            else:
                b.recovery_signals+=1;b.create_count+=1;b.tab=2
                rows=self.actor.server.security['standard_permissions']
                allowed=any(row['id_can_rez'] or row['id_can_rez_tmp'] for row in rows)
                if not allowed:b.status=DENIED;b.recovery_error=True
                elif not b.ignore_shape:
                    entity=str(uuid.uuid4());created=b.epoch()*1000;b.recovery_births[entity]=created
                    kind='Box' if b.actual_shape=='Cube' else 'Sphere'
                    b.recovery_events.append(dict(sequence=len(b.recovery_events)+1,id=entity,type=kind,hostType='domain',
                        sessionId='22222222-2222-2222-2222-222222222222',createdEpochUs=created,observedEpochMs=b.epoch()))
                    b.rows=[dict(id=entity,name='Shape',type=kind,shape=b.actual_shape,hostType='domain',modelUrl='',textures='',position=[0,1,-2],rotation=[0,0,0,1],
                        dimensions=[.2,.2,.2],parentId=None,visible=True,locked=False,lastEditedEpochUs=created,visuallyReady=True,naturalDimensions=[.2,.2,.2],
                        textureNames={},renderInfo=dict(vertices=0,textures=0,textureBytes=0,drawCalls=1))]
                    b.selected=[entity];b.name='Shape';b.dimensions=dict(x='.2',y='.2',z='.2');b.status='Entity created.';b.recovery_error=False
                else:b.status='Entity created.';b.recovery_error=False
            if b.lose==identifier:raise NativeUIError('declared lost actual normal Shape reply')
        def resources(b):
            native=original_resources(b);send=native.send
            def deliver(command):
                rows=b.rows;other=[r for r in rows if r['type']!='Model'];b.rows=[r for r in rows if r['type']=='Model']
                try:send(command)
                finally:b.rows=rows
                packet=json.loads(b.resource_raw)
                for row in other:packet['source']['bindings'].append(dict(entityId=row['id'],model=None))
                packet['source']['bindings'].sort(key=lambda r:r['entityId']);b.resource_raw=json.dumps(packet,indent=2)+'\n'
            native.send=deliver;return native
        for boundary in (patch.object(ResourceActor,'resource_reader',resources),patch.object(ModelBackend,'reader',reader),patch.object(ModelBackend,'work_reader',work),
                patch.object(parent.UnifiedIO,'capture',capture),patch.object(parent.UnifiedIO,'command',command)):
            boundary.start();self.addCleanup(boundary.stop)
    def denied(self):
        self.act('open');self.act('set-rez-permission',dict(allowed=False));self.act('create-denied')
    def test_normal_denial_actual_cube_retry_delete_close_and_original_rez_cleanup(self):
        self.denied();self.assertFalse(self.b.rows);self.assertEqual('denied',self.root.recovery_step()['outcome'])
        original=deepcopy(self.root.recovery_step()['effect']);self.make();self.act('set-rez-permission',dict(allowed=True));self.act('create-retry')
        self.assertEqual(('Box','Cube'),tuple(self.b.rows[0][k] for k in ('type','shape')));self.assertEqual('recovery',self.root.state()['subject'])
        self.assertEqual(original,self.root.recovery_state()['steps'][0]['effect']);self.make();self.act('delete-owned');self.assertFalse(self.b.rows)
        self.act('close');self.reader.activate(uuid.uuid4().hex,'cleanup',{});self.make();self.root.invoke('cleanup')
        self.assertIsNone(self.root.store.read());self.assertEqual(2,self.b.create_count);self.assertEqual(self.actor.original,self.actor.server.security)
        self.reader.close()
    def test_lost_denial_reply_reconciles_only_actual_new_status_and_no_input_replay(self):
        self.act('open');self.act('set-rez-permission',dict(allowed=False));self.b.lose='create.new-shape'
        with self.assertRaises(NativeUIError):self.act('create-denied')
        self.b.lose=None;count=len(self.b.inputs);self.make();self.root.invoke('reconcile')
        self.assertEqual(count,len(self.b.inputs));self.assertEqual(1,self.b.create_count);self.assertFalse(self.b.rows)
        self.assertEqual('denied',self.root.recovery_step()['outcome'])
    def test_wrong_actual_shape_never_qualifies_cube_and_distinct_cleanup_deletes_only_owned_id(self):
        self.denied();self.act('set-rez-permission',dict(allowed=True));self.b.actual_shape='Sphere'
        with self.assertRaises(NativeUIError):self.act('create-retry')
        self.assertIsNotNone(self.root.state()['pending']);self.assertEqual('Sphere',self.b.rows[0]['shape']);identifier=self.b.rows[0]['id']
        self.assertEqual(identifier,self.root.recovery_step()['entityId'])
        self.reader.activate(uuid.uuid4().hex,'cleanup',{});self.make();self.root.invoke('cleanup')
        self.assertFalse(self.b.rows);self.assertEqual(2,self.b.create_count);self.assertIsNone(self.root.store.read())
    def test_ack_without_local_insertion_cannot_complete_retry_or_discard_unknown_cleanup(self):
        self.denied();self.act('set-rez-permission',dict(allowed=True));self.b.ignore_shape=True
        with self.assertRaises(NativeUIError):self.act('create-retry')
        pending=self.root.state()['pending'];count=len(self.b.inputs);self.assertIsNotNone(pending)
        self.reader.activate(uuid.uuid4().hex,'cleanup',{});self.make()
        with self.assertRaises(NativeUIError):self.root.invoke('cleanup')
        self.assertEqual(pending,self.root.state()['pending']);self.assertEqual(count,len(self.b.inputs));self.assertEqual(2,self.b.create_count)


PARTITIONS=dict(flow=['test_normal_denial_actual_cube_retry_delete_close_and_original_rez_cleanup','test_lost_denial_reply_reconciles_only_actual_new_status_and_no_input_replay'],
    guards=['test_wrong_actual_shape_never_qualifies_cube_and_distinct_cleanup_deletes_only_owned_id','test_ack_without_local_insertion_cannot_complete_retry_or_discard_unknown_cleanup'])

def group(loader,kind):
    all_names=loader.getTestCaseNames(CreateRecoveryTests);names=[name for rows in PARTITIONS.values() for name in rows]
    need(sorted(names)==all_names and len(names)==len(set(names)))
    return unittest.TestSuite(CreateRecoveryTests(name) for name in PARTITIONS[kind])


if __name__=='__main__':unittest.main()
