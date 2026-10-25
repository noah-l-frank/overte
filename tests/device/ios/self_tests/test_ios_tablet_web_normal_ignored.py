"""Actual ordinary file inputs may return without creating the Script VM.

The native load/VM boundary is deliberately ignored by this host model. Cleanup
uses separate actual null-return dialog and native absence originals, retaining
the failed setup journal. This is not native execution or a complete journey.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner,input_scopes
from ios.adapters.tablet_web_cleanup import TabletWebCleanupAppOwner
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import quiet
from ios.self_tests.tablet_web_normal_fixture import TabletNormalBoundary


class TabletNormalIgnoredTests(unittest.TestCase):
    def test_returned_but_unloaded_file_uses_normal_close_and_original_file_absence(self):
        boundary=TabletNormalBoundary(self);boundary.ignored=True;owner=TabletWebAppOwner(boundary.runtime)
        with self.assertRaises(NativeUIError):owner.prepare('b'*32)
        failed=deepcopy(owner.saved);self.assertEqual('failed',owner.state['pending']['status'])
        self.assertEqual(1,len(boundary.loaded));self.assertIsNone(boundary.manager);self.assertEqual({},boundary.controls)
        scopes=input_scopes(boundary.root,boundary.binding,boundary.source.run);self.assertEqual(1,len(scopes))
        tail=TabletWebTail(boundary.runtime);before=tail.capture(scopes)
        cleanup=TabletWebCleanupAppOwner(boundary.runtime);cleanup.close_page();cleanup.stop_apps();stop=tail.capture(scopes)
        current=tail.capture(scopes);cleanup.release_files(before,stop,current)
        frames=[]
        for _ in range(3):boundary.sleep(1.6);frames.append(tail.read(tail.capture(scopes)))
        proof=quiet(tail.read(before),tail.read(stop),frames,[])
        self.assertTrue(proof['proof']['heldResources'])  # Actual cached Qt roots are preserved until OS retirement.
        self.assertEqual(failed,owner.store.read());self.assertFalse(boundary.ui.qt.opened)
        self.assertEqual(1,boundary.ui.file_ui.actions.count('script-file.confirm'))
        self.assertFalse(boundary.directories[scopes[0]['runId']].exists())
        self.assertEqual([],boundary.source.state['apps']);self.assertEqual([],boundary.ui.qt.rows)


if __name__=='__main__':unittest.main()
