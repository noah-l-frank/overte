"""One synchronous auxiliary decode retains originals, guards and read censuses."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile
import pstats
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.adapters.world_web_original_parts import WorldWebOriginalParts
from ios.self_tests import test_ios_world_web_auxiliary_verification as fixture


class WorldWebAuxiliaryReadTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.WorldWebAuxiliaryVerificationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def counted(self,parts,refs):
        profile=cProfile.Profile();profile.enable(subcalls=False,builtins=False)
        try:result=parts.read_frame(refs)
        finally:profile.disable()
        code=WorldWebOriginalParts.aux_original.__code__
        count=pstats.Stats(profile).stats[(code.co_filename,code.co_firstlineno,code.co_name)][1]
        return result,count
    def test_four_independent_projections_one_actual_typed_parent_per_call(self):
        f=self.f;expected={name:f.parts.read(ref) for name,ref in f.refs.items()}
        result,count=self.counted(f.parts,f.refs);self.assertEqual(1,count);self.assertEqual(expected,result)
        result['widgets']['shown']=True
        self.assertFalse(result['widgetReceipt']['observation']['shown'])
        result['browser']['actualReply']=999
        next_result,next_count=self.counted(f.parts,f.refs)
        self.assertEqual(1,next_count);self.assertEqual(expected,next_result)
    def test_distinct_actual_parents_are_never_merged(self):
        f=self.f;second=f.parts.write_aux(2,dict(f.inputs,browser=dict(actualReply=37)))
        refs=dict(f.refs,browser=second['browser']);result,count=self.counted(f.parts,refs)
        self.assertEqual(2,count);self.assertEqual(37,result['browser']['actualReply'])
    def test_every_fresh_census_reads_actual_chunks_and_cleared_membership_reopens(self):
        f=self.f;expected=set(f.parts.paths(f.refs['browser']['parent']))
        for _ in range(2):
            with scope(fresh=True) as reads:
                _result,count=self.counted(f.parts,f.refs);self.assertEqual(1,count);self.assertEqual(expected,reads)
        calls=[]
        with scope(fresh=True) as reads:
            def current_guard():
                calls.append(True)
                if len(calls)==5:reads.clear()
                return True
            f.owner.guard=current_guard
            _result,count=self.counted(f.parts,f.refs);self.assertEqual(2,count);self.assertEqual(expected,reads)
    def test_same_bytes_replaced_inode_during_current_owner_check_refuses(self):
        f=self.f;path=f.parts.paths(f.refs['browser']['parent'])[0];calls=[]
        def current_guard():
            calls.append(True)
            if len(calls)==4:
                retained=path.with_suffix('.retained-original');path.rename(retained)
                path.write_bytes(retained.read_bytes());path.chmod(0o600)
            return True
        f.owner.guard=current_guard
        with self.assertRaises(NativeUIError):f.parts.read_frame(f.refs)
        retained=path.with_suffix('.retained-original');self.assertTrue(retained.is_file())
        self.assertEqual(retained.read_bytes(),path.read_bytes())
    def test_last_current_guard_cannot_clear_membership_or_change_owner(self):
        f=self.f
        for fault in ('census','owner'):
            calls=[];binding=deepcopy(f.owner.binding)
            with scope(fresh=True) as reads:
                def current_guard():
                    calls.append(True)
                    if len(calls)==10:
                        if fault=='census':reads.clear()
                        else:f.owner.binding=dict(binding,sessionId='foreign-owner')
                    return True
                f.owner.guard=current_guard
                try:
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):f.parts.read_frame(f.refs)
                finally:f.owner.binding=binding
    def test_new_census_inside_current_guard_gets_real_reads(self):
        f=self.f;expected=set(f.parts.paths(f.refs['browser']['parent']));calls=[];entered=[]
        with scope(fresh=True) as first:
            def current_guard():
                calls.append(True)
                if len(calls)==5:
                    child=scope(fresh=True);second=child.__enter__();entered.append((child,second))
                return True
            f.owner.guard=current_guard
            try:
                _result,count=self.counted(f.parts,f.refs);self.assertEqual(2,count)
                self.assertEqual(expected,first);self.assertEqual(expected,entered[0][1])
                self.assertIsNot(first,entered[0][1])
            finally:
                for child,_reads in reversed(entered):child.__exit__(None,None,None)
    def test_changed_projection_and_malformed_bundle_cannot_borrow_parent(self):
        f=self.f
        for key,value in (('name','world'),('index',2),('acquisitionId','ios-'+'f'*32)):
            refs=deepcopy(f.refs);refs['browser'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):f.parts.read_frame(refs)
        parent=f.parts.legacy.write('widgets',2,dict(actual='malformed'))
        changed=dict(f.refs['browser'],index=2,parent=parent)
        with self.assertRaises(NativeUIError):f.parts.read_frame(dict(browser=changed))
    def test_substituted_projection_auxiliary_or_legacy_reader_keeps_literal_dispatch(self):
        f=self.f
        for owner,name in ((f.parts,'read'),(f.parts,'aux_original'),(f.parts,'aux_projection'),(f.parts.legacy,'read')):
            with self.subTest(name=name),patch.object(owner,name,wraps=getattr(owner,name)) as reader:
                result=f.parts.read_frame(f.refs);self.assertEqual(4,reader.call_count)
                self.assertEqual(f.inputs['browser'],result['browser'])
    def test_replaced_code_on_same_reader_function_keeps_literal_dispatch(self):
        f=self.f;literal=WorldWebOriginalParts.read;code=literal.__code__;calls=[]
        # Retain the original function tree independently; changing __code__
        # on the same object must be visible to the fast-path boundary.
        from types import FunctionType
        original=FunctionType(code,literal.__globals__)
        namespace=literal.__globals__;key='_auxiliary_read_counterexample'
        self.assertNotIn(key,namespace);namespace[key]=(calls,original)
        def changed(self,value):
            calls,original=globals()['_auxiliary_read_counterexample'];calls.append(True)
            return original(self,value)
        literal.__code__=changed.__code__
        try:self.assertEqual(f.inputs['browser'],f.parts.read_frame(f.refs)['browser']);self.assertEqual(4,len(calls))
        finally:literal.__code__=code;namespace.pop(key)


if __name__=='__main__':unittest.main()
