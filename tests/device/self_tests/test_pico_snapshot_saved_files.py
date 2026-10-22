"""Real private files/binary transfer; native readback endpoint is a named seam."""
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
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.android_snapshot_files import SnapshotFileError
from adapters.pico4.snapshot_exports import PicoSnapshotExports
from adapters.pico4.snapshot_saved_files import PicoSnapshotSavedFiles,META_SCRIPT,READ_SCRIPT
from self_tests.test_pico_snapshot_exports import packet,RUN

ID='d'*32
REQUEST='e'*32
JOB='f'*32
BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:original')


class PicoSnapshotSavedFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pico-saved-files-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);(self.root/'files').mkdir(mode=0o700)
        self.directory=self.root/'files'/('overte-snapshot-e2e-'+RUN);self.directory.mkdir(mode=0o700)
        self.content=b'actual independently transferred bytes\x00\xff';self.path=self.directory/(ID+'.bin')
        self.path.write_bytes(self.content);self.path.chmod(0o600);self.epoch=20000;self.clock=1.;self.calls=0;self.published=[]
        self.reader=object.__new__(PicoSnapshotExports);self.reader.pid=123;self.reader.clock_ms=lambda:self.epoch
        self.reader.request=self.readback
        self.owner=PicoSnapshotSavedFiles(None,'explicit-host-seam','org.overte.pico',BINDING,lambda:True,self.root/'artifacts',self.reader,RUN,self.publish)
        self.owner._execute=self.execute
    def readback(self,run):
        self.assertEqual(RUN,run);self.calls+=1
        original=dict(id=ID,request=REQUEST,path='/data/user/0/org.overte.pico/files/'+self.directory.name+'/'+ID+'.bin',phase='complete',
            bytes=len(self.content),sha256=hashlib.sha256(self.content).hexdigest(),capturedEpochMs=19900)
        body=dict(snapshotExportReadbacksVersion=1,instance='1'*32,sequence=self.calls,elapsedMs=self.calls,complete=True,copiesRetired=False,
            capturedEpochMs=self.epoch,workersTerminated=False,destinations=[dict(request=REQUEST,uri='content://media/external/images/media/1',inserted=True,published=True)],
            jobs=[dict(id=JOB,request=REQUEST,phase='complete',startedEpochMs=19800,completedEpochMs=19900,original=original)],files=[original],removedCopies=[])
        value=packet(PicoSnapshotExports.envelope(RUN),self.calls,self.epoch);value['readbacksRaw']=json.dumps(dict(accepted=False,source=body));return value
    def execute(self,script,*arguments,**_options):
        return subprocess.check_output(['sh','-c',script,'pico-original-test',*arguments],cwd=self.root,timeout=5)
    def publish(self,id,content):
        self.assertEqual(ID,id);self.published.append(content)
        target=self.root/'artifacts'/'original.bin'
        descriptor=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(content);stream.flush();os.fsync(stream.fileno())
        return target.name
    def test_actual_stat_hash_binary_and_published_bytes_keep_original_completion_separate(self):
        with patch('adapters.pico4.snapshot_saved_files.time.monotonic',side_effect=lambda:self.clock):result=self.owner.acquire_current(ID)
        self.assertEqual([self.content],self.published);self.assertEqual(self.content,(self.root/'artifacts'/result['artifact']).read_bytes())
        self.assertEqual(19900,result['originalCompletedEpochMs']);self.assertEqual(20000,result['capturedEpochMs'])
        self.assertEqual(self.path.stat().st_ino,result['inode']);self.assertEqual(self.path.stat().st_dev,result['device'])
        self.assertEqual(hashlib.sha256(self.content).hexdigest(),result['sha256']);self.assertIn('originalStat',result)
    def test_same_bytes_replacement_or_old_metadata_frame_cannot_qualify_original_copy(self):
        execute=self.execute
        def replace(script,*args,**kwargs):
            result=execute(script,*args,**kwargs)
            if script==READ_SCRIPT:
                replacement=self.path.with_suffix('.new');replacement.write_bytes(self.content);replacement.chmod(0o600);replacement.replace(self.path)
            return result
        self.owner._execute=replace
        with self.assertRaises(SnapshotFileError):self.owner.acquire_current(ID)
        self.assertEqual([],self.published)
        self.owner._execute=lambda *_a,**_k:b'OVT_SNAPSHOT_SAVED_META_V1\n1:2:3:1:600\n'+b'a'*64+b'\nOVT_SNAPSHOT_SAVED_META_END_V1\n'
        with self.assertRaises(SnapshotFileError):self.owner.metadata([self.directory.name,self.path.name])
    def test_final_publication_and_guard_cannot_age_sources_under_frozen_native_or_host_clock(self):
        for native,host in ((2000,0),(0,2)):
            self.epoch=20000;self.clock=1.;self.published=[]
            def publish(_id,_content):self.epoch+=native;self.clock+=host;return 'durably-retained.bin'
            self.owner.publish=publish
            with self.subTest(native=native,host=host),patch('adapters.pico4.snapshot_saved_files.time.monotonic',side_effect=lambda:self.clock),self.assertRaises(SnapshotFileError):self.owner.acquire_current(ID)
        self.assertEqual([],self.published)
    def test_symlink_or_public_permissions_never_get_transferred(self):
        self.path.chmod(0o644)
        with self.assertRaises(SnapshotFileError):self.owner.acquire_current(ID)
        self.path.unlink();self.path.symlink_to(self.root/'files')
        with self.assertRaises(SnapshotFileError):self.owner.acquire_current(ID)
        self.assertEqual([],self.published)


if __name__=='__main__':unittest.main()
