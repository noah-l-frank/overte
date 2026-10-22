"""Actual native private-file source on this host; no device or mock filesystem."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_create_files import PhoneCreateFiles,command,source
from overte_phone_create_file_owner import OwnedCreateFiles
from overte_phone_create_fixture import documents

RUN='b'*32
TICKET='c'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
BINDING=dict(sourceRevision='a'*40,artifactSha256='a'*64,processIdentity='process:31',
             sessionId='owned',generation=1,targetFingerprint='a'*64)
CPP=r'''#include "tests/device/native/PrivateCreateFiles.h"
#include <iostream>
int main(int argc,char** argv) {
    QCoreApplication app(argc,argv);overte::e2e::PrivateCreateFiles files;
    std::string line;while(std::getline(std::cin,line)) {
        auto command=QJsonDocument::fromJson(QByteArray::fromStdString(line)).object().toVariantMap();
        auto result=files.request(QString::fromLocal8Bit(argv[1]),command);
        std::cout<<QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).toStdString()<<std::endl;
    }
}
'''


class NativeFiles:
    def __init__(self,executable,directory):
        self.directory=Path(directory);self.sequence=0;self.value=None;self.commands=[]
        self.process=subprocess.Popen([str(executable),str(directory),'--testScript'],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.fault=None;self.drop=None;self.guard_ok=True
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=5)
        self.process.stdout.close();self.process.stderr.close()
    def send(self,request):
        self.commands.append(deepcopy(request));requested=int(time.time()*1000)
        self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
        original=json.loads(self.process.stdout.readline());self.sequence+=1
        self.value=dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],operation=request['operation'],
            instance='a'*32,sequence=self.sequence,processId=self.process.pid,requestedEpochMs=requested,
            capturedEpochMs=int(time.time()*1000),source=original)
        if self.fault:self.fault(self.value)
        if self.drop==request['operation']:raise NativeUIError('Synthetic response loss after native effect')
    def reader(self):
        return PhoneCreateFiles(self.send,lambda:json.dumps(self.value),lambda:int(time.time()*1000),
                                lambda:self.guard_ok,self.process.pid)
    def raw(self,operation,owner='d'*64,files=None):
        call=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-create-files',operation=operation,
                  runId=RUN,ownerToken=owner)
        if files is not None:call['files']={name:base64.b64encode(raw).decode() for name,raw in files.items()}
        self.send(call);return self.value['source']
    @property
    def root(self):return self.directory/('feature-create-'+RUN)


class CreateFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build=ROOT/'build/create-native-contract';build.mkdir(parents=True,exist_ok=True)
        cls.build=tempfile.TemporaryDirectory(prefix='files-',dir=build)
        cpp=Path(cls.build.name)/'files.cpp';cpp.write_text(CPP)
        cls.executable=cpp.with_suffix('')
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
        subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-I'+str(ROOT),str(cpp),'-o',str(cls.executable),*flags],check=True,timeout=60)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.base=Path(self.temporary.name)
        self.native=NativeFiles(self.executable,self.base)
    def tearDown(self):self.native.close();self.temporary.cleanup()
    def owner(self):
        return OwnedCreateFiles(self.native.reader(),PrivateFeatureState(self.base/'owner.json'),BINDING,RUN,TICKET,URL)
    def test_real_stage_reads_exact_input_bytes_and_never_writes_output(self):
        owner=self.owner();directory=owner.prepare()
        self.assertTrue(directory.endswith('/feature-create-'+RUN))
        for name,raw in documents(RUN,TICKET,URL).items():
            self.assertEqual(raw,(self.native.root/name).read_bytes())
            self.assertEqual(0o600,(self.native.root/name).stat().st_mode&0o777)
        self.assertFalse((self.native.root/'selection.json').exists())
        self.assertEqual(0o700,self.native.root.stat().st_mode&0o777)
    def test_real_product_output_is_separately_read_sealed_and_retired(self):
        owner=self.owner();owner.prepare();path=owner.begin_export();raw=b'{"actual":"ordinary-product-output"}\n'
        Path(path.removeprefix('file://')).write_bytes(raw)
        self.assertEqual(raw,owner.finish_export())
        owner.cleanup();self.assertFalse(self.native.root.exists())
        retained=[]
        owner.retire(lambda value:retained.append(value) or hashlib.sha256(
            json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        self.assertIsNone(owner.store.read());self.assertEqual('retired',retained[0]['phase'])
    def test_unissued_reserved_owner_can_retire_absence_without_staging(self):
        owner=self.owner();owner.cleanup();self.assertFalse(self.native.root.exists())
        self.assertNotIn('stage',[call['operation'] for call in self.native.commands])
    def test_lost_stage_response_is_reconciled_without_reissuing_stage(self):
        owner=self.owner();self.native.drop='stage'
        with self.assertRaises(NativeUIError):owner.prepare()
        self.native.drop=None;restored=self.owner();restored.prepare()
        self.assertEqual(1,[call['operation'] for call in self.native.commands].count('stage'))
        restored.cleanup();self.assertFalse(self.native.root.exists())
    def test_existing_foreign_root_is_never_adopted_or_removed(self):
        self.native.root.mkdir(mode=0o700);sentinel=self.native.root/'foreign';sentinel.write_bytes(b'preserve')
        owner=self.owner()
        with self.assertRaises(NativeUIError):owner.prepare()
        with self.assertRaises(NativeUIError):owner.cleanup()
        self.assertEqual(b'preserve',sentinel.read_bytes())
    def test_real_symlink_hardlink_fifo_and_directory_outputs_are_rejected(self):
        for kind in ('symlink','hardlink','fifo','directory'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as directory:
                native=NativeFiles(self.executable,directory)
                try:
                    native.raw('stage',files=documents(RUN,TICKET,URL));output=native.root/'selection.json'
                    foreign=Path(directory)/'foreign';foreign.write_bytes(b'preserve')
                    if kind=='symlink':output.symlink_to(foreign)
                    elif kind=='hardlink':os.link(foreign,output)
                    elif kind=='fifo':os.mkfifo(output,0o600)
                    else:output.mkdir(mode=0o700)
                    self.assertEqual({},native.raw('observe'));self.assertEqual({},native.raw('release'))
                    self.assertEqual(b'preserve',foreign.read_bytes());self.assertTrue(native.root.exists())
                finally:native.close()
    def test_wrong_owner_unknown_child_and_replaced_input_block_release(self):
        self.native.raw('stage',files=documents(RUN,TICKET,URL))
        self.assertEqual({},self.native.raw('release',owner='e'*64))
        child=self.native.root/'unknown';child.write_bytes(b'preserve')
        self.assertEqual({},self.native.raw('release'));child.unlink()
        original=self.native.root/'entity-import.json';original.write_bytes(b'foreign')
        self.assertEqual({},self.native.raw('release'));self.assertTrue(original.exists())
    def test_replaced_root_and_changed_sealed_output_cannot_be_retired(self):
        owner=self.owner();owner.prepare();path=Path(owner.begin_export().removeprefix('file://'));path.write_bytes(b'original')
        owner.finish_export();path.write_bytes(b'changed')
        with self.assertRaises(NativeUIError):owner.cleanup()
        self.assertEqual(b'changed',path.read_bytes())
    def test_output_before_export_intent_cannot_be_claimed(self):
        owner=self.owner();owner.prepare();(self.native.root/'selection.json').write_bytes(b'foreign')
        with self.assertRaises(NativeUIError):owner.begin_export()
        with self.assertRaises(NativeUIError):owner.cleanup()
        self.assertTrue(self.native.root.exists())
    def test_native_stage_is_exclusive_and_retired_run_cannot_be_staged_again(self):
        inputs=documents(RUN,TICKET,URL);self.native.raw('stage',files=inputs)
        self.assertEqual({},self.native.raw('stage',files=inputs))
        self.assertTrue(self.native.raw('release')['retired'])
        self.assertEqual({},self.native.raw('stage',files=inputs))
        self.assertTrue(self.native.raw('observe')['retired'])
    def test_packet_tampering_never_replaces_original_file_bytes(self):
        for fault in (lambda p:p.update(processId=1),lambda p:p.update(operation='release'),
                      lambda p:p['source'].update(files=[]),lambda p:p['source']['files'][0].update(sha256='0'*64)):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                native=NativeFiles(self.executable,directory)
                try:
                    reader=native.reader();reader.request('stage',RUN,'d'*64,documents(RUN,TICKET,URL));native.fault=fault
                    with self.assertRaises(NativeUIError):reader.request('observe',RUN,'d'*64)
                finally:native.close()
    def test_host_journal_change_cannot_issue_native_cleanup(self):
        owner=self.owner();owner.prepare();before=len(self.native.commands)
        value=owner.store.read();value['phase']='foreign';owner.store.write(value,owner.previous)
        with self.assertRaises(NativeUIError):owner.cleanup()
        self.assertEqual(before,len(self.native.commands));self.assertTrue(self.native.root.exists())


if __name__=='__main__':unittest.main()
