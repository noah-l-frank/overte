"""Actual Pico source factory; synthetic SDK/application/V8 boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from unittest.mock import patch

import test_normal_scripts as pico_seams
from self_tests.test_chat_script_source import CompiledBoundary,RUN
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock


class PicoChatScriptSourceTests(unittest.TestCase):
    def setUp(self):
        self.pico=pico_seams.PicoNormalScriptsTests();self.pico.setUp();self.addCleanup(self.pico.doCleanups)
        self.adapter,self.native=self.pico.instance,self.pico.native

    def source_routes(self):
        source=CompiledBoundary();write_original=self.native.write_debug_app_file;read_original=self.native.read_debug_app_file
        def write(target,package,path,raw):
            request=json.loads(raw);epoch=self.native.epoch_milliseconds(target)
            if request['action']=='feature-script-roots-observe':
                source.roots.epoch=epoch;source.roots.send(request);source.roots.value['processId']=123
            elif request['action']=='feature-script-observe':
                source.script.send(request);source.script.sample.update(processId=123,requestedEpochMs=epoch,capturedEpochMs=epoch)
            else:return write_original(target,package,path,raw)
        def read(target,package,path,**kwargs):
            if path.endswith('/feature-script-roots.json'):return source.roots.original()
            if path.endswith('/feature-script-observation.json'):return source.script.original()
            return read_original(target,package,path,**kwargs)
        for boundary in (patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch.object(self.native,'read_debug_app_file',side_effect=read)):
            boundary.start();self.addCleanup(boundary.stop)
        return source

    def test_actual_factory_captures_independent_native_root_code_root_sources_with_exact_parent_lock(self):
        source=self.source_routes();state,_=self.adapter._script_paths(self.native.target)
        lock=ScriptSourceLock(state.with_name('script-sources.lock'))
        primary=self.adapter._chat_script_source(self.native.target,RUN,role='primary',source_lock=lock)
        actor=self.adapter._chat_script_source(self.native.target,RUN,role='actor',source_lock=lock)
        witness=self.adapter._chat_script_source(self.native.target,RUN,role='actor',source_lock=lock,witness=True)
        self.assertIs(lock,primary.lock);self.assertIs(lock,actor.lock);self.assertIs(lock,witness.lock)
        self.assertEqual(3,len({item.store.path for item in (primary,actor,witness)}))
        before=self.native.epoch_milliseconds(self.native.target)
        first=primary.capture('1'*32,before);second=actor.capture('2'*32,before)
        self.assertEqual(first,second);self.assertIsNot(primary.roots,actor.roots);self.assertIsNot(primary.scripts,actor.scripts)
        self.assertEqual([],self.native.inputs);self.assertEqual([],self.native.controllers)
        self.assertEqual(4,len(source.roots.commands));self.assertEqual(2,len(source.script.commands))

    def test_changed_actual_candidate_and_rootless_source_chunks_cannot_qualify_cleanup(self):
        state,_=self.adapter._script_paths(self.native.target);lock=ScriptSourceLock(state.with_name('script-sources.lock'))
        original_digest=self.native.digest;self.native.digest='f'*64
        with self.assertRaises(ValueError):self.adapter._chat_script_source(self.native.target,RUN,role='primary',source_lock=lock)
        self.native.digest=original_digest
        store=self.adapter._chat_script_source_store(self.native.target,'actor',witness=True)
        child=PrivateFeatureState(store.path.with_name(store.path.name+'.frame-000.json'))
        original={'original':'unresolved-native-root-and-v8-compilation'};child.write(original,None)
        node=child.path.lstat();self.assertTrue(self.adapter._chat_chunk_store_retained(store))
        with self.assertRaises(ValueError):self.pico.cleanup_instance().cleanup(self.native.target)
        self.assertFalse(self.native.running);self.assertEqual(original,child.read());self.assertIsNone(store.read())
        self.assertEqual((node.st_dev,node.st_ino),(child.path.lstat().st_dev,child.path.lstat().st_ino))


if __name__=='__main__':unittest.main()
