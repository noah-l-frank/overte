"""Ordinary controls -> actual JS callbacks -> passive modeled Rig originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from types import SimpleNamespace
from adapters.emote_rig_measurements import playback,restoration
from ios.self_tests.emote_script_vm_fixture import normal_ui
from ios.self_tests.emote_vm_rig_fixture import ActualVMRig


class VMRigTests(unittest.TestCase):
    def setUp(self):
        self.clock=SimpleNamespace(time=0.)
        self.clock.sleep=lambda seconds:setattr(self.clock,'time',self.clock.time+seconds)
        self.clock.epoch=lambda:20000+round(self.clock.time*1000)
        self.vm,self.ui_native,self.ui=normal_ui(self,clock=self.clock);self.rig=ActualVMRig(self.vm,self.clock);self.reader=self.rig.reader()

    def read(self):return self.reader.read(self.reader.sequence,require_animation_history=True)

    def test_actual_script_caller_clip_pose_and_early_restore_share_one_original_timeline(self):
        baseline=self.read();self.ui.open();self.ui.play('Waving');self.read();self.clock.sleep(.25)
        group=self.rig.group(self.read());measured=playback(group,baseline,pid=31,epoch=self.clock.epoch())
        self.assertEqual('Waving',measured['state']['animation']);self.assertGreater(measured['state']['poseProgress'],0.)
        self.assertEqual(self.vm.pin['sha256'],measured['event']['caller']['code']['sha256'])
        self.assertEqual(self.vm.state['events'][0]['epochMs'],measured['event']['caller']['invokedEpochMs'])
        barrier=self.read();self.ui.cancel();group=self.rig.group(self.read())
        restored=restoration(group,measured,pid=31,epoch=self.clock.epoch(),native_barrier=barrier)
        self.assertTrue(restored['state']['restoredBeforeNominalEnd']);self.assertFalse(restored['state']['override'])
        self.assertEqual([],self.vm.state['timers'])

    def test_actual_script_sit_choices_and_natural_timer_keep_all_native_history(self):
        self.ui.open();seen=[]
        for _ in range(3):
            baseline=self.read();self.ui.play('Sit');self.read();self.clock.sleep(.25)
            group=self.rig.group(self.read());measured=playback(group,baseline,pid=31,epoch=self.clock.epoch())
            seen.append(measured['state']['sit']);self.ui_native.sleep(2.1)
            group=self.rig.group(self.read());restored=restoration(group,measured,pid=31,epoch=self.clock.epoch())
            self.assertFalse(restored['state']['restoredBeforeNominalEnd'])
        self.assertEqual({'Sit1','Sit2','Sit3'},set(seen));self.assertEqual(6,self.rig.value['animation']['history']['callSequence'])


if __name__=='__main__':unittest.main()
