"""Actual private file/process and token-only readonly backend source checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from fixture.assets_originals import AssetsOriginals,original
from fixture.messages_mixer import start_identity
from fixture.domain import DomainControlHandler

ID='12345678-1234-4234-8234-123456789abc'
RUN='a'*32

class AssetsOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.path=self.root/'source';self.path.mkdir(mode=0o700)
        self.process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)','-t','3','--server-port','40102'])
        self.reader=AssetsOriginals(self.path,self.process,lambda pid:pid==self.process.pid,ID)
        self.value=dict(assetsBakeOriginalsVersion=2,instance='b'*32,sequence=1,processId=self.process.pid,processStart=start_identity(self.process.pid),
            domainId=ID,assetServerId=ID,capturedEpochMs=time.time_ns()//1000000,contextCapturedEpochMs=time.time_ns()//1000000,valid=True,jobs=[],mappings=[],blobs=[],pending=0)
        self.value['contextCapturedEpochMs']=self.value['capturedEpochMs']
        self.call=dict(schemaVersion=1,runId=RUN);self.file=self.path/'assets-bakes.json';self.write()
    def tearDown(self):self.process.terminate();self.process.wait(timeout=5);self.tmp.cleanup()
    def write(self):
        self.file.write_text(json.dumps(self.value));self.file.chmod(0o600)
    def test_actual_private_original_and_process_identity_are_preserved(self):
        self.assertEqual(self.value,self.reader.read(self.call)['source']);self.value['sequence']+=1;self.write()
        self.assertEqual(2,self.reader.read(self.call)['source']['sequence'])
    def test_missing_partial_stale_replaced_server_scope_and_counts_are_red(self):
        for change in (dict(valid=False),dict(contextCapturedEpochMs=self.value['capturedEpochMs']-5000),dict(contextCapturedEpochMs=self.value['capturedEpochMs']+1),dict(capturedEpochMs=self.value['capturedEpochMs']-5000),dict(processId=self.process.pid+1),dict(processStart='1'),dict(domainId='ffffffff-ffff-4fff-8fff-ffffffffffff'),dict(pending=1),dict(blobs=[dict(hash='c'*64,actualSha256='d'*64,bytes=1)])):
            old=deepcopy(self.value);self.value.update(change);self.write()
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):self.reader.read(self.call)
            self.value=old
        self.write();self.reader.read(self.call);self.value['assetServerId']='ffffffff-ffff-4fff-8fff-ffffffffffff';self.write()
        with self.assertRaises(NativeUIError):self.reader.read(self.call)
    def test_symlink_hardlink_fifo_replaced_directory_inode_or_file_are_red(self):
        self.reader.read(self.call)
        for kind in ('symlink','hardlink','fifo','file'):
            self.file.unlink();target=self.root/'outside';target.write_text(json.dumps(self.value));target.chmod(0o600)
            if kind=='symlink':self.file.symlink_to(target)
            elif kind=='hardlink':os.link(target,self.file)
            elif kind=='fifo':os.mkfifo(self.file,0o600)
            else:self.write()
            with self.subTest(kind=kind),self.assertRaises((NativeUIError,OSError)):self.reader.read(self.call)
        self.file.unlink();self.path.rmdir();self.path.mkdir(mode=0o700);self.write()
        with self.assertRaises(NativeUIError):self.reader.read(self.call)
    def test_worker_success_needs_actual_start_process_exit_and_terminal_originals(self):
        now=self.value['capturedEpochMs'];job=dict(instance='c'*32,hash='d'*64,path='/e2e-'+RUN+'/stand.fbx',version=7,queuedEpochMs=now-10,
            startedEpochMs=now-9,runExitedEpochMs=now-5,ovenProcessId=999,ovenFinishedEpochMs=now-8,exitCode=0,exitStatus=0,terminalEpochMs=now-7,outcome='complete',destroyedEpochMs=now-6)
        self.value['jobs']=[job];original(self.value)
        for change in (dict(ovenProcessId=None),dict(ovenFinishedEpochMs=None),dict(exitCode=1),dict(terminalEpochMs=now-9),dict(destroyedEpochMs=now-9)):
            bad=deepcopy(self.value);bad['jobs'][0].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):original(bad)
    def test_read_credentials_are_independent_and_cannot_write_permissions(self):
        class Handler(DomainControlHandler):
            token='permission-control-secret';assets_original_tokens=('primary-read-secret','actor-read-secret');assets_originals=None
            def log_message(self,*_args):pass
        control=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=control.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(control.server_address[1])
        def post(path,token,call):
            with urlopen(Request(url+path,data=json.dumps(call).encode(),headers={'X-Overte-E2E-Token':token}),timeout=2) as reply:return json.loads(reply.read())
        try:
            with self.assertRaises(HTTPError) as disabled:post('/v1/assets-originals','primary-read-secret',self.call)
            self.assertEqual(404,disabled.exception.code);disabled.exception.close()
            Handler.assets_originals=staticmethod(self.reader.read)
            for token in Handler.assets_original_tokens:self.assertEqual(self.value,post('/v1/assets-originals',token,self.call)['source'])
            with self.assertRaises(HTTPError) as write:post('/v1/assets-permissions','actor-read-secret',{})
            self.assertEqual(404,write.exception.code);write.exception.close()
            with self.assertRaises(HTTPError) as permission:post('/v1/assets-originals',Handler.token,self.call)
            self.assertEqual(404,permission.exception.code);permission.exception.close()
        finally:control.shutdown();control.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
