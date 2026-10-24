"""Canonical source/Stop/OS bridge; native/WDA/OS and preflight declared models.

This small suite does not qualify the whole Emote journey or native execution.
The actual installed, normal Stop and independent OS reader guards are used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.installed_process_runtime import admitted_source,retired_process_observer
from ios.adapters.retired_process import absent
from ios.self_tests.emote_rooted_whole_end_fixture import WholeRootedEndFixture,installed_tree


class RootedEndBridgeTests(unittest.TestCase):
    def setUp(self):self.f=WholeRootedEndFixture(self)
    def test_real_canonical_stop_retires_exact_installed_source_then_only_independent_os_is_read(self):
        f=self.f;binding=f.bindings['actor'];source=admitted_source(f.runtime,'actor',binding)
        self.assertEqual(f.summary['bundleIdentity'],installed_tree(f.trees['actor']))
        self.assertEqual({'stopped':True},f.base.invoke('actor','app.stop',{}));self.assertEqual(['actor'],f.stops)
        self.assertEqual('retired',f.base._binding_store('actor').read()['phase'])
        before=deepcopy(f.native_reads);reader=retired_process_observer(f.runtime,'actor',binding,source)
        reader.epoch_ms=f.facades['actor'].epoch_ms;reader.monotonic=f.facades['actor'].monotonic
        self.assertTrue(absent(reader.read()));self.assertEqual(before,f.native_reads)
        factories=deepcopy(f.source_factories)
        with self.assertRaises((ValueError,RuntimeError)):f.runtime._sources('actor')
        self.assertEqual(factories,f.source_factories)
        with self.assertRaises((ValueError,RuntimeError)):f.base.invoke('actor','app.stop',{})
        self.assertEqual(['actor'],f.stops)
    def test_changed_actual_candidate_bytes_block_before_canonical_stop(self):
        f=self.f;f.ipa.write_bytes(f.ipa.read_bytes()+b'foreign candidate bytes')
        with self.assertRaises((ValueError,RuntimeError,NativeUIError)):f.base.invoke('actor','app.stop',{})
        self.assertEqual([],f.stops);self.assertTrue(f.alive['actor'])
    def test_independently_changed_installed_tree_cannot_echo_the_selected_zip(self):
        f=self.f;(f.trees['actor']/'Overte').write_bytes(b'Foreign independently observed installed bytes')
        with self.assertRaises((ValueError,RuntimeError,NativeUIError)):admitted_source(f.runtime,'actor',f.bindings['actor'])
        self.assertEqual([],f.stops);self.assertTrue(f.alive['actor'])


if __name__=='__main__':unittest.main()
