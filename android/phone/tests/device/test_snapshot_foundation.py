"""Actual private files/journals; explicit normal-input and native-source seams.

The existing normal SNAP W3C/byte-decoder suite tests its input/render boundary
separately. This composition verifies strict foundation handback and recovery.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_foundation import PhoneSnapshotFoundation
from overte_phone_snapshot_capture_files import PhoneSnapshotCaptureFiles
from overte_phone_snapshot_settings import PhoneSnapshotSettings
from adapters.normal_feature_state import PrivateFeatureState
from test_snapshot_capture_files import Producer,LocalTransport,CONTEXT,BODY
from test_snapshot_settings import Boundary as SettingsBoundary


class Settings(SettingsBoundary):
    def send(self,request):
        super().send(request)
        if self.raw:
            value=json.loads(self.raw);value['processId']=77;self.raw=json.dumps(value)
    def reader(self):
        return PhoneSnapshotSettings(self.send,lambda:self.raw,lambda:self.epoch,lambda:True,77,
            monotonic=lambda:self.clock,sleep=self.sleep)


class Adapter:
    def __init__(self,root):
        self.root=root;self.artifacts=root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.producer=Producer(root);self.settings=Settings();self.open=False;self.alive=True;self.late=False;self.clock=0.
        self.owners=[];self.fault=None
    def state_path(self,selector):return self.root/'phone-state.json'
    def _snapshot_settings(self,selector,read_only=False):return self.settings.reader()
    def _snapshot_capture_files(self,selector,artifact,owner_path,read_only=False):
        value=PhoneSnapshotCaptureFiles(LocalTransport(self.root,artifact),self.producer.reader(read_only),CONTEXT,owner_path,
            read_only=read_only,clock_ms=lambda:self.producer.epoch);self.owners.append(value);return value
    def _snapshot_capture_file_source(self,selector,read_only=False):return self.producer.reader(read_only)
    def _snapshot_source(self,selector):return self
    def read(self,scope):
        history=dict(events=[])
        if self.late:history['events']=[dict(originalLateActivity=self.clock)]
        return dict(instance='e'*32,capturedEpochMs=self.settings.epoch,source=dict(review=dict(present=self.open),
            captures=[c for c in self.producer.body['captures'] if not c['terminal']],uploads=[],history=history,scriptHistory=dict(events=[])))
    def sleep(self,seconds):self.clock+=seconds;self.settings.sleep(seconds)
    def foundation(self,binding=CONTEXT,root=None):
        return PhoneSnapshotFoundation(self,'test',root or self.artifacts,binding,lambda:self.alive,
            monotonic=lambda:self.clock,sleep=self.sleep)


class Flow:
    """Explicit ordinary-input producer seam, never the production UI oracle."""
    def __init__(self,adapter,owner):
        self.adapter,self.owner=adapter,owner;self.state=dict(capturePending=False);self.ignore_close=False
    def invoke(self,operation,arguments):
        if operation=='snapshot.open':
            self.adapter.open=True;self.state['capturePending']=False
            self.adapter.settings.current['format'].update(set=True,value='png')
            self.adapter.settings.current['entries']['snapshotFormat'].update(present=True,value='png')
        elif operation=='snapshot.files':return self.owner.files(arguments['prefix'])
        elif operation=='snapshot.capture':
            self.state['capturePending']=True;self.adapter.producer.capture(pending=arguments.get('pending',False))
        elif operation=='snapshot.close':
            if not self.ignore_close:self.adapter.open=False
        else:raise AssertionError('Unknown explicit input seam')
        return dict(performed=True)


class SnapshotFoundationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-foundation-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.adapter=Adapter(self.root);self.owner=self.adapter.foundation();self.flow=Flow(self.adapter,self.owner)
    def invoke(self,op,args=None):return self.owner.invoke(self.flow,op,args or {})
    def captured(self):
        self.invoke('snapshot.open');name='parity-'+'b'*16+'-still-png';self.invoke('snapshot.files',dict(prefix=name))
        self.invoke('snapshot.capture');return self.invoke('snapshot.files',dict(prefix=name))['files'][0]
    def test_five_foundation_prefixes_own_real_bytes_then_complete_native_and_host_handback(self):
        scopes=[]
        for label in ('still-png','still-jpg','animated','panorama','cubemap'):
            self.invoke('snapshot.open');name='parity-'+'b'*16+'-'+label
            self.assertEqual({'files':[]},self.invoke('snapshot.files',dict(prefix=name)))
            scopes.append(self.owner.state['scope']);self.invoke('snapshot.capture')
            row=self.invoke('snapshot.files',dict(prefix=name))['files'][0]
            self.assertEqual(BODY,(self.adapter.artifacts/row['artifact']).read_bytes())
        self.assertEqual(1,len(set(scopes)));self.assertNotEqual('b'*32,scopes[0])
        self.assertEqual(5,len(self.adapter.producer.body['captures']))
        self.invoke('snapshot.close');self.assertGreaterEqual(self.adapter.clock,6)
        self.assertEqual([],list(self.adapter.producer.directory.iterdir()));self.assertEqual([],list(self.adapter.artifacts.iterdir()))
        self.assertIsNone(self.owner.store.read());self.assertFalse(list(self.root.glob('phone-snapshot-foundation-*-files.json')))
        self.assertEqual(self.adapter.settings.original,self.adapter.settings.current)
        self.assertTrue(all(plan['sealed'] for plan in self.adapter.producer.body['plans']))
        self.assertEqual(5,self.adapter.producer.unlinks)
        self.assertTrue(self.adapter.foundation().finalize())
    def test_open_close_without_capture_also_restores_settings_and_leaves_no_journal(self):
        self.invoke('snapshot.open');self.invoke('snapshot.close')
        self.assertEqual(self.adapter.settings.original,self.adapter.settings.current);self.assertIsNone(self.owner.store.read())
        self.assertEqual([],self.adapter.producer.body['plans'])
    def test_ignored_close_retains_original_journal_and_does_not_delete_any_output(self):
        row=self.captured();self.flow.ignore_close=True
        with self.assertRaises(NativeUIError):self.invoke('snapshot.close')
        self.assertIsNotNone(self.owner.store.read());self.assertTrue((self.adapter.artifacts/row['artifact']).exists())
        self.assertEqual(0,self.adapter.producer.unlinks)
        self.flow.ignore_close=False;self.invoke('snapshot.close');self.assertIsNone(self.owner.store.read())
    def test_missing_native_settings_restore_never_completes_after_file_cleanup(self):
        self.captured();self.adapter.settings.fault='unrestored'
        with self.assertRaises(NativeUIError):self.invoke('snapshot.close')
        self.assertEqual('restoring',self.owner.store.read()['phase'])
        operation=self.owner.store.read()['restoreId'];self.adapter.settings.fault=None
        self.invoke('snapshot.close');self.assertIsNone(self.owner.store.read())
        restores=[r for r in self.adapter.settings.calls if r['operation']=='restore']
        self.assertTrue(all(r['restoreId']==operation for r in restores))
    def test_partial_outputs_remain_owned_cannot_be_empty_preflight_or_pass_cleanup(self):
        self.invoke('snapshot.open');name='parity-'+'b'*16+'-animated';self.invoke('snapshot.files',dict(prefix=name))
        self.invoke('snapshot.capture',dict(pending=True))
        self.assertEqual({'files':[]},self.invoke('snapshot.files',dict(prefix=name)))
        self.assertEqual(1,len(self.owner.files_owner().inventory()['files']))
        self.flow.state['capturePending']=False
        with self.assertRaises(NativeUIError):self.invoke('snapshot.files',dict(prefix=name))
        with self.assertRaises(NativeUIError):self.invoke('snapshot.close')
        self.assertEqual(0,self.adapter.producer.unlinks);self.assertIsNotNone(self.owner.store.read())
    def test_lost_target_delete_reply_resumes_same_original_intent_once(self):
        self.captured();self.adapter.producer.lost=True
        with self.assertRaises(NativeUIError):self.invoke('snapshot.close')
        self.assertEqual(1,self.adapter.producer.unlinks);self.invoke('snapshot.close')
        self.assertEqual(1,self.adapter.producer.unlinks);self.assertIsNone(self.owner.store.read())
    def test_changed_process_or_artifact_root_cannot_adopt_pending_owner(self):
        self.captured()
        for binding,root in ((dict(CONTEXT,processIdentity='78:123'),None),(CONTEXT,self.root)):
            owner=self.adapter.foundation(binding,root);flow=Flow(self.adapter,owner)
            with self.subTest(binding=binding,root=root),self.assertRaises(NativeUIError):owner.invoke(flow,'snapshot.close',{})
        self.assertEqual(0,self.adapter.producer.unlinks)
    def test_ignored_file_delete_or_foreign_same_bytes_inode_cannot_be_handback(self):
        for fault in ('ignored','foreign'):
            # A fresh scenario for each actual namespace mutation.
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                adapter=Adapter(Path(directory));owner=adapter.foundation();flow=Flow(adapter,owner)
                owner.invoke(flow,'snapshot.open',{});name='parity-'+'b'*16+'-still-png';owner.invoke(flow,'snapshot.files',dict(prefix=name))
                owner.invoke(flow,'snapshot.capture',{});owner.invoke(flow,'snapshot.files',dict(prefix=name))
                if fault=='ignored':adapter.producer.ignored=True
                else:
                    path=next(adapter.producer.directory.iterdir());path.rename(str(path)+'.foreign');path.write_bytes(BODY)
                with self.assertRaises(NativeUIError):owner.invoke(flow,'snapshot.close',{})
                self.assertIsNotNone(owner.store.read());self.assertEqual(0,adapter.producer.unlinks)
    def test_late_original_activity_breaks_the_independent_three_second_window(self):
        self.captured();self.adapter.late=True
        with self.assertRaises(NativeUIError):self.invoke('snapshot.close')
        self.assertEqual(0,self.adapter.producer.unlinks);self.assertIsNotNone(self.owner.store.read())
    def test_lost_host_receipt_unlink_resumes_archival_against_fresh_native_originals(self):
        self.captured();original=PrivateFeatureState.discard;failure=[True]
        def discard(store,previous):
            if store.path.name.endswith('-files.json') and failure[0]:
                failure[0]=False;original(store,previous);raise OSError('Synthetic lost completion after actual receipt unlink')
            return original(store,previous)
        from unittest.mock import patch
        with patch.object(PrivateFeatureState,'discard',discard):
            with self.assertRaises(NativeUIError):self.invoke('snapshot.close')
        self.assertEqual('archiving',self.owner.store.read()['phase']);self.invoke('snapshot.close')
        self.assertIsNone(self.owner.store.read());self.assertEqual(1,self.adapter.producer.unlinks)


if __name__=='__main__':unittest.main()
