"""Untouched static original acquisitions, no ordinary input or device access."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests.navigation_baseline_image_fixture import Baseline


class NavigationBaselineImageTests(unittest.TestCase):
    def setUp(self):self.f=Baseline(self);self.h=self.f.h

    def held(self):return self.h.flow.held()

    def test_both_untouched_roles_keep_actual_static_originals_and_independent_original_pngs(self):
        with self.held():
            first=self.f.owner();result,proof,raw=first.acquire(self.h.now())
            self.assertFalse(proof['originals']['navigation']['source']['challengeMarker']['present'])
            self.assertEqual(b'\x89PNG\r\n\x1a\n',raw[:8]);self.assertEqual([],self.h.flow_fixture.b.inputs)
            other=self.f.owner(role='actor',request='ios-'+uuid.uuid4().hex)
            measured,peer,_=other.acquire(self.h.now())
            self.assertNotEqual(result['rendered']['frameId'],measured['rendered']['frameId'])
            self.assertNotEqual(proof['originals']['navigation']['requestId'],peer['originals']['navigation']['requestId'])
            self.assertEqual(2,self.h.gpu.frames)
            commands=deepcopy(self.h.gpu.commands);self.h.sdk.okay=False
            self.assertEqual((result,proof,raw),self.f.owner(historical=True).archive())
            self.assertEqual(commands,self.h.gpu.commands)

    def test_blank_actual_png_keeps_its_owned_original_and_cannot_be_replaced_by_a_later_read(self):
        self.f.black=True
        with self.held():
            owner=self.f.owner()
            with self.assertRaises(NativeUIError):owner.acquire(self.h.now())
            stored=deepcopy(owner.store.read());commands=deepcopy(self.h.gpu.commands)
            self.assertEqual('reading',unpack(stored['payload'])[0]['phase'])
            self.f.black=False
            with self.assertRaises(NativeUIError):self.f.owner().acquire(self.h.now())
            with self.assertRaises(NativeUIError):self.f.owner().recover()
            self.assertEqual(stored,owner.store.read());self.assertEqual(commands,self.h.gpu.commands)
            self.assertEqual([],self.h.flow_fixture.b.inputs)

    def test_lost_final_result_recovers_immutable_originals_without_refreshing_freshness_or_sdk_calls(self):
        with self.held():
            owner=self.f.owner();write=owner.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['phase']=='observed':raise OSError('Synthetic final journal loss')
                return write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.acquire(self.h.now())
            commands=deepcopy(self.h.gpu.commands);self.h.sdk.gpu.clock+=2
            rebuilt=self.f.owner();rebuilt.recover();rebuilt.archive()
            with self.assertRaises(NativeUIError):rebuilt.fresh()
            self.assertEqual(commands,self.h.gpu.commands)

    def test_lost_middle_source_retains_pending_query_and_does_not_read_or_capture_again(self):
        with self.held():
            source=self.f.sources['model'];original=source.read
            source.read=lambda _run:(_ for _ in ()).throw(OSError('Synthetic middle source loss'))
            owner=self.f.owner()
            with self.assertRaises(OSError):owner.acquire(self.h.now())
            state=unpack(owner.store.read()['payload'])[0]
            self.assertIn('model',state['issued']);self.assertNotIn('model',[ref['kind'] for ref in state['records']])
            commands=deepcopy(self.h.gpu.commands);source.read=original
            with self.assertRaises(NativeUIError):self.f.owner().recover()
            self.assertEqual(commands,self.h.gpu.commands);self.assertEqual([],self.h.flow_fixture.b.inputs)

    def test_a_later_run_scene_cannot_be_reported_as_an_untouched_baseline_even_with_static_looking_pixels(self):
        self.h.flow.prepare()
        with self.held():
            owner=self.f.owner()
            with self.assertRaises(NativeUIError):owner.acquire(self.h.now())
            self.assertTrue(self.h.sdk.navigation.source['challengeMarker']['present'])
            self.assertEqual('reading',unpack(owner.store.read()['payload'])[0]['phase'])
            self.assertNotIn('restored',owner.state)

    def test_changed_original_component_or_candidate_cannot_replay_a_baseline_archive(self):
        with self.held():
            owner=self.f.owner();owner.acquire(self.h.now())
            path=owner.component('navigation');original=path.read();changed=deepcopy(original)
            changed['original']['processId']=43;path.write(changed,original)
            with self.assertRaises(NativeUIError):self.f.owner(historical=True).archive()
            path.write(original,changed);self.assertIsNotNone(self.f.owner(historical=True).archive())
            self.h.sdk.okay=False
            with self.assertRaises(NativeUIError):owner.bound()

    def test_lost_gpu_read_drains_only_its_actual_slot_and_retains_unknown_capture_ownership(self):
        self.h.gpu.drop=True
        with self.held():
            owner=self.f.owner()
            with self.assertRaises(NativeUIError):owner.acquire(self.h.now())
            state=unpack(owner.store.read()['payload'])[0]
            self.assertIn('capture',state['issued']);self.assertNotIn('capture',[ref['kind'] for ref in state['records']])
            self.assertIn('retirement',[ref['kind'] for ref in state['records']])
            self.assertEqual(1,sum(row['operation']=='read' for row in self.h.gpu.commands))
            self.h.gpu.drop=False;owner.drain()
            before=deepcopy(self.h.gpu.commands)
            with self.assertRaises(NativeUIError):self.f.owner().recover()
            self.assertEqual(before,self.h.gpu.commands);self.assertEqual([],self.h.flow_fixture.b.inputs)

    def test_slow_final_archive_validation_cannot_return_a_fresh_baseline(self):
        with self.held():
            owner=self.f.owner();archive=owner.archive
            def slow():
                value=archive();self.h.sdk.gpu.clock+=2;return value
            owner.archive=slow
            with self.assertRaises(NativeUIError):owner.acquire(self.h.now())
            self.assertEqual('observed',owner.state['phase'])
            self.assertIsNotNone(self.f.owner(historical=True).archive())
            with self.assertRaises(NativeUIError):self.f.owner().fresh()


if __name__=='__main__':unittest.main()
