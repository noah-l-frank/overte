"""Review absence/hidden/current facts are separate from input and retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4.snapshot_review import validate
from adapters.pico4.navigation import validate_snapshot
from adapters.normal_ui import NativeUIError


def observation():
    return dict(snapshotReviewObservationVersion=1,present=True,review=dict(
        componentUrl='file:///actual/scripts/system/snapshot/NativeSnapshotReview.qml',visible=True,
        capturing=False,processing=False,loggedIn=False,canShare=False,canBlast=False,statusError=False,
        captureSettingsLoaded=True,statusText='Take a snapshot.',uploadPath='',exportTicket='',mode=1,
        format='png',capabilities=[],exportBusy=False,exportError='',images=[]))


class SnapshotReviewTests(unittest.TestCase):
    def test_hidden_owned_review_is_present_and_a_live_root_absence_is_not_missing_source(self):
        value=observation();value['review'].update(visible=False,capturing=True)
        self.assertIs(value,validate(value))
        absent=dict(snapshotReviewObservationVersion=1,present=False,review=None)
        self.assertIs(absent,validate(absent))
        for value in ({},{**absent,'review':{}},{**absent,'present':True},{**absent,'retired':True}):
            with self.subTest(value=value),self.assertRaises(NativeUIError):validate(value)
    def test_foreign_ambiguous_unknown_or_malformed_originals_are_unavailable(self):
        faults=(lambda v:v.update(snapshotReviewObservationVersion=True),lambda v:v['review'].update(capturing=1),
            lambda v:v['review'].update(componentUrl='file:///foreign/SnapshotReview.qml'),
            lambda v:v['review'].update(componentUrl='https://remote.invalid/system/snapshot/NativeSnapshotReview.qml'),
            lambda v:v['review'].update(componentUrl='file:///foreign/../system/snapshot/NativeSnapshotReview.qml'),
            lambda v:v['review'].update(mode=4),lambda v:v['review'].update(expectedCancelled=True),
            lambda v:v['review'].update(capabilities=[True]),lambda v:v['review'].update(capabilities=['save','save']),
            lambda v:v['review'].update(images=[dict(path='/actual/a.png',storyPresent=False)]*2))
        for fault in faults:
            value=observation();fault(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):validate(value)
    def test_actual_optional_navigation_field_is_strict_and_does_not_change_original_control_dto(self):
        value=dict(schemaVersion=1,bridgeId='12345678-1234-4234-8234-123456789abc',
            generation='22345678-1234-4234-8234-123456789abc',processId=31,elapsedMs=3,updatedEpochMs=20000,
            lastCommandSequence=0,open=True,ready=True,controls=[],picoSnapshotReview=observation())
        validate_snapshot(value,31,20000)
        broken=deepcopy(value);broken['picoSnapshotReview']['review']['capturing']='ack'
        with self.assertRaises((ValueError,RuntimeError)):validate_snapshot(broken,31,20000)
        value.pop('picoSnapshotReview');validate_snapshot(value,31,20000)


if __name__=='__main__':unittest.main()
