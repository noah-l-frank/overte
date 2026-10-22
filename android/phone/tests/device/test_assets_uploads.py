"""Passive normal-upload reader boundaries; no backend effect producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_assets_uploads import PhoneAssetsUploads,command,source
from adapters.normal_ui import NativeUIError
from appium_adapter import readonly_feature_command

RUN='a'*32
ID='12345678-1234-4234-8234-123456789abc'
EPOCH=1700000000000
SHA=hashlib.sha256(b'actual body').hexdigest()


def original():
    return dict(assetsUploadsVersion=1,instance='c'*32,runId=RUN,valid=True,retired=False,activeBundles=0,liveRequests=0,retainedBundles=1,bundles=[dict(
        id=ID,runId=RUN,directorySha256=SHA,destination='/e2e-'+RUN+'/',primary='stand.fbx',files=[dict(relativePath='stand.fbx',filenameSha256=SHA)],
        connection=dict(domainId=ID,sessionId=ID,assetServerId=ID),createdEpochMs=EPOCH-10,active=False,finishedEpochMs=EPOCH,errorSha256=SHA,
        requests=[dict(instance='d'*32,kind='upload',issuedEpochMs=EPOCH-9,completedEpochMs=EPOCH-5,destroyedEpochMs=EPOCH-4,
            original=dict(filenameSha256=SHA,originalSha256=SHA,originalBytes=11,errorCode=0,returnedHash=SHA)),
            dict(instance='e'*32,kind='mapping',issuedEpochMs=EPOCH-3,completedEpochMs=EPOCH-2,destroyedEpochMs=EPOCH-1,
                original=dict(path='/e2e-'+RUN+'/stand.fbx',hash=SHA,errorCode=0))])])


class Boundary:
    def __init__(self):self.packet=None;self.seq=0;self.epoch=EPOCH;self.elapsed=0;self.fault=lambda value:None
    def send(self,call):
        self.seq+=1;self.packet=dict(schemaVersion=1,requestId=call['commandId'],runId=RUN,operation=call['operation'],instance='b'*32,
            sequence=self.seq,processId=321,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=original());self.fault(self.packet)
    def reader(self):return PhoneAssetsUploads(self.send,lambda:json.dumps(self.packet),lambda:self.epoch,lambda:True,321,monotonic=lambda:self.elapsed,sleep=lambda _:None)


class AssetsUploadsTests(unittest.TestCase):
    def test_full_originals_are_preserved_without_an_effect_verdict(self):
        b=Boundary();reader=b.reader();self.assertEqual(original(),reader.request('observe',RUN)['source'])
        self.assertEqual(2,reader.request('observe',RUN)['sequence'])
    def test_missing_false_boolean_counts_and_dead_unfinished_are_red(self):
        faults=[lambda s:s.update(valid=False),lambda s:s.pop('retired'),lambda s:s.update(activeBundles=False),lambda s:s.update(liveRequests=1),
            lambda s:s['bundles'][0]['requests'][0].update(completedEpochMs=None),lambda s:s['bundles'][0]['requests'][0].update(destroyedEpochMs=EPOCH-8),
            lambda s:s['bundles'][0]['requests'][0]['original'].update(returnedHash='f'*64),lambda s:s['bundles'][0]['requests'][1]['original'].update(path='/foreign/stand.fbx'),
            lambda s:s['bundles'][0]['files'].append(deepcopy(s['bundles'][0]['files'][0])),lambda s:s.update(retired=True)]
        for fault in faults:
            b=Boundary();b.fault=lambda p:fault(p['source'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().request('observe',RUN)
    def test_wrong_process_replay_replaced_scope_stale_and_real_slow_reads_are_red(self):
        for fault in (lambda p:p.update(processId=322),lambda p:p.update(capturedEpochMs=EPOCH-2000),lambda p:p.update(sequence=False)):
            b=Boundary();b.fault=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().request('observe',RUN)
        for fault in (lambda p:p.update(sequence=1),lambda p:p['source'].update(instance='f'*32)):
            b=Boundary();reader=b.reader();reader.request('observe',RUN);b.fault=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.request('observe',RUN)
        b=Boundary();reader=b.reader();old=reader.original
        def slow():b.elapsed+=5.1;return old()
        reader.original=slow
        with self.assertRaises(NativeUIError):reader.request('observe',RUN)
    def test_release_requires_exact_original_identity_and_readonly_has_no_release(self):
        observe=dict(schemaVersion=1,commandId='b'*32,action='phone-assets-uploads',operation='observe',runId=RUN)
        readonly_feature_command(observe)
        release=observe|dict(operation='release',instance='c'*32,bundleIds=[ID]);command(release)
        with self.assertRaises((ValueError,NativeUIError)):readonly_feature_command(release)
        for bad in (release|dict(instance='0'*32),release|dict(bundleIds=[ID,ID]),observe|dict(expected={})):
            with self.assertRaises(NativeUIError):command(bad)

if __name__=='__main__':unittest.main()
