"""Actual Scope constructors retain literal v1 and distinct v2 held semantics."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.self_tests.test_ios_web_closures import ClosureBoundary,RUN,URL
from ios.self_tests.test_ios_process_retirement import BINDING


class LegacyWorldScope(IOSWorldWebScope):
    """Literal legacy producer selected before its first private original."""
    def __init__(self,*args,**kwargs):
        self._scope_version=1;super().__init__(*args,**kwargs)


class WorldWebScopeVersionsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__();self.addCleanup(self.held.__exit__,None,None,None)
        self.runtime=object.__new__(IOSScriptRuntime);self.runtime.state_path=lambda _selector:self.root/'session.json'
        def native(bound=False):return NativeFeatureObservation(lambda _:None,lambda:'',lambda:20000,lambda:True,42,ios=True,native_clock_bound=bound)
        self.observer=SimpleNamespace(bound_native_observer=lambda _:native(True),emote_world=lambda _:SimpleNamespace(last=None),
            script_terminal=lambda _:SimpleNamespace(last=None),script_work=lambda _:SimpleNamespace(last=None),
            web_closures=lambda:SimpleNamespace(last=None),script_dialogs=lambda _:SimpleNamespace(last=None),script_fixture_files=lambda:None)
        self.runtime._sources=lambda _selector:dict(binding=deepcopy(BINDING),check=lambda:True,observer=self.observer,clock_source=native())
    def owner(self,cls=IOSWorldWebScope):return cls(self.runtime,'existing-only',self.root,RUN,'primary',URL,'b'*32,self.lock)
    def held_originals(self):
        source=ClosureBoundary();source.version=5;reader=source.reader();admitted=reader.read(RUN,URL)
        source.retired=1;source.resources['policy-grant']=dict(created=1,retired=1,pending=0)
        current=reader.read(RUN,URL);return source,reader,admitted,current
    def test_literal_one_actual_constructor_and_reconstruction_remain_strict_without_packet_relabel(self):
        legacy=self.owner(LegacyWorldScope);legacy.save();original=deepcopy(legacy.previous)
        self.assertEqual(1,original['iosWorldWebMarkerScopeVersion']);rebuilt=self.owner()
        self.assertEqual(1,rebuilt._scope_version);self.assertEqual(original,rebuilt.previous)
        native,reader,admitted,current=self.held_originals()
        with self.assertRaises(NativeUIError):rebuilt.quiet_web(dict(web=current),dict(web=admitted))
        for kind in native.resources:native.resources[kind]=dict(created=1,retired=1,pending=0)
        released=reader.read(RUN,URL);self.assertTrue(rebuilt.quiet_web(dict(web=released),dict(web=admitted)))
        archived=IOSWorldWebScope.archive(original,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock)
        self.assertEqual(1,archived._scope_version);self.assertEqual(original,archived.envelope(archived.state))
    def test_actual_new_constructor_and_reconstruction_keep_two_held_counters_and_no_complete_claim(self):
        owner=self.owner();owner.save();self.assertEqual(2,owner.previous['iosWorldWebMarkerScopeVersion'])
        rebuilt=self.owner();self.assertEqual(2,rebuilt._scope_version);_native,_reader,admitted,current=self.held_originals()
        before=deepcopy(current);result=rebuilt.quiet_web(dict(web=current),dict(web=admitted))
        self.assertEqual('held',result['mode']);self.assertEqual(current,before);self.assertEqual(current['contexts'],result['contexts'])
        self.assertEqual(1,result['contexts'][0]['resources']['native-bitmap']['pending'])
        self.assertEqual(1,result['contexts'][0]['resources']['scenegraph-node']['pending']);self.assertNotIn('complete',result)
        archived=IOSWorldWebScope.archive(rebuilt.previous,root=self.root,binding=BINDING,run=RUN,role='primary',lock=self.lock)
        self.assertEqual(2,archived._scope_version);self.assertEqual('held',archived.quiet_web(dict(web=current),dict(web=admitted))['mode'])


if __name__=='__main__':unittest.main()
