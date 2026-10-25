"""Interrupted real picker setup cancels once and proves actual no-VM cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner,input_scopes
from ios.adapters.tablet_web_cleanup import TabletWebCleanupAppOwner
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import quiet
from ios.self_tests.tablet_web_normal_fixture import TabletNormalBoundary


class TabletNormalCancelTests(unittest.TestCase):
    def test_actual_open_picker_interruption_never_loads_and_ordinary_cancel_closes_actual_listener(self):
        boundary=TabletNormalBoundary(self);owner=TabletWebAppOwner(boundary.runtime);once=owner.once
        def interrupted(generation,label,function):
            result=once(generation,label,function)
            if label=='open-picker-1':raise InterruptedError('Host interrupted after actual ordinary picker-open returned')
            return result
        owner.once=interrupted
        with self.assertRaises(InterruptedError):owner.prepare('b'*32)
        original=deepcopy(owner.saved);self.assertTrue(boundary.ui.file_ui.opened);self.assertEqual([],boundary.loaded)
        scopes=input_scopes(boundary.root,boundary.binding,boundary.source.run);tail=TabletWebTail(boundary.runtime);before=tail.capture(scopes)
        cleanup=TabletWebCleanupAppOwner(boundary.runtime);cleanup.close_page();cleanup.stop_apps();stop=tail.capture(scopes)
        current=tail.capture(scopes);cleanup.release_files(before,stop,current);frames=[]
        for _ in range(3):boundary.sleep(1.6);frames.append(tail.read(tail.capture(scopes)))
        proof=quiet(tail.read(before),tail.read(stop),frames,[])
        self.assertTrue(proof['proof']['heldResources']);self.assertEqual(original,owner.store.read())
        self.assertEqual(1,boundary.ui.file_ui.actions.count('script-file.cancel'));self.assertEqual([],boundary.ui.file_ui.accepted)
        self.assertEqual([],boundary.loaded);self.assertIsNone(boundary.manager);self.assertFalse(boundary.ui.qt.opened)
        self.assertFalse(boundary.directories[scopes[0]['runId']].exists())


if __name__=='__main__':unittest.main()
