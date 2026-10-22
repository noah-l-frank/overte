"""Actual compiled private bundle files and real filesystem counterexamples."""
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
from overte_phone_assets_files import PhoneAssetsFiles,command,source
from overte_phone_assets_file_owner import OwnedAssetsFiles
from overte_phone_assets_fixture import documents,NAMES
from overte_phone_script_history import canonical
from test_create_files import NativeFiles as CreateNativeFiles,BINDING,RUN,TICKET,URL

CPP=r'''#include "tests/device/native/PrivateAssetsFiles.h"
#include <iostream>
int main(int argc,char**argv){QCoreApplication app(argc,argv);overte::e2e::PrivateAssetsFiles files;
 std::string line;while(std::getline(std::cin,line)){
  const auto command=QJsonDocument::fromJson(QByteArray::fromStdString(line)).object().toVariantMap();
  const auto actual=files.request(QString::fromLocal8Bit(argv[1]),command);
  std::cout<<QJsonDocument(QJsonObject::fromVariantMap(actual)).toJson(QJsonDocument::Compact).toStdString()<<std::endl;
 }}'''


class NativeFiles(CreateNativeFiles):
    def reader(self):return PhoneAssetsFiles(self.send,lambda:json.dumps(self.value),lambda:int(time.time()*1000),lambda:self.guard_ok,self.process.pid)
    def raw(self,operation,owner='d'*64,files=None):
        call=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-assets-files',operation=operation,runId=RUN,ownerToken=owner)
        if files is not None:call['files']={name:base64.b64encode(raw).decode() for name,raw in files.items()}
        self.send(call);return self.value['source']
    @property
    def root(self):return self.directory/('feature-assets-'+RUN)


class AssetsFilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build=ROOT/'build/assets-native-contract';build.mkdir(parents=True,exist_ok=True)
        cls.build=tempfile.TemporaryDirectory(prefix='files-',dir=build);cpp=Path(cls.build.name)/'files.cpp';cpp.write_text(CPP);cls.executable=cpp.with_suffix('')
        flags=subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Core'],text=True).split()
        subprocess.run(['c++','-std=c++17','-fPIC','-fmax-errors=1','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PHONE_INTERFACE',
            '-I'+str(ROOT),str(cpp),'-o',str(cls.executable),*flags],check=True,timeout=60)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        self.native=NativeFiles(self.executable,self.base);self.addCleanup(self.native.close)
    def owner(self):return OwnedAssetsFiles(self.native.reader(),PrivateFeatureState(self.base/'assets-owner.json'),BINDING,RUN,TICKET,URL)
    def test_real_fixed_bundles_preserve_all_original_relative_bytes_and_private_modes(self):
        owner=self.owner();url=owner.prepare();self.assertTrue(url.endswith('/feature-assets-'+RUN))
        self.assertEqual(set(NAMES),{str(path.relative_to(self.native.root)) for path in self.native.root.rglob('*') if path.is_file() and path.name!='.owner.v1.json'})
        for name,raw in documents().items():
            path=self.native.root/name;self.assertEqual(raw,path.read_bytes());self.assertEqual(0o600,path.stat().st_mode&0o777)
        self.assertTrue(all(path.stat().st_mode&0o777==0o700 for path in self.native.root.rglob('*') if path.is_dir()))
        owner.cleanup();owner.cleanup();self.assertFalse(self.native.root.exists())
    def test_actual_main_retirement_keeps_companions_and_repeated_calls_use_only_observation(self):
        owner=self.owner();owner.prepare();owner.retire_primary();count=sum(call['operation']=='retire-primary' for call in self.native.commands)
        self.assertFalse((self.native.root/'gltf-bundle/main.gltf').exists());self.assertTrue((self.native.root/'gltf-bundle/mesh/triangle.bin').is_file())
        self.owner().retire_primary();self.assertEqual(count,sum(call['operation']=='retire-primary' for call in self.native.commands))
        self.owner().cleanup();self.assertFalse(self.native.root.exists())
    def test_lost_stage_and_retire_replies_recover_actual_files_without_replaying_input(self):
        owner=self.owner();self.native.drop='stage'
        with self.assertRaises(NativeUIError):owner.prepare()
        self.native.drop=None;owner=self.owner();owner.prepare();self.assertEqual(1,sum(c['operation']=='stage' for c in self.native.commands))
        self.native.drop='retire-primary'
        with self.assertRaises(NativeUIError):owner.retire_primary()
        self.native.drop=None;self.owner().retire_primary();self.assertEqual(1,sum(c['operation']=='retire-primary' for c in self.native.commands))
        self.owner().cleanup()
    def test_foreign_child_file_and_directory_block_cleanup_without_deleting_owned_inputs(self):
        for name in ('foreign.txt','gltf-bundle/foreign','obj-bundle/materials/foreign'):
            with self.subTest(name=name):
                if not self.native.root.exists():self.owner().prepare()
                foreign=self.native.root/name;foreign.write_bytes(b'foreign');foreign.chmod(0o600)
                with self.assertRaises(NativeUIError):self.owner().cleanup()
                self.assertTrue(foreign.is_file());self.assertTrue((self.native.root/'fbx-bundle/stand.fbx').is_file());foreign.unlink()
        self.owner().cleanup()
    def test_same_name_replacement_and_hardlink_do_not_forget_original_inode(self):
        self.owner().prepare();path=self.native.root/'gltf-bundle/main.gltf';original=path.read_bytes();backup=self.base/'original-main'
        path.rename(backup);path.write_bytes(original);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertTrue(path.is_file());path.unlink();backup.rename(path)
        linked=self.base/'linked';os.link(path,linked)
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        linked.unlink()
        # Relinking/renaming changed ctime, so this owner must stay red even when
        # bytes and filename return. It cannot forget the original inode receipt.
        with self.assertRaises(NativeUIError):self.owner().cleanup()
    def test_symlink_and_fifo_do_not_cross_file_boundary(self):
        self.owner().prepare();path=self.native.root/'obj-bundle/main.obj';outside=self.base/'outside';outside.write_bytes(b'outside')
        path.unlink();path.symlink_to(outside)
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertEqual(b'outside',outside.read_bytes());path.unlink();os.mkfifo(path)
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertTrue(outside.is_file())
    def test_wrong_token_and_revival_are_refused(self):
        owner=self.owner();owner.prepare();self.assertEqual({},self.native.raw('release',owner='e'*64))
        self.assertTrue(self.native.root.is_dir());owner.cleanup()
        self.assertEqual({},self.native.raw('stage',owner=owner.state['ownerToken'],files=documents()))
    def test_unknown_preexisting_root_is_never_adopted_even_for_the_same_run(self):
        self.native.root.mkdir(mode=0o700);foreign=self.native.root/'foreign';foreign.write_bytes(b'foreign');foreign.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner().prepare()
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertEqual(b'foreign',foreign.read_bytes())
    def test_replaced_bundle_directory_and_readable_foreign_copy_are_not_owned(self):
        self.owner().prepare();original=self.native.root/'gltf-bundle';backup=self.base/'original-gltf';original.rename(backup)
        original.mkdir(mode=0o700);foreign=original/'main.gltf';foreign.write_bytes(documents()['gltf-bundle/main.gltf']);foreign.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertTrue((backup/'mesh/triangle.bin').is_file());self.assertTrue(foreign.is_file());self.assertTrue((self.native.root/'fbx-bundle/stand.fbx').is_file())
    def test_changed_bytes_are_not_deleted_as_owned_input(self):
        self.owner().prepare();path=self.native.root/'obj-bundle/main.obj';path.write_bytes(b'foreign bytes')
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertEqual(b'foreign bytes',path.read_bytes())
    def test_weakened_private_mode_keeps_owner_journal_and_inputs(self):
        self.owner().prepare();path=self.native.root/'gltf-bundle/mesh/triangle.bin';path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.owner().cleanup()
        self.assertTrue(path.exists());self.assertIsNotNone(self.owner().store.read())
    def test_lost_release_reply_resumes_actual_absence_before_host_retirement(self):
        owner=self.owner();owner.prepare();self.native.drop='release'
        with self.assertRaises(NativeUIError):owner.cleanup()
        self.assertFalse(self.native.root.exists());self.assertIsNotNone(owner.store.read())
        self.native.drop=None;self.owner().cleanup();self.assertFalse(self.native.root.exists())
    def test_readonly_grammar_rejects_stage_unlink_and_release_even_with_the_real_token(self):
        from appium_adapter import readonly_feature_command
        value=dict(schemaVersion=1,commandId='c'*32,action='phone-assets-files',operation='observe',runId=RUN,ownerToken='d'*64)
        readonly_feature_command(value)
        for operation in ('release','retire-primary'):
            with self.subTest(operation=operation),self.assertRaises(ValueError):readonly_feature_command(value|dict(operation=operation))

    def test_host_journal_retires_only_after_actual_native_absence_and_retained_exact_original(self):
        owner=self.owner();owner.prepare();owner.cleanup();retained=[]
        def retain(value):retained.append(deepcopy(value));return hashlib.sha256(canonical(value)).hexdigest()
        owner.retire(retain);self.assertIsNone(owner.store.read());self.assertEqual('retired',retained[0]['phase']);self.assertFalse(self.native.root.exists())
    def test_invalid_payload_path_owner_or_schema_cannot_create_any_private_root(self):
        value=dict(schemaVersion=1,commandId='c'*32,action='phone-assets-files',operation='stage',runId=RUN,ownerToken='d'*64,
            files={name:base64.b64encode(raw).decode() for name,raw in documents().items()})
        for change in (dict(schemaVersion=True),dict(path='/foreign'),dict(files={'../foreign':'eA=='}),dict(ownerToken='foreign')):
            call=value|change
            with self.subTest(change=change),self.assertRaises((NativeUIError,ValueError)):command(call)
        self.assertFalse(self.native.root.exists())


if __name__=='__main__':unittest.main()
