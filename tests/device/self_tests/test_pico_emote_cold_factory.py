"""Actual cold Parent/Common/Source graph at explicit modeled SDK boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
import hashlib
import subprocess
import time
import unittest

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from self_tests.pico_emote_cold_factory_fixture import ColdModel

RETAINED=[]


class ColdFactoryTests(unittest.TestCase):
    def setUp(self):
        self.model=ColdModel();self.addCleanup(self.finalize)
        print('Retained cold original roots:',*[str(root) for root in self.model.roots],flush=True)

    def finalize(self):
        m=self.model
        def inventory():
            return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
                for root in m.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();m.close();after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(roots=[str(root) for root in m.roots],files=after))

    def held(self):
        stack=ExitStack();stack.enter_context(self.model.m.s.lock.held());stack.enter_context(self.model.actor_lock.held());return stack

    def test_cold_construction_performs_zero_json_getters_before_existing_parent_bootstrap(self):
        m=self.model
        with self.held():
            cycle=m.cold()
            self.assertEqual([],m.cold_calls);self.assertIsNone(cycle.originals);self.assertIsNone(cycle.parent.previous)
            self.assertEqual('attached',cycle.phase);self.assertEqual(2,cycle.parent.version)
            self.assertFalse(any(runtime.ui.initialized for runtime in m.runtimes.values()))
            with self.assertRaises(NativeUIError):m.runtimes['primary'].read('marker')
            self.assertEqual([],m.cold_calls)

    def test_canonical_bound_factory_keeps_productive_default_clocks_and_zero_getters(self):
        m=self.model
        with self.held():
            cycle=m.cold(canonical=True)
            self.assertEqual([],m.cold_calls);self.assertIsNone(cycle.originals);self.assertIsNone(cycle.parent.previous)
            self.assertIs(cycle.source.monotonic,time.monotonic)
            for runtime in m.runtimes.values():
                self.assertIs(runtime.monotonic,time.monotonic);self.assertIs(runtime.sleep,time.sleep)
                self.assertIs(runtime.native.monotonic,time.monotonic);self.assertIs(runtime.native.sleep,time.sleep)
                self.assertFalse(runtime.ui.initialized);self.assertIsNone(runtime.ui.bridge)
            self.assertEqual('attached',cycle.phase);self.assertEqual(2,cycle.parent.version)

    def test_actual_cold_baseline_uses_same_raw_archive_before_original_scriptio_parser(self):
        m=self.model
        with self.held():
            cycle=m.cold();cycle.parent.baseline()
            self.assertFalse(cycle.parent.state['baseline'] is None)
            self.assertTrue(m.runtimes['primary'].ui.initialized)
            self.assertTrue(m.cold_calls);archive=cycle.originals.archive
            for runtime in m.runtimes.values():
                for reference in runtime.originals:self.assertIs(type(archive.literal(reference)),bytes)
            self.assertEqual('armed',cycle.phase)
            self.assertFalse(cycle.parent.state['baseline'].get('wholeFeatureComplete',False))

    def test_every_inherited_input_entry_refuses_before_initial_scriptio_with_zero_sdk_or_getter(self):
        m=self.model
        with self.held():
            cycle=m.cold();ui=m.runtimes['primary'].ui
            entries=(lambda:ui.activate('emote.entry'),lambda:ui.replace('script-file.folder','literal'),
                lambda:ui.submit('script-file.folder'),lambda:ui.select_index('script-file.primary',0),
                lambda:ui.tablet(True),ui.release)
            before={role:list(sdk.events) for role,sdk in m.sdks.items()}
            for entry in entries:
                with self.assertRaises(NativeUIError):entry()
                self.assertEqual(before,{role:list(sdk.events) for role,sdk in m.sdks.items()})
            self.assertEqual([],m.cold_calls);self.assertEqual([],m.m.input.inputs)
            self.assertEqual([],m.m.input.controllers);self.assertIsNone(cycle.parent.previous)
            self.assertFalse(ui.initialized);self.assertIsNone(cycle.originals)

    def test_same_cold_parent_normal_open_then_play_has_actual_effect_originals(self):
        m=self.model
        with self.held():
            cycle=m.cold();owner=cycle.parent;owner.baseline()
            owner.act(m.m.input.call('open'));opened=owner.observe()
            self.assertTrue(opened['state']['panel']);self.assertEqual(['tablet.open'],m.m.input.controllers)
            owner.act(m.m.input.call('play',{'name':'Crying'}));played=owner.observe()
            self.assertEqual('Crying',played['state']['animation']);self.assertTrue(played['state']['override'])
            self.assertEqual(2,len(owner.state['steps']));self.assertIs(owner.source,cycle.source)
            self.assertIs(m.runtimes['primary'].ready(),cycle.originals.archive)
            self.assertFalse(owner.common.finished())

    def first_reentry(self,kind):
        m=self.model;claims=[]
        with self.held():
            cycle=m.cold();runtime=m.runtimes['primary']
            def reenter():
                if runtime.active is None:return
                setattr(m,kind,None);original=runtime.active
                with self.assertRaises(NativeUIError):runtime.read('probe')
                claims.append((original,runtime.active))
            setattr(m,kind,reenter)
            with self.assertRaises(NativeUIError):cycle.parent.baseline()
            self.assertEqual(1,len(claims));self.assertIs(claims[0][0],claims[0][1])
            self.assertTrue(runtime.failed);self.assertEqual([],m.cold_calls)
            self.assertEqual('baseline-issued',cycle.parent.store.read()['state']['phase'])

    def test_first_clock_reentry_refuses_zero_getter_without_clearing_outer_claim(self):
        self.first_reentry('clock_hook')

    def test_first_kernel_guard_reentry_refuses_zero_getter_without_clearing_outer_claim(self):
        self.first_reentry('process_hook')

    def test_first_malformed_nul_return_is_retained_before_original_debug_parser(self):
        m=self.model;literal=b'not JSON\x00'+bytes(range(256))*16
        with self.held():
            cycle=m.cold();m.getter_fault=lambda wire:literal
            with self.assertRaises((NativeUIError,ValueError)):cycle.parent.baseline()
            runtime=m.runtimes['primary'];self.assertEqual(1,len(m.cold_calls))
            self.assertEqual([literal],[cycle.originals.archive.literal(ref) for ref in runtime.originals])
            self.assertFalse(runtime.ui.initialized);self.assertEqual([],m.m.input.inputs)

    def test_first_late_partial_timeout_retained_on_original_reservation_without_new_getter(self):
        m=self.model;literal=b'actual partial\x00'+bytes(range(256))
        with self.held():
            cycle=m.cold()
            def timeout(wire):
                m.m.tick(5000);raise subprocess.TimeoutExpired('declared SDK process',5,output=literal)
            m.getter_fault=timeout
            with self.assertRaises((NativeUIError,ValueError,subprocess.TimeoutExpired)):cycle.parent.baseline()
            runtime=m.runtimes['primary'];self.assertEqual(1,len(m.cold_calls))
            self.assertEqual([literal],[cycle.originals.archive.literal(ref) for ref in runtime.originals])
            self.assertEqual('baseline-issued',cycle.parent.store.read()['state']['phase'])
            before=list(m.cold_calls)
            with self.assertRaises(NativeUIError):runtime.read('marker')
            self.assertEqual(before,m.cold_calls)


if __name__=='__main__':unittest.main()
