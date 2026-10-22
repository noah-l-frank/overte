"""Original capture metadata joins over explicit Qt facts; no compilation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_capture_controls as controls,normal_input
from ios.self_tests.test_ios_normal_input import Boundary


def original():
    value=Boundary(field='snapshot.capture').observed();value.update(snapshotCaptureControlsVersion=1,tabletShown=True)
    value['sampleEpochMs']=int(value['sampleEpochMs']);row=value['controls'][0]
    row.update(snapshotCaptureControlVersion=1,snapshotRootId='11111111-2222-4333-8444-777777777777',
        snapshotQmlSource='qrc:/scripts/system/snapshot/NativeSnapshotReview.qml',snapshotNameSha256=controls.EMPTY,
        snapshotName='',snapshotNameOwned=False,snapshotMode=2,snapshotFormat='jpg',snapshotCapturing=False,
        snapshotProcessing=False,snapshotSettingsLoaded=True,snapshotStatusError=False,snapshotImageCount=0,
        snapshotSystemBlocked=False,inputReady=True)
    return value


class CaptureBoundary(Boundary):
    def __init__(self,field='snapshot.capture'):
        super().__init__(field=field);self.name='';self.changed=False
    def observed(self):
        value=super().observed();value.update(snapshotCaptureControlsVersion=1,tabletShown=True)
        value['sampleEpochMs']=int(value['sampleEpochMs']);row=value['controls'][0]
        row.update({key:original()['controls'][0][key] for key in controls.FIELDS})
        owned=bool(controls.PREFIX.fullmatch(self.name));row.update(snapshotNameOwned=owned,
            snapshotName=self.name if owned else '',snapshotNameSha256=hashlib.sha256(self.name.encode()).hexdigest())
        if self.changed:row.update(snapshotSystemBlocked=True,inputReady=False)
        return value
    def post(self,request,timeout):
        import json
        payload=json.loads(request.data);response=super().post(request,timeout)
        if payload['operation']=='edit' and payload['input']['operation']=='replace':self.name=payload['input']['text']
        return response


class SnapshotCaptureControlTests(unittest.TestCase):
    def test_actual_settings_name_and_root_are_original_target_metadata_not_capture_results(self):
        value=original();projected=controls.project(value);row=projected['controls'][0]
        self.assertEqual((2,'jpg',controls.EMPTY),(row['snapshotMode'],row['snapshotFormat'],row['snapshotNameSha256']))
        later=deepcopy(projected);later['scope']['sampleEpochMs']+=2;later['scope']['elapsedMs']+=2
        self.assertEqual(row,controls.same_reference(projected,later,'snapshot.capture'))
        self.assertNotIn('captureHistory',projected);self.assertNotIn('files',projected)

    def test_changed_title_mode_format_root_or_processing_prevents_use_of_old_reference(self):
        value=controls.project(original())
        for key,changed in [('snapshotNameSha256','a'*64),('snapshotMode',1),('snapshotFormat','png'),
            ('snapshotRootId','11111111-2222-4333-8444-888888888888'),('snapshotProcessing',True)]:
            later=deepcopy(value);later['controls'][0][key]=changed
            with self.subTest(key=key),self.assertRaises(NativeUIError):controls.same_reference(value,later,'snapshot.capture')

    def test_controlled_title_hash_must_match_and_foreign_name_is_only_a_redacted_hash(self):
        value=original();row=value['controls'][0];row.update(snapshotNameOwned=True,snapshotName='parity-'+'a'*16+'-animated')
        with self.assertRaises(NativeUIError):controls.project(value)
        row['snapshotNameSha256']=hashlib.sha256(row['snapshotName'].encode()).hexdigest();controls.project(value)
        row.update(snapshotName='private foreign title',snapshotNameOwned=False)
        with self.assertRaises(NativeUIError):controls.project(value)
        row['snapshotName']='';controls.project(value)

    def test_mixed_actual_roots_or_ready_under_a_native_sheet_cannot_qualify(self):
        for fault in ('root','name','blocked','version','count'):
            value=original();row=deepcopy(value['controls'][0]);row.update(id='snapshot.name',token='11111111-2222-4333-8444-888888888888')
            value['controls'].append(row)
            if fault=='root':row['snapshotRootId']='11111111-2222-4333-8444-888888888888'
            elif fault=='name':row['snapshotNameSha256']='f'*64
            elif fault=='blocked':row['snapshotSystemBlocked']=True
            elif fault=='version':row['snapshotCaptureControlVersion']=True
            else:row['snapshotImageCount']=9
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):controls.project(value)

    def test_qml_properties_are_passive_and_disabled_without_actual_feature_api(self):
        root=Path(__file__).resolve().parents[4];qml=(root/'scripts/system/snapshot/NativeSnapshotReview.qml').read_text()
        native=(root/'tests/device/native/IOSSnapshotCaptureControls.h').read_text()
        self.assertIn('readonly property string featureCaptureName: featureObservation ? captureName.text : ""',qml)
        self.assertIn('featureSnapshotQtInputBlocked()',native);self.assertIn('NormalControlUi::ownsPoint',native)
        self.assertNotIn('setSnapshotFormat(',native);self.assertNotIn('takeSnapshot(',native)

    def test_real_native_input_route_sends_only_current_capture_token_and_no_effect_verdict(self):
        boundary=CaptureBoundary()
        with patch.object(normal_input,'urlopen',boundary.post):
            native=boundary.input();reference=controls.project(native.capture())
            self.assertEqual(dict(performed=True),native.snapshot_capture_input('snapshot.capture','activate',reference=reference))
        self.assertEqual(['observe','observe','edit'],[row['operation'] for row in boundary.requests])
        command=boundary.requests[-1]['input'];self.assertEqual('activate',command['operation']);self.assertEqual(boundary.token,command['fieldToken'])
        self.assertNotIn('files',command);self.assertNotIn('captureHistory',command)

    def test_normal_key_route_can_restore_the_actual_empty_title_without_legacy_prefix_relaxation(self):
        boundary=CaptureBoundary('snapshot.name');title='parity-'+'a'*16+'-still-png'
        with patch.object(normal_input,'urlopen',boundary.post):
            native=boundary.input();reference=controls.project(native.capture())
            native.snapshot_capture_input('snapshot.name','replace',reference=reference,text=title)
            reference=controls.project(native.capture());self.assertEqual(title,reference['controls'][0]['snapshotName'])
            native.snapshot_capture_input('snapshot.name','replace',reference=reference,text='')
            self.assertEqual(controls.EMPTY,controls.project(native.capture())['controls'][0]['snapshotNameSha256'])
            with self.assertRaises((NativeUIError,ValueError)):native.edit('replace','',field='snapshot.name')
        self.assertEqual([title,''],[row['input']['text'] for row in boundary.requests if row['operation']=='edit'])

    def test_foreign_title_or_new_system_sheet_prevents_any_real_edit_post(self):
        for fault in ('foreign-title','sheet','legacy'):
            boundary=CaptureBoundary('snapshot.name')
            if fault=='foreign-title':boundary.name='private foreign draft'
            with patch.object(normal_input,'urlopen',boundary.post):
                native=boundary.input();reference=controls.project(native.capture())
                if fault=='sheet':boundary.changed=True
                if fault=='legacy':reference['iosSnapshotCaptureControlsVersion']=True
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):native.snapshot_capture_input('snapshot.name','replace',reference=reference,text='')
            self.assertFalse(any(row['operation']=='edit' for row in boundary.requests))


if __name__=='__main__':unittest.main()
