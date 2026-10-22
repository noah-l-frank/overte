"""Real token transport and modeled Qt/UIKit source facts; no compilation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,snapshot_export_controls as controls
from ios.self_tests.test_ios_normal_input import Boundary as NormalBoundary


class Boundary(NormalBoundary):
    def __init__(self):super().__init__(field='snapshot.save.0');self.change=None
    def observed(self):
        value=super().observed();value.update(tabletShown=True,snapshotExportControlsVersion=1)
        value['sampleEpochMs']=int(value['sampleEpochMs'])
        value['controls'][0].update(snapshotExportControlVersion=1,snapshotRootId='11111111-2222-4333-8444-777777777777',
            snapshotQmlSource='qrc:/scripts/system/snapshot/NativeSnapshotReview.qml',snapshotRow=0,
            snapshotFileName='parity-'+'a'*16+'-still-png-snap_100000_1.png',snapshotFileOwned=True,snapshotExportTicket='',
            snapshotCapturing=False,snapshotProcessing=False,snapshotSystemBlocked=False,inputReady=True)
        if self.change:self.change(value)
        return value


class SnapshotExportControlTests(unittest.TestCase):
    def test_actual_route_consumes_only_current_source_token_and_has_no_expected_outcome(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            native=b.input();reference=controls.project(native.capture())
            self.assertEqual(dict(performed=True),native.snapshot_export_input('snapshot.save.0',reference=reference))
        self.assertEqual(['observe','observe','edit'],[request['operation'] for request in b.requests])
        command=b.requests[-1]['input'];self.assertEqual('activate',command['operation']);self.assertEqual(b.token,command['fieldToken'])
        self.assertEqual({'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'},set(command))
        self.assertNotIn('saved',reference);self.assertNotIn('shares',reference)

    def test_changed_root_row_file_ticket_or_native_sheet_prevents_any_input_delivery(self):
        for fault in ('root','row','file','ticket','blocked','sequence'):
            b=Boundary()
            with patch.object(normal_input,'urlopen',b.post):
                native=b.input();reference=controls.project(native.capture())
                def change(value):
                    row=value['controls'][0]
                    if fault=='root':row['snapshotRootId']='11111111-2222-4333-8444-888888888888'
                    elif fault=='row':row['snapshotRow']=1
                    elif fault=='file':row['snapshotFileName']=row['snapshotFileName'].replace('snap_100000_1','snap_100000_2')
                    elif fault=='ticket':row['snapshotExportTicket']='11111111-2222-4333-8444-888888888888'
                    elif fault=='blocked':row.update(snapshotSystemBlocked=True,inputReady=False)
                    else:value['lastSequence']+=1
                b.change=change
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):native.snapshot_export_input('snapshot.save.0',reference=reference)
            self.assertTrue(all(request['operation']=='observe' for request in b.requests))

    def test_legacy_readability_does_not_invent_export_source_and_blocked_cannot_claim_ready(self):
        old=NormalBoundary(field='snapshot.capture').observed();normal_input.observation(old,42)
        with self.assertRaises(NativeUIError):controls.project(old)
        for fault in ('missing','version','foreign','blocked','unowned'):
            value=Boundary().observed();row=value['controls'][0]
            if fault=='missing':del value['snapshotExportControlsVersion']
            elif fault=='version':value['snapshotExportControlsVersion']=True
            elif fault=='foreign':row['snapshotQmlSource']='https://foreign.invalid/system/snapshot/NativeSnapshotReview.qml'
            elif fault=='blocked':row['snapshotSystemBlocked']=True
            else:row.update(snapshotFileOwned=False,snapshotFileName='')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):normal_input.observation(value,42)

    def test_reference_age_and_foreign_nonce_do_not_produce_an_effect(self):
        b=Boundary()
        with patch.object(normal_input,'urlopen',b.post):
            native=b.input();reference=controls.project(native.capture());old=deepcopy(reference)
            old['scope']['sampleEpochMs']-=4000;old['scope']['elapsedMs']=0
            with self.assertRaises(NativeUIError):native.snapshot_export_input('snapshot.save.0',reference=old)
            b.mutation='foreign-nonce'
            with self.assertRaises(NativeUIError):native.snapshot_export_input('snapshot.save.0',reference=reference)
        self.assertTrue(all(request['operation']=='observe' for request in b.requests))

    def test_native_controls_are_gated_and_real_system_presentation_blocks_underlying_qt_events(self):
        root=Path(__file__).resolve().parents[4]
        qml=(root/'scripts/system/snapshot/NativeSnapshotReview.qml').read_text()
        header=(root/'tests/device/native/IOSSnapshotExportControls.h').read_text()
        native=(root/'ios/snapshot/IOSSnapshotAdapter.mm').read_text()
        route=(root/'ios/ui/IOSNormalUiInput.cpp').read_text()
        self.assertIn('typeof Snapshot.featureObservationEnabled === "function"',qml)
        self.assertIn('root.featureObservation ? "snapshotSave" : ""',qml)
        self.assertIn('onClicked: root.exportImage(modelData.localPath, "save")',qml)
        self.assertIn('onClicked: root.exportImage(modelData.localPath, "share")',qml)
        self.assertIn('defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)',header)
        self.assertIn('featureSnapshotQtInputBlocked()',header)
        self.assertIn('controller.presentingViewController!=nil',native)
        self.assertIn('UIApplicationStateActive',native)
        self.assertIn('snapshotExportControlSource(control)!=_controls.value(controlId).source',route)
        self.assertNotIn('requestAuthorization',header);self.assertNotIn('exportImage(',header)


if __name__=='__main__':unittest.main()
