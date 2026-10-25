"""Normal one-SDK Stop followed by actual retired-reader HTTP composition.

This does not bypass Whole's required paired live seal. It qualifies only the
existing adapter/readers' mechanics over explicit OS and Node-clock models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.retired_process import absent
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,SELECTOR
from ios.self_tests.tablet_web_lifecycle_fixture import attach
from ios.self_tests.tablet_web_retired_fixture import TabletRetiredModel


class TabletRetiredFlowTests(unittest.TestCase):
    def prepared(self):
        f=PairedTabletFixture(self);attach(f);model=TabletRetiredModel(f.boundary)
        return f,model,f.primary.runtime.adapter
    def read(self,f):
        reader=IOSGraphicsRuntime._retired_process_observer(f.primary.runtime,SELECTOR,f.boundary.binding,deepcopy(f.boundary.context_test.admission.fixture.source))
        reader.epoch_ms,reader.monotonic=f.boundary.host,f.boundary.mono
        return reader
    def test_normal_Stop_and_two_independent_OS_readers_never_query_dead_native_or_stop_twice(self):
        f,model,adapter=self.prepared();queries=len(f.boundary.commands)
        self.assertEqual({'stopped':True},adapter.invoke(SELECTOR,'app.stop',{}))
        self.assertFalse(model.running);self.assertEqual('retired',adapter._binding_store(SELECTOR).read()['phase'])
        primary=self.read(f);actor=self.read(f);a=primary.read();f.boundary.sleep(3.1);b=actor.read()
        self.assertTrue(absent(a) and absent(b));self.assertEqual(a['anchor'],b['anchor']);self.assertGreater(b['sequence'],a['sequence'])
        self.assertGreater(a['clockBefore']['epochMs']-primary.acquisition['hostAfterEpochMs'],86399000)
        self.assertEqual(queries,len(f.boundary.commands));self.assertEqual(2,len(model.originals))
        self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in model.calls))
        with self.assertRaises((NativeUIError,ValueError)):adapter.invoke(SELECTOR,'app.stop',{})
        self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in model.calls));self.assertEqual([],f.sdk.errors)
    def test_lost_Stop_return_retires_only_via_original_source_absence_without_another_input(self):
        f,model,adapter=self.prepared();model.lose_return='mobile: terminateApp';queries=len(f.boundary.commands)
        with self.assertRaises(RuntimeError):adapter.invoke(SELECTOR,'app.stop',{})
        self.assertFalse(model.running);self.assertEqual('retiring',adapter._binding_store(SELECTOR).read()['phase'])
        IOSGraphicsRuntime._graphics_final_stopped(f.primary.runtime,SELECTOR,f.boundary.binding,deepcopy(f.boundary.context_test.admission.fixture.source))
        self.assertEqual('retired',adapter._binding_store(SELECTOR).read()['phase']);self.assertTrue(absent(self.read(f).read()))
        self.assertEqual(queries,len(f.boundary.commands));self.assertEqual(1,sum(op=='mobile: terminateApp' for op,_ in model.calls))
        self.assertEqual(1,len(f.sdk.errors));self.assertIsInstance(f.sdk.errors[0],OSError)


if __name__=='__main__':unittest.main()
