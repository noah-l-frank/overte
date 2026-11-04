"""Original normal-input geometry grammar; native/DOM producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4 import browser_source as source
from adapters.script_journey.history import canonical
from self_tests import test_pico_tablet_web_flow as flow


class BrowserInputHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=flow.PicoTabletWebFlowTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.activate();f.primary.prepare();f.act('open')
        f.act('focus-type',dict(text='Overte ä Ω 東京 '+f.run))
        with f.target.lock.held():
            packet=f.primary.sample_native(f.primary.owner())
        self.rows=deepcopy(packet['source']['inputs'])
        self.documents={source.identity(row):row for row in packet['source']['documents']}
        self.request=next(row for row in reversed(f.target.command_log) if row['operation']=='observe')
        self.epoch=packet['capturedEpochMs']
        self.assertTrue(any(row['imeEpochMs'] is not None for row in self.rows))

    def validate(self,rows):
        return source.input_history(rows,self.request,self.epoch,self.documents)

    def test_actual_normal_inputs_decode_each_literal_once_per_validation_and_keep_all_checks(self):
        before=canonical(self.rows);calls=len(self.fixture.target.command_log)
        count=sum(row[key] is not None for row in self.rows for key in ('geometryRaw','focusRaw'))
        with patch.object(source,'decode',wraps=source.decode) as decode:
            self.assertIs(self.rows,self.validate(self.rows))
            self.assertEqual(2*count,decode.call_count)
            self.assertIs(self.rows,self.validate(self.rows))
            self.assertEqual(4*count,decode.call_count)
        self.assertEqual(before,canonical(self.rows))
        self.assertEqual(calls,len(self.fixture.target.command_log))

    def test_each_later_read_still_rejects_changed_original_geometry_and_focus(self):
        self.validate(self.rows)
        for mode in ('center','document','focus-sequence','cursor'):
            rows=deepcopy(self.rows)
            row=next(row for row in rows if row['imeEpochMs'] is not None)
            field='focusRaw' if mode=='focus-sequence' else 'geometryRaw'
            value=json.loads(json.loads(row[field]))
            if mode=='center':value['center']['x']+=1
            elif mode=='document':value['document']['href']+='?foreign'
            elif mode=='focus-sequence':value['sequence']=json.loads(json.loads(row['geometryRaw']))['sequence']
            else:value['editor']['cursor']=True
            row[field]=json.dumps(json.dumps(value))
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):self.validate(rows)
        self.assertIs(self.rows,self.validate(self.rows))

    def test_actual_duplicate_or_nonfinite_lexical_originals_are_not_normalized_before_refusal(self):
        for inner in ('{"requestId":"a","requestId":"b"}','{"x":NaN}'):
            rows=deepcopy(self.rows);rows[0]['geometryRaw']=json.dumps(inner)
            with self.subTest(inner=inner),self.assertRaises((NativeUIError,ValueError)):
                self.validate(rows)


if __name__=='__main__':unittest.main()
