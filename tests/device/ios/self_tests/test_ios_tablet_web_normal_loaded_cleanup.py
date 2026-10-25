"""Ordinary selected app through actual JS Ending and native-model held quiet.

This is one observer's loaded-app cleanup composition, not independent Actor,
terminal OS/SDK completion or native/device execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUI,Locator
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner,input_scopes
from ios.adapters.tablet_web_cleanup import TabletWebCleanupAppOwner
from ios.adapters.tablet_web_inputs import TabletWebInputs
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import quiet
from ios.self_tests.tablet_web_page_fixture import TabletPageBoundary


class TabletNormalLoadedCleanupTests(unittest.TestCase):
    def test_normal_file_load_web_input_Ending_file_absence_and_repeated_held_quiet(self):
        b=TabletPageBoundary(self);owner=TabletWebAppOwner(b.runtime);owner.prepare('b'*32)
        ui=NativeUI(b.ui,b.binding['sessionId'],lambda:True,monotonic=b.mono,sleep=b.sleep)
        row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.open')
        ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.open'),row['token'])
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        inputs.perform('b'*32,'normal-owned-submit','tap','bridge')
        initial=b.runtime.validate_original(b.runtime.observe())['public']['state']
        self.assertEqual((1,1,1),tuple(initial[key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        scopes=input_scopes(b.root,b.binding,b.source.run);tail=TabletWebTail(b.runtime)
        before=tail.capture(scopes);source_input=deepcopy(owner.saved)
        cleanup=TabletWebCleanupAppOwner(b.runtime);cleanup.close_page();cleanup.stop_apps()
        stop=tail.capture(scopes);current=tail.capture(scopes);cleanup.release_files(before,stop,current)
        frames=[]
        for _ in range(3):b.sleep(1.6);frames.append(tail.read(tail.capture(scopes)))
        proof=quiet(tail.read(before),tail.read(stop),frames,b.source.app_sources())
        self.assertTrue(proof['proof']['heldResources'])
        self.assertEqual(source_input,owner.store.read());self.assertTrue(b.ending_original['stopped'])
        self.assertEqual(0,b.ending_original['connections']);self.assertIsNotNone(b.host_app.process.poll())
        self.assertEqual(1,b.ui.qt.inputs.count('scripts.stop.0'));self.assertFalse(b.ui.qt.opened)
        self.assertFalse(b.directories[scopes[0]['runId']].exists())
        self.assertGreaterEqual(proof['hostAfterMonotonic']-proof['hostBeforeMonotonic'],3)
        # Repeated ordinary cleanup resolves originals; it cannot replay Stop.
        TabletWebCleanupAppOwner(b.runtime).stop_apps()
        self.assertEqual(1,b.ui.qt.inputs.count('scripts.stop.0'))


if __name__=='__main__':unittest.main()
