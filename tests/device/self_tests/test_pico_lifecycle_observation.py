"""Fresh primary samples joined to the existing complete Lifecycle owner path.

Python owners, clocks, storage, sources and session are real. Qt, physics and
OS/process sources retain the existing explicit model seams; no device claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_bundles
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_observation import PicoLifecycleObservation
from self_tests import test_pico_lifecycle_restore as original


class LifecycleObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.LifecycleRestoreJoinTests()
        temporary=tempfile.TemporaryDirectory
        def retain(*args,**kwargs):
            result=temporary(*args,**kwargs)
            if kwargs.get('prefix')=='lifecycle-editor-' and Path(result.name).parent==Path(tempfile.gettempdir()):
                # Retain this test's own originals from their construction,
                # including any setup failure before addCleanup is reached.
                result._finalizer.detach();result.cleanup=lambda:None
            return result
        with patch.object(tempfile,'TemporaryDirectory',retain):self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.close=self.fixture.fixture.owner;self.pending=self.close.pending
        background_fixture=self.fixture.fixture.fixture.fixture
        self.chat=background_fixture.chat;self.editor=background_fixture.fixture.fixture.owner
        self.world,self.native,self.root=self.fixture.world,self.fixture.native,self.fixture.root
        self.owner=PicoLifecycleObservation(self.fixture.restore,self.editor,self.chat,self.pending,
            self.root/'lifecycle-primary-observation.json')

    def test_two_fresh_original_samples_continue_same_restore_and_process_path(self):
        before=len(self.world.state['frames']);normal=len(self.fixture.inputs)
        first=self.owner.read(after_sequence=0);self.native.sleep(.25)
        second=self.owner.read(after_sequence=1)
        self.assertEqual((1,2),(first['sequence'],second['sequence']))
        self.assertEqual(('scripts',4,1,0),(second['state']['editor'],second['state']['generation'],
            second['state']['staleAttempts'],second['state']['deferredInputs']))
        self.assertEqual(before+2,len(self.world.state['frames']));self.assertEqual(normal,len(self.fixture.inputs))
        self.assertEqual([],second['artifacts']);self.assertTrue(second['resources'])
        for position,record_index in enumerate(self.owner.disk['records']):
            row,_=source_bundles.original(self.owner.history,self.owner.disk['chunks'],self.owner.disk['bundles'],record_index)
            self.assertEqual(before+position,row['worldFrameIndex']);self.assertEqual(position+1,row['result']['sequence'])
            pending,_=source_bundles.original(self.owner.history,self.owner.disk['chunks'],self.owner.disk['bundles'],row['pendingBundle'])
            self.assertEqual('observe',pending['request']['operation'])
        # Continue exactly the existing Restore/Prepare/Restart positive, not a
        # second lifecycle implementation. Its new reads keep these two frames.
        self.fixture.test_original_begin_existing_editor_pending_close_prefix_location_restore_and_process_restart()
        self.assertEqual(127,len(self.world.state['frames']));self.assertEqual('process-retired',self.fixture.process.state['phase'])
        original_disk=deepcopy(self.owner.disk)
        with self.assertRaises(NativeUIError):self.owner.read(after_sequence=2)
        self.assertTrue(self.owner.failed);self.assertEqual(original_disk,self.owner.store.read())

    def test_actual_outer_lock_exit_latches_failure_after_successful_inner_reads(self):
        held=self.world.lock.held;depth=0;trigger=False
        @contextmanager
        def exit_failure():
            nonlocal depth,trigger
            outer=depth==0;depth+=1
            try:
                with held():yield
            finally:depth-=1
            if outer:
                trigger=True;raise NativeUIError('Explicit actual outer source-lock exit failure')
        with patch.object(self.world.lock,'held',exit_failure):
            with self.assertRaises(NativeUIError):self.owner.read(after_sequence=0)
        self.assertTrue(trigger);self.assertTrue(self.owner.failed)
        self.assertEqual(1,len(self.owner.store.read()['records']))
        before=len(self.world.state['frames'])
        with self.assertRaises(NativeUIError):self.owner.read(after_sequence=0)
        self.assertEqual(before,len(self.world.state['frames']))

    def test_landed_final_save_with_frozen_host_and_native_age_is_retained_not_delivered(self):
        save=self.owner.save;landed=False;clock=self.owner.native.clock_ms
        def late(value):
            nonlocal landed
            save(value)
            if value['pending'] is None and value['records']:
                landed=True;self.owner.native.clock_ms=lambda:clock()+2000
        self.owner.save=late
        with self.assertRaises(NativeUIError):self.owner.read(after_sequence=0)
        self.assertTrue(landed);self.assertTrue(self.owner.failed)
        self.assertEqual(1,len(self.owner.store.read()['records']))

    def test_cap_refuses_before_any_additional_source_read(self):
        with self.world.lock.held():
            while len(self.world.state['frames'])<128:self.world.current()
        calls=[]
        def forbidden(*_args,**_kwargs):
            calls.append('source-send');raise AssertionError('Source read after original World cap')
        self.world.source.send=self.world.axes.send=self.world.avatar.send=self.owner.reader.send=self.owner.native.send=forbidden
        self.world.source.capture=self.world.axes.capture=self.world.avatar.capture=self.owner.reader.read=self.owner.native.read=forbidden
        with self.assertRaises(NativeUIError):self.owner.read(after_sequence=0)
        self.assertEqual([],calls);self.assertEqual(128,len(self.world.state['frames']));self.assertIsNone(self.owner.store.read())


class LifecycleObservationResourceTests(unittest.TestCase):
    def test_host_journals_are_not_product_resources_at_the_common_baseline(self):
        owner=object.__new__(PicoLifecycleObservation)
        self.assertEqual([],owner.resources(dict(ui=dict(source=dict(editors=[]))),dict(resources=dict(pendingRuns=[]))))

    def test_actual_retained_qt_context_and_pending_run_remain_resources_without_a_current_editor(self):
        owner=object.__new__(PicoLifecycleObservation)
        packets=dict(ui=dict(source=dict(editors=[dict(id='a'*32,alive=False,current=False),dict(id='b'*32,alive=True,current=False)])))
        self.assertEqual(['panel:lifecycle-'+'b'*32,'input:lifecycle-'+'c'*32],
            owner.resources(packets,dict(resources=dict(pendingRuns=['c'*32]))))


if __name__=='__main__':unittest.main()
