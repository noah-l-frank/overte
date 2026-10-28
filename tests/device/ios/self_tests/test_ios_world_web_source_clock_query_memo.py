"""Actual retained clock/source files; native/SDK producers are host models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile,json,os,subprocess,sys,unittest
from pathlib import Path
from contextvars import ContextVar
from types import MethodType
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters import original_marker_clock_queries as literal
from ios.adapters import world_web_clock_validation as memo,world_web_sources as source_module
from ios.self_tests.test_ios_world_web_sample_clocks import WorldWebSampleClockTests


class WorldWebSourceClockQueryMemoTests(unittest.TestCase):
    def setUp(self):self.fixture=WorldWebSampleClockTests()
    def original(self,source,make):
        owner=make()
        with owner.owned():source.native.read(source.native.sequence)
        return owner,owner.rows(owner.state)
    def original_calls(self,function):
        code=literal.queries.__code__;profile=cProfile.Profile();profile.enable()
        try:value=function()
        finally:profile.disable();profile.create_stats()
        row=profile.stats.get((code.co_filename,code.co_firstlineno,code.co_name))
        return value,0 if row is None else row[1]
    def test_actual_source_frame_full_query_list_is_decoded_once_and_keeps_shared_default(self):
        with self.fixture.owners() as (sdk,source,_make):
            frame=source.frame(source.capture('source-clock-positive'));sent=len(sdk.native.commands)
            # Complete actual Source validation, not an injected proof/cache row.
            with memo.scope():
                _,first=self.original_calls(lambda:source.validate_frame(frame))
                _,second=self.original_calls(lambda:source.validate_frame(frame))
                self.assertGreater(first,0);self.assertEqual(0,second)
                self.assertIsNone(literal.bracket(source.PROFILE,frame,source.pid))
            self.assertEqual(sent,len(sdk.native.commands))
    def test_same_byte_original_carrier_replacement_still_refuses_after_warm_source_queries(self):
        with self.fixture.owners() as (sdk,source,_make):
            ref=source.capture('source-clock-inode');frame=source.frame(ref);sent=len(sdk.native.commands);path=source.record_store(ref['index']).path
            with memo.scope(),self.assertRaises(NativeUIError),source.validation_round():
                source.validate_frame(frame);raw=path.read_bytes();inode=path.stat().st_ino;replacement=path.with_suffix('.replacement')
                replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
                self.assertNotEqual(inode,path.stat().st_ino);self.assertEqual(raw,path.read_bytes());source.guard_originals()
            self.assertEqual(sent,len(sdk.native.commands));self.assertIsNone(source._round)
    def test_changed_actual_raw_pid_nonce_and_strictness_cannot_reuse_a_source_success(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                first=memo.source_queries(rows,sdk.pid);self.assertEqual(sdk.pid,first['processId'])
                with self.assertRaises(NativeUIError):memo.source_queries(rows,sdk.pid+1)
                changed=deepcopy(rows);packet=json.loads(changed[0]['raws'][0]);packet['processId']+=1;changed[0]['raws'][0]=json.dumps(packet)
                self.assertIsNone(memo.source_queries(changed,sdk.pid,strict=False))
                with self.assertRaises(NativeUIError):memo.source_queries(changed,sdk.pid)
                changed=deepcopy(rows);changed[0]['query']['commandId']='ios-'+'f'*32;self.assertIsNone(memo.source_queries(changed,sdk.pid))
                returned=memo.source_queries(rows,sdk.pid);returned['processId']=999;self.assertEqual(first,memo.source_queries(rows,sdk.pid))
    def test_replaced_source_bracket_keeps_its_literal_three_argument_call_shape(self):
        with self.fixture.owners() as (_sdk,source,_make):
            frame=source.frame(source.capture('source-clock-bracket'));actual=source_module.clock_bracket;called=[]
            def bracket(profile,value,pid):called.append(pid);return actual(profile,value,pid)
            with memo.scope(),patch.object(source_module,'clock_bracket',bracket):source.validate_frame(frame)
            self.assertEqual([source.pid],called)
    def test_same_function_foreign_receiver_cannot_hit_a_warm_source_decoder_entry(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);actual=memo.original_queries
            with memo.scope():
                memo.source_queries(rows,sdk.pid)
                with patch.object(memo,'original_queries',MethodType(actual,object())):
                    value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid))
                    self.assertEqual(sdk.pid,value['processId']);self.assertEqual(1,calls)
    def test_in_place_original_decoder_code_change_is_observed_before_a_warm_source_hit(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);actual=memo.original_queries;code=actual.__code__
            def changed(rows,pid,*,strict=True):raise RuntimeError('Original decoder code changed during the pure read')
            with memo.scope():
                memo.source_queries(rows,sdk.pid)
                try:
                    actual.__code__=changed.__code__
                    with self.assertRaisesRegex(RuntimeError,'Original decoder code changed'):memo.source_queries(rows,sdk.pid)
                finally:actual.__code__=code
    def test_in_place_keyword_default_change_keeps_actual_decoder_fallback(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);actual=memo.original_queries;old=actual.__kwdefaults__['strict']
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid)
                try:
                    actual.__kwdefaults__['strict']=False
                    value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,value);self.assertEqual(1,calls)
                finally:actual.__kwdefaults__['strict']=old
    def test_changed_capacity_or_scope_code_retains_literal_validation(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid)
                for name,value in (('MAX_BYTES',1),('MAX_ENTRIES',0)):
                    with self.subTest(constant=name),patch.object(memo,name,value):
                        actual,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,actual);self.assertEqual(1,calls)
                body=memo.scope.__wrapped__;code=body.__code__
                def different_scope():yield
                try:
                    body.__code__=different_scope.__code__
                    actual,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,actual);self.assertEqual(1,calls)
                finally:body.__code__=code
    def test_foreign_active_context_cannot_adopt_source_results_and_original_scope_resets(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);original=memo._ACTIVE
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid);foreign=ContextVar('foreign_source_query_scope',default=dict(entries={},bytes=0))
                with patch.object(memo,'_ACTIVE',foreign):
                    actual,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(expected,actual);self.assertEqual(1,calls)
                    self.assertEqual(0,len(foreign.get()['entries']))
            self.assertIsNone(original.get())
    def test_nonliteral_gpu_parser_entries_cannot_be_adopted_by_later_literal_source_calls(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make);actual=memo.original_queries
            with memo.scope():
                with patch.object(memo,'original_queries',wraps=actual):memo.queries(rows,sdk.pid)
                value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(sdk.pid,value['processId']);self.assertEqual(1,calls)
                _value,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid));self.assertEqual(0,calls)

    def test_substituted_snapshot_builtins_refuse_reuse_without_opaque_invocation(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                expected=memo.source_queries(rows,sdk.pid)
                for name in ('bool','int','float','str','list','any','zip'):
                    with self.subTest(alias=name),patch.object(memo,name,create=True,side_effect=AssertionError('Opaque snapshot alias executed')) as opaque:
                        actual,calls=self.original_calls(lambda:memo.source_queries(rows,sdk.pid))
                        self.assertEqual(expected,actual);self.assertEqual(1,calls);opaque.assert_not_called()
    def test_changed_literal_query_size_limit_cannot_adopt_a_warm_source_success(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            with memo.scope():
                memo.source_queries(rows,sdk.pid)
                with patch.object(literal,'LIMIT',1),self.assertRaises(NativeUIError):memo.source_queries(rows,sdk.pid)
    def test_actual_marshal_audit_mutation_and_opaque_buffer_are_isolated_in_owned_child(self):
        with self.fixture.owners() as (sdk,source,make):
            _owner,rows=self.original(source,make)
            payload=source.store.path.parent/'source-clock-audit-child-input.json'
            payload.write_text(json.dumps(dict(rows=rows,pid=sdk.pid)));payload.chmod(0o600)
            before=payload.read_bytes();metadata=payload.stat()
            stamp=lambda value:(value.st_dev,value.st_ino,value.st_mode,value.st_uid,value.st_gid,value.st_size,value.st_mtime_ns,value.st_ctime_ns,value.st_nlink)
            original_stamp=stamp(metadata)
            code=r"""
