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
    def test_single_script_lookup_keeps_actual_file_checks_without_copying_all_440_rows(self):
        expected=next(row for row in self.expected['files'] if row['runtimePath']=='system/snapshot.js')
        parse=admission._catalog_text;copy=admission.deepcopy;digest=hashlib.sha256
        with patch.object(admission,'_catalog_text',wraps=parse) as parses,patch.object(admission,'deepcopy',wraps=copy) as copies,patch.object(admission.hashlib,'sha256',wraps=digest) as hashes:
            with admission.verified_catalog_pass(self.path) as reader:
                first=admission.script_pin(reader,'system/snapshot.js');self.assertEqual(expected,first)
                first['sha256']='0'*64;first['runtimePath']='foreign.js'
                for index in range(136):self.assertEqual(expected,admission.script_pin(reader,'system/snapshot.js'))
                self.assertEqual(1,parses.call_count);self.assertEqual(138,hashes.call_count)
                # One complete defensive copy for initial schema qualification;
                # all later consumers copy only their own required original pin.
                whole=[call for call in copies.call_args_list if 'files' in call.args[0]]
                self.assertEqual(1,len(whole));self.assertEqual(138,copies.call_count)
            self.assertEqual(139,hashes.call_count)
        with self.assertRaises(NativeUIError):admission.script_pin(reader,'system/snapshot.js')
        self.assertEqual(expected,admission.script_pin(self.path,'system/snapshot.js'))
        self.assertEqual(expected,admission.script_pin(None,'system/snapshot.js'))
    def test_single_pin_lookup_cannot_adopt_missing_ambiguous_foreign_or_caller_expected_data(self):
        for path in (self.path,None):
            for runtime_path in ('unknown.js','../system/snapshot.js',{},'system/snapshot.js?foreign'):
                with self.subTest(path=path,runtime_path=runtime_path),self.assertRaises((NativeUIError,TypeError)):
                    admission.script_pin(path,runtime_path)
        with admission.verified_catalog_pass(self.path) as reader:
            with self.assertRaises(NativeUIError):admission.script_pin(reader,'foreign.js')
            # Deliberately corrupt internal implementation state: even this
            # cannot silently choose one of two identical runtime paths.
            row=next(row for row in reader._value['files'] if row['runtimePath']=='system/snapshot.js')
            reader._value['files'].append(deepcopy(row))
            with self.assertRaises(NativeUIError):admission.script_pin(reader,'system/snapshot.js')
        for value in (self.expected,{'sha256':'0'*64}):
            with self.assertRaises(TypeError):admission.script_pin(value,'system/snapshot.js')
    def test_single_pin_lookup_still_reads_original_file_and_rejects_same_bytes_replacement(self):
        with self.assertRaises(NativeUIError):
            with admission.verified_catalog_pass(self.path) as reader:
                admission.script_pin(reader,'system/snapshot.js')
                self.path.rename(self.path.with_suffix('.retained'));self.path.write_bytes(self.raw)
                admission.script_pin(reader,'system/snapshot.js')
        self.assertTrue(self.path.with_suffix('.retained').exists())
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


