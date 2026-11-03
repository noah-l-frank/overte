"""Original Snapshot source acquisition after Close; native producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_base_frame import validate as base_frame, clocks as base_clocks
from adapters.pico4.snapshot_upload_owner import PicoSnapshotUploadOwner
from self_tests.test_pico_snapshot_background_owner import fixture


class SnapshotFrameAcquisitionTests(unittest.TestCase):
    def fixture(self, *, closed=True):
        records = fixture()
        header = records[-1]['header']
        original = deepcopy(records[-1]['state']['frames'][-1])
        current = deepcopy(original)
        if closed:
            ui = current['base']['ui']
            ui.update(open=False, ready=False, controls=[], generation=str(uuid.uuid4()))
            ui['picoSnapshotReview']['review']['visible'] = False
        calls = []
        owner = object.__new__(PicoSnapshotUploadOwner)
        owner.run, owner.binding = header['runId'], header['binding']
        epoch = json.loads(current['base']['native']['raw'])['capturedEpochMs']
        native = json.loads(original['base']['native']['raw'])
        path = original['base']['ui']['picoSnapshotReview']['review']['images'][0]['path']
        def read_base():
            calls.append('base')
            return deepcopy(current['base'])
        owner.base = SimpleNamespace(now=lambda:current['hostMonotonic'], read_frame=read_base,
            frame=lambda row:base_frame(row, owner.run, 123, owner.binding['sessionId']),clocks=base_clocks,
            state=dict(frames=[deepcopy(original['base'])],capture=dict(frame=0,file=dict(path=path),requestId=native['requests'][0]['requestId'])))
        owner.native = SimpleNamespace(pid=123,clock_ms=lambda:epoch)
        def upload(run):
            self.assertEqual(owner.run,run);calls.append('upload')
        owner.uploads = SimpleNamespace(read=upload, original=lambda:deepcopy(current['upload']))
        def account(sequence, **options):
            self.assertEqual(9,sequence);self.assertEqual(dict(require_account=True),options);calls.append('account')
            return json.loads(current['account']['raw'])
        owner.account = SimpleNamespace(sequence=9,read=account,original=lambda:current['account']['raw'])
        def provider():
            calls.append('provider')
            return deepcopy(current['provider'])
        owner.fixture = SimpleNamespace(provider=provider)
        return owner,current,calls

    def test_closed_sources_are_acquired_once_but_ordinary_upload_still_requires_open_review(self):
        owner,current,calls=self.fixture()
        observed=owner.read_source_frame()
        self.assertEqual(['base','upload','account','provider'],calls)
        self.assertFalse(observed['base']['ui']['open'])
        self.assertEqual(current,observed)
        self.assertIsNotNone(owner.anchor)
        with self.assertRaises(NativeUIError):owner.read_frame()
        self.assertEqual(['base','upload','account','provider']*2,calls)

    def test_foreign_or_malformed_original_remains_refused_without_an_open_page_fallback(self):
        for fault in ('foreign','malformed'):
            with self.subTest(fault=fault):
                owner,current,calls=self.fixture()
                if fault=='foreign':
                    value=json.loads(current['upload']['raw']);value['instance']='f'*32
                    current['upload']['raw']=json.dumps(value)
                    import hashlib
                    current['upload']['sha256']=hashlib.sha256(current['upload']['raw'].encode()).hexdigest()
                else:current['account']['raw']='{'  # Actual reader returns this unparsed original.
                with self.assertRaises((NativeUIError,ValueError)):owner.read_source_frame()
                self.assertEqual(1,calls.count('base'))
                self.assertFalse(current['base']['ui']['open'])
                self.assertFalse(hasattr(owner,'anchor'))

    def test_same_acquisition_keeps_the_existing_open_upload_validation(self):
        owner,current,calls=self.fixture(closed=False)
        observed=owner.read_frame()
        self.assertEqual(current,observed)
        self.assertEqual(['base','upload','account','provider'],calls)
        observed['base']['ui']['controls'].clear()
        self.assertTrue(current['base']['ui']['controls'])


if __name__=='__main__':unittest.main()
