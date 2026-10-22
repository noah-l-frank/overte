"""Actual pinned source in Node behind ordinary modeled token controls."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.token_emote_ui import NAMES
from ios.self_tests.emote_script_vm_fixture import normal_ui


class ScriptVMTests(unittest.TestCase):
    def test_every_normal_name_invokes_actual_script_url_range_rate_and_restoration(self):
        vm,native,ui=normal_ui(self);ui.open()
        for name in NAMES:
            ui.play(name);event=vm.state['events'][-1]
            self.assertEqual('overrideAnimation',event['method']);request=event['request']
            self.assertEqual((60,False,0,120),(request['framesPerSecond'],request['loop'],request['firstFrame'],request['lastFrame']))
            self.assertTrue(request['url'].startswith(vm.root+'/system/assets/animations/'))
            self.assertTrue(request['url'].endswith('.fbx'));ui.cancel()
            self.assertEqual('restoreAnimation',vm.state['events'][-1]['method'])
        self.assertEqual(10,sum(row['method']=='overrideAnimation' for row in vm.state['events']));self.assertEqual([],vm.state['timers'])
        ui.close();self.assertFalse(native.page)

    def test_three_sit_results_are_selected_by_actual_script_without_requested_variant(self):
        vm,native,ui=normal_ui(self);ui.open();urls=[]
        for _ in range(3):
            ui.play('Sit');urls.append(vm.state['events'][-1]['request']['url']);ui.cancel()
        self.assertEqual({'Sit1.fbx','Sit2.fbx','Sit3.fbx'},{url.rsplit('/',1)[1] for url in urls})
        self.assertTrue(all('variant' not in str(request) for request in native.requests))

    def test_early_cancel_and_natural_timer_have_original_different_times(self):
        vm,native,ui=normal_ui(self);ui.open();ui.play('Waving');started=vm.state['events'][-1]
        native.sleep(.1);ui.cancel();cancel=vm.state['events'][-1]
        self.assertLess(cancel['epochMs'],started['epochMs']+2000)
        ui.play('Waving');started=vm.state['events'][-1];native.sleep(2.1)
        self.assertEqual('restoreAnimation',vm.state['events'][-1]['method'])
        self.assertGreaterEqual(vm.state['events'][-1]['epochMs'],started['epochMs']+2000);self.assertEqual([],vm.state['timers'])

    def test_missing_resource_cannot_become_a_native_override(self):
        vm,native,ui=normal_ui(self);ui.open()
        vm.command('resource',url=vm.root+'/system/assets/animations/Waving.fbx',state=4)
        ui.play('Waving')
        self.assertEqual('',native.active)
        self.assertEqual([],vm.state['events']);self.assertEqual('Animation failed to load',vm.state['states'][-1]['status'])


if __name__=='__main__':unittest.main()
