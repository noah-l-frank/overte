"""Actual loopback clock concurrency; declared product sources only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import threading
import time
import unittest
from self_tests.pico_browser_process_fixture import ProductSources,Rpc
from self_tests.pico_browser_host_clock import BrowserHostClock
from adapters.normal_ui import NativeUIError

class ClockDispatchTests(unittest.TestCase):
    def source(self,independent=True,clock=None):
        clock=BrowserHostClock() if clock is None else clock
        fixture=SimpleNamespace(clock=clock,target=SimpleNamespace(binding={'declared':True},foreground=True))
        source=ProductSources(fixture,SimpleNamespace(),independent_clock=independent)
        self.addCleanup(source.close)
        return source
    def rpc(self,source):
        rpc=Rpc(dict(port=source.server.server_address[1],token=source.token));self.addCleanup(rpc.close);return rpc
    def test_real_actor_clock_does_not_block_primary_product_but_product_calls_remain_serialized(self):
        source=self.source();actor=self.rpc(source);primary=self.rpc(source);clock=self.rpc(source)
        sleep_done=threading.Event();result=[]
        def sleep():actor.call('sleep',.3);sleep_done.set()
        worker=threading.Thread(target=sleep);worker.start();self.addCleanup(worker.join,2)
        deadline=time.monotonic()+1
        while 'sleep' not in source.calls and time.monotonic()<deadline:time.sleep(.001)
        self.assertIn('sleep',source.calls);before=time.monotonic()
        self.assertEqual({'binding':{'declared':True},'foreground':True},primary.call('candidate'))
        self.assertFalse(sleep_done.is_set());self.assertLess(time.monotonic()-before,.15)
        with source.mutex:
            product_done=threading.Event()
            def product():result.append(primary.call('candidate'));product_done.set()
            pending=threading.Thread(target=product);pending.start();self.addCleanup(pending.join,2)
            time.sleep(.025);self.assertFalse(product_done.is_set())
            self.assertGreater(clock.call('host'),0);self.assertGreater(clock.call('epoch'),0)
            self.assertFalse(product_done.is_set())
        pending.join(2);worker.join(2)
        self.assertTrue(product_done.is_set());self.assertTrue(sleep_done.is_set());self.assertEqual(1,len(result))
    def test_default_dispatch_keeps_original_clock_serialization(self):
        source=self.source(False);rpc=self.rpc(source);done=threading.Event()
        with source.mutex:
            worker=threading.Thread(target=lambda:(rpc.call('host'),done.set()));worker.start();self.addCleanup(worker.join,2)
            time.sleep(.025);self.assertFalse(done.is_set());self.assertNotIn('host',source.calls)
        worker.join(2);self.assertTrue(done.is_set())
    def test_explicit_mode_refuses_a_virtual_clock_or_non_boolean_selector(self):
        for selector,clock in ((True,SimpleNamespace()),(1,BrowserHostClock())):
            with self.assertRaises(NativeUIError):ProductSources(SimpleNamespace(clock=clock),None,independent_clock=selector)

if __name__=='__main__':unittest.main()
