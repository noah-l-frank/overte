"""Original AssetMappingModel/proxy/read request joined to normal QML input.

Server/assignment/stdin/controller remain host endpoints. Foreign fixture rows
are browsed only; no upload, write, import, oven or render result is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import test_assets_cancel_effects as effects_module
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_input_fence import PhaseInputFence
from adapters.script_journey.history import pack,unpack,canonical,MAX_FRAMES,MAX_RAW
from feature_journeys.phase_fixture import PhaseFixtureReader


class ModelInputFence(PhaseInputFence):
    def original(self):return self.expected


class AssetsMappingModelTests(unittest.TestCase):
    setUp=effects_module.AssetsCancelEffectsTests.setUp
    make=effects_module.AssetsCancelEffectsTests.make
    cancel_phase=effects_module.AssetsCancelEffectsTests.cancel_phase
    home_owner=effects_module.AssetsCancelEffectsTests.home_owner
    pointers=effects_module.AssetsCancelEffectsTests.pointers
    exercise_cancel_home=effects_module.AssetsCancelEffectsTests.exercise_cancel_home
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-real-model-build-')
        cls.binary,cls.environment,cls.args=effects_module.compile_ui(cls.build.name,persistent_tablet=True,original_server=True,original_model=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=effects_module.compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def preserve(self):
        effects_module.AssetsCancelEffectsTests.preserve(self)
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination is None:return
        directory=Path(destination).resolve(strict=True)
        for role,value in [('model',dict(mappingModelHostEvidenceVersion=1,originals=pack(getattr(self,'model_frames',[])),
                inputOriginals=pack(getattr(self,'input_frames',[])),phaseOriginals=pack(self.model_fence.frames if hasattr(self,'model_fence') else []),
                bodyOriginals=json.loads((Path(self.build.name)/'mapping-original-provenance.json').read_text()))),
                *([('model-input',self.model_store.read())] if hasattr(self,'model_store') else [])]:
            PrivateFeatureState(directory/(self._testMethodName+'-'+role+'.json')).write(value,None)
    def model_snapshot(self):
        for attempt in range(51):
            raw=self.host.request(dict(action='host-original-mapping-model'));value=json.loads(raw)
            self.model_frames.append(dict(raw=raw))
            if value.get('updatedSignals',0)>0:break
            self.assertLess(attempt,50);time.sleep(.1)
        self.assertEqual('AssetMappingModel',value['className']);self.assertEqual('QSortFilterProxyModel',value['proxyClassName'])
        self.assertTrue(value['sourceMatches'] and value['ownerThread']);self.assertEqual(self.host.process.pid,value['processId'])
        self.assertGreater(value['updatedSignals'],0);self.assertGreater(value['lastUpdatedEpochMs'],0)
        return value
    def mappings(self):
        result=effects_module.AssetsCancelEffectsTests.mappings(self)
        if hasattr(self,'model_frames'):
            model=self.model_snapshot();self.assertEqual(0,model['numPendingBakes'])
            self.assertEqual({'/foreign/','/foreign/original.bin'},{row['path'] for row in model['rows']})
            self.assertFalse(any(row['path'].startswith('/.baked/') for row in model['rows']))
            if hasattr(self,'ui') and self.journal.runs[self.run]['stimulus']['verb']!='close':
                snapshot=self.ui.capture();page=self.ui.page(snapshot);self.input_frames.append(deepcopy(snapshot))
                self.assertEqual('/foreign/original.bin',page['selectedPath']);self.assertEqual('--',page['selectedStatus'])
                self.assertFalse(self.ui.row(snapshot,'assets.baking',enabled=False)['enabled'])
        return result
    def test_actual_mapping_model_proxy_normal_selection_hidden_rows_and_original_home_stop(self):
        self.model_frames=[];self.input_frames=[];before=self.model_snapshot();self.assertTrue(before['autoRefreshEnabled'])
        baseline=self.mappings();self.assertEqual(2,len(baseline));self.assertTrue(any(row['path'].startswith('/.baked/') for row in baseline))
        fence=ModelInputFence(PhaseFixtureReader(self.client,self.run,'assets'));fence.expected=fence.source.read()['status']
        self.model_fence=fence;self.model_store=PrivateFeatureState(self.path/'model-input.json')
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
            pending['native']=deepcopy(command);commands=unpack(state['inputs']);commands.append(dict(input=deepcopy(pending['input']),
                value=deepcopy(pending['value']),native=deepcopy(command),after=None));state['inputs']=pack(commands);save();fence.check()
        self.ui=self.host.controls(intent,before_send=native,audit=audit)
        self.ui.input('assets.refresh');after=self.model_snapshot();self.assertGreater(after['updatedSignals'],before['updatedSignals'])
        self.ui.select_mapping('/foreign/original.bin');self.assertEqual(baseline,self.mappings());original=deepcopy(self.model_store.read())
        counts,raw=self.exercise_cancel_home(baseline);final=self.model_snapshot()
        for frames in (self.model_frames,self.input_frames,fence.frames,unpack(original['inputs'])):counts+=len(frames);raw+=len(canonical(frames))
        self.assertLessEqual(counts,MAX_FRAMES);self.assertLessEqual(raw,MAX_RAW)
        self.assertFalse(final['autoRefreshEnabled']);self.assertEqual(original,self.model_store.read())
        self.assertEqual(4,len(unpack(original['inputs'])));self.assertIsNone(original['pending'])
        self.assertFalse(self.pointers()['pageAlive']);self.assertTrue(self.pointers()['contextAlive'])


if __name__=='__main__':unittest.main()
