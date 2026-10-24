"""Original GeometryResource download/worker ownership; stop before Baker.

Recorded ATP transport, cache scheduling and FST/texture processing are explicit
boundaries. Original loaded/failure/HFM fields and actual deletion are observed,
not substituted with ready or rendering results.
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
import time
import unittest
import test_assets_entity_resources as resources_module
import test_assets_geometry_parser as parser_module
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import canonical
from assets_geometry_fixture import indexed_documents

HERE=Path(__file__).resolve().parent


class AssetsGeometryResourceTests(unittest.TestCase):
    prepare_name="assets-geometry-resource-prepare.py"
    model_cache=False
    model_baker=False
    make=resources_module.AssetsEntityResourcesTests.make
    cancel_phase=resources_module.AssetsEntityResourcesTests.cancel_phase
    home_owner=resources_module.AssetsEntityResourcesTests.home_owner
    pointers=resources_module.AssetsEntityResourcesTests.pointers
    inputs=resources_module.AssetsEntityResourcesTests.inputs
    model_snapshot=resources_module.AssetsEntityResourcesTests.model_snapshot
    mappings=resources_module.AssetsEntityResourcesTests.mappings
    exercise=resources_module.AssetsEntityResourcesTests.exercise
    setUp=parser_module.AssetsGeometryParserTests.setUp
    resource_documents=parser_module.AssetsGeometryParserTests.resource_documents
    preserve=resources_module.AssetsEntityResourcesTests.preserve
    @classmethod
    def setUpClass(cls):
        resources_module.AssetsEntityResourcesTests.setUpClass.__func__(cls)
        cls.indexed_fixture=Path(cls.build.name)/'indexed-original-entity-input'
        for name,data in indexed_documents().items():
            if not name.startswith('gltf-bundle/'):continue
            target=cls.indexed_fixture/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        cls.parser_stage=Path(cls.build.name)/'geometry-resource'
        spec=importlib.util.spec_from_file_location('assets_geometry_resource_prepare',HERE/cls.prepare_name)
        prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
        command=prepare.prepare(cls.parser_stage,cls.environment,Path(cls.environment['OVERTE_QT5_HOST_ROOT']))
        cls.compile_native(command)
        cls.parser=cls.parser_stage/'geometry-parser'
    @classmethod
    def compile_native(cls,command):subprocess.run(command,check=True,timeout=90,env=cls.environment)
    def prepare_native_environment(self):pass
    def native_provenance_names(self):
        return (('geometry-resource-original-provenance.json','geometry-parser-original-provenance.json','resource-data-original-provenance.json')+
            (('model-cache-original-provenance.json',) if self.model_cache else ())+
            (('model-baker-original-provenance.json',) if self.model_baker else ()))
    def validate_native_source_provenance(self,value):pass
    def native_source_provenance(self):
        return {name:json.loads((self.parser_stage/name).read_text()) for name in self.native_provenance_names()}
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def entity_snapshot(self):
        result=resources_module.AssetsEntityResourcesTests.entity_snapshot(self)
        if result['objects'] and not hasattr(self,'parser_store'):
            self.model_fence.check();destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
            journal=Path(destination).resolve(strict=True)/(self._testMethodName+'-geometry-resource.json') if destination else self.path/'geometry-resource.json'
            self.parser_store=PrivateFeatureState(journal)
            raw=self.resource_disk['raw'];packet=self.path/'geometry-input.json';output=self.path/'geometry-output.json'
            with packet.open('x') as stream:stream.write(raw)
            self.prepare_native_environment()
            pending=dict(geometryResourceHostEvidenceVersion=1,binding=deepcopy(self.binding),
                inputSha256=hashlib.sha256(raw.encode()).hexdigest(),inputOriginal=raw,
                parserArtifactSha256=hashlib.sha256(self.parser.read_bytes()).hexdigest(),
                originalCppSources=self.native_source_provenance(),
                pending=True,raw=None,processReturncode=None,stderr=None)
            self.parser_store.write(pending,None);previous=deepcopy(pending);started=time.monotonic()
            try:
                completed=subprocess.run([str(self.parser),str(packet),str(output)],env=self.environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=1.5)
            except subprocess.TimeoutExpired as failure:
                # Retain actual already-written output/diagnostics before the
                # disposable runtime disappears. Timeout never proves release.
                pending.update(raw=output.read_text() if output.exists() else None,processReturncode=None,
                    stderr=(failure.stderr or b'').decode(errors='replace'),pending=False,timedOut=True)
                self.parser_store.write(pending,previous);self.parser_disk=deepcopy(pending)
                self.validate_native_source_provenance(pending['originalCppSources'])
                raise
            elapsed=time.monotonic()-started
            pending.update(raw=output.read_text() if output.exists() else None,processReturncode=completed.returncode,
                stderr=completed.stderr.decode(errors='replace'),pending=False)
            self.parser_store.write(pending,previous);self.parser_disk=deepcopy(pending);self.model_fence.check()
            self.validate_native_source_provenance(pending['originalCppSources'])
            self.assertLessEqual(elapsed,1.5);self.assertEqual(0,completed.returncode,pending['stderr'])
            self.assertEqual(raw,packet.read_text());self.assertEqual(self.resource_disk,self.resources_store.read())
            native=json.loads(pending['raw']);self.parser_original=native
            self.validate_native_result(native,pending)
        return result
    def validate_native_result(self,native,pending):
        self.assertEqual(1,native['geometryResourceHostEvidenceVersion']);self.assertTrue(native['protocolValid'] and native['workerRetired'])
        self.assertEqual(pending['inputSha256'],native['sourcePacketSha256'])
        self.assertFalse(native['rendererReadinessQualified']);self.assertEqual(self.model_baker and self.indexed,native['bakerProcessingQualified'])
        self.assertEqual(0,native['pending']);self.assertEqual(0,native['processing']);self.assertEqual(1,native['cacheCompletions'])
        main=self.resource_original['resources'][0];self.assertEqual(main['sha256'],native['loadedOriginalSha256'])
        owner=native['ownerOriginals'];self.assertEqual(['constructed','loaded-signal','finished-external-reference-released','retired'],[row['phase'] for row in owner])
        self.assertEqual(1,len({row['id'] for row in owner}));self.assertTrue(all(row['alive'] and row['ownerThread'] for row in owner[:3]))
        self.assertTrue(all(row['actualQtClass']=='GeometryResource' for row in owner[:3]))
        self.assertEqual(0,owner[0]['bytes']);self.assertEqual(self.model_cache,owner[0]['requestAlive'])
        self.assertTrue(owner[1]['requestAlive']);self.assertFalse(owner[1]['resourceFailed'])
        self.assertTrue(owner[2]['resourceFailed']);self.assertEqual(main['bytes'],owner[1]['bytes']);self.assertEqual(main['bytes'],owner[2]['bytes'])
        self.assertFalse(any(row['resourceLoaded'] or row['hfmPresent'] for row in owner[:3]))
        self.assertFalse(owner[3]['alive'] or owner[3]['requestAlive']);self.assertIsNone(owner[3]['hfmPresent'])
        self.assertTrue(all(b['observedEpochMs']>=a['observedEpochMs'] for a,b in zip(owner,owner[1:])))
        worker=native['workerOriginals'];self.assertEqual(['constructed','run-enter','run-exit','destructor-enter'],[row['phase'] for row in worker])
        self.assertEqual(1,len({row['id'] for row in worker}));self.assertEqual({owner[0]['id']},{row['resourceId'] for row in worker})
        self.assertTrue(all(row['autoDelete'] for row in worker));self.assertEqual(native['callerThread'],worker[0]['thread'])
        self.assertNotEqual(worker[0]['thread'],worker[1]['thread']);self.assertEqual(1,len({row['thread'] for row in worker[1:]}))
        self.assertEqual(1,len(native['loaderOriginals']));loader=native['loaderOriginals'][0]
        self.assertEqual(main['url'],loader['url']);self.assertEqual(main['sha256'],loader['sha256']);self.assertEqual(main['bytes'],loader['bytes'])
        self.assertEqual(dict(combineParts=True,deduplicateIndices=True,**({'picoOriginalMarker':True} if self.model_cache else {})),loader['mapping']);self.assertEqual(worker[1]['thread'],loader['thread'])
        self.assertEqual(4 if self.model_cache else 2,len(native['resourceObserverOriginals']));self.assertEqual({row['url'] for row in self.resource_original['resources'][:2]},
            {row['url'] for row in native['resourceObserverOriginals']})
        self.assertEqual([False,True],native['transportPresenceBeforeProcessExit'])
    def exercise_cancel_home(self,baseline):
        counts,raw=resources_module.AssetsEntityResourcesTests.exercise_cancel_home(self,baseline)
        self.assertEqual(self.parser_disk,self.parser_store.read());native=self.parser_original
        for key in ('workerOriginals','loaderOriginals','transportOriginals','ownerOriginals','resourceObserverOriginals','cacheOriginals','bakerOriginals'):counts+=len(native.get(key,[]))
        counts+=2;raw+=len(canonical(native))+len(self.parser_disk['inputOriginal'].encode())
        return counts,raw
    def test_original_geometry_nonindexed_parser_refusal_and_original_owner_retirement(self):
        self.exercise(True);self.assertEqual({},self.parser_original['parsedHandoff'])
        self.assertIs(False,self.parser_original['loaderOriginals'][0]['returnedModel'])
        self.assertIn('No indices accessor',self.parser_disk['stderr'])
    def test_indexed_geometry_original_download_worker_cpu_handoff_and_original_owner_retirement(self):
        self.exercise(True);native=self.parser_original;handoff=native['parsedHandoff']
        self.assertIs(True,native['loaderOriginals'][0]['returnedModel']);self.assertEqual('atp:/original-model/main.gltf',handoff['url'])
        self.assertEqual(0,handoff['errors']);self.assertEqual(1,handoff['joints']);self.assertEqual(1,handoff['materials'])
        self.assertEqual(1,len(handoff['meshes']));mesh=handoff['meshes'][0]
        self.assertEqual([[-.5,0,0],[.5,0,0],[0,1,0]],mesh['vertices']);self.assertEqual([0,1,2],sorted(mesh['indices']))
        self.assertFalse(mesh['graphicsMeshExists']);self.assertTrue(mesh['skinningDataValid'])
        self.assertEqual(2,len(native['transportOriginals']))
        for original,row in zip(self.resource_original['resources'],native['transportOriginals']):
            self.assertEqual(original['url'],row['url']);self.assertEqual(original['sha256'],row['sha256']);self.assertEqual(original['bytes'],row['bytes'])
        self.assertEqual([True,False],[row['parented'] for row in native['transportOriginals']])


if __name__=='__main__':unittest.main()
