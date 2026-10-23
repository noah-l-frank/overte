"""Actual GLTF CPU parser/worker with original-model URL, ATP bytes and Home.

Transport replay and the Baker target are explicit host endpoints. The old
fixture remains a refusal counter; only new indexed data may reach CPU HFM.
Neither path qualifies the original GeometryResource, Baker or renderer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import test_assets_entity_resources as resources_module
from adapters.assets_input import documents
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import canonical
from assets_geometry_fixture import indexed_documents

HERE=Path(__file__).resolve().parent


class AssetsGeometryParserTests(unittest.TestCase):
    make=resources_module.AssetsEntityResourcesTests.make
    cancel_phase=resources_module.AssetsEntityResourcesTests.cancel_phase
    home_owner=resources_module.AssetsEntityResourcesTests.home_owner
    pointers=resources_module.AssetsEntityResourcesTests.pointers
    inputs=resources_module.AssetsEntityResourcesTests.inputs
    model_snapshot=resources_module.AssetsEntityResourcesTests.model_snapshot
    mappings=resources_module.AssetsEntityResourcesTests.mappings
    exercise=resources_module.AssetsEntityResourcesTests.exercise
    @classmethod
    def setUpClass(cls):
        resources_module.AssetsEntityResourcesTests.setUpClass.__func__(cls)
        cls.indexed_fixture=Path(cls.build.name)/'indexed-original-entity-input'
        for name,data in indexed_documents().items():
            if not name.startswith('gltf-bundle/'):continue
            target=cls.indexed_fixture/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        cls.parser_stage=Path(cls.build.name)/'parser'
        spec=importlib.util.spec_from_file_location('assets_geometry_parser_prepare',HERE/'assets-geometry-parser-prepare.py')
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        command=prepare.prepare(cls.parser_stage,cls.environment,Path(cls.environment['OVERTE_QT5_HOST_ROOT']))
        subprocess.run(command,check=True,timeout=90,env=cls.environment)
        cls.parser=cls.parser_stage/'geometry-parser'
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination:
            # Every inherited cleanup writer uses this same parent and this
            # method prefix. Refuse wrong rights/existing output BEFORE any
            # actual host, normal input or source acquisition can start.
            directory=Path(destination).resolve(strict=True)
            self.assertIsNone(PrivateFeatureState(directory/(self._testMethodName+'-evidence-preflight.json')).read())
            self.assertEqual([],list(directory.glob(self._testMethodName+'-*')))
        self.environment=dict(type(self).environment)
        self.indexed=self._testMethodName.startswith('test_indexed_')
        if self.indexed:self.environment['OVERTE_ASSETS_ENTITY_FIXTURE']=str(self.indexed_fixture)
        resources_module.AssetsEntityResourcesTests.setUp(self)
    def resource_documents(self):return indexed_documents() if self.indexed else documents()
    def preserve(self):
        # The parser intent/input/response already lives outside the disposable
        # runtime directory when evidence was requested. Its original survives
        # even if an independent inherited cleanup writer refuses a value.
        resources_module.AssetsEntityResourcesTests.preserve(self)
    def entity_snapshot(self):
        result=resources_module.AssetsEntityResourcesTests.entity_snapshot(self)
        if result['objects'] and not hasattr(self,'parser_store'):
            self.model_fence.check()
            destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
            journal=Path(destination).resolve(strict=True)/(self._testMethodName+'-parser.json') if destination else self.path/'parser.json'
            self.parser_store=PrivateFeatureState(journal)
            raw=self.resource_disk['raw'];packet=self.path/'parser-input.json';output=self.path/'parser-output.json'
            with packet.open('x') as stream:stream.write(raw)
            pending=dict(geometryParserHostEvidenceVersion=1,binding=deepcopy(self.binding),
                inputSha256=hashlib.sha256(raw.encode()).hexdigest(),inputOriginal=raw,
                parserArtifactSha256=hashlib.sha256(self.parser.read_bytes()).hexdigest(),
                originalCppSources=json.loads((self.parser_stage/'geometry-parser-original-provenance.json').read_text()),
                pending=True,raw=None,processReturncode=None,stderr=None)
            self.parser_store.write(pending,None);previous=deepcopy(pending)
            started=time.monotonic()
            completed=subprocess.run([str(self.parser),str(packet),str(output)],env=self.environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1.5)
            elapsed=time.monotonic()-started
            # Store the original child response before interpreting any outcome.
            pending.update(raw=output.read_text() if output.exists() else None,processReturncode=completed.returncode,
                stderr=completed.stderr.decode(errors='replace'),pending=False)
            self.parser_store.write(pending,previous);self.parser_disk=deepcopy(pending)
            self.model_fence.check()
            self.assertLessEqual(elapsed,1.5);self.assertEqual(0,completed.returncode,pending['stderr'])
            self.assertEqual(raw,packet.read_text());self.assertEqual(self.resource_disk,self.resources_store.read())
            self.parser_original=json.loads(pending['raw']);observed=self.parser_original
            self.assertEqual(1,observed['geometryParserHostEvidenceVersion']);self.assertTrue(observed['protocolValid'] and observed['workerRetired'])
            self.assertEqual(pending['inputSha256'],observed['sourcePacketSha256'])
            self.assertFalse(observed['geometryReadinessQualified'] or observed['rendererReadinessQualified'])
            self.assertEqual(dict(completed=True,success=False,completions=1),observed['hostReceiverOriginal'])
            self.assertTrue(observed['hostReceiverDead']);self.assertEqual(0,observed['pending']);self.assertEqual(0,observed['processing'])
            worker=observed['workerOriginals']
            self.assertEqual(['constructed','run-enter','run-exit','destructor-enter'],[row['phase'] for row in worker])
            self.assertEqual(1,len({row['id'] for row in worker}));self.assertTrue(all(row['autoDelete'] for row in worker))
            self.assertEqual(observed['callerThread'],worker[0]['thread']);self.assertNotEqual(worker[0]['thread'],worker[1]['thread'])
            self.assertEqual(1,len({row['thread'] for row in worker[1:]}))
            self.assertTrue(all(b['observedEpochMs']>=a['observedEpochMs'] for a,b in zip(worker,worker[1:])))
            self.assertEqual(1,len(observed['loaderOriginals']));loader=observed['loaderOriginals'][0]
            main=self.resource_original['resources'][0]
            self.assertEqual(main['url'],loader['url']);self.assertEqual(main['sha256'],loader['sha256']);self.assertEqual(main['bytes'],loader['bytes'])
            self.assertEqual(dict(combineParts=True,deduplicateIndices=True),loader['mapping']);self.assertEqual(worker[1]['thread'],loader['thread'])
        return result
    def exercise_cancel_home(self,baseline):
        counts,raw=resources_module.AssetsEntityResourcesTests.exercise_cancel_home(self,baseline)
        self.assertEqual(self.parser_disk,self.parser_store.read())
        original=self.parser_original
        counts+=len(original['workerOriginals'])+len(original['loaderOriginals'])+len(original['transportOriginals'])+2
        raw+=len(canonical(original))+len(self.parser_disk['inputOriginal'].encode())
        return counts,raw
    def test_original_nonindexed_bytes_remain_a_parser_refusal_counter(self):
        self.exercise(True)
        self.assertEqual({},self.parser_original['parsedHandoff'])
        self.assertFalse(self.parser_original['loaderOriginals'][0].get('returnedModel',False))
    def test_indexed_original_model_atp_bytes_actual_cpu_parser_worker_and_baker_boundary(self):
        self.exercise(True)
        original=self.parser_original;handoff=original['parsedHandoff']
        self.assertTrue(original['loaderOriginals'][0]['returnedModel']);self.assertEqual('atp:/original-model/main.gltf',handoff['url'])
        self.assertEqual(0,handoff['errors']);self.assertEqual(1,handoff['joints']);self.assertEqual(1,handoff['materials'])
        self.assertEqual(1,len(handoff['meshes']));mesh=handoff['meshes'][0]
        self.assertEqual([[-.5,0,0],[.5,0,0],[0,1,0]],mesh['vertices']);self.assertEqual([0,1,2],sorted(mesh['indices']))
        self.assertEqual(3,len(mesh['normals']));self.assertEqual(3,len(mesh['texcoords']))
        self.assertTrue(mesh['skinningDataValid']);self.assertFalse(mesh['graphicsMeshExists'])
        self.assertEqual([dict(name='checker.png',url='atp:/original-model/textures/checker.png',embeddedBytes=0)],handoff['textures'])
        self.assertEqual(1,len(original['transportOriginals']));transport=original['transportOriginals'][0]
        self.assertEqual('atp:/original-model/mesh/triangle.bin',transport['url']);self.assertEqual(102,transport['bytes'])
        self.assertEqual(self.resource_original['resources'][1]['sha256'],transport['sha256'])
        self.assertEqual('GLTFSerializer::requestData',transport['extra']);self.assertEqual(handoff['thread'],transport['thread'])
        self.assertTrue(original['transportAliveBeforeProcessExit']);self.assertFalse(original['transportRetirementQualified'])


if __name__=='__main__':unittest.main()
