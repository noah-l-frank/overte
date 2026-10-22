"""One-pass expected-catalog parsing preserves actual file and source checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
import adapters.emote_admission as admission
import test_snapshot_handoff as handoffs


class SnapshotCatalogPassTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.path=self.root/'pins.json'
        self.raw=admission.PINS.read_bytes();self.path.write_bytes(self.raw)
        self.expected=admission.catalog(self.path)
    def test_137_actual_opens_and_hashes_parse_all_catalog_rows_once_then_discard(self):
        parse=admission._catalog_text;digest=hashlib.sha256
        with patch.object(admission,'_catalog_text',wraps=parse) as parses,patch.object(admission.hashlib,'sha256',wraps=digest) as hashes:
            with admission.verified_catalog_pass(self.path) as reader:
                for index in range(137):
                    value=admission.catalog(reader);self.assertEqual(self.expected,value)
                    value['files'][0]['sha256']='0'*64
                self.assertEqual(1,parses.call_count);self.assertEqual(138,hashes.call_count)
            self.assertEqual(139,hashes.call_count);self.assertEqual(1,parses.call_count)
            self.assertIsNone(reader._value);self.assertIsNone(reader._raw)
            with self.assertRaises(NativeUIError):admission.catalog(reader)
            with admission.verified_catalog_pass(self.path) as second:self.assertEqual(self.expected,admission.catalog(second))
            self.assertEqual(2,parses.call_count)
    def test_arbitrary_caller_dto_foreign_reader_and_previous_pass_cannot_supply_pins(self):
        with admission.verified_catalog_pass(self.path) as reader:self.assertEqual(self.expected,admission.catalog(reader))
        for value in (self.expected,deepcopy(self.expected),object(),reader):
            with self.subTest(kind=type(value).__name__),self.assertRaises((NativeUIError,TypeError)):
                admission.catalog(value)
        class Foreign:
            def read(self):return self.expected
        with self.assertRaises(TypeError):admission.catalog(Foreign())
    def test_all_catalog_rows_are_validated_on_first_pass_and_again_next_pass(self):
        value=deepcopy(self.expected);value['files'][-1]['encoding']='foreign'
        self.path.write_text(json.dumps(value))
        with self.assertRaises(NativeUIError):
            with admission.verified_catalog_pass(self.path):self.fail('invalid final catalog row was accepted')
        self.path.write_bytes(self.raw)
        with admission.verified_catalog_pass(self.path) as reader:self.assertEqual(self.expected,admission.catalog(reader))
        self.path.write_text(json.dumps(value))
        with self.assertRaises(NativeUIError):
            with admission.verified_catalog_pass(self.path):self.fail('previous pass supplied new expectations')
    def test_actual_file_changes_between_accesses_or_at_final_close_remain_red(self):
        for fault in ('missing','inode','bytes','invalid','mode','hardlink','mtime'):
            for final_only in (False,True):
                with self.subTest(fault=fault,final_only=final_only):
                    path=self.root/(fault+str(final_only)+'.json');path.write_bytes(self.raw)
                    reader=None
                    with self.assertRaises((NativeUIError,OSError,ValueError)):
                        with admission.verified_catalog_pass(path) as reader:
                            self.assertEqual(self.expected,admission.catalog(reader))
                            if fault=='missing':path.unlink()
                            elif fault=='inode':
                                old=path.with_suffix('.retained');path.rename(old);path.write_bytes(self.raw)
                                self.assertNotEqual(old.stat().st_ino,path.stat().st_ino)
                            elif fault=='bytes':
                                value=deepcopy(self.expected);value['sourceBase']='0'*40;path.write_text(json.dumps(value))
                            elif fault=='invalid':path.write_bytes(b'not json')
                            elif fault=='mode':path.chmod(0o600)
                            elif fault=='hardlink':os.link(path,path.with_suffix('.foreign-link'))
                            else:
                                info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1000000))
                            if not final_only:admission.catalog(reader)
                    self.assertIsNone(reader._value);self.assertIsNone(reader._raw)
                    if fault=='inode':self.assertEqual(self.raw,path.read_bytes());self.assertEqual(self.raw,old.read_bytes())
    def test_read_rechecks_path_and_descriptor_identity_after_actual_open(self):
        original=admission.os.fdopen;changed=[False]
        class Stream:
            def __init__(self,raw):self.raw=raw
            def __enter__(self):return self
            def __exit__(self,*args):return self.raw.__exit__(*args)
            def fileno(self):return self.raw.fileno()
            def read(self,count):
                value=self.raw.read(count)
                if not changed[0]:
                    changed[0]=True;self_path.rename(self_path.with_suffix('.original'));self_path.write_bytes(value)
                return value
        self_path=self.path
        with patch.object(admission.os,'fdopen',side_effect=lambda *args,**kwargs:Stream(original(*args,**kwargs))):
            with self.assertRaises(NativeUIError):
                with admission.verified_catalog_pass(self.path):self.fail('path replaced during actual read')
        self.assertTrue(changed[0]);self.assertTrue(self.path.with_suffix('.original').exists())
    def test_initial_symlink_nonregular_or_multiple_link_file_never_supplies_expectations(self):
        for kind in ('symlink','directory','hardlink'):
            path=self.root/kind
            if kind=='symlink':path.symlink_to(self.path)
            elif kind=='directory':path.mkdir()
            else:os.link(self.path,path)
            with self.subTest(kind=kind),self.assertRaises((NativeUIError,OSError)):
                with admission.verified_catalog_pass(path):self.fail('unqualified source file was read')
            if kind=='hardlink':path.unlink()
    def test_exception_discards_context_and_default_catalog_reader_stays_fresh(self):
        with self.assertRaisesRegex(RuntimeError,'actual pass failure'):
            with admission.verified_catalog_pass(self.path) as reader:raise RuntimeError('actual pass failure')
        self.assertIsNone(reader._value)
        with self.assertRaises(NativeUIError):reader.read()
        value=deepcopy(self.expected);value['sourceBase']='1'*40;self.path.write_text(json.dumps(value))
        self.assertEqual(value,admission.catalog(self.path))


class SnapshotHandoffCatalogPassTests(unittest.TestCase):
    def frames(self,count=8):
        b=handoffs.Boundary();return b,[b.frame() for _ in range(count)]
    def test_full_original_history_and_new_current_source_each_keep_own_catalog_pass(self):
        b,frames=self.frames(137);reader=b.reader();parse=admission._catalog_text
        with patch.object(admission,'_catalog_text',wraps=parse) as parses:
            reader.restore_history(frames)
            self.assertEqual(1,parses.call_count);self.assertEqual(frames[-1],reader.last);self.assertIsNone(reader.pins_path)
            b.packet=b.frame();reader.read();self.assertEqual(2,parses.call_count)
        second=b.reader()
        with patch.object(admission,'_catalog_text',wraps=parse) as parses:
            second.restore_history(frames);self.assertEqual(1,parses.call_count)
    def test_foreign_originals_and_actual_history_regressions_are_still_fully_validated(self):
        for fault in ('native','vm','lifecycle','chronology','probe-code'):
            b,frames=self.frames();row=frames[4];group=row['source']['source']['group']
            if fault=='native':group['snapshot']['processId']+=1
            elif fault=='vm':group['snapshot']['source']['scriptHistory']['events'][0]['capturedEpochMs']-=1
            elif fault=='lifecycle':row['source']['source']['context']['lifecycle']['launches']+=1
            elif fault=='chronology':row['source']['sequence']=frames[3]['source']['sequence']
            else:group['script']['source']['engines'][0]['code']['sha256']='0'*64
            reader=b.reader()
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):reader.restore_history(frames)
            self.assertIsNone(reader.last);self.assertIsNone(reader.scripts);self.assertIsNone(reader.pins_path)
    def test_midpass_file_replacement_and_final_file_recheck_prevent_history_publication(self):
        for final_only in (False,True):
            b,frames=self.frames(3)
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'pins.json';path.write_bytes(admission.PINS.read_bytes())
                reader=b.reader();reader.pins_path=path;validate=reader.validate;calls=[0]
                def changed(value,epoch):
                    result=validate(value,epoch);calls[0]+=1
                    if calls[0]==(len(frames) if final_only else 1):
                        path.rename(path.with_suffix('.original'));path.write_bytes(admission.PINS.read_bytes())
                    return result
                reader.validate=changed
                with self.subTest(final_only=final_only),self.assertRaises(NativeUIError):reader.restore_history(frames)
                self.assertIsNone(reader.last);self.assertIsNone(reader.scripts);self.assertEqual(path,reader.pins_path)
                self.assertTrue(path.with_suffix('.original').exists())


if __name__=='__main__':unittest.main()
