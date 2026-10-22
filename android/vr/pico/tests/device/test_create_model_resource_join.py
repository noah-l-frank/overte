"""Normal Model owner joined to an independently faultable resource actor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import tempfile
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

from test_create_models import ModelBackend,ModelIO,RUN,TICKET,SECOND,URL,OwnedCreateModels,OriginalReader
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_model_resources import NativeCreateModelResources
from adapters.pico4.create_model_resource_join import ResourceJoinedCreateModels
from adapters.token_create_ui import TokenCreateUI


class ResourceActor(ModelBackend):
    def __init__(self,path):
        super().__init__(path);self.model_objects={};self.geometry_objects={};self.material_objects={};self.resource_objects={};self.render_models={}
        self.resource_sequence=0;self.resource_raw='';self.ignore_renderer=False;self.retain_resources=False;self.retain_models=False
        self.resource_delay=.6;self.replace_native_model=False
    def allocate(self,records):
        identifier=uuid.uuid4().hex;records[identifier]=dict(instance=identifier,firstObservedEpochMs=self.epoch(),alive=True);return identifier
    def resource_reader(self):
        def send(command):
            self.settle();self.resource_sequence+=1;bindings=[];present={r['id'] for r in self.rows}
            for row in self.rows:
                if row['id'] not in self.render_models or self.replace_native_model:
                    model=self.allocate(self.model_objects);geometry=self.allocate(self.geometry_objects);material=self.allocate(self.material_objects)
                    original=row['modelUrl'].rsplit('/',1)[0]+'/textures/checker.png'
                    resource=self.allocate(self.resource_objects);self.resource_objects[resource].update(sharedAvailable=True,state=dict(url=original,loaded=False,failed=False))
                    self.render_models[row['id']]=dict(model=model,geometry=geometry,material=material,resource=resource,url=row['modelUrl'],property='',readyAt=self.now()+self.resource_delay)
                    self.replace_native_model=False
                actor=self.render_models[row['id']]
                if row['textures']!=actor['property'] and not self.ignore_renderer:
                    actual=json.loads(row['textures']);resource=self.allocate(self.resource_objects)
                    self.resource_objects[resource].update(sharedAvailable=True,state=dict(url=actual['checker.png'],loaded=False,failed=False))
                    actor.update(resource=resource,property=row['textures'],readyAt=self.now()+self.resource_delay)
                loaded=self.submitted is not None and self.now()-self.submitted>=.6 and not self.bad_load
                resource=self.resource_objects[actor['resource']];resource['state']['loaded']=loaded and self.now()>=actor['readyAt']
                bindings.append(dict(entityId=row['id'],model=actor['model'],geometry=actor['geometry'],loaded=loaded,
                    loadedSourceSha256=hashlib.sha256(actor['url'].encode()).hexdigest() if loaded else '',
                    textures=[dict(material=actor['material'],materialIndex=0,channel=0,slot='checker.png',resource=actor['resource'])]))
            for identifier in self.absent:bindings.append(dict(entityId=identifier,model=None))
            live=[self.render_models[k] for k in present]
            for records,key,retained in ((self.model_objects,'model',self.retain_models),(self.geometry_objects,'geometry',self.retain_models),
                    (self.material_objects,'material',self.retain_models),(self.resource_objects,'resource',self.retain_resources)):
                ids={m[key] for m in live}
                for identifier,row in records.items():
                    row['alive']=row['alive'] and (identifier in ids or retained)
                    if key=='resource':
                        row['sharedAvailable']=row['alive']
                        if not row['alive']:row['state']=None
            session=dict(domainSessionVersion=1,instance='7'*32,revision=self.domain_revision,connected=True,
                domainSha256=hashlib.sha256((RUN+':').encode()+uuid.UUID('11111111-1111-1111-1111-111111111111').bytes).hexdigest(),
                connectionBirth=self.domain_birth,connectedEpochMs=19000)
            source=dict(createModelResourcesVersion=1,runId=RUN,domainSession=session,bindings=sorted(bindings,key=lambda r:r['entityId']),
                models=[deepcopy(self.model_objects[k]) for k in sorted(self.model_objects)],geometries=[deepcopy(self.geometry_objects[k]) for k in sorted(self.geometry_objects)],
                materials=[deepcopy(self.material_objects[k]) for k in sorted(self.material_objects)],resources=[deepcopy(self.resource_objects[k]) for k in sorted(self.resource_objects)])
            epoch=self.epoch();self.resource_raw=json.dumps(dict(schemaVersion=1,requestId=command['commandId'],instance='9'*32,sequence=self.resource_sequence,
                processId=123,requestedEpochMs=epoch,capturedEpochMs=epoch,source=source),indent=2)+'\n'
        return NativeCreateModelResources(send,lambda:self.resource_raw,self.epoch,lambda:True,123,run=RUN,monotonic=self.now,sleep=self.ui.sleep)
    def make(self):
        component=super().make();resources=OriginalReader(self.resource_reader(),self.store('resources'),self.binding)
        self.owner=ResourceJoinedCreateModels(component.store,self.binding,lambda intent:TokenCreateUI(ModelIO(self),intent,
            monotonic=self.now,sleep=self.ui.sleep),component.entities,component.callbacks,component.work,resources=resources,
            join_store=self.store('resource-join'),monotonic=self.now,sleep=self.ui.sleep)
        return self.owner


class CreateModelResourceJoinTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.b=ResourceActor(self.path);self.flow=self.b.make()
    def create(self):return self.flow.create(RUN,TICKET,URL,'gltf-bundle/main.gltf')
    def texture(self):return self.flow.apply_texture(RUN,SECOND,URL,'checker.png')
    def test_production_factory_uses_join_and_inventory_keeps_resource_orphans(self):
        import test_normal_scripts as sources
        fixture=sources.PicoNormalScriptsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        instance,native=fixture.instance,fixture.native
        with patch.dict(os.environ,{'OVERTE_PICO_NORMAL_CREATE':'1'}):
            flow=instance._create_models(native.target,RUN)
            with flow.lock.held():
                joined=flow.flow();self.assertIsInstance(joined,ResourceJoinedCreateModels)
                self.assertEqual(RUN,joined.resources.reader.run)
            flow.store('resource-join').write({'original':'retained'},None)
            self.assertTrue(flow.owned());self.assertTrue(instance._create_models_owned(native.target))
            self.assertEqual([],native.inputs)
    def test_normal_texture_joins_distinct_actual_loaded_material_resource_and_preserves_originals(self):
        self.create();before=deepcopy(self.flow.join_state());self.texture();after=self.flow.join_state()
        self.assertEqual(before['anchors'][0],after['anchors'][0]);self.assertEqual(2,len(after['anchors']))
        texture=after['anchors'][1];original=json.loads(texture['raw']);self.assertEqual(hashlib.sha256(texture['raw'].encode()).hexdigest(),texture['sha256'])
        self.assertEqual('texture',texture['operation']);self.assertEqual(TICKET,texture['ticket'])
        actual=self.flow.current_resources;binding=self.flow.model_binding(actual,self.b.rows[0]['id'])
        self.assertEqual(texture['model'],binding['model']);self.assertEqual(texture['geometry'],binding['geometry'])
        self.assertTrue(self.flow.texture_bound(actual,binding,URL+'tickets/'+SECOND+'/checker.png'))
        self.assertNotEqual(original['source']['resources'],actual['source']['resources'])
        self.flow=self.b.make();self.flow.delete();self.flow.release();self.assertFalse(list(self.path.glob('*.json')))
    def test_actual_entity_property_and_consumed_apply_do_not_prove_renderer_binding(self):
        self.create();self.b.ignore_renderer=True
        with self.assertRaises(NativeUIError):self.texture()
        self.assertEqual(URL+'tickets/'+SECOND+'/checker.png',json.loads(self.b.rows[0]['textures'])['checker.png'])
        count=len(self.b.inputs);self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.join_store.read())
        self.flow.delete();self.flow.release()
    def test_lost_apply_response_reconciles_independent_loaded_resource_without_resending(self):
        self.create();self.b.lose='create.apply-typed'
        with self.assertRaises(NativeUIError):self.texture()
        self.b.lose=None;count=len(self.b.inputs);self.flow=self.b.make();self.flow.reconcile()
        self.assertEqual(count,len(self.b.inputs));self.flow.delete();self.flow.release()
    def test_cached_texture_qobject_or_retained_model_blocks_owner_retirement(self):
        self.create();self.texture();self.b.retain_resources=True;self.b.retain_models=True;self.flow.delete();count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.flow.release()
        self.assertIsNotNone(self.flow.store.read());self.b.retain_models=False;self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.release()
        self.assertEqual(count,len(self.b.inputs));self.b.retain_resources=False;self.flow=self.b.make();self.flow.release()
    def test_original_model_replacement_with_same_entity_uuid_refuses_new_texture_input(self):
        self.create();self.b.replace_native_model=True;count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.texture()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.store.read())
    def test_join_baseline_write_failure_prevents_first_associated_normal_input(self):
        with patch.object(self.flow.join_store,'write',side_effect=OSError('synthetic durable resource baseline failure')):
            with self.assertRaises(OSError):self.create()
        self.assertEqual([],self.b.inputs);self.assertIsNotNone(self.flow.store.read());self.assertIsNotNone(self.flow.resources.store.read())
    def test_tampered_pinned_resource_original_refuses_reconstruction(self):
        self.create();before=self.flow.join_store.read();bad=deepcopy(before);bad['anchors'][0]['raw']+=' '
        self.flow.join_store.write(bad,before)
        with self.assertRaises(NativeUIError):self.b.make()
    def test_partial_resource_journal_retirement_leaves_fresh_readonly_orphan_recovery(self):
        self.create();self.flow.delete();count=len(self.b.inputs)
        with patch.object(self.flow.join_store,'discard',side_effect=OSError('synthetic final resource join retirement failure')):
            with self.assertRaises(OSError):self.flow.release()
        self.assertIsNone(self.flow.store.read());self.assertIsNotNone(self.flow.join_store.read())
        self.flow=self.b.make();self.flow.release_observations();self.assertEqual(count,len(self.b.inputs));self.assertFalse(list(self.path.glob('*.json')))
    def test_orphan_recovery_keeps_original_domain_generation_after_other_journals_retire(self):
        self.create();self.flow.delete();count=len(self.b.inputs)
        with patch.object(self.flow.join_store,'discard',side_effect=OSError('synthetic final resource join retirement failure')):
            with self.assertRaises(OSError):self.flow.release()
        self.b.domain_birth='4'*32;self.b.domain_revision+=2;self.flow=self.b.make()
        with self.assertRaises(NativeUIError):self.flow.release_observations()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.join_store.read())
    def test_legacy_owner_without_original_preinput_resource_anchor_cannot_claim_resource_retirement(self):
        self.create();self.flow.join_store.discard(self.flow.join_previous);self.flow.join_previous=None
        self.flow=self.b.make();self.flow.delete();count=len(self.b.inputs)
        with self.assertRaises(NativeUIError):self.flow.release()
        self.assertEqual(count,len(self.b.inputs));self.assertIsNotNone(self.flow.store.read())


if __name__=='__main__':unittest.main()