class SnapshotCurrentCatalogPassTests(unittest.TestCase):
    def test_eleven_actual_current_native_reads_keep_distinct_original_nonces_times_and_sequences(self):
        b=handoffs.Boundary();reader=b.reader();parse=admission._catalog_text;actual=[]
        def fresh():
            b.epoch+=1
            def sampled(value):
                if type(value) is dict:
                    for key,item in value.items():
                        if key in ('requestedEpochMs','capturedEpochMs') and item==20000:value[key]=b.epoch
                        else:sampled(item)
                elif type(value) is list:
                    for item in value:sampled(item)
            group=deepcopy(b.group);sampled(group);original=b.group;b.group=group
            try:value=b.frame();sampled(value)
            finally:b.group=original
            actual.append(deepcopy(value));return json.dumps(value)
        reader.original=fresh
        with patch.object(admission,'_catalog_text',wraps=parse) as parses:
            with reader.expected_catalog():
                escaped=reader.pins_path
                for index in range(11):reader.read()
                reader.verify_expected_catalog();self.assertEqual(1,parses.call_count)
            self.assertIsNone(reader.pins_path);self.assertIsNone(reader._catalog_pass)
            self.assertEqual(11,len(actual))
            self.assertEqual(11,len({row['source']['sequence'] for row in actual}))
            self.assertEqual(11,len({row['publishedEpochMs'] for row in actual}))
            self.assertEqual(11,len({row['source']['source']['group']['snapshot']['requestId'] for row in actual}))
            with self.assertRaises(NativeUIError):admission.script_pin(escaped,'system/snapshot.js')
            with reader.expected_catalog():reader.read()
            self.assertEqual(2,parses.call_count)
    def test_current_stale_foreign_and_replayed_native_sources_are_not_cached_or_skipped(self):
        for fault in ('stale','pid','vm','sequence'):
            b=handoffs.Boundary();reader=b.reader()
            with self.subTest(fault=fault):
                with self.assertRaises(NativeUIError):
                    with reader.expected_catalog():
                        reader.read();b.packet=b.frame()
                        if fault=='stale':b.epoch+=1501
                        elif fault=='pid':b.packet['source']['source']['group']['snapshot']['processId']+=1
                        elif fault=='vm':b.packet['source']['source']['group']['script']['source']['engines'][0]['code']['sha256']='0'*64
                        else:b.packet['source']['sequence']=reader.last['source']['sequence']
                        reader.read()
                self.assertIsNone(reader._catalog_pass);self.assertIsNone(reader.pins_path)
    def test_role_checks_actual_catalog_before_frame_and_manifest_publication(self):
        import test_snapshots_role as roles
        from overte_phone_snapshots_role import PhoneSnapshotsRole
        for fault in ('none','before_commit','during_write','after_original','pending'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);b=roles.SnapshotRolesBoundary(root);b.system_mode()
                path=root/'pins.json';path.write_bytes(admission.PINS.read_bytes())
                with b.lock.held():
                    role=PhoneSnapshotsRole(b.feature,'primary');role.handoff.pins_path=path
                    original=role.finish_archive;seen=[]
                    def finish(frame):
                        seen.append('finish')
                        if fault=='during_write':path.write_bytes(self_changed)
                        return original(frame)
                    self_changed=admission.PINS.read_bytes()+b' '
                    role.finish_archive=finish
                    if fault=='before_commit':
                        bound=role.bound;count=[0]
                        def changed():
                            result=bound();count[0]+=1
                            if count[0]==2:path.write_bytes(self_changed)
                            return result
                        role.bound=changed
                    elif fault=='after_original':
                        write=role.originals.write
                        def changed_original(*args):
                            reference=write(*args);path.write_bytes(self_changed);return reference
                        role.originals.write=changed_original
                    elif fault=='pending':
                        from overte_phone_snapshots_measurements import SnapshotPending
                        role.acquire=lambda *_:(_ for _ in ()).throw(SnapshotPending())
                        role.recover=lambda:None
                    if fault=='none':
                        parse=admission._catalog_text
                        with patch.object(admission,'_catalog_text',wraps=parse) as parses:value=role.read(0)
                        self.assertGreaterEqual(parses.call_count,1);self.assertEqual(1,value['sequence'])
                        rows=role.frames[-1]['handoffOriginals'];self.assertGreaterEqual(len(rows),3)
                        self.assertEqual(len(rows),len({row['source']['sequence'] for row in rows}))
                    else:
                        from overte_phone_snapshots_measurements import SnapshotPending
                        with self.assertRaises(SnapshotPending if fault=='pending' else NativeUIError):role.read(0)
                        self.assertEqual(0,role.state['sequence']);self.assertEqual([],role.state['manifests'])
                        self.assertFalse(list(root.glob('emote-index-snapshots-*.json')))
                        if fault=='before_commit':self.assertEqual([],seen)
                    self.assertEqual(path,role.handoff.pins_path);self.assertIsNone(role.handoff._catalog_pass)
                    self.assertFalse(role._host_publication)


if __name__=='__main__':unittest.main()
