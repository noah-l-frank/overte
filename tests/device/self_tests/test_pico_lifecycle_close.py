"""Existing whole prefix, original X closure and second World owner action.

Python owner/session/storage run; Qt/OpenXR/widget/physics remain explicit seams.
Every current source query is still stored in the original capped World journal.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest
import zlib
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_close import PicoLifecycleClose,run_close
from adapters.pico4.lifecycle_pending import run_pending
from adapters.pico4.lifecycle_world import MAX_FRAMES
from adapters.script_journey.history import unpack,canonical,MAX_PACKED
from self_tests import test_pico_lifecycle_pending as pending_fixture
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class LifecycleCloseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=pending_fixture.LifecyclePendingTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        run_pending(self.fixture.owner)
        self.pending,self.world,self.native,self.root,self.lock=self.fixture.owner,self.fixture.world,self.fixture.native,self.fixture.root,self.fixture.lock
        self.path=self.root/'lifecycle-close-owner.json';self.inputs=[];self.ignore=False;self.lost=False
        transport=self.world.session.transport;world_stage=type(transport).stage.__get__(transport,type(transport))
        original_status=transport.read_status
        def stage(envelope,profile,*,before_publish=None):
            if envelope['commands'][0]['operation']!='controller.button':return world_stage(envelope,profile)
            disk=unpack(json.loads(self.path.read_text())['payload'])[0]
            self.assertEqual(envelope,disk['inputs'][-1]['envelope']);self.inputs.append(deepcopy(envelope))
            result=FakeTransport.stage(transport,envelope,profile,before_publish=before_publish)
            if not self.ignore:
                if self.native.ui.home:self.native.ui.shown=False
                else:
                    current=next(row for row in self.native.ui.rows if row['current'])
                    current.update(fieldAlive=False,pageAlive=False,current=False,attached=False,visible=False,focused=False,text='')
                    self.native.ui.home=True;self.native.ui.raised=False
            return result
        def status(**kwargs):
            if self.lost and kwargs.get('expected_sequence') is not None:raise NativeUIError('Explicit lost original close-X acknowledgment')
            return original_status(**kwargs)
        transport.stage=stage;transport.read_status=status
        self.owner=self.make()

    def make(self):return PicoLifecycleClose(self.pending,self.path)

    def test_same_original_prefix_normal_close_then_second_world_motion_and_neutral_quiet(self):
        before=len(self.world.state['frames']);result=run_close(self.owner)
        self.assertEqual(('none','',0,False,False,0,1,1),(result['editor'],result['text'],result['generation'],result['focused'],
            result['keyboard'],result['deferredInputs'],result['worldAttempts'],result['staleAttempts']))
        self.assertEqual(2,len(self.inputs));self.assertFalse(result['completeLifecycle'])
        self.assertEqual(before+len(self.owner.state['frames']),len(self.world.state['frames']))
        for row in self.owner.state['frames']:
            self.assertEqual(canonical(row['original']['world']),canonical(self.world.state['frames'][row['worldFrameIndex']]))
        moved=self.world.world_input();self.assertEqual((2,['forward'],.5),(moved['worldAttempts'],moved['heldInputs'],moved['worldDisplacement']))
        released=self.world.release();self.assertEqual(2,released['worldAttempts']);self.assertEqual([],released['heldInputs'])
        self.assertEqual(.5,released['worldDisplacement']);self.assertLessEqual(len(self.world.state['frames']),MAX_FRAMES)
        self.assertTrue(self.pending.store.path.exists());self.assertTrue(self.owner.store.path.exists())

    def test_lost_original_page_x_reconciles_then_hides_without_repressing_it(self):
        self.owner.prepare();self.lost=True
        with self.assertRaises(NativeUIError):self.owner.press()
        self.lost=False;self.owner=self.make();result=run_close(self.owner)
        self.assertEqual(0,result['generation']);self.assertEqual(2,len(self.inputs));self.assertEqual('closed',self.owner.state['phase'])

    def test_ignored_second_x_cannot_become_closed_or_be_replayed(self):
        self.owner.prepare();self.owner.press();self.ignore=True
        with self.assertRaises(NativeUIError):self.owner.press()
        with self.assertRaises(NativeUIError):run_close(self.make())
        self.assertEqual(2,len(self.inputs));self.assertTrue(self.native.ui.shown)

    def test_original_world_frame_cap_cannot_be_reset_by_the_close_container(self):
        self.owner.prepare()
        # Keep the real failed append before ScriptSourceLock deliberately
        # replaces its inner exception. This is evidence only, never a second
        # source journal or an observation that the owner may adopt/replay.
        original_save=self.world.save
        def save(state):
            try:return original_save(state)
            except Exception as error:
                raw=canonical([state]);encoded=base64.b64encode(zlib.compress(raw,level=9))
                evidence=dict(
                    diagnosticVersion=1,exceptionType=type(error).__name__,exceptionMessage=str(error),
                    savedFrameCount=len(self.world.state['frames']),attemptedFrameCount=len(state['frames']),
                    originalOwnerSha256=hashlib.sha256(self.world.store.path.read_bytes()).hexdigest(),
                    attemptedStateBytes=len(raw),attemptedStateSha256=hashlib.sha256(raw).hexdigest(),
                    attemptedPackedBytes=len(encoded),packedLimit=MAX_PACKED,
                    actualUnsavedFrame=deepcopy(state['frames'][-1]))
                try:PrivateFeatureState(self.root/'close-world-failed-append.json').write(evidence,None)
                except Exception as diagnostic_error:
                    error.add_note('Failed append evidence could not be saved: '+type(diagnostic_error).__name__)
                raise
        self.world.save=save
        with self.lock.held():
            while len(self.world.state['frames'])<MAX_FRAMES:self.world.current()
        before=[len(item.commands) for item in (self.native.ui,self.native.axes,self.native.drive)]
        with self.assertRaises(NativeUIError):self.owner.press()
        self.assertEqual(MAX_FRAMES,len(self.world.state['frames']));self.assertEqual([],self.inputs)
        self.assertEqual(before,[len(item.commands) for item in (self.native.ui,self.native.axes,self.native.drive)])

    def test_changed_original_pending_archive_blocks_any_normal_close_input(self):
        self.owner.prepare();value=self.pending.store.read();changed=deepcopy(value);changed['binding']['generation']=False
        self.pending.store.write(changed,value)
        with self.assertRaises(NativeUIError):self.owner.press()
        self.assertEqual([],self.inputs)


if __name__=='__main__':unittest.main()
