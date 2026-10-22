"""Real fixed-shell binary acquisition over synthetic SDK/native-source seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

import test_snapshot_readback_source as source
from adapters.android_snapshot_files import SnapshotFileError
from overte_phone_snapshot_saved_files import PhoneSnapshotSavedFiles


class SdkBoundary:
    def __init__(self,app):self.app=app;self.fault='';self.calls=0;self.before_read=None
    def execute_bytes(self,args,*,target,timeout):
        assert target=='synthetic-readback-only' and args[0]=='exec-out'
        remote=shlex.split(args[1]);assert remote[:4]==['run-as','io.github.noah_be.overte.phone','sh','-c']
        assert remote[5]=='overte-snapshot-files'
        self.calls+=1
        if 'SAVED_BYTES_V1' in remote[4] and self.before_read:self.before_read()
        result=subprocess.run(['sh','-c',remote[4],*remote[5:]],cwd=self.app,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,check=False)
        raw=result.stdout
        if self.fault=='missing-footer' and 'SAVED_BYTES_V1' in remote[4]:return raw[:-2]
        if self.fault=='wrong-body' and 'SAVED_BYTES_V1' in remote[4]:return raw.replace(b'actual-provider-bytes',b'foreign-receiver-data')
        return raw


class SnapshotSavedFilesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-saved-streams-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.app=self.root/'synthetic app';self.app.mkdir()
        directory=self.app/'files'/('overte-snapshot-e2e-'+'e'*32);directory.mkdir(parents=True,mode=0o700)
        self.file=directory/(source.COPY+'.bin');self.file.write_bytes(b'actual-provider-bytes\0\xff\nindependent-original');self.file.chmod(0o600)
        self.sdk=SdkBoundary(self.app);self.boundary=source.Boundary();self.boundary.complete()
        original=self.boundary.component['files'][0];original.update(bytes=self.file.stat().st_size,sha256=hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.boundary.component['jobs'][0]['original']=deepcopy(original)
        self.context=dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='31:314159')
        self.reader=self.boundary.reader();self.artifacts=self.root/'artifacts'
        self.files=PhoneSnapshotSavedFiles(self.sdk,'synthetic-readback-only','io.github.noah_be.overte.phone',self.context,
            lambda:self.boundary.okay,self.artifacts,self.reader,source.RUN)

    def test_actual_binary_bytes_match_provider_original_and_are_published_privately(self):
        value=self.files.acquire(source.COPY);artifact=self.artifacts/value['artifact']
        self.assertEqual(self.file.read_bytes(),artifact.read_bytes());self.assertEqual('snapshot-saved-original',value['source'])
        self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(),value['sha256'])
        self.assertEqual(0o600,artifact.stat().st_mode&0o777);self.assertEqual(10000,value['capturedEpochMs'])
        self.assertNotIn('path',value);self.assertNotIn('uri',value)
        self.assertEqual(value,self.files.acquire(source.COPY))

    def test_input_accepts_only_copy_id_and_cannot_select_foreign_paths_or_results(self):
        for id in ('/tmp/foreign.png','../expected','content://expected/file','expected-digest'):
            with self.subTest(id=id),self.assertRaises(SnapshotFileError):self.files.acquire(id)
        self.assertEqual(0,self.sdk.calls)

    def test_old_or_foreign_or_missing_native_receipt_cannot_authorize_file_transfer(self):
        for fault in ('stale','uninitialized','missing','foreign-job','no-original'):
            with self.subTest(fault=fault):
                self.setUp()
                if fault=='stale':self.boundary.epoch+=2000
                elif fault=='uninitialized':
                    self.boundary.fault=lambda v:v.update(source=dict(accepted=False,source=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True)))
                elif fault=='missing':self.boundary.component['jobs']=[]
                elif fault=='foreign-job':self.boundary.component['jobs'][0]['request']='3'*32
                else:self.boundary.component['jobs'][0]['original']=None
                with self.assertRaises(SnapshotFileError):self.files.acquire(source.COPY)
                self.assertEqual(0,self.sdk.calls)

    def test_missing_binary_footer_or_wrong_transferred_bytes_remain_red(self):
        for fault in ('missing-footer','wrong-body'):
            with self.subTest(fault=fault):
                self.sdk.fault=fault
                with self.assertRaises(SnapshotFileError):self.files.acquire(source.COPY)
        self.assertEqual([],list(self.artifacts.iterdir()))

    def test_actual_file_alias_permission_or_same_bytes_replacement_is_rejected(self):
        for fault in ('symlink','hardlink','mode','replacement'):
            with self.subTest(fault=fault):
                self.setUp();raw=self.file.read_bytes()
                if fault=='symlink':
                    foreign=self.app/'foreign';foreign.write_bytes(raw);self.file.unlink();self.file.symlink_to(foreign)
                elif fault=='hardlink':(self.app/'foreign').hardlink_to(self.file)
                elif fault=='mode':self.file.chmod(0o644)
                else:
                    def replace():
                        held=self.file.with_suffix('.old');self.file.rename(held);self.file.write_bytes(raw);self.file.chmod(0o600)
                    self.sdk.before_read=replace
                with self.assertRaises(SnapshotFileError):self.files.acquire(source.COPY)

    def test_changed_original_bytes_between_metadata_and_transfer_are_rejected(self):
        self.sdk.before_read=lambda:self.file.write_bytes(b'a different actual provider copy')
        with self.assertRaises(SnapshotFileError):self.files.acquire(source.COPY)
        self.assertEqual([],list(self.artifacts.iterdir()))

    def test_native_source_replacement_or_retirement_during_transfer_is_rejected(self):
        for fault in ('instance','retired','pid','aged'):
            with self.subTest(fault=fault):
                self.setUp()
                def mutate():
                    if fault=='instance':self.boundary.component['instance']='3'*32
                    elif fault=='retired':self.boundary.component.update(copiesRetired=True,workersTerminated=True,files=[],removedCopies=[source.COPY])
                    elif fault=='pid':self.boundary.okay=False
                    else:self.boundary.epoch+=2000
                self.sdk.before_read=mutate
                with self.assertRaises(SnapshotFileError):self.files.acquire(source.COPY)

    def test_changed_host_artifact_is_not_silently_overwritten(self):
        value=self.files.acquire(source.COPY);path=self.artifacts/value['artifact'];path.write_bytes(b'foreign')
        with self.assertRaises(SnapshotFileError):self.files.acquire(source.COPY)
        self.assertEqual(b'foreign',path.read_bytes())

    def test_process_mismatch_cannot_construct_a_source_for_another_client(self):
        with self.assertRaises(SnapshotFileError):PhoneSnapshotSavedFiles(self.sdk,'synthetic-readback-only',
            'io.github.noah_be.overte.phone',self.context|dict(processIdentity='99:1'),lambda:True,
            self.artifacts,self.reader,source.RUN)


if __name__=='__main__':unittest.main()
