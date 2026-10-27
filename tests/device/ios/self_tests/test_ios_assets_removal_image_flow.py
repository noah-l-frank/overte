"""Normal Marker/Model/Delete, two original PNGs and pure owned replay.

QML and marker JavaScript execute; native/Qt/controller/parser/backend/GPU
producers remain explicit host models, not an iOS product qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters import assets_removal_images
from ios.self_tests.assets_image_removal_fixture import Fixture,RemovalImageSources
from ios.self_tests.assets_reply_fixture import TICKET


def census(root):
    return {p.name:(p.stat().st_dev,p.stat().st_ino,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
        for p in root.iterdir() if p.is_file()}


class AssetsRemovalImageFlowTests(unittest.TestCase):
    def test_normal_owned_delete_joins_two_actual_original_images_before_marker_cleanup(self):
        root=Path(tempfile.mkdtemp(prefix='assets-removal-image-flow-'));root.chmod(0o700)
        print('owned original root',root,flush=True)
        f=Fixture(self,root)
        self.assertEqual([],f.scope.frames[f.scope.state['baseline']-1]['create']['source']['entities'])
        f.image_sources=RemovalImageSources(f)
        before,sources=f.sample('ios-'+uuid.uuid4().hex);policy=sources.regions()
        before.capture(TICKET,round(before.epoch_ms()));before.qualify(policy)
        f.attach_removal();owner=OwnedAssetsModelRemoval(f.parsed,PrivateFeatureState(f.f.path('model-removal')),lock=f.f.lock)
        owner.reserve();proof=owner.remove();owner.close_context()
        self.assertFalse(f.domain.current()['source']['tabletShown'])
        after,again=f.sample('ios-'+uuid.uuid4().hex);self.assertIs(sources,again)
        after.capture(TICKET,round(after.epoch_ms()))
        self.assertEqual('captured',after.state['phase'])
        commands=deepcopy(f.f.boundary.native_clock.commands);inputs=deepcopy(f.f.boundary.inputs);requests=deepcopy(f.f.requests);files=census(root)
        with (patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure image join write')),
              patch('subprocess.Popen',side_effect=AssertionError('pure image join process')),
              patch('socket.socket',side_effect=AssertionError('pure image join socket'))):
            observed=assets_removal_images.compose(owner,before,after,policy)
            self.assertEqual(proof,observed['removal']);self.assertFalse(observed['resourceRetirementAvailable'])
            self.assertGreaterEqual(observed['subjectChangedFraction'],.05)
            self.assertEqual([],observed['after']['renderItemIds'])
            self.assertTrue(any(row['objectAlive'] and row['hfmAlive'] for row in observed['removal']['resources']))
            self.assertEqual(files,census(root))
            with patch.object(after.frame_owner.store,'read',return_value=None),self.assertRaises(NativeUIError):
                assets_removal_images.compose(owner,before,after,policy)
            # The actual parent journal remains authoritative; changing only
            # memory cannot fabricate completed context closure or a Delete.
            saved=owner.state['contextClosedBy'];owner.state['contextClosedBy']=None
            try:
                with self.assertRaises(NativeUIError):assets_removal_images.compose(owner,before,after,policy)
            finally:owner.state['contextClosedBy']=saved
        self.assertEqual(commands,f.f.boundary.native_clock.commands);self.assertEqual(inputs,f.f.boundary.inputs);self.assertEqual(requests,f.f.requests)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
        f.marker.cleanup();self.assertEqual('released',f.marker.state['phase'])
        self.assertEqual([],f.domain.current()['source']['entities'])
        self.assertEqual(3,f.scope._version)
