"""Actual cleanup Home, native source files and ordinary UIKit close ownership.

These tests qualify the close packet only. Scene pixel/weak/paired retirement
still requires the separate composed source decoder; a UIKit ACK proves none.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_operation_clock
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_controls import IOSAvatarIO
from ios.adapters.avatar_scene import IOSAvatarScene
from ios.self_tests import test_ios_avatar_cleanup_controls as fixture


class AvatarSceneCloseTests(unittest.TestCase):
    def setUp(self):
        self.case=fixture.AvatarCleanupControlsTests();self.case.setup_case();self.addCleanup(self.case.doCleanups)
        self.case.open_page();self.case.close(self.case.owner());self.f=self.case.f
        self.clock=avatar_operation_clock.begin(self.f.fixture.now(),self.f.fixture.clock)
        self.owner=self.scene(self.f.source)

    def scene(self,source):
        f=self.f;scope=object.__new__(IOSAvatarMarkerScope);scope.lock=f.lock;scope.binding=source.binding
        scope.bound=source.bound;samples=object.__new__(IOSAvatarSamples);samples.lock=f.lock
        samples.store=SimpleNamespace(path=f.path/'ios-avatar-primary-samples.json')
        fixture_source=source
        class Runtime(IOSAvatarRuntime):
            def state_path(_self,_selector):return f.path/'session.json'
            def _sources(_self,_selector):return dict(binding=fixture_source.binding,client=f.sdk,session='owned-session',check=lambda:True)
        runtime=Runtime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:True))
        baseline=dict(index=1,sha256=digest(source.frames[0]))
        return IOSAvatarScene(runtime,'target',source,scope,samples,baseline,self.clock,epoch_ms=f.fixture.now,
            monotonic=lambda:f.fixture.clock,sleep=f.fixture.sleep)

    def fresh_sources(self):
        self.f.readers=self.f.fixture.readers();self.f.readers['ui']=IOSAvatarIO(self.f.native);return self.f.make_sources()

    def test_normal_home_precedes_actual_uikit_close_and_original_source_still_decides_closed(self):
        before=len(self.f.sdk.inputs);self.owner.close_tablet()
        self.assertEqual(['OverteTabletClose'],self.f.sdk.inputs[before:]);self.assertFalse(self.f.fixture.widget.shown)
        self.assertEqual('observed',self.owner.state['close']['phase'])
        self.assertFalse(self.owner.source(self.owner.state['close']['after'])['ui']['open'])
        self.owner.close_tablet();self.assertEqual(before+1,len(self.f.sdk.inputs))

    def test_lost_uikit_return_stays_owned_even_when_a_later_source_is_already_empty(self):
        call=self.f.sdk.call
        def lost(method,path,body=None):
            result=call(method,path,body)
            if path.endswith('/click'):raise OSError('Lost actual UIKit close return')
            return result
        with patch.object(self.f.sdk,'call',side_effect=lost),self.assertRaises(NativeUIError):self.owner.close_tablet()
        self.assertFalse(self.f.fixture.widget.shown);before=deepcopy(self.f.sdk.inputs);rebuilt=self.scene(self.fresh_sources())
        with self.assertRaises(NativeUIError):rebuilt.close_tablet()
        self.assertEqual(before,self.f.sdk.inputs);self.assertEqual('issued',rebuilt.state['close']['phase'])

    def test_lost_source_return_after_saved_uikit_delivery_uses_passive_read_without_second_close(self):
        source=self.owner.sources;read=source.read;sent=[]
        def lost():
            frame=read()
            if self.owner.state['close'] is not None and self.owner.state['close']['phase']=='delivered' and not sent:
                sent.append(True);raise OSError('Lost original source return after normal UIKit delivery')
            return frame
        with patch.object(source,'read',side_effect=lost),self.assertRaises(OSError):self.owner.close_tablet()
        before=deepcopy(self.f.sdk.inputs);rebuilt=self.scene(self.fresh_sources());rebuilt.close_tablet()
        self.assertEqual(before,self.f.sdk.inputs);self.assertEqual('observed',rebuilt.state['close']['phase'])

    def test_slow_durable_uikit_intent_cannot_send_after_the_original_whole_deadline(self):
        store=self.owner.store;write=store.write
        def slow(value,previous):
            write(value,previous)
            if self.owner.state['close'] is not None and self.owner.state['close']['phase']=='issued':self.f.fixture.clock+=26
        before=deepcopy(self.f.sdk.inputs)
        with patch.object(store,'write',side_effect=slow),self.assertRaises(NativeUIError):self.owner.close_tablet()
        self.assertEqual(before,self.f.sdk.inputs)


if __name__=='__main__':unittest.main()
