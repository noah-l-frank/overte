"""Held-scope sample2 uses actual private PNG owners; marker admission modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_held_samples import IOSAvatarHeldSamples,history
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.self_tests import test_ios_avatar_samples as fixture


class AvatarHeldSamplesTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarSamplesTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        scope=object.__new__(IOSAvatarHeldMarkerScope);scope.__dict__.update(self.f.scope.__dict__);self.f.scope=scope
        seam=patch.object(IOSAvatarHeldMarkerScope,'archive',return_value=scope);seam.start();self.addCleanup(seam.stop)
    def owner(self):
        return IOSAvatarHeldSamples(self.f.runtime,'owned',self.f.scope,self.f.root,self.f.policy,self.f.phase,self.f.lock,
            monotonic=lambda:self.f.gpu.clock,epoch_ms=lambda:fixture.HOST+self.f.gpu.clock*1000,sleep=self.f.gpu.sleep)
    def history(self,value):
        return history(value,store=self.owner().store,root=self.f.root,binding=fixture.BINDING,run=fixture.RUN,role='primary',
            policy=self.f.policy,lock=self.f.lock)
    def test_new_sample2_preserves_original_png_gpu_and_never_reinterprets_v1(self):
        owner=self.owner();row=owner.capture(fixture.TICKET);frame,raw,measurement=owner.archive(row)
        self.assertEqual(self.f.raw,raw);self.assertTrue(measurement['modelLoaded'])
        self.assertEqual(2,owner.previous['iosAvatarSamplesVersion']);self.assertEqual(2,owner.read_record(row)['iosAvatarSampleVersion'])
        old=deepcopy(owner.previous);before=(owner.store.path.stat().st_ino,owner.store.path.read_bytes())
        self.assertEqual(raw,self.history(old).archive(row)[1]);self.assertEqual(before,(owner.store.path.stat().st_ino,owner.store.path.read_bytes()))
        with self.assertRaises(NativeUIError):IOSAvatarSamples.history(old,store=owner.store,root=self.f.root,binding=fixture.BINDING,
            run=fixture.RUN,role='primary',policy=self.f.policy,lock=self.f.lock)
        owner.drain();self.assertTrue(self.f.gpu.retired)
    def test_scope1_cannot_be_admitted_by_live_sample2(self):
        scope=object.__new__(IOSAvatarMarkerScope);scope.__dict__.update(self.f.scope.__dict__);self.f.scope=scope
        with self.assertRaises(NativeUIError):self.owner()
    def test_lost_current_world_original_never_recaptures_gpu_on_drain(self):
        owner=self.owner();self.f.fail_world_after=True
        with self.assertRaises(OSError):owner.capture(fixture.TICKET)
        reads=self.f.draw;self.f.fail_world_after=False;self.owner().drain()
        self.assertEqual(reads,self.f.draw);self.assertTrue(self.f.gpu.retired)


if __name__=='__main__':unittest.main()
