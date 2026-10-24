"""Canonical Pico Source3 factory over explicit native/Qt model boundaries.

The original binding, path admission, source lock and file transports execute.
This stops before normal Create input; no device or whole-journey claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_normal_scripts as normal_fixture
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_observation import PicoLifecycleObservation
from adapters.pico4 import lifecycle_source as ui,lifecycle_gesture as gesture,lifecycle_drive as drive
from adapters.pending_commit_owner import FILE as PENDING_FILE
from self_tests import test_pico_lifecycle_editor as editor_fixture
from self_tests import test_pico_lifecycle_observation_baseline as baseline_fixture


class LifecycleReadOnlyFactoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=normal_fixture.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.transport=self.fixture.instance,self.fixture.native
        original=self.fixture.fixture.fixture.fixture.temporary
        original._finalizer.detach();original.cleanup=lambda:None
        print('Canonical Source3 originals retained: '+original.name,flush=True)

    def at_original_begin(self,probe):
        root=self.adapter._lifecycle_world_store(self.transport.target).path.parent
        directories=SimpleNamespace(TemporaryDirectory=lambda **_kwargs:SimpleNamespace(name=str(root),cleanup=lambda:None))
        case=baseline_fixture.LifecycleObservationBaselineTests();self.addCleanup(case.doCleanups)
        reached=[];completed=[];self.commands=[]
        read,write=self.adapter.adb.read_debug_app_file,self.adapter.adb.write_debug_app_file
        def construct(_cls,restore,editor,reader,_path):
            world=restore.world;native=case.editor.native
            self.assertEqual(root,world.store.path.parent)
            def send(request):
                self.commands.append(deepcopy(request))
                sources={gesture.ACTION:native.axes.send,drive.ACTION:native.drive.send,
                    'feature-pending-commit-owner':case.boundary.send}
                self.assertIn(request['action'],sources);sources[request['action']](request)
            def app_write(target,package,path,raw):
                if path!=ui.COMMAND:return write(target,package,path,raw)
                self.assertEqual((self.transport.target,'org.overte.pico'),(target,package))
                request=json.loads(raw);self.commands.append(deepcopy(request));native.ui.send(request)
            def app_read(target,package,path,**kwargs):
                sources={ui.FILE:native.ui.read,gesture.FILE:native.axes.read,drive.FILE:native.drive.read,
                    PENDING_FILE:reader.original}
                name=path.removeprefix('files/overte-e2e/')
                if path!='files/overte-e2e/'+name or name not in sources:return read(target,package,path,**kwargs)
                self.assertEqual((self.transport.target,'org.overte.pico'),(target,package));return sources[name]()
            self.adapter.adb.write_debug_app_file=app_write;self.adapter.adb.read_debug_app_file=app_read
            self.adapter._native_feature_observer=lambda _target:SimpleNamespace(pid=world.pid,guard=lambda:world.guard(),
                send=send,clock_ms=native.epoch,monotonic=lambda:native.clock,sleep=native.sleep)
            self.adapter.require_pico_session_identity=lambda _target:world.identity
            before=deepcopy(world.disk);queries=len(self.commands)
            self.owner=self.adapter._lifecycle_observation_readonly_begin(self.transport.target,world.run,restore=restore,editor=editor)
            self.assertEqual(before,world.disk);self.assertEqual(queries,len(self.commands))
            self.assertEqual(root/'lifecycle-primary-observation.json',self.owner.store.path)
            self.assertIs(self.owner.lock,world.lock);self.assertEqual(3,self.owner.version)
            self.assertIsNone(self.owner.reader.intent);self.assertIsNone(self.owner.reader._before_send)
            for actual,original in zip(self.owner.acquisition.readers,(world.source,world.axes,world.avatar)):
                self.assertIsNot(actual,original);self.assertIs(actual.source_lock,world.lock)
            case.reader=self.owner.reader
            return self.owner
        def baseline():
            reached.append(True);probe(case,self.owner);completed.append(True)
            raise NativeUIError('Explicit stop after actual canonical Source3 factory probe')
        case.collect_baseline=baseline
        with patch.object(editor_fixture,'tempfile',directories),patch.object(PicoLifecycleObservation,'before_inputs',classmethod(construct)):
            with self.assertRaises(NativeUIError):case.setUp()
        self.assertEqual([True],reached);self.assertEqual([True],completed)
        self.assertEqual([],case.editor.transport.envelopes)
        self.assertEqual([],self.transport.inputs);self.assertEqual([],self.transport.controllers)
        return case

    def test_actual_canonical_factory_acquires_fresh_readonly_triple_without_mutating_world(self):
        def probe(case,owner):
            before=deepcopy(owner.world.disk);previous=deepcopy([r.previous for r in (owner.world.source,owner.world.axes,owner.world.avatar)])
            result=owner.read(after_sequence=0)
            self.assertEqual(1,result['sequence']);self.assertEqual([],result['resources'])
            self.assertEqual('none',result['state']['editor']);self.assertEqual(before,owner.world.disk)
            self.assertEqual(previous,[r.previous for r in (owner.world.source,owner.world.axes,owner.world.avatar)])
            self.assertEqual(1,len(owner.disk['records']));self.assertEqual(2,len(owner.world.state['frames']))
            self.assertEqual([gesture.ACTION,drive.ACTION,'observe','feature-pending-commit-owner'],[row['action'] for row in self.commands])
            with owner.lock.held():owner.world.load()
        self.at_original_begin(probe)

    def test_foreign_process_is_refused_before_any_factory_source_query(self):
        def probe(_case,owner):
            self.adapter.require_pico_session_identity=lambda _target:'124:foreign-process'
            with self.assertRaises(ValueError):
                self.adapter._lifecycle_observation_readonly_begin(self.transport.target,owner.run,restore=owner.restore,editor=owner.editor)
            self.assertEqual([],self.commands);self.assertIsNone(owner.store.read())
        self.at_original_begin(probe)


if __name__=='__main__':unittest.main()
