"""Bounded Snapshot groups; actual Host files, Native/Qt/SDK are models.

Storage-cost fixtures never satisfy Native frame/effect/Actor contracts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import inspect
import unittest
from unittest.mock import patch
from self_tests.pico_snapshot_settings_scope2_fixture import Scope2Boundary
from adapters.normal_ui import NativeUIError


class SnapshotSettingsDecodedGroupsTests(unittest.TestCase):
    def make(self):
        m=Scope2Boundary(self);lease=m.attach();m.parent.prepare();m.h.activate('open');m.parent.open()
        self.assertEqual(2,len(m.sdk_calls));return m,lease,lease.raw.namespace

    def target(self,namespace,lease,index=0):
        rows,parts,graphs=namespace.known(lease)
        children=sorted(row[0] for name,row in rows.items() if row[3]=='chunk' and name.startswith('snapshot-cancel-originals.'))
        self.assertTrue(children);return children[index if index==0 else len(children)//2]

    def corrupt(self,path):
        original=path.read_bytes();inode=path.stat().st_ino
        path.write_bytes(b'['+original[1:]);self.assertEqual(inode,path.stat().st_ino)
        return path.read_bytes()

    def mutation(self,middle=False,after=False):
        m,lease,namespace=self.make();calls=len(m.sdk_calls);native=m.sequence;changes=[]
        with lease.lock.held():target=self.target(namespace,lease,1 if middle else 0)
        read=namespace.read;guard=lease.raw.codec.guard;boundaries=[]
        def reading(path,*args):
            value=read(path,*args)
            if not after and path==target and not changes:
                changes.append(self.corrupt(path))
            return value
        def boundary():
            result=guard();frame=inspect.currentframe().f_back
            if frame.f_code.co_name in ('measure','flush'):
                boundaries.append(namespace.decoding)
                if after and len(boundaries)==3:changes.append(self.corrupt(target))
            return result
        with lease.lock.held(),patch.object(namespace,'read',reading),patch.object(lease.raw.codec,'guard',boundary):
            with self.assertRaises(NativeUIError):namespace.measure(lease)
        self.assertEqual(1,len(changes));self.assertEqual(changes[0],target.read_bytes())
        self.assertTrue(namespace.failed);self.assertFalse(namespace.decoding)
        self.assertFalse(namespace.close_host());self.assertEqual(calls,len(m.sdk_calls));self.assertEqual(native,m.sequence)
        self.assertTrue(boundaries);self.assertTrue(all(flag is False for flag in boundaries))

    def test_current_first_original_mutation_is_caught_by_fresh_footer(self):self.mutation()
    def test_current_middle_original_mutation_is_caught_by_fresh_footer(self):self.mutation(middle=True)
    def test_current_after_decode_mutation_is_caught_before_return(self):self.mutation(after=True)

    def test_foreign_json_encoder_class_cannot_run_inside_pure_batch(self):
        import json
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;original=json.JSONEncoder
        boundaries=[];calls=[]
        def foreign(*args,**kwargs):
            calls.append(namespace.decoding);return original(*args,**kwargs)
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                boundaries.append(1)
                if len(boundaries)==2:json.JSONEncoder=foreign
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):
                namespace.measure(lease)
        finally:json.JSONEncoder=original
        self.assertEqual([],calls,'Foreign JSONEncoder must not execute at all')
        self.assertEqual(2,len(m.sdk_calls))

    def test_foreign_json_class_descriptor_is_not_evaluated(self):
        import json
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;changes=[];calls=[]
        class ForeignDescriptor:
            def __get__(self,obj,owner):calls.append('get');return False
            def __set__(self,obj,value):calls.append('set')
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                changes.append(1)
                if len(changes)==2:json.JSONEncoder.skipkeys=ForeignDescriptor()
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):namespace.measure(lease)
        finally:
            if 'skipkeys' in json.JSONEncoder.__dict__:del json.JSONEncoder.skipkeys
        self.assertEqual([],calls);self.assertEqual(2,len(m.sdk_calls));self.assertFalse(namespace.decoding)

    def test_same_json_decoder_class_changed_method_is_not_called(self):
        import json
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;original=json.JSONDecoder.raw_decode;changes=[];calls=[]
        def foreign(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                changes.append(1)
                if len(changes)==2:json.JSONDecoder.raw_decode=foreign
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):namespace.measure(lease)
        finally:json.JSONDecoder.raw_decode=original
        self.assertEqual([],calls);self.assertEqual(2,len(m.sdk_calls));self.assertFalse(namespace.decoding)

    def test_json_dumps_mutated_keyword_defaults_cannot_invoke_foreign_class(self):
        import json
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;original=json.dumps.__kwdefaults__['cls'];changes=[];calls=[]
        def foreign(*args,**kwargs):calls.append(namespace.decoding);return json.JSONEncoder(*args,**kwargs)
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                changes.append(1)
                if len(changes)==2:json.dumps.__kwdefaults__['cls']=foreign
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):namespace.measure(lease)
        finally:json.dumps.__kwdefaults__['cls']=original
        self.assertEqual([],calls);self.assertEqual(2,len(m.sdk_calls));self.assertFalse(namespace.decoding)

    def test_plain_graph_rejects_alias_metaclass_without_foreign_equality(self):
        from adapters.pico4.snapshot_settings_namespace import SnapshotSettingsNamespaceBill
        calls=[]
        class Alias(type):
            def __eq__(cls,other):calls.append(1);return True
        class Foreign(metaclass=Alias):pass
        self.assertFalse(SnapshotSettingsNamespaceBill.plain_record(Foreign()));self.assertEqual([],calls)

    def test_managed_finish_descriptor_never_executes_during_class_identity_check(self):
        from adapters.pico4.snapshot_settings_namespace import _SnapshotPackedCosts
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;original=_SnapshotPackedCosts.__dict__['finish'];boundaries=[];calls=[]
        class ForeignDescriptor:
            def __get__(self,obj,owner):
                calls.append(namespace.decoding);return original.__get__(obj,owner)
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                boundaries.append(1)
                if len(boundaries)==2:_SnapshotPackedCosts.finish=ForeignDescriptor()
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):namespace.measure(lease)
        finally:_SnapshotPackedCosts.finish=original
        self.assertEqual([],calls,'Managed-class descriptor executed before identity refusal')
        self.assertEqual(2,len(m.sdk_calls))

    def test_managed_namespace_plain_record_descriptor_never_executes(self):
        from adapters.pico4.snapshot_settings_namespace import SnapshotSettingsNamespaceBill
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;original=SnapshotSettingsNamespaceBill.__dict__['plain_record'];boundaries=[];calls=[]
        class ForeignDescriptor:
            def __get__(self,obj,owner):calls.append(1);return original.__get__(obj,owner)
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                boundaries.append(1)
                if len(boundaries)==2:SnapshotSettingsNamespaceBill.plain_record=ForeignDescriptor()
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):namespace.measure(lease)
        finally:SnapshotSettingsNamespaceBill.plain_record=original
        self.assertEqual([],calls);self.assertEqual(2,len(m.sdk_calls));self.assertTrue(namespace.failed)

    def test_managed_namespace_getattribute_descriptor_never_executes_even_on_failure(self):
        from adapters.pico4.snapshot_settings_namespace import SnapshotSettingsNamespaceBill
        m,lease,namespace=self.make();guard=lease.raw.codec.guard;boundaries=[];calls=[]
        self.assertNotIn('__getattribute__',SnapshotSettingsNamespaceBill.__dict__)
        class ForeignDescriptor:
            def __get__(self,obj,owner):calls.append(1);return object.__getattribute__.__get__(obj,owner)
        def boundary():
            result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):
                boundaries.append(1)
                if len(boundaries)==2:SnapshotSettingsNamespaceBill.__getattribute__=ForeignDescriptor()
            return result
        try:
            with lease.lock.held(),patch.object(lease.raw.codec,'guard',boundary),self.assertRaises(NativeUIError):namespace.measure(lease)
        finally:
            if '__getattribute__' in SnapshotSettingsNamespaceBill.__dict__:del SnapshotSettingsNamespaceBill.__getattribute__
        self.assertEqual([],calls);self.assertEqual(2,len(m.sdk_calls));self.assertTrue(namespace.failed)

    def early_descriptor(self,reader):
        from adapters.pico4.snapshot_settings_namespace import SnapshotSettingsNamespaceBill
        m,lease,namespace=self.make();calls=[];clock_calls=[]
        class ForeignDescriptor:
            def __get__(self,obj,owner):calls.append('get');return False
        codes={getattr(fn,'__code__',None) for fn in (lease.reader.clock_ms,lease.reader.guard)}-{None}
        real=lease.raw.real_clock
        def watched(frame,event,arg):
            if event=='call' and frame.f_code in codes:clock_calls.append('source')
            if event=='c_call' and arg is real:clock_calls.append('real-clock')
        with lease.lock.held():
            SnapshotSettingsNamespaceBill.decoding=ForeignDescriptor()
            old=sys.getprofile()
            try:
                sys.setprofile(watched)
                with self.assertRaises(NativeUIError):
                    if reader:lease.reader.capture(lease.run)
                    else:lease.raw.resource()
            finally:
                sys.setprofile(old);del SnapshotSettingsNamespaceBill.decoding
        self.assertEqual([],calls);self.assertEqual([],clock_calls);self.assertEqual(2,len(m.sdk_calls))
        self.assertFalse(lease.reader.active)

    def test_raw_resource_rejects_namespace_flag_descriptor_before_clock_or_getter(self):self.early_descriptor(False)
    def test_reader_rejects_namespace_flag_descriptor_before_lock_clock_or_getter(self):self.early_descriptor(True)

    def test_actual_active_scope_refuses_source_capacity_reentry_before_callbacks(self):
        from adapters.pico4.snapshot_settings_namespace import _NAMESPACE_DICT,SnapshotSettingsNamespaceBill
        m,lease,namespace=self.make();calls=[];source_calls=[]
        state=_NAMESPACE_DICT.__get__(namespace,SnapshotSettingsNamespaceBill)
        codes={getattr(fn,'__code__',None) for fn in (lease.reader.clock_ms,lease.reader.guard)}-{None}
        real=lease.raw.real_clock
        def watched(frame,event,arg):
            if event=='call' and frame.f_code in codes:source_calls.append('source')
            if event=='c_call' and arg is real:source_calls.append('real-clock')
        with lease.lock.held():
            state['decoding']=state['original_decoding']=True
            old=sys.getprofile()
            try:
                sys.setprofile(watched)
                with patch.object(namespace,'read',lambda *args:calls.append(args)):
                    for operation in (lambda:namespace.measure(lease),lease.raw.resource,lease.raw.fresh,
                            lambda:lease.reader.capture(lease.run)):
                        with self.assertRaises(NativeUIError):operation()
            finally:
                sys.setprofile(old);state['decoding']=state['original_decoding']=False
            self.assertTrue(lease.raw.close_host())
        self.assertEqual([],calls);self.assertEqual([],source_calls);self.assertEqual(2,len(m.sdk_calls))
        self.assertEqual(2,len(lease.raw.state['queries']));self.assertFalse(lease.reader.active)

    def test_profile_fallback_keeps_original_guarded_path_and_budget(self):
        m,lease,namespace=self.make();read=namespace.read;windows=[];inside=[]
        def reading(path,*args):windows.append(path);return read(path,*args)
        def watched(frame,event,arg):
            if namespace.decoding:inside.append(1)
        with lease.lock.held(),patch.object(namespace,'read',reading):
            rows,parts,graphs=namespace.known(lease);old=sys.getprofile()
            try:
                sys.setprofile(watched);bill=namespace.measure(lease)
            finally:sys.setprofile(old)
            self.assertEqual(len(rows),len(windows));self.assertEqual([],inside)
            self.assertLessEqual(bill['decodedBytes']+bill['transientBytes'],16777216)
            self.assertTrue(lease.raw.close_host())
        self.assertEqual(2,len(m.sdk_calls))

    def fault_original(self,m,lease,payload):
        # Declared Host-archive stress/fault, not a Native frame/effect or
        # restoration. Existing owned container/global family remains in use.
        with lease.lock.held():
            owner=m.parent.originals;reference=owner.put('frame',dict(declaredHostStorageFault=payload))
            path=owner.history._path(reference['snapshotOriginal']);raw=path.read_bytes()
        return path,raw

    def test_nested_decode_credit_refuses_actual_large_literal_before_inner_unpack(self):
        from adapters.script_journey.history import pack
        m,lease,namespace=self.make();payload=pack([dict(declaredHostStorageStress='x'*(6*1024*1024))])
        path,raw=self.fault_original(m,lease,payload);caught=[]
        with lease.lock.held():
            try:namespace.measure(lease)
            except NativeUIError as error:
                trace=error.__traceback__
                while trace is not None:
                    frame=trace.tb_frame
                    if frame.f_code.co_name=='expand' and frame.f_locals.get('size')==payload['bytes']:
                        outer=frame;eligible=None
                        while outer is not None and outer.f_code.co_name!='measure':
                            if outer.f_code.co_name=='flush':eligible=outer.f_locals['eligible']
                            outer=outer.f_back
                        caught.append(dict(size=frame.f_locals['size'],eligible=eligible,
                            credit=outer.f_locals['decode_credit'],line=trace.tb_lineno))
                    trace=trace.tb_next
            else:self.fail('Actual nested decoded extent must exceed original credit')
        self.assertTrue(caught);self.assertTrue(all(row['eligible'] for row in caught))
        self.assertTrue(all(3*row['size']>row['credit'] for row in caught))
        self.assertEqual(raw,path.read_bytes());self.assertTrue(namespace.failed);self.assertIsNotNone(namespace.costs.pending)
        namespace.directory.require(namespace.directory.fd);self.assertEqual(2,len(m.sdk_calls));self.assertFalse(namespace.decoding)

    def test_actual_bad_inner_codec_keeps_pending_originals_and_directory_ofd(self):
        import gc,zlib
        m,lease,namespace=self.make();payload=dict(encoding='zlib-base64-json',bytes=2,sha256='0'*64,data='AAAA')
        path,raw=self.fault_original(m,lease,payload)
        with lease.lock.held(),self.assertRaises(zlib.error):namespace.measure(lease)
        gc.collect();self.assertEqual(raw,path.read_bytes());self.assertTrue(namespace.failed)
        self.assertIsNotNone(namespace.costs.pending);namespace.directory.require(namespace.directory.fd)
        self.assertFalse(namespace.close_host());self.assertEqual(2,len(m.sdk_calls));self.assertFalse(namespace.decoding)

    def test_declared_host_storage_400_global_admission_probe(self):
        import json,os,random,time
        m,lease,namespace=self.make();randomness=random.Random(20261104)
        parent_header=m.parent.store.path.read_bytes();baseline_header=lease.store.path.read_bytes()
        old_chunks=list(m.parent.originals.disk['chunks']);old_queries=list(lease.raw.state['queries'])
        refs=[];started=time.monotonic();out=Path(os.environ.get('PICO_BATCH_PROBE_OUT',str(m.h.adb.app.parent)))
        for index in range(400):
            self.assertLess(time.monotonic()-lease.raw.created_actual,120)
            # Pure Host storage/cost corpus, deliberately NEVER consumed as
            # Native frame/effect/Actor facts or ordinary Parent state.
            record=dict(declaredHostStorageCost=index,payload='x'*7500+randomness.randbytes(2048).hex())
            with lease.lock.held():refs.append(m.parent.originals.put('frame',record))
        generated=time.monotonic()-started
        self.assertEqual(parent_header,m.parent.store.path.read_bytes());self.assertEqual(baseline_header,lease.store.path.read_bytes())
        self.assertEqual(old_chunks,m.parent.originals.disk['chunks'][:len(old_chunks)])
        self.assertEqual(old_queries,lease.raw.state['queries']);self.assertEqual(400,len(refs))
        before=time.monotonic();bill=None;failure=None
        with lease.lock.held():
            try:bill=namespace.measure(lease)
            except NativeUIError as error:
                failure=[];trace=error.__traceback__
                while trace is not None:
                    failure.append(dict(function=trace.tb_frame.f_code.co_name,line=trace.tb_lineno))
                    trace=trace.tb_next
            elapsed=time.monotonic()-before
            self.assertLess(time.monotonic()-lease.raw.created_actual,120)
            if bill is not None:
                self.assertLessEqual(bill['parts'],512)
                self.assertLessEqual(bill['decodedBytes']+bill['transientBytes']+2097152,16777216)
        self.assertEqual(2,len(m.sdk_calls));self.assertEqual(['tablet.open'],m.h.adb.controllers)
        (out/'global-host-storage400.json').write_text(json.dumps(dict(qualification='DECLARED_HOST_STORAGE_400_ACTUAL_NAMESPACE_ONLY',
            nativeFacts=False,device=False,whole=False,normalClosedTiming=False,records=400,generatedSeconds=generated,
            measureSeconds=elapsed,admitted=bill is not None,bill=bill,failure=failure,
            parentHeaderUnchanged=True,baselineHeaderUnchanged=True,oldRefsUnchanged=True,
            namespaceFailed=namespace.failed,memoEntries=len(namespace.costs.rows),jsonAndCodeMetadataBytes=namespace.json_bill),indent=2)+'\n')
        self.assertIsNotNone(bill,'Declared400-record corpus must fit the SAME original global bill')

    def test_later_group_mutation_of_earlier_original_is_caught_by_final_whole_footer(self):
        import random,time
        m,lease,namespace=self.make();randomness=random.Random(20261104)
        first=len(m.parent.originals.disk['chunks'])
        for index in range(400):
            self.assertLess(time.monotonic()-lease.raw.created_actual,120)
            with lease.lock.held():m.parent.originals.put('frame',dict(declaredHostStorageCost=index,
                payload='x'*7500+randomness.randbytes(2048).hex()))
        target=m.parent.originals.history._path(first);later=m.parent.originals.history._path(first+399)
        read=namespace.read;target_reads=[];changes=[]
        def reading(path,*args):
            if path==later and len(target_reads)==1 and not changes:changes.append(self.corrupt(target))
            value=read(path,*args)
            if path==target:target_reads.append(1)
            return value
        with lease.lock.held(),patch.object(namespace,'read',reading),self.assertRaises(NativeUIError):namespace.measure(lease)
        self.assertEqual(1,len(target_reads));self.assertEqual(1,len(changes));self.assertEqual(changes[0],target.read_bytes())
        self.assertTrue(namespace.failed);self.assertFalse(namespace.decoding);namespace.directory.require(namespace.directory.fd)
        self.assertEqual(2,len(m.sdk_calls));self.assertEqual(['tablet.open'],m.h.adb.controllers)

    def test_late_group_original_mutation_is_caught_by_final_whole_footer(self):
        import random,time
        m,lease,namespace=self.make();randomness=random.Random(20261104)
        first=len(m.parent.originals.disk['chunks'])
        for index in range(400):
            self.assertLess(time.monotonic()-lease.raw.created_actual,120)
            with lease.lock.held():m.parent.originals.put('frame',dict(declaredHostStorageCost=index,
                payload='x'*7500+randomness.randbytes(2048).hex()))
        target=m.parent.originals.history._path(first+399);read=namespace.read;changes=[]
        def reading(path,*args):
            value=read(path,*args)
            if path==target and not changes:changes.append(self.corrupt(target))
            return value
        with lease.lock.held(),patch.object(namespace,'read',reading),self.assertRaises(NativeUIError):namespace.measure(lease)
        self.assertEqual(1,len(changes));self.assertEqual(changes[0],target.read_bytes());self.assertTrue(namespace.failed)
        self.assertFalse(namespace.decoding);namespace.directory.require(namespace.directory.fd)
        self.assertEqual(2,len(m.sdk_calls));self.assertEqual(['tablet.open'],m.h.adb.controllers)

    def test_actual_same_owner_batch_has_second_full_window_and_no_extra_query(self):
        m,lease,namespace=self.make();windows=[];read=namespace.read;guard=lease.raw.codec.guard;boundaries=[]
        def reading(path,*args):
            self.assertFalse(namespace.decoding);result=read(path,*args);windows.append(path);return result
        def boundary():
            self.assertFalse(namespace.decoding);result=guard()
            if inspect.currentframe().f_back.f_code.co_name in ('measure','flush'):boundaries.append(1)
            return result
        with lease.lock.held(),patch.object(namespace,'read',reading),patch.object(lease.raw.codec,'guard',boundary):
            first=namespace.measure(lease);first_windows=list(windows);windows.clear();second=namespace.measure(lease)
            self.assertEqual(first,second);self.assertEqual(first_windows,windows)
            half=len(windows)//2;self.assertEqual(2*half,len(windows));self.assertEqual(windows[:half],windows[half:]);self.assertGreater(half,0)
            self.assertGreaterEqual(len(boundaries),6);self.assertFalse(namespace.decoding)
            self.assertTrue(lease.raw.close_host())
        self.assertEqual(2,len(m.sdk_calls));self.assertEqual(['tablet.open'],m.h.adb.controllers)


ADMISSION_TESTS={
    'test_declared_host_storage_400_global_admission_probe',
    'test_later_group_mutation_of_earlier_original_is_caught_by_final_whole_footer',
    'test_late_group_original_mutation_is_caught_by_final_whole_footer',
}

def load_tests(loader,tests,pattern):
    return unittest.TestSuite(SnapshotSettingsDecodedGroupsTests(name) for name in
        loader.getTestCaseNames(SnapshotSettingsDecodedGroupsTests) if name not in ADMISSION_TESTS)

if __name__=='__main__':unittest.main(verbosity=2)
