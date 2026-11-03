"""The actual Background factory refuses retained ranges before live runtime."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
import os
import unittest
from unittest.mock import patch

from test_lifecycle_background_raw_binding import BackgroundRawBindingTests
from test_create_journey import RUN
from adapters.pico4 import lifecycle_background_raw_state as state


class BackgroundRawFactoryTests(BackgroundRawBindingTests):
    def factory_refused(self,option):
        before=self.originals();inputs=list(self.native.inputs)
        with ExitStack() as patches:
            methods=[]
            for name in dir(self.native):
                if not name.startswith('_') and callable(getattr(self.native,name)):
                    methods.append(patches.enter_context(patch.object(self.native,name,
                        side_effect=AssertionError('Unexpected native read or write'))))
            for name in ('_script_runtime','_native_feature_observer'):
                methods.append(patches.enter_context(patch.object(self.adapter,name,
                    side_effect=AssertionError('Unexpected live runtime acquisition'))))
            with self.assertRaisesRegex(ValueError,'OVT_PICO_BINDING_REJECTED'):
                self.adapter._lifecycle_background_owner(self.native.target,RUN,raw_layout=option)
            self.assertTrue(all(method.call_count==0 for method in methods))
        self.assertEqual(inputs,self.native.inputs);self.assertEqual(before,self.originals())

    def test_retained_rootless_ranges_refuse_both_factory_modes_before_live_sources(self):
        for index,(option,suffix) in enumerate((option,suffix) for option in (False,True)
                for suffix in ('','.part-000.bin','.index-00.json','.pending-unknown')):
            with self.subTest(raw_layout=option,suffix=suffix):
                if index:self.setUp()
                path=self.directory()/(state.NAME+suffix)
                with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:
                    stream.write(b'unknown retained original\n')
                self.factory_refused(option)

    def test_non_boolean_layout_cannot_create_a_scope_or_acquire_a_live_runtime(self):
        for option in (None,0,1,'true'):
            with self.subTest(raw_layout=option):self.factory_refused(option)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(BackgroundRawFactoryTests(name) for name in (
        'test_retained_rootless_ranges_refuse_both_factory_modes_before_live_sources',
        'test_non_boolean_layout_cannot_create_a_scope_or_acquire_a_live_runtime'))

if __name__=='__main__':unittest.main()
