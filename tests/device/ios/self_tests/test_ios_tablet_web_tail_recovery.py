"""Failed tail stays failed; only a new complete acquisition can be quiet.

Uses actual HTTP/AFC/private owners with explicit native/SDK models, no device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import inspect
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary


class TabletTailRecoveryTests(unittest.TestCase):
    def test_old_auxiliary_lookup_archives_actual_failure_and_requires_a_new_complete_tail(self):
        boundary=TabletWholeBoundary(self);runtime=boundary.runtime;tail=TabletWebTail(runtime)
        boundary.lost='feature-ios-pointer-state'
        with self.assertRaises((OSError,NativeUIError)):tail.capture([])
        failed=deepcopy(tail.state['pending']);count=len(boundary.commands);boundary.lost=None;boundary.sleep(4.)
        runtime.recover_auxiliaries([]);self.assertEqual(count,len(boundary.commands))
        reference=tail.archive_failed();self.assertEqual(count,len(boundary.commands))
        self.assertEqual(failed,tail.read(reference)['row']);self.assertEqual('failed',tail.read(reference)['row']['status'])
        fresh=tail.read(tail.capture([]));self.assertEqual('returned',fresh['row']['status']);self.assertGreater(len(boundary.commands),count)
        rebuilt=TabletWebTail(runtime,historical=True);self.assertEqual(['failed','returned'],[value['row']['status'] for value in rebuilt.frames])
        self.assertEqual(failed,rebuilt.read(reference)['row'])
        with self.assertRaises(NativeUIError):inspect(rebuilt.read(reference),fresh,fresh,[])


if __name__=='__main__':unittest.main()
