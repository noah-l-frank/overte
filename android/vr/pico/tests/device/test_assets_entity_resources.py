"""Actual original entity URL joined to an independent original ATP byte reader.

No Renderer/ModelCache request or child-request death is inferred. Real resource
QObject death, mapping/hash decoding and physical original bytes are measured.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import uuid
import test_assets_entity_effect as entity_module
import test_assets_cancel_effects as effects
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import pack,canonical,unpack,MAX_RAW,MAX_FRAMES
from adapters.assets_input import documents


class AssetsEntityResourcesTests(unittest.TestCase):
    setUp=entity_module.AssetsEntityEffectTests.setUp
    make=entity_module.AssetsEntityEffectTests.make
    cancel_phase=entity_module.AssetsEntityEffectTests.cancel_phase
    home_owner=entity_module.AssetsEntityEffectTests.home_owner
    pointers=entity_module.AssetsEntityEffectTests.pointers
    inputs=entity_module.AssetsEntityEffectTests.inputs
    model_snapshot=entity_module.AssetsEntityEffectTests.model_snapshot
    mappings=entity_module.AssetsEntityEffectTests.mappings
    exercise=entity_module.AssetsEntityEffectTests.exercise
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-resource-build-')
        cls.binary,cls.environment,cls.args=effects.compile_ui(cls.build.name,persistent_tablet=True,original_server=True,original_model=True,original_entity=True,original_resources=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=effects.compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def preserve(self):
        entity_module.AssetsEntityEffectTests.preserve(self)
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination is None:return
        directory=Path(destination).resolve(strict=True)
        if hasattr(self,'resources_store'):
            PrivateFeatureState(directory/(self._testMethodName+'-resources.json')).write(self.resources_store.read(),None)
    def entity_snapshot(self):
        result=entity_module.AssetsEntityEffectTests.entity_snapshot(self)
        if result['objects'] and not getattr(self,'resource_attempted',False):
            self.resource_attempted=True;self.resources_store=PrivateFeatureState(self.path/'resources.json')
            self.assertEqual(1,len(result['objects']));entity=result['objects'][0]
            request=dict(action='host-original-entity-resources',requestId=uuid.uuid4().hex,runId=self.run,entityId=entity['id'])
            pending=dict(assetsEntityResourceHostEvidenceVersion=1,binding=deepcopy(self.binding),entityOriginal=deepcopy(self.entity_frames[-1]),
                command=deepcopy(request),raw=None,bodyOriginals=json.loads((Path(self.build.name)/'resource-original-provenance.json').read_text()))
            self.model_fence.mark();self.resources_store.write(pending,None);previous=deepcopy(pending);self.model_fence.check()
            started=time.monotonic();epoch=self.host.epoch_milliseconds();raw=self.host.request(request)
            pending['raw']=raw;self.resources_store.write(pending,previous);self.model_fence.check()
            self.assertLessEqual(time.monotonic()-started,1.5);packet=json.loads(raw)
            self.assertEqual(1,packet['assetsEntityResourcesHostVersion']);self.assertEqual(self.host.process.pid,packet['processId'])
            self.assertEqual(request['requestId'],packet['requestId']);self.assertEqual(self.run,packet['runId'])
            self.assertEqual(1,packet['sequence']);uuid.UUID(packet['instance'])
            self.assertTrue(epoch<=packet['capturedEpochMs']<=self.host.epoch_milliseconds());self.assertLessEqual(packet['elapsedMs'],1500)
            self.assertEqual(entity['id'],packet['entityId']);self.assertEqual(entity['modelUrl'],packet['entityUrl'])
            self.assertEqual(['main','mesh','texture'],[row['role'] for row in packet['resources']]);self.resource_original=deepcopy(packet)
            expected=documents();names=('main.gltf','mesh/triangle.bin','textures/checker.png')
            for row,name in zip(packet['resources'],names):
                data=base64.b64decode(row['base64'],validate=True)
                self.assertEqual(expected['gltf-bundle/'+name],data);self.assertEqual(len(data),row['bytes']);self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
                self.assertEqual('atp:/original-model/'+name,row['url']);self.assertEqual('',row['relativeUrl'])
                self.assertEqual(0,row['result']);self.assertEqual(2,row['state']);self.assertTrue(row['completed'])
                self.assertFalse(row['loadedFromCache'] or row['resourceAlive'])
            wires=packet['serverOriginals'];self.assertEqual(6,len(wires))
            first_files=wires[0]['serverFiles'];self.assertTrue(all(row['serverFiles']==first_files for row in wires))
            self.assertTrue(all(row['serverInstance']==packet['serverInstance'] for row in wires))
            for index,(resource,name) in enumerate(zip(packet['resources'],names)):
                mapping,blob=wires[index*2:index*2+2];self.assertEqual('mapping',mapping['operation']);self.assertEqual('/original-model/'+name,mapping['path'])
                wire=base64.b64decode(mapping['wireBase64'],validate=True)
                self.assertEqual(34,len(wire));self.assertEqual(0,wire[0]);self.assertEqual(0,wire[-1]);self.assertEqual(resource['sha256'],wire[1:33].hex())
                self.assertEqual('blob',blob['operation']);self.assertEqual(resource['sha256'],blob['hash']);self.assertEqual(resource['base64'],blob['base64']);self.assertEqual(0,blob['error'])
                physical=next(row for row in blob['serverFiles'] if row['hash']==blob['hash'])
                self.assertTrue(physical['exists']);self.assertEqual(physical['sha256'],resource['sha256']);self.assertEqual(physical['bytes'],resource['bytes'])
            self.resource_disk=deepcopy(self.resources_store.read())
        return result
    def exercise_cancel_home(self,baseline):
        counts,raw=effects.AssetsCancelEffectsTests.exercise_cancel_home(self,baseline)
        self.assertTrue(self.resource_attempted);self.assertEqual(self.resource_disk,self.resources_store.read())
        # Current independent GetAll physical originals stay identical to every
        # resource-source read, before and after Cancel/file/Home windows.
        files=self.resource_original['serverOriginals'][0]['serverFiles']
        self.assertTrue(all(json.loads(frame['raw'])['serverFiles']==files for frame in self.actor.server_originals))
        counts+=len(self.resource_original['serverOriginals'])+len(self.resource_original['resources'])+1
        raw+=len(canonical(self.resource_original))+len(canonical([self.resource_disk['entityOriginal'],self.resource_disk['command']]))
        return counts,raw
    def test_original_entity_url_full_atp_request_companion_bytes_and_actual_resource_death(self):
        self.exercise(True)
        # No extra entity/model request or normal input was replayed by the byte reader.
        self.assertEqual(1,self.resource_original['sequence']);self.assertTrue(self.resource_attempted)


if __name__=='__main__':unittest.main()
