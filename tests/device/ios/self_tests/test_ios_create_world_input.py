"""Actual durable touch owner on synthetic native/SDK sources; no device input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI, NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import create_state, create_world_input
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters.normal_input import NativeInput
from ios.self_tests.test_ios_create_state import packet, add_model, add_editor, version2, RUN, ID, ROOT, EPOCH
from ios.self_tests.test_ios_create_files import BINDING
from self_tests.test_native_feature_observation import Boundary as ClockBoundary

TICKET = 'd'*32


class Boundary:
    def __init__(self):
        self.clock = 1.; self.sequence = 0; self.query = self.geometry_query = None
        self.state = packet(); entity = add_model(self.state); add_editor(self.state, selected=[ID]); version2(self.state)
        entity.update(type='PolyVox', model={}, name='e2e-'+RUN+'-voxel', voxels=dict(ready=True, bytes=12,
            sha256='e'*64, volume=[8, 8, 8], onCount=64))
        source = self.state['source']; source['tabletShown'] = False
        source['roots'][0].update(active=False, visible=False, voxelSettings=dict(createAppMode='voxel', voxelEditMode='cube',
            voxelEditDynamics='click', voxelPointerMode='laser', voxelSphereSize=.5, voxelRemove=True))
        source['view'].update(aspectRatio=1024/728, uiWidth=1024, uiHeight=728)
        self.calls = []; self.lost = False; self.on_rect = None; self.on_check = None; self.keyboard = False

    def tick(self): self.clock += .001; return EPOCH+round(self.clock*1000)
    def epoch(self): return EPOCH+round(self.clock*1000)
    def monotonic(self): return self.clock
    def sleep(self, value): self.clock += value
    def guard(self): return True
    def send(self, query): self.query = deepcopy(query)
    def original(self):
        self.sequence += 1; before = self.tick(); after = self.tick()
        value = deepcopy(self.state); value.update(requestId=self.query['commandId'], sequence=self.sequence,
            clockBefore=dict(epochMs=before, monotonicMs=before-EPOCH), clockAfter=dict(epochMs=after, monotonicMs=after-EPOCH))
        return json.dumps(value)
    def send_geometry(self, query): self.geometry_query = deepcopy(query)
    def geometry(self):
        return json.dumps(dict(schemaVersion=1, commandId=self.geometry_query['commandId'], observation=dict(schemaVersion=1,
            sampleSequence=1, sampleEpochMs=self.tick(), nativeUi=dict(valid=True, surfaceWidth=1024, surfaceHeight=768,
                safeInsetLeft=0, safeInsetTop=20, safeInsetRight=0, safeInsetBottom=20,
                keyboardVisible=self.keyboard, imeInsetBottom=0), window=dict(width=1024, height=728))))
    def ui(self):
        return dict(schemaVersion=1, instance=ROOT, frameSpace='qt-window-logical', processId=42,
            sampleEpochMs=self.tick(), elapsedMs=round(self.clock*1000), lastSequence=0, tabletShown=False, ready=True, controls=[])
    def call(self, method, path, body=None):
        self.calls.append((method, path, deepcopy(body)))
        if method == 'GET':
            if self.on_rect: self.on_rect()
            return dict(x=0, y=0, width=1024, height=768)
        if method == 'POST' and self.lost: raise NativeUIError('Lost UIKit transport result')
        return None


class WorldInputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name); path.chmod(0o700); self.store = PrivateFeatureState(path/('ios-create-world-input-'+TICKET+'.json'))
        self.lock = ScriptSourceLock(path/'script-feature-sources.lock'); self.boundary = Boundary(); b = self.boundary
        clock = ClockBoundary()
        def stamp(value): value.update(processId=42, requestedEpochMs=b.tick(), capturedEpochMs=b.epoch(), animation={}, animationFence={})
        clock.mutate = stamp
        self.native = NativeFeatureObservation(clock.send, clock.original, b.tick, b.guard, 42, ios=True,
            monotonic=b.monotonic, sleep=b.sleep)
        self.source = create_state.IOSCreateState(b.send, b.original, b.tick, b.guard, 42, monotonic=b.monotonic, sleep=b.sleep)
        self.geometry = OriginalGeometry(b.send_geometry, b.geometry, b.tick, b.guard, monotonic=b.monotonic, sleep=b.sleep)
        self.normal = object.__new__(NativeInput); self.normal.capture = b.ui
        def check():
            if b.on_check: b.on_check()
            return True
        self.ui = NativeUI(b, 'bound-session', check, monotonic=b.monotonic, sleep=b.sleep)

    def owner(self):
        return create_world_input.CreateWorldInput(self.store, BINDING, RUN, TICKET, self.lock, self.native, self.source,
            self.geometry, self.normal, self.ui, self.boundary.guard, epoch_ms=self.boundary.epoch, monotonic=self.boundary.monotonic)

    def test_touch_coordinates_follow_original_camera_and_safe_viewport_and_do_not_claim_voxel_effect(self):
        b = self.boundary
        with self.lock.held():
            owner = self.owner(); owner.tap(ID, ROOT, b.epoch())
            posts = [row for row in b.calls if row[0] == 'POST']; self.assertEqual(1, len(posts))
            move = posts[0][2]['actions'][0]['actions'][0]; self.assertEqual((512, 384), (move['x'], move['y']))
            self.assertEqual('released', owner.state['phase']); self.assertTrue(owner.state['releaseObserved'])
            self.assertEqual('e'*64, b.state['source']['entities'][0]['voxels']['sha256'])
            self.assertNotIn('voxelValue', owner.state)
            self.assertEqual(1, sum(row[0] == 'DELETE' for row in b.calls))
            self.assertEqual([512.,364.],owner.qt_position())
            changed=deepcopy(owner.state);changed['originals']['geometry']['observation']['window']['height']=700
            with self.assertRaises((NativeUIError,ValueError)):owner.qt_position(changed)

    def test_uncertain_post_is_never_replayed_after_reconstruction(self):
        b = self.boundary; b.lost = True
        with self.lock.held():
            with self.assertRaises(NativeUIError): self.owner().tap(ID, ROOT, b.epoch())
            recovered = self.owner(); self.assertEqual('issued', recovered.state['phase'])
            with self.assertRaises(NativeUIError): recovered.tap(ID, ROOT, b.epoch())
            recovered.recover_release(); self.assertEqual('issued', recovered.state['phase'])
        self.assertEqual(1, sum(row[0] == 'POST' for row in b.calls))

    def test_camera_or_entity_change_before_input_admission_refuses_the_old_point(self):
        b = self.boundary; b.on_rect = lambda: b.state['source']['view']['position'].__setitem__(0, .1)
        with self.lock.held(), self.assertRaises(NativeUIError): self.owner().tap(ID, ROOT, b.epoch())
        self.assertFalse(any(row[0] == 'POST' for row in b.calls))

    def test_visible_keyboard_stale_deadline_and_empty_volume_never_emit_touch(self):
        for fault in ('keyboard', 'deadline', 'empty'):
            self.setUp(); b = self.boundary
            if fault == 'keyboard': b.keyboard = True
            elif fault == 'empty': b.state['source']['entities'][0]['voxels']['onCount'] = 0
            else: b.on_check = lambda: setattr(b, 'clock', b.clock+2)
            with self.subTest(fault=fault), self.lock.held(), self.assertRaises(NativeUIError): self.owner().tap(ID, ROOT, b.epoch())
            self.assertFalse(any(row[0] == 'POST' for row in b.calls))


if __name__ == '__main__': unittest.main()
