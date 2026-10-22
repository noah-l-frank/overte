"""Historical retirement prefixes survive genuine later original acquisitions.

Live owners continue to reject unjournaled original files; archive objects
cannot acquire, save or settle ownership. Native producers remain modeled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_file_receipts import IOSEmoteFileReceipts
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.self_tests import test_ios_emote_file_receipts as files_boundary
from ios.self_tests import test_ios_emote_marker_entities as entities_boundary
from ios.self_tests import test_ios_emote_pointers as pointer_boundary


class RetirementPrefixTests(unittest.TestCase):
    def assert_historical(self,owner,archive,old,first,current,rebuild):
        original=owner.original(first);historical=archive(old)
        self.assertEqual(original,historical.original(first))
        # No guard/source is even installed on the historical object. All
        # ownership mutations must fail closed before reaching such a callback.
        mutations=[historical.save,historical.resolve,historical.abandon]
        if hasattr(historical,'retain'):mutations.append(lambda:historical.retain({}))
        for mutate in mutations:
            with self.assertRaises(NativeUIError):mutate()
        # Rolling current metadata back to the old prefix leaves a real newer
        # immutable file. A live constructor must still detect that orphan.
        owner.store.write(old,current)
        with self.assertRaises(NativeUIError):rebuild()
        owner.store.write(current,old)
        # The historical path still validates each retained original byte/SHA.
        path=owner.record_store(first['index']) if hasattr(owner,'record_store') else owner.file(first['index'])
        saved=path.read();changed=deepcopy(saved);changed['unownedField']=True;path.write(changed,saved)
        with self.assertRaises(NativeUIError):archive(old)

    def test_native_file_prefix_is_read_only_while_live_orphans_and_modified_originals_still_fail(self):
        f=files_boundary.FileReceiptsTests();f.setUp();self.addCleanup(f.tearDown)
        owner=f.reader();first=owner.capture('bytes',f.ownership);old=owner.store.read()
        f.owner.release();owner.capture('absent',f.ownership);current=owner.store.read()
        archive=lambda value:IOSEmoteFileReceipts.archive(value,store=owner.store,root=f.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=f.lock)
        self.assert_historical(owner,archive,old,first,current,f.reader)

    def test_pointer_prefix_is_read_only_while_live_orphans_and_modified_originals_still_fail(self):
        f=pointer_boundary.PointerOwnerTests();f.setUp();self.addCleanup(f.doCleanups)
        owner=f.owner;first=owner.state['records'][0];old=owner.store.read();owner.capture();current=owner.store.read()
        archive=lambda value:IOSEmotePointers.archive(value,store=owner.store,root=owner.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=owner.lock)
        self.assert_historical(owner,archive,old,first,current,f.qt.owner)

    def test_marker_entity_prefix_is_read_only_while_live_orphans_and_modified_originals_still_fail(self):
        f=entities_boundary.MarkerEntityTests();f.setUp();self.addCleanup(f.doCleanups)
        owner=f.owner;first=owner.state['records'][0];old=owner.store.read();owner.capture();current=owner.store.read()
        archive=lambda value:IOSEmoteMarkerEntities.archive(value,store=owner.store,root=owner.root,binding=owner.binding,
            run=owner.run,role=owner.role,lock=owner.lock)
        self.assert_historical(owner,archive,old,first,current,f.entities.owner)
