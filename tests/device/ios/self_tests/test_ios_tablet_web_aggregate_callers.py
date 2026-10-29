"""Existing observer/input callers on actual owned unequal source originals.

Native/WDA endpoints are explicitly modeled; no native effects or full26
completion is inferred from input delivery. No original packet is retimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_aggregate_root as aggregate
from ios.adapters.tablet_web_inputs import TabletWebInputs
from ios.adapters.tablet_web_observer import TabletWebObserver
from ios.adapters.tablet_web_source_owner import ORDER
from ios.self_tests import test_ios_tablet_web_aggregate_root as fixture
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS
from ios.self_tests.test_ios_tablet_web_native_input import SDK


class TabletAggregateCallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.TabletOwnedAggregateRootTests.setUpClass()

    def setUp(self):
        self.f=fixture.TabletOwnedAggregateRootTests();self.addCleanup(self.f.doCleanups);self.f.setUp()
        self.source=self.f.open();self.boundary=self.f.boundary

    def input_owner(self,client,source=None):
        return TabletWebInputs(client,self.source.children['dom'] if source is None else source,self.boundary.reader('dom'),
            self.source.lock,lambda:self.boundary.epoch,**self.f.clocks())

    def test_actual_observer_reopens_owned_global_reference_and_publishes_only_derived_original_facts(self):
        calls=list(self.boundary.calls)
        self.boundary.epoch=self.boundary.host+int(self.boundary.mono*1000)+100
        observer=TabletWebObserver(self.source,{name:self.boundary.reader(name) for name in ORDER},self.boundary.native(),
            self.boundary.phase,lambda:deepcopy(self.boundary.frame['browser']),ORIGINS)
        original=observer.observe();actual=observer.validate_original(original)
        self.assertEqual(2,original['reference']['index']);self.assertEqual(2,actual['public']['sequence'])
        self.assertEqual(list(ORDER),self.boundary.calls[len(calls):])
        historical=aggregate.source_owner(*self.f.arguments(),**self.f.clocks(),historical=True)
        self.assertIs(type(historical),aggregate.TabletWebAggregateRoot)
        row,frame,_prefix=historical.frame_at(original['reference'])
        self.assertEqual(original['hostProcessId'],row['hostProcessId']);self.assertEqual(row['nativeAfter']['lifecycle'],actual['public']['lifecycle'])
        self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))

    def test_actual_input2_retains_global_dom_reference_and_old_decoder_cannot_adopt_it(self):
        client=SDK();owner=self.input_owner(client);before=len(self.boundary.calls)
        reference=owner.perform('e'*32,'owned-root-normal-tap','tap','bridge')
        row=owner.originals.read(owner.originals.expand(reference))
        self.assertEqual(2,row['tabletWebInputVersion']);self.assertEqual(self.f.counts['dom']+1,row['sourceIndex'])
        self.assertEqual(self.source.children['dom'].reference(row['sourceIndex']),row['sourceRef'])
        self.assertEqual(['dom'],self.boundary.calls[before:]);self.assertEqual(['POST','DELETE'],[method for method,_path,_body in client.calls])
        calls=deepcopy(client.calls);queries=list(self.boundary.calls)
        rebuilt=self.input_owner(client)
        self.assertEqual(reference,rebuilt.perform('e'*32,'owned-root-normal-tap','tap','bridge'))
        self.assertEqual(calls,client.calls);self.assertEqual(queries,self.boundary.calls)
        # This actual new WAL cannot be reinterpreted by a literal legacy
        # Packet owner, even though both owners use the SAME real root/binding.
        with self.assertRaises(NativeUIError):self.input_owner(client,self.f.source.children['dom'])
        self.assertEqual(calls,client.calls);self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))

    def test_unknown_new_input_return_releases_original_once_and_never_replays_after_owned_reconstruction(self):
        client=SDK();client.fail=True;owner=self.input_owner(client)
        with self.assertRaises(NativeUIError):owner.perform('e'*32,'owned-root-lost-tap','tap','bridge')
        self.assertEqual(['POST','DELETE'],[method for method,_path,_body in client.calls])
        calls=deepcopy(client.calls);queries=list(self.boundary.calls);client.fail=False
        rebuilt=self.input_owner(client)
        for label in ('owned-root-lost-tap','foreign-retry'):
            with self.subTest(label=label),self.assertRaises(NativeUIError):rebuilt.perform('e'*32,label,'tap','bridge')
        self.assertEqual(calls,client.calls);self.assertEqual(queries,self.boundary.calls)
        self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))


if __name__=='__main__':unittest.main()
