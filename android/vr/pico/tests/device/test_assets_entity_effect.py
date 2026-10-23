"""Normal original-model Add to World through original native entity dispatch.

Property/Octree/model-factory/packet/avatar/renderer endpoints remain host seams.
A local object and creation marker prove insertion only. No loaded/rendered,
unit-size, server-accepted or deleted entity claim is made.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import test_assets_cancel_effects as effects
import test_assets_mapping_model as models
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import pack,unpack,canonical,MAX_FRAMES,MAX_RAW
from feature_journeys.phase_fixture import PhaseFixtureReader
from adapters.assets_input import documents


class AssetsEntityEffectTests(unittest.TestCase):
    def setUp(self):
        self.args=list(type(self).args)
        if 'without_tree' in self._testMethodName:self.args.append('--entity-without-local-tree')
        effects.AssetsCancelEffectsTests.setUp(self)
    make=effects.AssetsCancelEffectsTests.make
    cancel_phase=effects.AssetsCancelEffectsTests.cancel_phase
    home_owner=effects.AssetsCancelEffectsTests.home_owner
    pointers=effects.AssetsCancelEffectsTests.pointers
    exercise_cancel_home=effects.AssetsCancelEffectsTests.exercise_cancel_home
    model_snapshot=models.AssetsMappingModelTests.model_snapshot
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-entity-build-')
        cls.binary,cls.environment,cls.args=effects.compile_ui(cls.build.name,persistent_tablet=True,original_server=True,original_model=True,original_entity=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=effects.compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def preserve(self):
        effects.AssetsCancelEffectsTests.preserve(self)
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination is None:return
        directory=Path(destination).resolve(strict=True)
        PrivateFeatureState(directory/(self._testMethodName+'-entity.json')).write(dict(assetsEntityEffectHostEvidenceVersion=1,
            entityOriginals=pack(getattr(self,'entity_frames',[])),modelOriginals=pack(getattr(self,'model_frames',[])),
            inputOriginals=pack(getattr(self,'input_frames',[])),phaseOriginals=pack(self.model_fence.frames if hasattr(self,'model_fence') else []),
            entityCppBodies=json.loads((Path(self.build.name)/'entity-original-provenance.json').read_text()),
            modelCppBodies=json.loads((Path(self.build.name)/'mapping-original-provenance.json').read_text()),
            retainedEntityIds=getattr(self,'retained',[])),None)
        if hasattr(self,'model_store'):PrivateFeatureState(directory/(self._testMethodName+'-input.json')).write(self.model_store.read(),None)
    def mappings(self):return effects.AssetsCancelEffectsTests.mappings(self)
    def entity_snapshot(self):
        start=time.monotonic();epoch=self.host.epoch_milliseconds()
        raw=self.host.request(dict(action='host-original-entity-effect',runId=self.run));self.entity_frames.append(dict(raw=raw))
        # Original response is durable before interpreting any claimed effect.
        self.effect_store.write(dict(assetsEntityHostOriginalsVersion=1,originals=pack(self.entity_frames)),getattr(self,'effect_disk',None))
        self.effect_disk=self.effect_store.read();value=json.loads(raw)
        self.assertEqual(1,value['assetsEntityHostVersion']);self.assertEqual(self.host.process.pid,value['processId'])
        self.assertTrue(epoch<=value['capturedEpochMs']<=self.host.epoch_milliseconds())
        self.assertLessEqual(time.monotonic()-start,1.5)
        self.assertEqual(len(self.entity_frames),value['sequence']);return value
    def inputs(self):
        fence=models.ModelInputFence(PhaseFixtureReader(self.client,self.run,'assets'));fence.expected=fence.source.read()['status']
        self.model_fence=fence;self.model_store=PrivateFeatureState(self.path/'entity-model-input.json')
        state=dict(modelInputHostEvidenceVersion=1,binding=deepcopy(self.binding),runId=self.run,phaseOriginal=deepcopy(fence.expected),pending=None,inputs=pack([]))
        self.model_store.write(state,None);disk=deepcopy(state);draft=None
        def save():
            nonlocal disk
            self.model_store.write(state,disk);disk=deepcopy(state)
        def audit(phase,value):
            nonlocal draft
            if phase=='intent':draft=deepcopy(value);return True
            self.assertEqual('receipt',phase);self.assertIsNotNone(state['pending']['native'])
            commands=unpack(state['inputs']);commands[-1]['after']=deepcopy(value['after']['scope']);state['inputs']=pack(commands)
            state['pending']=None;save();fence.check();return True
        def intent(value):
            self.assertIsNone(state['pending']);fence.mark();state['pending']=dict(input=deepcopy(value),value=deepcopy(draft['value']),native=None);save();fence.check()
        def native(command,navigation):
            fence.check();pending=state['pending'];self.assertIsNone(pending['native'])
            self.assertTrue(all(command[key]==pending['input'][key] for key in ('controlId','controlToken','action')))
            self.assertEqual(command['sequence'],pending['input']['scope']['sequence']+1)
            pending['native']=deepcopy(command);commands=unpack(state['inputs']);commands.append(dict(input=deepcopy(pending['input']),value=deepcopy(pending['value']),native=deepcopy(command),after=None))
            state['inputs']=pack(commands);save();fence.check()
        self.ui=self.host.controls(intent,before_send=native,audit=audit)
    def exercise(self,tree):
        self.entity_frames=[];self.model_frames=[];self.input_frames=[];self.effect_store=PrivateFeatureState(self.path/'entity-originals.json')
        baseline=self.mappings();model=self.model_snapshot();self.assertTrue(model['autoRefreshEnabled'])
        for name,data in documents().items():
            if name.startswith('gltf-bundle/'):
                path='/original-model/'+name.split('/',1)[1];mapping=next(row for row in baseline if row['path']==path)
                self.assertEqual(hashlib.sha256(data).hexdigest(),mapping['hash'])
        self.inputs();before=self.entity_snapshot();self.assertEqual(tree,before['treeAttached'])
        self.assertEqual([],before['objects']);self.assertEqual([],before['creations']['events']);self.assertEqual(0,before['calls'])
        self.ui.input('assets.refresh');self.ui.select_mapping('/original-model/main.gltf')
        selected=self.ui.capture();self.input_frames.append(deepcopy(selected));self.assertEqual('/original-model/main.gltf',self.ui.page(selected)['selectedPath'])
        self.assertTrue(self.ui.row(selected,'assets.import')['enabled'])
        self.ui.input('assets.import');dialog=self.ui.wait(lambda value:self.ui.row(value,'assets.model.url') is not None)
        self.input_frames.append(deepcopy(dialog));self.assertEqual('atp:/original-model/main.gltf',self.ui.row(dialog,'assets.model.url')['text'])
        in_dialog=self.entity_snapshot();self.assertEqual(0,in_dialog['calls']);self.assertEqual([],in_dialog['objects'])
        self.ui.input('assets.model.accept');closed=self.ui.wait(lambda value:self.ui.row(value,'assets.model.url') is None)
        self.input_frames.append(deepcopy(closed));after=self.entity_snapshot();self.assertEqual(1,after['calls'])
        self.assertTrue(after['returnedId'].replace('0','').replace('-',''));self.assertEqual(1,len(after['packets']))
        self.assertEqual(after['returnedId'],after['packets'][0]['id']);self.assertEqual('atp:/original-model/main.gltf',after['packets'][0]['url'])
        self.retained=[after['returnedId']]
        if tree:
            self.assertEqual(1,after['inserted']);self.assertEqual(1,after['postAdded']);self.assertEqual(1,len(after['objects']))
            obj=after['objects'][0];event=after['creations']['events'][0]
            self.assertEqual(obj['id'],after['returnedId']);self.assertEqual(obj['id'],event['id']);self.assertEqual('Model',event['type'])
            self.assertEqual('domain',event['hostType']);self.assertEqual(obj['editor'],event['sessionId']);self.assertEqual(obj['createdEpochUs'],event['createdEpochUs'])
            self.assertGreater(obj['createdEpochUs'],0);self.assertEqual(obj['createdEpochUs'],obj['lastEditedEpochUs'])
            self.assertGreaterEqual(obj['lastBroadcastEpochUs'],obj['createdEpochUs']);self.assertEqual(2,obj['simulationPriority']);self.assertTrue(obj['ownerThread'])
            self.assertEqual('Model',obj['type']);self.assertEqual('main.gltf',obj['name']);self.assertEqual('atp:/original-model/main.gltf',obj['modelUrl'])
            self.assertEqual('simple-compound',obj['shape']);self.assertFalse(obj['dynamic'] or obj['collisionless'] or obj['grabbable'] or obj['dimensionsInitialized'])
            self.assertTrue(obj['delegateToParent']);self.assertEqual({'grabbableKey':{'grabbable':False}},json.loads(obj['userData']))
            self.assertEqual(dict(x=0,y=0,z=2),obj['position']);self.assertEqual(dict(x=0,y=0,z=0),obj['gravity'])
            for dimension in obj['dimensions'].values():self.assertAlmostEqual(.1,dimension,places=6)
        else:
            self.assertEqual([],after['objects']);self.assertEqual([],after['creations']['events']);self.assertEqual(0,after['inserted'])
        # Both paths produce the original QML success text. It cannot prove insertion.
        self.assertEqual('Added asset to the world.',self.ui.page(closed)['status'])
        self.assertEqual(baseline,self.mappings());original_input=deepcopy(self.model_store.read())
        counts,raw=self.exercise_cancel_home(baseline)
        final=self.entity_snapshot();self.assertEqual(after['objects'],final['objects']);self.assertEqual(after['creations'],final['creations'])
        self.assertEqual(after['packets'],final['packets']);self.assertEqual(original_input,self.model_store.read())
        self.assertFalse(self.model_snapshot()['autoRefreshEnabled']);self.assertFalse(self.pointers()['pageAlive']);self.assertTrue(self.pointers()['contextAlive'])
        for frames in (self.entity_frames,self.model_frames,self.input_frames,self.model_fence.frames,unpack(original_input['inputs'])):
            counts+=len(frames);raw+=len(canonical(frames))
        self.assertLessEqual(counts,MAX_FRAMES);self.assertLessEqual(raw,MAX_RAW)
        self.assertIsNone(original_input['pending']);self.assertEqual(1,sum(row['native']['controlId']=='assets.model.accept' for row in unpack(original_input['inputs'])))
    def test_original_model_row_normal_add_world_actual_local_entity_marker_and_retained_home(self):self.exercise(True)
    def test_original_nonempty_id_and_qml_success_without_tree_never_prove_entity_insertion(self):self.exercise(False)


if __name__=='__main__':unittest.main()