import json,marshal,os,sys
from pathlib import Path
sys.path[:]=json.loads(sys.argv[2])
from ios.adapters import world_web_clock_validation as memo
value=json.loads(Path(sys.argv[1]).read_text());rows=value['rows'];pid=value['pid'];baseline=json.loads(Path(sys.argv[1]).read_text())['rows']
events=[];buffers=[];armed=[rows]
class OpaqueBuffer:
    def __buffer__(self,flags):
        buffers.append('opaque-buffer');return memoryview(b'controlled-host-only')
def audit(event,args):
    if event=='marshal.dumps' and armed[0] is not None:
        events.append('marshal.dumps');target=armed[0];armed[0]=None
        target[0]['raws'].append(OpaqueBuffer())
sys.addaudithook(audit)
with memo.scope():
    first=memo.source_queries(rows,pid);second=memo.source_queries(rows,pid)
assert first['processId']==pid and second==first
assert events==[] and buffers==[]
assert rows==baseline and all(type(raw) is str for row in rows for raw in row['raws'])
# Controlled reproduction of the former post-typecheck mutation window.
scratch=json.loads(Path(sys.argv[1]).read_text())['rows']
assert memo.bounded(scratch,pid,True)
armed[0]=scratch
marshal.dumps((scratch,pid,True),4)
assert events==['marshal.dumps'] and buffers==['opaque-buffer']
print(json.dumps(dict(pid=os.getpid(),protectedMarshalEvents=0,protectedBufferCalls=0,legacyMarshalEvents=len(events),legacyBufferCalls=len(buffers))),flush=True)
"""
            with subprocess.Popen([sys.executable,'-c',code,str(payload),json.dumps(sys.path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) as child:
                process_id=child.pid
                try:
                    process_stat=Path('/proc')/str(process_id)/'stat';start=process_stat.read_text().split(') ',1)[1].split()[19]
                    stdout,stderr=child.communicate(timeout=20)
                except BaseException:
                    child.kill();child.communicate();raise
                self.assertEqual(0,child.returncode,stderr)
            self.assertTrue(child.stdout.closed and child.stderr.closed)
            self.assertFalse((Path('/proc')/str(process_id)).exists())
            receipt=json.loads(stdout);self.assertEqual(process_id,receipt['pid'])
            self.assertEqual(0,receipt['protectedMarshalEvents']);self.assertEqual(0,receipt['protectedBufferCalls'])
            self.assertEqual(1,receipt['legacyMarshalEvents']);self.assertEqual(1,receipt['legacyBufferCalls'])
            self.assertEqual(before,payload.read_bytes());self.assertEqual(original_stamp,stamp(payload.stat()))
            receipt.update(startTicks=start,exitCode=child.returncode,streamsClosed=True,inputBytesAndNineStatUnchanged=True)
            output=payload.with_name('source-clock-audit-child-result.json');output.write_text(json.dumps(receipt));output.chmod(0o600)


if __name__=='__main__':unittest.main()
