"""Synthetic original native event packets test the reader, never Qt behavior."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.prepared_field_commit import OriginalCommit,digest,validate as validate_native

RUN='a'*32
PID=123
NONCE='b'*32
SOURCE='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml'


def validate(value,request_id,run,pid,epoch_ms):
    return validate_native(value,request_id,run,pid,epoch_ms,original_component_url=SOURCE)


def sample(*,nonce=NONCE,sequence=1,kind=None,reason=None,elapsed=100):
    events=[dict(sequence=1,kind='captured',reason='none',capturedEpochMs=20000,elapsedMs=0)]
    if kind is not None:
        events.append(dict(sequence=2,kind=kind,reason=reason or ('context-retired' if kind=='rejected' else
            'hold-deadline' if kind=='expired' else 'none'),capturedEpochMs=20000+elapsed,elapsedMs=elapsed))
    return dict(pendingFieldCommitVersion=1,requestId=nonce,instance='c'*32,eventId='d'*32,
        sequence=sequence,processId=PID,createdEpochMs=20000,capturedEpochMs=20000+elapsed,elapsedMs=elapsed,
        pending=kind is None,source=dict(componentUrl='qrc:/qml/hifi/dialogs/TabletRunningScripts.qml',
        fieldName='scriptFilter',initialTextSha256=digest('retry-'+RUN),inputSha256=digest('Overte ä Ω 東京 '+RUN),
        inputCodeUnits=len(('Overte ä Ω 東京 '+RUN).encode('utf-16-le'))//2),events=events)


class PreparedFieldCommitReader(unittest.TestCase):
    def test_actual_original_receipt_prefix_is_pinned_before_retired_attempt(self):
        reader=OriginalCommit(RUN,PID,SOURCE);value=reader.read(sample(),NONCE,20100)
        value['source']['fieldName']='forged'
        with self.assertRaises(ValueError):reader.retired_attempt()
        current=sample(nonce='e'*32,sequence=2,kind='rejected',elapsed=300)
        reader.read(current,'e'*32,20300)
        self.assertEqual(current['events'][-1],reader.retired_attempt())
        self.assertEqual('scriptFilter',reader.previous['source']['fieldName'])

    def test_release_expiry_send_and_other_rejections_are_not_stale_context_success(self):
        for kind,reason,elapsed in [('released','none',100),('expired','hold-deadline',10000),
                ('sent','none',100),('rejected','focus-lost',100),('rejected','editor-changed',100)]:
            with self.subTest(kind=kind,reason=reason):
                reader=OriginalCommit(RUN,PID,SOURCE)
                reader.read(sample(kind=kind,reason=reason,elapsed=elapsed),NONCE,20000+elapsed)
                with self.assertRaises(ValueError):reader.retired_attempt()

    def test_wrong_nonce_pid_run_clock_and_extra_verdict_are_rejected(self):
        for change in ({'requestId':'f'*32},{'processId':PID+1},{'capturedEpochMs':18000},
                       {'elapsedMs':5000},{'pendingFieldCommitVersion':True},{'passed':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate(dict(sample(),**change),NONCE,RUN,PID,20100)
        with self.assertRaises(ValueError):validate(sample(),NONCE,'f'*32,PID,20100)
        with self.assertRaises(ValueError):validate(sample(),NONCE,RUN,PID,25000)

    def test_source_and_input_identity_cannot_be_replaced_with_expected_labels(self):
        for change in ({'fieldName':'password'},{'componentUrl':'https://owned.test/hifi/dialogs/TabletRunningScripts.qml'},
                       {'componentUrl':'file:///foreign/hifi/dialogs/TabletRunningScripts.qml'},
                       {'inputSha256':'f'*64},{'initialTextSha256':'f'*64},{'inputCodeUnits':True}):
            value=sample();value['source'].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(value,NONCE,RUN,PID,20100)

    def test_terminal_history_cannot_regress_change_identity_or_be_retimed(self):
        original=sample(kind='rejected',elapsed=300)
        for change in ({'instance':'f'*32},{'eventId':'f'*32},{'createdEpochMs':20001},
                       {'sequence':1},{'pending':True}):
            reader=OriginalCommit(RUN,PID,SOURCE);reader.read(original,NONCE,20300)
            value=sample(nonce='e'*32,sequence=2,kind='rejected',elapsed=500);value.update(change)
            # Preserve the original terminal event unless this is the explicit
            # regression case. A current snapshot is not a new event time.
            value['events']=deepcopy(original['events'])
            with self.subTest(change=change),self.assertRaises(ValueError):reader.read(value,'e'*32,20500)
        reader=OriginalCommit(RUN,PID,SOURCE);reader.read(original,NONCE,20300)
        with self.assertRaises(ValueError):reader.read(sample(nonce='e'*32,sequence=2,kind='rejected',elapsed=500),'e'*32,20500)

    def test_missing_terminal_receipt_and_expired_or_replayed_capture_cannot_pass(self):
        for value in (dict(sample(),pending=False),sample(elapsed=10000),dict(sample(),events=[])):
            with self.subTest(value=value),self.assertRaises(ValueError):validate(value,NONCE,RUN,PID,value['capturedEpochMs'])
        reader=OriginalCommit(RUN,PID,SOURCE);reader.read(sample(),NONCE,20100)
        with self.assertRaises(ValueError):reader.read(sample(sequence=2),NONCE,20100)
        with self.assertRaises(ValueError):reader.read(sample(),[],20100)

    def test_later_fresh_snapshot_keeps_original_terminal_time_and_release_inventory(self):
        reader=OriginalCommit(RUN,PID,SOURCE);old=sample(kind='rejected',elapsed=300)
        reader.read(old,NONCE,20300)
        current=sample(nonce='ios-'+'e'*32,sequence=2,kind='rejected',elapsed=600)
        current['events']=deepcopy(old['events'])
        reader.read(current,current['requestId'],20600)
        self.assertEqual(20300,reader.retired_attempt()['capturedEpochMs'])
        self.assertFalse(reader.previous['pending'])

    def test_malformed_event_order_or_input_deadline_cannot_be_normalized(self):
        for change in ({'sequence':3},{'kind':'accepted'},{'reason':'none'},{'elapsedMs':10000},
                       {'capturedEpochMs':19999}):
            value=sample(kind='rejected',elapsed=300);value['events'][-1].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):validate(value,NONCE,RUN,PID,20300)


if __name__=='__main__':unittest.main()
