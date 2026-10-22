"""Original weak-history boundaries; actual Qt source has its native check."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.pico4.view_menu_lifetimes import validate,accept,retired,FLAGS
from adapters.normal_ui import NativeUIError


def packet(sequence=1,rows=None):
    row=dict(instance='b'*32,firstObservedEpochMs=10000,alive=True,timerRunning=False,pendingMenuItem=False,
        **{key:True for key in FLAGS})
    return dict(instance='a'*32,sequence=sequence,capturedEpochMs=10000,originals=[row] if rows is None else rows)


class MenuLifetimeTests(unittest.TestCase):
    def test_closed_original_fields_and_partial_death_do_not_infer_context_release(self):
        first=packet(rows=[]);current=packet(2);self.assertFalse(retired(first,current))
        row=current['originals'][0];row.update(pageAlive=False,stackAlive=False,timerAlive=False)
        validate(current,10000);self.assertFalse(retired(first,current))
        row.update(alive=False,contextAlive=False,timerContextAlive=False)
        self.assertTrue(retired(first,current))

    def test_expected_fields_coercion_stale_time_and_contradictory_flags_are_rejected(self):
        for edit in (lambda p:p.update(sequence=True),lambda p:p.update(capturedEpochMs=8000),
                lambda p:p.update(expectedRetired=True),lambda p:p['originals'][0].update(alive=False),
                lambda p:p['originals'][0].update(timerAlive=False,timerRunning=True),
                lambda p:p['originals'][0].update(pageAlive=1),lambda p:p['originals'].append(deepcopy(p['originals'][0]))):
            value=packet();edit(value)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):validate(value,10000)

    def test_dropped_reordered_replaced_original_or_changed_birth_is_not_adopted(self):
        first=packet();second=packet(2)
        for edit in (lambda p:p.update(instance='c'*32),lambda p:p.update(originals=[]),
                lambda p:p['originals'][0].update(instance='c'*32),
                lambda p:p['originals'][0].update(firstObservedEpochMs=9999),lambda p:p.update(sequence=1)):
            value=deepcopy(second);edit(value)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):accept(first,value)

    def test_any_dead_original_qpointer_cannot_become_alive_in_later_packet(self):
        first=packet();first['originals'][0]['timerAlive']=False
        with self.assertRaises(NativeUIError):accept(first,packet(2))

    def test_baseline_shared_objects_are_not_owned_and_missing_owned_history_is_not_proof(self):
        with self.assertRaises(NativeUIError):retired(packet(),packet(2))
        before=packet();current=packet(2);extra=deepcopy(current['originals'][0]);extra.update(instance='c'*32,alive=False,
            **{key:False for key in FLAGS});current['originals'].append(extra)
        self.assertTrue(retired(before,current))


if __name__=='__main__':unittest.main()
