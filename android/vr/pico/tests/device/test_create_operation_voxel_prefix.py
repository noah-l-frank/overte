"""Same original CLI/Parent through the first fifteen normal Create actions.

The PolyVox producer is the existing explicit native/UI/controller model,
without GPU/device or full Actor claims. The separate twelve-action selector
keeps the original Model-only child; it cannot observe a later PolyVox world.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import base64
from pathlib import Path
import time
import unittest
import uuid

from test_create_operation_cli import CreateOperationCliTests
from test_create_journey import RUN,URL
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.create_entities import voxel_source
from adapters.script_journey.history import unpack
from feature_journeys.scenarios import SCENARIOS
from test_create_files import NativeBoundary,TICKET,ROLE


class CreateOperationVoxelPrefixTests(CreateOperationCliTests):
    def setUp(self):
        CreateOperationCliTests.setUp(self)
        self.prefix[1]=str(Path(__file__).with_name('create_operation_voxel_cli_host.py'))

    def test_same_original_cli_fifteen_actions_and_exact_original_voxel_edit(self):
        started=time.monotonic();deadline=started+120
        self.component('prepare')
        for index,step in enumerate(SCENARIOS['create']['steps'][:15],1):
            self.assertLess(time.monotonic(),deadline)
            self.act(step['verb'],step['inputs'])
        metadata=PrivateFeatureState(self.area/'model-host.json').read();self.assertEqual(1,metadata['factoryCalls'])
        state_root=Path(metadata['stateRoot'])
        parent=PrivateFeatureState(next(state_root.glob('create-feature-owner-*.json'))).read()
        self.assertEqual(15,len(parent['calls']));self.assertIsNone(parent['pending']);self.assertIsNone(parent['subject'])
        self.assertEqual('deleted',parent['primitives'][-1]['outcome'])
        self.assertIsNotNone(parent['voxelEdit'])
        edit=parent['voxelEdit'];self.assertEqual('edited',edit['outcome']);self.assertTrue(edit['settingsRestored'])
        self.assertEqual(3,len(edit['streams']))
        after=unpack(edit['after']['native'])
        entities=json.loads(next(row['raw'] for row in after if row['role']=='entities'))
        volume=voxel_source(entities['source']['entities'][0]['voxels'])
        self.assertEqual(16,sum(value!=0 for value in volume))
        sample=self.component('sample');self.authority.epoch=sample['sampleAnchor']['nativeEpochMs']
        with self.assertRaisesRegex(RuntimeError,'unresolved'):
            with self.host.create_input_context(RUN,URL,'cleanup',None):
                self.authority.activate(uuid.uuid4().hex,'cleanup',{})
                self.component('cleanup')
        self.assertTrue(self.host.failed)
        errors=b''.join(path.read_bytes() for path in sorted(self.artifacts.glob('stderr-*.bin')))
        self.assertIn(b'Original Create Qt context, listener or delivery remains retained',errors)
        self.assertLess(time.monotonic(),deadline)
        (self.area/'fifteen-action-prefix-result.json').write_text(json.dumps(dict(
            componentOnly=True,completeCommonObservation=False,actions=15,cleanupSucceeded=False,
            retainedQtContext=True,independentActorObserved=False,gpuPixelsObserved=False,host=metadata,
            parent=parent,hostElapsedSeconds=time.monotonic()-started),sort_keys=True))


class CreateFileClockTests(unittest.TestCase):
    def test_original_file_producer_samples_clock_around_actual_stage_io(self):
        import tempfile
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);root.chmod(0o700);observed=[]
        boundary=None
        def clock():
            observed.append(boundary.root.exists());return 20000+100*len(observed)
        boundary=NativeBoundary(root,clock_ms=clock)
        literal=b'{"actual-file-clock-source":true}'
        command=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-script-files',sourceRole=ROLE,
            operation='stage',runId=RUN,ticket=TICKET,ownerToken='d'*64,
            files={'entity-import.json':base64.b64encode(literal).decode()})
        boundary.send(command)
        self.assertEqual([False,True],observed)
        self.assertEqual((20100,20200),(boundary.sample['requestedEpochMs'],boundary.sample['capturedEpochMs']))
        self.assertEqual(literal,(boundary.root/'entity-import.json').read_bytes())


def load_tests(loader,tests,pattern):
    return unittest.TestSuite([CreateOperationVoxelPrefixTests(
        'test_same_original_cli_fifteen_actions_and_exact_original_voxel_edit'),
        loader.loadTestsFromTestCase(CreateFileClockTests)])


if __name__=='__main__':unittest.main()
