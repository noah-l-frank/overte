"""Ordinary adapter lifecycle delivery with durable Tablet background intents.

Only the OS/native producers and their clocks are models. Real existing-only
SDK HTTP, adapter lifecycle methods, journals and native readers execute.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_background import TabletWebBackground
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,SELECTOR
from ios.self_tests.tablet_web_lifecycle_fixture import attach
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletBackgroundFlowTests(unittest.TestCase):
    def prepared(self):
        f=PairedTabletFixture(self);model=attach(f);b=f.boundary
        owner=TabletWebBackground(f.primary.runtime,SELECTOR,RUN,b.binding,monotonic=b.mono,sleep=b.sleep)
        call=dict(contractVersion=16,runId=RUN,ticket='c'*32,fixtureUrl=b.source.fixture,verb='background-resume',inputs={})
        return f,model,owner,call
    def test_real_native_adapter_background_resume_preserves_original_PID_and_native_counters(self):
        f,model,owner,call=self.prepared();b=f.boundary
        with f.primary.parts() as observer:
            owner.start(observer,call);self.assertEqual({'performed':True},owner.finish(observer))
            self.assertEqual('observed',owner.state['phase']);before=owner.original(owner.state['before']);after=owner.original(owner.state['after'])
            self.assertEqual(before['instance'],after['instance']);self.assertEqual(42,after['processId'])
            self.assertEqual(dict(backgrounds=1,activations=2,launches=1),after['lifecycle'])
            calls=list(model.calls)
            rebuilt=TabletWebBackground(f.primary.runtime,SELECTOR,RUN,b.binding,monotonic=b.mono,sleep=b.sleep)
            rebuilt.lock=observer.observer.source.lock;rebuilt.resume()
            self.assertEqual(1,sum(op=='mobile: backgroundApp' for op,_ in model.calls));self.assertEqual(1,sum(op=='mobile: activateApp' for op,_ in model.calls))
            self.assertTrue(len(model.calls)>len(calls))  # Fresh OS reads, never repeated input.
        self.assertEqual([],f.sdk.errors)
    def test_ack_without_background_effect_retains_issued_owner_without_any_activation_or_native_replay(self):
        f,model,owner,call=self.prepared();model.ignore_background=True
        with f.primary.parts() as observer:
            with self.assertRaises((NativeUIError,RuntimeError)):owner.start(observer,call)
            self.assertEqual('background-issued',owner.state['phase']);queries=len(f.boundary.commands)
            rebuilt=TabletWebBackground(f.primary.runtime,SELECTOR,RUN,f.boundary.binding,monotonic=f.boundary.mono,sleep=f.boundary.sleep)
            rebuilt.lock=observer.observer.source.lock
            with self.assertRaises(NativeUIError):rebuilt.start(observer,call)
            self.assertEqual(queries,len(f.boundary.commands));self.assertEqual(1,sum(op=='mobile: backgroundApp' for op,_ in model.calls))
            self.assertEqual(0,sum(op=='mobile: activateApp' for op,_ in model.calls));self.assertTrue(model.foreground)
    def test_lost_activation_return_reconstructs_actual_foreground_and_never_resends_activation(self):
        f,model,owner,call=self.prepared();model.lose_return='mobile: activateApp'
        with f.primary.parts() as observer:
            with self.assertRaises((NativeUIError,RuntimeError)):owner.start(observer,call)
            self.assertEqual('foreground-issued',owner.state['phase']);self.assertTrue(model.foreground)
            rebuilt=TabletWebBackground(f.primary.runtime,SELECTOR,RUN,f.boundary.binding,monotonic=f.boundary.mono,sleep=f.boundary.sleep)
            rebuilt.lock=observer.observer.source.lock;rebuilt.resume();rebuilt.finish(observer)
            self.assertEqual('observed',rebuilt.state['phase'])
            self.assertEqual(1,sum(op=='mobile: backgroundApp' for op,_ in model.calls));self.assertEqual(1,sum(op=='mobile: activateApp' for op,_ in model.calls))
            self.assertEqual(1,len(f.sdk.errors));self.assertIsInstance(f.sdk.errors[0],OSError)


if __name__=='__main__':unittest.main()
