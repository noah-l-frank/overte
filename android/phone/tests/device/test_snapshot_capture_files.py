"""Actual fixed shell/file transport and private host filesystem counterprobes.

The target source producer is explicitly synthetic; separate Qt source tests
exercise the unchanged native Snapshot save method. No Android acceptance here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_capture_files import CaptureFileTransport,PhoneSnapshotCaptureFiles
from overte_phone_snapshot_capture_source import PhoneSnapshotCaptureFileSource
from adapters.normal_feature_state import PrivateFeatureState

RUN='a'*32;PREFIX='e2e-'+RUN;FILE='c'*32;CAPTURE='original_capture_1'
ANDROID='/data/user/0/io.github.noah_be.overte.phone/files/Snapshots/'
BODY=b'actual controlled host fixture original bytes\x00\xff'
CONTEXT=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='77:123',sessionId='own-session',generation=4,targetFingerprint='3'*64)


class LocalTransport(CaptureFileTransport):
    def __init__(self,root,artifact,guard=lambda:True):
        super().__init__(None,'host-synthetic-only','io.github.noah_be.overte.phone',
            {key:CONTEXT[key] for key in ('sourceRevision','artifactSha256','processIdentity')},guard,artifact)
        self.app=root;self.calls=[]
    def _execute(self,script,*arguments,timeout=20):
        self._check();self.calls.append((script,arguments,timeout))
        result=subprocess.run(['sh','-c',script,'host-explicit-shell-seam',*arguments],cwd=self.app,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        self._check();return result.stdout


class Producer:
    def __init__(self,app):
        self.app=app;self.directory=app/'files/Snapshots';self.directory.mkdir(parents=True,mode=0o700)
        self.epoch=100000;self.sequence=0;self.event=0;self.sent=[];self.last=None;self.time=0
        self.ignored=False;self.lost=False;self.switch=False;self.unlinks=0;self.outer='e'*32
        self.body=dict(phoneSnapshotCaptureFilesVersion=1,instance='d'*32,complete=True,sequence=0,
            capturedEpochMs=self.epoch,rows=[],plans=[],captures=[])
    def send(self,request):
        self.sent.append(deepcopy(request));self.last=deepcopy(request)
        if request['action'].endswith('observe'):return
        if self.ignored:return
        op=request['operation'];id=request['operationId'];run=request['runId'];root=self.directory.stat()
        if op=='plan':
            self.event+=1;self.body['plans'].append(dict(id=id,runId=run,prefix=request['prefix'],event=self.event,
                checkedEpochMs=self.epoch,rootPresent=True,rootDevice=root.st_dev,rootInode=root.st_ino,sealed=False,sealId='',sealedEpochMs=0))
        elif op=='retire':
            row=next(row for row in self.body['rows'] if row['id']==request['fileId'])
            path=self.directory/Path(row['path']).name
            if row['retireId']:return
            if row['nativeRemoved'] or not row['opened']:
                if path.exists():return
                row.update(retireId=id,absent=True,checkedEpochMs=self.epoch)
            else:
                info=path.stat()
                if info.st_ino!=row['inode'] or info.st_dev!=row['device'] or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:return
                row.update(retireId=id,deleteIssued=True,deleteResult=0);path.unlink();self.unlinks+=1
                row.update(absent=True,checkedEpochMs=self.epoch)
        elif op=='seal':
            plan=next(row for row in self.body['plans'] if row['id']==request['fileId'])
            if list(self.directory.glob(plan['prefix']+'-*')):return
            plan.update(sealed=True,sealId=id,sealedEpochMs=self.epoch)
        if self.lost:self.lost=False;raise RuntimeError('Explicit lost native ACK seam after original effect')
    def read(self):
        self.sequence+=1;self.body.update(sequence=self.sequence,capturedEpochMs=self.epoch)
        for row in self.body['rows']:
            if row['retireId'] and (self.directory/Path(row['path']).name).exists():self.body['complete']=False
        for plan in self.body['plans']:
            if plan['sealed'] and list(self.directory.glob(plan['prefix']+'-*')):self.body['complete']=False
        return json.dumps(dict(schemaVersion=1,requestId=self.last['commandId'],runId=self.last['runId'],instance=self.outer,
            sequence=self.sequence,processId=77,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,accepted=True,source=self.body))
    def reader(self,read_only=False):
        return PhoneSnapshotCaptureFileSource(self.send,self.read,lambda:self.epoch,lambda:True,77,
            read_only=read_only,monotonic=lambda:self.time,sleep=lambda seconds:None)
    def capture(self,*,pending=False,failed=False,open_failed=False):
        self.event+=1;self.epoch+=1;plan=self.body['plans'][-1];capture=CAPTURE if not self.body['captures'] else CAPTURE+'_'+str(len(self.body['captures']))
        file=FILE if not self.body['rows'] else format(len(self.body['rows']),'032x')
        path=self.directory/(plan['prefix']+'-'+capture+'.png');original=ANDROID+path.name
        if not open_failed:path.write_bytes(BODY)
        info=path.stat() if path.exists() else None;root=self.directory.stat()
        self.body['captures'].append(dict(captureId=capture,event=self.event,beganEpochMs=self.epoch,
            terminal='' if pending else 'error' if failed or open_failed else 'complete',terminalPath='' if pending or failed or open_failed else original,
            terminalEpochMs=0 if pending else self.epoch))
        row=dict(id=file,captureId=capture,path=original,planId=plan['id'],runId=plan['runId'],sha256='' if pending or open_failed else hashlib.sha256(BODY).hexdigest(),
            retireId='',deleteIssued=False,deleteResult=-2,absent=False,checkedEpochMs=0,phase='writing' if pending else 'open-failed' if open_failed else 'closed',
            preexisting=False,rootDevice=root.st_dev,rootInode=root.st_ino,device=info.st_dev if info else 0,inode=info.st_ino if info else 0,
            uid=info.st_uid if info else 0,links=1 if info else 0,opened=not open_failed,closed=not pending,bytes=0 if pending or open_failed else len(BODY),
            createdEpochMs=self.epoch,closedEpochMs=0 if pending else self.epoch,removeAttempted=False,removeAttempts=0,nativeRemoved=False)
        self.body['rows'].append(row);return row,path


class CaptureFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);os.chmod(self.root,0o700)
        self.producer=Producer(self.root);self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.owner_path=self.root/'owner.json';self.owner=self.make()
    def tearDown(self):self.temp.cleanup()
    def make(self,*,actor=False):
        artifact=self.artifacts
        owner_path=self.owner_path
        if actor:
            artifact=self.root/'actor';artifact.mkdir(mode=0o700,exist_ok=True);owner_path=self.root/'actor-owner.json'
        return PhoneSnapshotCaptureFiles(LocalTransport(self.root,artifact),self.producer.reader(actor),CONTEXT,owner_path,
            read_only=actor,clock_ms=lambda:self.producer.epoch)
    def ready(self):
        self.owner.plan(RUN,PREFIX);return self.producer.capture()
    def acquire(self):
        row,path=self.ready();value=self.owner.acquire(row['path'],row['captureId']);return row,path,value
    def test_actual_private_binary_inodes_and_fresh_reacquisition(self):
        row,path,value=self.acquire();self.assertEqual(path.stat().st_ino,value['inode'])
        self.assertEqual(BODY,(self.artifacts/value['artifact']).read_bytes());self.assertEqual(hashlib.sha256(BODY).hexdigest(),value['sha256'])
        self.producer.epoch+=5;second=self.owner.acquire(row['path'],row['captureId'])
        self.assertEqual(value['artifact'],second['artifact']);self.assertGreater(second['capturedEpochMs'],value['capturedEpochMs'])
        self.assertGreaterEqual(len(self.owner.transport.calls),8)
    def test_native_and_host_files_retire_once_and_fresh_second_check(self):
        row,path,value=self.acquire();self.owner.retire();self.owner.retire();self.assertEqual(1,self.producer.unlinks)
        self.assertFalse(path.exists());self.assertFalse((self.artifacts/value['artifact']).exists());self.assertTrue(self.make().require_retired()['retired'])
        self.assertTrue(self.owner_path.exists())
    def test_durable_plan_retry_observes_existing_owned_output_without_new_input(self):
        row,path=self.ready();self.owner.plan(RUN,PREFIX);self.make().plan(RUN,PREFIX)
        self.assertEqual(1,len(self.producer.body['plans']));self.assertEqual(1,len(self.producer.body['captures']));self.assertTrue(path.exists())
    def test_preflight_foreign_file_never_creates_native_plan_or_deletes(self):
        foreign=self.producer.directory/(PREFIX+'-user.png');foreign.write_bytes(BODY)
        with self.assertRaises(NativeUIError):self.owner.plan(RUN,PREFIX)
        self.assertFalse(self.producer.body['plans']);self.assertEqual(BODY,foreign.read_bytes())
    def test_same_bytes_foreign_target_inode_not_adopted_or_deleted(self):
        row,path=self.ready();path.rename(str(path)+'.foreign');path.write_bytes(BODY)
        with self.assertRaises(NativeUIError):self.owner.acquire(row['path'],row['captureId'])
        with self.assertRaises(NativeUIError):self.owner.retire()
        self.assertTrue(path.exists());self.assertEqual(0,self.producer.unlinks)
    def test_mutated_target_body_or_root_or_extra_original_stays_red(self):
        for fault in ('body','root','extra','symlink','hardlink'):
            with self.subTest(fault=fault):
                if fault!='body':self.tearDown();self.setUp()
                row,path=self.ready()
                if fault=='body':path.write_bytes(b'changed')
                elif fault=='root':self.producer.directory.rename(str(self.producer.directory)+'.old');self.producer.directory.mkdir();path.write_bytes(BODY)
                elif fault=='extra':(path.parent/(PREFIX+'-extra.png')).write_bytes(BODY)
                elif fault=='symlink':path.rename(str(path)+'.old');path.symlink_to(str(path)+'.old')
                else:os.link(path,str(path)+'.old')
                with self.assertRaises((NativeUIError,RuntimeError)):self.owner.retire()
                self.assertEqual(0,self.producer.unlinks)
    def test_partial_failed_and_native_removed_outputs_have_retirement_obligations(self):
        for native_removed in (False,True):
            if native_removed:self.tearDown();self.setUp()
            self.owner.plan(RUN,PREFIX);row,path=self.producer.capture(failed=True)
            if native_removed:path.unlink();row.update(removeAttempted=True,removeAttempts=1,nativeRemoved=True)
            with self.assertRaises(NativeUIError):self.owner.acquire(row['path'],row['captureId'])
            self.assertEqual(0 if native_removed else 1,len(self.owner.inventory()['files']))
            self.owner.retire();self.assertTrue(self.owner.require_retired()['retired'])
    def test_open_failed_absence_requires_actual_native_error_history(self):
        self.owner.plan(RUN,PREFIX);row,path=self.producer.capture(open_failed=True);self.owner.retire()
        self.assertFalse(path.exists());self.assertEqual(0,self.producer.unlinks)
    def test_actual_pending_producer_or_close_cannot_retire(self):
        self.owner.plan(RUN,PREFIX);row,path=self.producer.capture(pending=True)
        self.assertEqual(1,len(self.owner.inventory()['files']))
        with self.assertRaises(NativeUIError):self.owner.retire()
        self.assertTrue(path.exists())
    def test_missing_native_file_without_original_delete_intent_cannot_retire(self):
        row,path=self.ready();path.unlink()
        with self.assertRaises(NativeUIError):self.owner.retire()
    def test_lost_native_delete_ack_resumes_original_intent_without_resending(self):
        row,path,value=self.acquire();self.producer.lost=True
        with self.assertRaises(NativeUIError):self.owner.retire()
        self.assertFalse(path.exists());self.make().retire();self.assertEqual(1,self.producer.unlinks)
        self.assertEqual(1,len([item for item in self.producer.sent if item.get('operation')=='retire']))
    def test_ignored_delete_and_second_operation_cannot_turn_absence_green(self):
        row,path=self.ready();self.producer.ignored=True
        with self.assertRaises(NativeUIError):self.owner.retire()
        self.producer.ignored=False
        with self.assertRaises(NativeUIError):self.make().retire()
        self.assertTrue(path.exists());self.assertEqual(1,len([item for item in self.producer.sent if item.get('operation')=='retire']))
    def test_missing_changed_and_samebytes_replaced_private_artifact_are_rejected_before_target_delete(self):
        for fault in ('missing','body','inode'):
            if fault!='missing':self.tearDown();self.setUp()
            row,path,value=self.acquire();artifact=self.artifacts/value['artifact']
            if fault=='missing':artifact.unlink()
            elif fault=='body':artifact.write_bytes(b'changed')
            else:artifact.rename(str(artifact)+'.old');artifact.write_bytes(BODY);os.chmod(artifact,0o600)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,FileNotFoundError)):self.owner.retire()
            self.assertTrue(path.exists());self.assertEqual(0,self.producer.unlinks)
    def test_lost_host_delete_completion_uses_durable_intent_and_actual_absence(self):
        row,path,value=self.acquire();artifact=self.artifacts/value['artifact']
        # Actual unlink happens; a process interruption prevents terminal journal write.
        original=Path.unlink
        def interrupted(target,*args,**kwargs):
            result=original(target,*args,**kwargs)
            if target==artifact:raise RuntimeError('Synthetic process stop after actual host unlink')
            return result
        from unittest.mock import patch
        with patch.object(Path,'unlink',interrupted),self.assertRaises(RuntimeError):self.owner.retire()
        self.make().retire();self.assertTrue(self.make().require_retired()['retired'])
    def test_planned_collision_and_opened_incomplete_host_copy_stay_owned_and_red(self):
        row,path,value=self.acquire();state=PrivateFeatureState(self.owner_path).read();record=state['artifacts'][FILE]
        record.update(phase='planned',file=None);PrivateFeatureState(self.owner_path).write(state,PrivateFeatureState(self.owner_path).read())
        with self.assertRaises(NativeUIError):self.make().retire()
        self.assertTrue(path.exists())
    def test_interrupted_opened_copy_resumes_only_exact_owned_actual_prefix(self):
        row,path,value=self.acquire();state=PrivateFeatureState(self.owner_path).read();state['artifacts'][FILE]['phase']='opened'
        PrivateFeatureState(self.owner_path).write(state,PrivateFeatureState(self.owner_path).read())
        artifact=self.artifacts/value['artifact'];artifact.write_bytes(BODY[:9])
        self.make().retire();self.assertFalse(artifact.exists());self.assertFalse(path.exists())
    def test_late_target_or_host_original_cannot_hide_behind_old_retirement(self):
        row,path,value=self.acquire();self.owner.retire();path.write_bytes(BODY)
        with self.assertRaises(NativeUIError):self.make().require_retired()
        path.unlink();self.producer.body['complete']=True;(self.artifacts/value['artifact']).write_bytes(BODY)
        with self.assertRaises(NativeUIError):self.make().require_retired()
    def test_late_unknown_namespace_file_and_dropped_history_are_red(self):
        row,path,value=self.acquire();self.owner.retire();(path.parent/(PREFIX+'-late.png')).write_bytes(BODY)
        with self.assertRaises(NativeUIError):self.make().require_retired()
        (path.parent/(PREFIX+'-late.png')).unlink();self.producer.body['complete']=True;self.producer.body['rows']=[];self.producer.body['captures']=[]
        with self.assertRaises(NativeUIError):self.make().require_retired()
    def test_late_unknown_private_original_or_replaced_artifact_root_is_red(self):
        row,path,value=self.acquire();self.owner.retire()
        unknown=self.artifacts/('snapshot-owned-'+RUN+'-'+'9'*32+'.bin');unknown.write_bytes(BODY)
        with self.assertRaises(NativeUIError):self.make().require_retired()
        unknown.unlink();self.artifacts.rename(str(self.artifacts)+'.old');self.artifacts.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):self.make().require_retired()
    def test_restart_or_foreign_context_does_not_adopt_journal(self):
        row,path=self.ready();self.owner.inventory();self.producer.outer='f'*32
        with self.assertRaises(NativeUIError):self.make().retire()
        state=PrivateFeatureState(self.owner_path).read();state['binding']['sessionId']='foreign'
        PrivateFeatureState(self.owner_path).write(state,PrivateFeatureState(self.owner_path).read())
        with self.assertRaises(NativeUIError):self.make().inventory()
    def test_independent_actor_original_and_own_artifact_close_without_target_control(self):
        row,path,value=self.acquire();binding=self.owner.binding();actor=self.make(actor=True);actor.attach(binding)
        actual=actor.acquire(row['path'],row['captureId']);self.assertEqual(BODY,(self.root/'actor'/actual['artifact']).read_bytes())
        count=len(self.producer.sent)
        with self.assertRaises(NativeUIError):actor.plan(RUN,PREFIX)
        with self.assertRaises(NativeUIError):actor.retire()
        self.assertTrue(all(item['action'].endswith('observe') for item in self.producer.sent[count:]))
        self.owner.retire();actor.retire();actor.require_retired();self.assertFalse((self.root/'actor'/actual['artifact']).exists())
    def test_foundation_and_extended_scopes_are_separate_with_old_history_retained(self):
        foundation='parity-'+'b'*16+'-still-png';self.owner.plan('b'*32,foundation);row,path=self.producer.capture();self.owner.retire()
        second=PhoneSnapshotCaptureFiles(LocalTransport(self.root,self.artifacts),self.producer.reader(),CONTEXT,self.root/'extended.json',clock_ms=lambda:self.producer.epoch)
        second.plan(RUN,PREFIX);new,newpath=self.producer.capture();second.acquire(new['path'],new['captureId']);second.retire()
        self.assertEqual(2,len(self.producer.body['plans']));self.owner.require_retired();self.assertFalse(path.exists());self.assertFalse(newpath.exists())

if __name__=='__main__':unittest.main()
