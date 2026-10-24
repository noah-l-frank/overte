"""Existing owner chain acquires its primary baseline before normal input.

No new journey: the original Restore fixture builds the same Create/X/Chat/
background/Pending owners. Native Qt/process/physics remain its explicit seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_bundles
from adapters.pending_commit_owner import NativePendingCommitOwner
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_observation import PicoLifecycleObservation
from adapters.pico4.lifecycle_restore import PicoLifecycleRestore
from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_pending import PicoLifecyclePending
from adapters.pico4.lifecycle_close import PicoLifecycleClose
from self_tests import test_pico_lifecycle_restore as original
from self_tests import test_pico_lifecycle_editor as editor_fixture
from self_tests import test_pico_lifecycle_pending as pending_fixture
from self_tests import test_pico_lifecycle_background_owner as background_fixture
from self_tests.test_pending_commit_owner import Boundary


class LifecycleObservationBaselineTests(unittest.TestCase):
    def setUp(self):
        self.observer=None;self.editor=None;self.baseline=[];self.boundary=Boundary()
        self.fixture=original.LifecycleRestoreJoinTests()
        temporary=tempfile.TemporaryDirectory
        def retain(*args,**kwargs):
            result=temporary(*args,**kwargs)
            if kwargs.get('prefix')=='lifecycle-editor-' and Path(result.name).parent==Path(tempfile.gettempdir()):
                result._finalizer.detach();result.cleanup=lambda:None
            return result
        joined=editor_fixture.LifecycleEditorTests.joined
        def remember(editor):self.editor=editor;return joined(editor)
        begin=PicoLifecycleRestore.begin
        def before_first_input(restore):
            result=begin(restore);world=restore.world;native=self.editor.native
            self.native_producer=restore.native.original.__self__
            self.boundary.epoch=native.epoch
            def raw():
                value=json.loads(self.boundary.original())
                if not any(row['kind']=='scripts' and row['current'] for row in native.ui.rows):value['current']=dict(status='none')
                return json.dumps(value)
            self.reader=NativePendingCommitOwner(self.boundary.send,raw,native.epoch,lambda:native.alive and world.guard() is not False,
                world.pid,monotonic=world.monotonic,sleep=world.sleep)
            self.observer=PicoLifecycleObservation.before_inputs(restore,self.editor.owner,self.reader,
                world.store.path.with_name('lifecycle-primary-observation.json'))
            self.before=len(world.state['frames'])
            self.collect_baseline()
            self.assertEqual([],self.editor.transport.envelopes)
            self.assertEqual(['observe']*3,[row['operation'] for row in self.boundary.commands])
            self.assertIsNone(self.reader.intent);self.assertIsNone(self.reader._before_send)
            self.assertEqual(self.before+3,len(world.state['frames']))
            return result
        def pending_boundary():
            if getattr(self,'handoff_fault',None)=='sequence':
                original_raw=self.boundary.original
                def backwards():
                    value=json.loads(original_raw());value['sequence']=1
                    return json.dumps(value)
                self.boundary.original=backwards
            return self.boundary
        patches=[patch.object(tempfile,'TemporaryDirectory',retain),
            patch.object(editor_fixture.LifecycleEditorTests,'joined',remember),
            patch.object(PicoLifecycleRestore,'begin',before_first_input),
            patch.object(pending_fixture,'PendingBoundary',pending_boundary),
            # One modeled process-wide Native producer, shared by its original
            # readers. Actual OS fixture transitions update its counters; no
            # requested lifecycle delta is injected into a returned sample.
            patch.object(background_fixture,'Feature',lambda:self.native_producer)]
        for owner,role in ((PicoLifecycleChatDraft,'chat'),(PicoLifecycleBackground,'background'),
                (PicoLifecyclePending,'pending'),(PicoLifecycleClose,'close')):
            prepare=owner.prepare
            def attached(actual,*args,_prepare=prepare,_role=role,**kwargs):
                if hasattr(self,'before_participant'):self.before_participant(_role,actual)
                with self.observer.lock.held():
                    self.observer.bound()
                    result=_prepare(actual,*args,**kwargs)
                    if _role=='pending' and getattr(self,'handoff_fault',None)=='sequence':
                        self.counter_owner=actual;self.counter_reached=True
                        try:self.observer.attach_pending(actual)
                        except NativeUIError:self.counter_refused=True
                        else:self.counter_refused=False
                        # Do not execute another owner/source query after this
                        # actual boundary, even if the expected refusal failed.
                        raise NativeUIError('Explicit test stop after actual Pending reader handoff')
                    getattr(self.observer,'attach_'+_role)(actual)
                    return result
            patches.append(patch.object(owner,'prepare',attached))
        for active in patches:active.start();self.addCleanup(active.stop)
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.world=self.fixture.world;self.root=self.fixture.root

    def collect_baseline(self):
        for sequence in range(3):
            self.baseline.append(self.observer.read(after_sequence=sequence))
            if sequence<2:self.editor.native.sleep(.25)

    def test_original_absence_before_create_then_full_live_participants_and_scripts_four(self):
        for sequence,value in enumerate(self.baseline,1):
            self.assertEqual(sequence,value['sequence']);self.assertEqual([],value['resources'])
            self.assertEqual(('none','',False,False,0,0,0,0),(value['state']['editor'],value['state']['text'],
                value['state']['keyboard'],value['state']['focused'],value['state']['generation'],
                value['state']['worldAttempts'],value['state']['staleAttempts'],value['state']['deferredInputs']))
        self.assertEqual({'close'},self.observer.missing)
        self.assertIs(self.fixture.fixture.owner.pending,self.observer.pending)
        self.assertIsNot(self.reader,self.observer.pending.pending)
        self.assertIsNone(self.reader.intent);self.assertIsNone(self.reader._before_send)
        before=len(self.world.state['frames']);sample=self.observer.read(after_sequence=3)
        self.assertEqual(before+1,len(self.world.state['frames']))
        self.assertEqual(('scripts',4,1,0),(sample['state']['editor'],sample['state']['generation'],
            sample['state']['staleAttempts'],sample['state']['deferredInputs']))
        self.assertEqual(dict(backgrounds=1,activations=2,launches=1),sample['lifecycle'])
        self.fixture.fixture.owner.prepare()
        self.assertEqual(set(),self.observer.missing)
        self.assertIs(self.fixture.fixture.owner,self.observer.close)
        row,_=source_bundles.original(self.observer.history,self.observer.disk['chunks'],self.observer.disk['bundles'],
            self.observer.disk['records'][0])
        self.assertEqual(['background','chat','close','pending'],row['absentRoles'])
        native_pending,_=source_bundles.original(self.observer.history,self.observer.disk['chunks'],self.observer.disk['bundles'],row['pendingBundle'])
        actual=json.loads(native_pending['pending']['raw'])
        self.assertEqual({},actual['commit']);self.assertEqual('none',actual['current']['status'])
        self.assertEqual(dict(pendingRuns=[],archivedEvents=0),actual['resources'])
        self.assertEqual(2,self.observer.disk['lifecyclePrimaryObservationVersion'])
        self.assertEqual({'chat','background','pending','close'},set(self.observer.disk['attached']))
        self.assertEqual([],self.observer.disk['absentRoles'])
        self.assertLessEqual(len(self.world.state['frames']),128)


class LifecycleObservationHandoffTests(unittest.TestCase):
    def test_actual_prepared_reader_cannot_regress_original_baseline_sequence(self):
        fixture=LifecycleObservationBaselineTests();fixture.handoff_fault='sequence'
        try:
            with self.assertRaises(NativeUIError):fixture.setUp()
            self.assertTrue(fixture.counter_reached)
            observer=fixture.observer;pending=fixture.counter_owner
            first=json.loads(observer.reader.last_raw);next_packet=json.loads(pending.pending.last_raw)
            self.assertEqual(first['instance'],next_packet['instance']);self.assertEqual(3,first['sequence'])
            self.assertEqual(1,next_packet['sequence']);self.assertGreaterEqual(next_packet['capturedEpochMs'],first['capturedEpochMs'])
            self.assertEqual(first,observer.reader.last);self.assertEqual(next_packet,pending.pending.last)
            # Both complete originals are real source responses retained by
            # their separate owners. Neither is retimed into another sample.
            self.assertTrue(fixture.counter_refused,'same-instance original sequence3→1 was accepted at actual attach')
            self.assertTrue(observer.failed);self.assertIsNone(observer.pending)
            self.assertEqual(['observe']*4,[row['operation'] for row in fixture.boundary.commands])
        finally:fixture.doCleanups()

    def test_readonly_query_cannot_regress_actual_mutating_owner_intent_floor(self):
        fixture=LifecycleObservationBaselineTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        observer=fixture.observer;owner=observer.pending
        original=json.loads(owner.pending.last_raw)
        self.assertEqual(5,original['lastIntentSequence']);self.assertEqual(0,observer.reader.last['lastIntentSequence'])
        source=observer.reader.original
        def backwards():
            value=json.loads(source());value['lastIntentSequence']=0
            return json.dumps(value)
        observer.reader.original=backwards
        calls=[];send=observer.native.send
        def native(request):calls.append(deepcopy(request));return send(request)
        observer.native.send=native
        with self.assertRaises(NativeUIError):observer.read(after_sequence=3)
        self.assertTrue(observer.failed);self.assertEqual([],calls)
        # The actually returned bad original remains durably readable. A
        # refused read is not turned into a current sample or retried.
        index=observer.disk['pending']['pendingBundle']
        row,_=source_bundles.original(observer.history,observer.disk['chunks'],observer.disk['bundles'],index)
        returned=json.loads(row['pending']['raw'])
        self.assertEqual(original['instance'],returned['instance']);self.assertGreater(returned['sequence'],original['sequence'])
        self.assertEqual(0,returned['lastIntentSequence']);self.assertEqual(5,original['lastIntentSequence'])


if __name__=='__main__':unittest.main()
