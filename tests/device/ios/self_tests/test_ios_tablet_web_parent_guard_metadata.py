"""Metadata key equivalence and actual mutable-default fallback."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import sys
import unittest
from ios.adapters import tablet_web_child_rotation as closed
from ios.adapters import tablet_web_parent_guard_cache as cache
from ios.adapters.tablet_web_record_cache import scope
from ios.self_tests import test_ios_tablet_web_parent_guard_cache as owners


class TabletParentGuardMetadataKeyTests(unittest.TestCase):
    def test_current_keys_distinguish_scalar_types_signed_zero_and_unicode_sequences(self):
        values=[True,1,1.0,False,0,0.0,-0.0,None,'1']
        keys=[cache._header_key(dict(value=value)) for value in values]
        self.assertEqual(len(values),len({repr(key) for key in keys}))
        self.assertEqual(cache._header_key(dict(a=[1,dict(v='abc')],b=None)),
            cache._header_key(dict(b=None,a=[1,dict(v='abc')])))
        self.assertNotEqual(cache._header_key(dict(value='\U0001f600')),
            cache._header_key(dict(value='\ud83d\ude00')))
        self.assertNotEqual(cache._header_key(dict(value='\ud800')),cache._header_key(dict(value='\ufffd')))

    def test_opaque_subclasses_cycles_nonfinite_and_resource_excess_refuse_without_hooks(self):
        class Opaque:
            def __iter__(self):raise AssertionError('Unexpected metadata iterator')
        class ForeignList(list):
            def __iter__(self):raise AssertionError('Unexpected subclass metadata iterator')
        cyclic=[];cyclic.append(cyclic)
        for value in (Opaque(),ForeignList([1]),cyclic,[float('nan')],[float('inf')],[None]*4097):
            with self.subTest(kind=type(value).__name__),self.assertRaises(cache._Unsupported):cache._header_key(value)
        value=None
        for _ in range(34):value=[value]
        with self.assertRaises(cache._Unsupported):cache._header_key(value)


class TabletParentGuardMetadataOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):owners.TabletParentGuardCacheTests.setUpClass()
    def setUp(self):
        self.f=owners.TabletParentGuardCacheTests();self.addCleanup(self.f.doCleanups);self.f.setUp()

    def test_current_mutable_copy_default_is_rescanned_and_never_takes_none_fastpath(self):
        monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
        monitor.use_tool_id(tool,'tablet-current-mutable-default');seen=[];code=closed.decode.__code__
        def call(_code,_offset):seen.append(_code)
        monitor.register_callback(tool,monitor.events.PY_START,call);monitor.set_local_events(tool,code,monitor.events.PY_START)
        defaults=copy.deepcopy.__defaults__;sentinel=defaults[1];self.assertIs(type(sentinel),list)
        saved=list(sentinel);queries=list(self.f.f.boundary.calls)
        try:
            with scope(self.f.cache):self.assertTrue(self.f.owner._parent_guard())
            self.assertEqual([],seen)
            sentinel.append('actual-default-drift')
            with scope(self.f.cache):self.assertTrue(self.f.owner._parent_guard())
            self.assertEqual([code,code],seen)
            sentinel[:]=saved;seen.clear()
            with scope(self.f.cache):self.assertTrue(self.f.owner._parent_guard())
            self.assertEqual([],seen);self.assertEqual(queries,self.f.f.boundary.calls)
            self.assertEqual(self.f.f.canonical,self.f.f.pins(self.f.f.canonical_paths))
        finally:
            sentinel[:]=saved;self.assertIs(copy.deepcopy.__defaults__,defaults)
            monitor.set_local_events(tool,code,0);monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)
