"""Original Native read plus SAME durable raw, over declared SDK/Qt only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib,json,os,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.native_feature_observation import LIMIT
from self_tests import test_pico_lifecycle_background_state5 as fixture_module
from self_tests import test_native_feature_observation as feature_fixture

class LifecycleFeatureOriginalTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.LifecycleBackgroundState5Tests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.owner,self.bank,self.helper=self.fixture.owner,self.fixture.bank,self.fixture.owner.state5
        self.lock=self.fixture.seams.lock

    def prepare(self):
        self.fixture.prepare();return self.owner.runtime[2]

    def assert_no_next_sdk(self,reader,commands,reads):
        with self.lock.held(),self.assertRaises(NativeUIError):self.helper.read_feature_original(reader)
        self.assertEqual(commands,len(self.fixture.seams.feature.commands));self.assertEqual(reads,self.bank.archive.state['reads'])

    def test_work_reserved_before_first_source_and_actual_capture_uses_five_originals_without_second_feature_getter(self):
        self.assertEqual(0,self.bank.archive.state['reads']);self.assertEqual([],self.fixture.seams.feature.commands)
        self.assertEqual((6*LIMIT+3*65536,),self.helper.feature_work)
        self.assertGreaterEqual(self.helper.metadata_bytes(),self.helper.feature_work[0])
        reader=self.prepare();before=self.bank.archive.state['reads']
        with self.lock.held():
            row=self.owner.capture();self.assertEqual(before+5,self.bank.archive.state['reads'])
            records=[r for page in self.bank.archive.pages.values() for r in page['receipts'] if r is not None]
            latest=max((r for r in records if r['role']=='feature'),key=lambda r:r['read'])
            ref=dict(audioRawRangeVersion=1,scopeSha256=self.bank.archive.scope_sha,read=latest['read'],sha256=latest['sha256'])
            self.assertEqual(self.bank.archive.literal(ref),row['native']['raw'])
            self.assertEqual(reader.sequence,json.loads(row['native']['raw'])['sequence'])
            reads=self.bank.archive.state['reads'];self.owner.packet(row);self.assertEqual(reads,self.bank.archive.state['reads'])
        self.assertIsNone(self.helper.active);self.assertEqual([],self.helper.held)

    def test_foreign_same_type_reader_is_refused_before_its_first_sdk(self):
        self.prepare();foreign=feature_fixture.Boundary().reader();reads=self.bank.archive.state['reads']
        commands=len(self.fixture.seams.feature.commands)
        with self.lock.held(),self.assertRaises(NativeUIError):self.helper.read_feature_original(foreign)
        self.assertEqual([],foreign.send.__self__.commands)
        self.assertIs(self.helper.held[-1].source,foreign);self.assert_no_next_sdk(self.owner.runtime[2],commands,reads)

    def test_foreign_instance_read_callable_getter_receives_zero_calls_before_sdk(self):
        reader=self.prepare();calls=[];commands=len(self.fixture.seams.feature.commands);reads=self.bank.archive.state['reads']
        class Foreign:
            def __getattr__(self,name):calls.append(name);raise AssertionError('No foreign getter')
        reader.read=Foreign()
        try:
            with self.lock.held(),self.assertRaises(NativeUIError):self.helper.read_feature_original(reader)
            self.assertEqual([],calls);self.assertEqual(commands,len(self.fixture.seams.feature.commands))
            self.assertEqual(reads,self.bank.archive.state['reads'])
        finally:del reader.read

    def test_capacity_refusal_precedes_original_native_read_and_retains_attempt(self):
        reader=self.prepare();commands=len(self.fixture.seams.feature.commands);reads=self.bank.archive.state['reads']
        original=self.bank.other_bill
        def exhausted():
            value=original();value['decodedBytes']=16*1024*1024;return value
        with self.lock.held(),patch.object(self.bank,'other_bill',exhausted),self.assertRaises(NativeUIError):
            self.helper.read_feature_original(reader)
        self.assertIs(self.helper.held[-1].source,reader)
        self.assert_no_next_sdk(reader,commands,reads)

    def test_business_failure_after_actual_response_keeps_durable_raw_and_returned_value_before_refusal(self):
        reader=self.prepare();retain=self.bank.archive.retain;originals=[];before=self.bank.archive.state['reads']
        def after_response(token,value):
            ref=retain(token,value)
            if token['role']=='feature':originals.append((ref,value));self.bank.failed=True
            return ref
        with self.lock.held(),patch.object(self.bank.archive,'retain',after_response),self.assertRaises(NativeUIError):
            self.helper.read_feature_original(reader)
        self.assertEqual(1,len(originals));self.assertEqual(before+1,self.bank.archive.state['reads'])
        stage=self.helper.held[-1];self.assertIs(type(stage.source),dict)
        self.assertEqual(originals[0][0]['sha256'],hashlib.sha256(originals[0][1].encode()).hexdigest())
        with self.lock.held():self.assertEqual(originals[0][1],self.bank.archive.literal(originals[0][0]))
        self.assert_no_next_sdk(reader,len(self.fixture.seams.feature.commands),self.bank.archive.state['reads'])

    def test_same_byte_root_replacement_after_return_is_not_adopted_or_removed(self):
        reader=self.prepare();retain=self.bank.archive.retain;replaced=[];before=self.bank.archive.state['reads']
        def changed(token,value):
            ref=retain(token,value)
            if token['role']=='feature':
                path=self.bank.archive.path;raw=path.read_bytes();tmp=path.with_name(path.name+'.foreign')
                tmp.write_bytes(raw);tmp.chmod(0o600);os.replace(tmp,path);replaced.append((path,raw,path.stat().st_ino))
            return ref
        with self.lock.held(),patch.object(self.bank.archive,'retain',changed),self.assertRaises(NativeUIError):
            self.helper.read_feature_original(reader)
        self.assertEqual(before+1,self.bank.archive.state['reads']);self.assertEqual(1,len(replaced))
        path,raw,node=replaced[0];self.assertEqual(raw,path.read_bytes());self.assertEqual(node,path.stat().st_ino)
        self.assertIs(type(self.helper.held[-1].source),dict)
        self.assert_no_next_sdk(reader,len(self.fixture.seams.feature.commands),self.bank.archive.state['reads'])

    def test_mutated_fixed_work_cannot_undercount_before_next_native(self):
        reader=self.prepare();commands=len(self.fixture.seams.feature.commands);reads=self.bank.archive.state['reads']
        self.helper.feature_work=(0,)
        with self.lock.held(),self.assertRaises(NativeUIError):self.helper.read_feature_original(reader)
        self.assertEqual(commands,len(self.fixture.seams.feature.commands));self.assertEqual(reads,self.bank.archive.state['reads'])

    def test_after_durable_return_class_descriptor_or_read_code_change_refuses_without_getter_or_next_sdk(self):
        from adapters.native_feature_observation import NativeFeatureObservation
        for mode in ('code','descriptor'):
            with self.subTest(mode=mode):
                fixture=fixture_module.LifecycleBackgroundState5Tests();fixture.setUp()
                self.addCleanup(fixture.doCleanups);fixture.prepare()
                helper,bank,reader=fixture.owner.state5,fixture.bank,fixture.owner.runtime[2]
                original_read=type.__getattribute__(NativeFeatureObservation,'__dict__')['read'];code=original_read.__code__
                retain=bank.archive.retain;originals=[];getters=[];before=bank.archive.state['reads']
                def other(self,*args,**kwargs):raise AssertionError('Foreign read must not execute')
                class Foreign:
                    def __get__(self,instance,owner):getters.append(True);raise AssertionError('No descriptor binding')
                def changed(token,value):
                    ref=retain(token,value)
                    if token['role']=='feature':
                        originals.append((ref,value))
                        if mode=='code':original_read.__code__=other.__code__
                        else:NativeFeatureObservation.read=Foreign()
                    return ref
                try:
                    with fixture.seams.lock.held(),patch.object(bank.archive,'retain',changed),self.assertRaises(NativeUIError):
                        helper.read_feature_original(reader)
                finally:
                    original_read.__code__=code;NativeFeatureObservation.read=original_read
                self.assertEqual([],getters);self.assertEqual(1,len(originals));self.assertEqual(before+1,bank.archive.state['reads'])
                self.assertIs(type(helper.held[-1].source),dict)
                with fixture.seams.lock.held():self.assertEqual(originals[0][1],bank.archive.literal(originals[0][0]))
                commands=len(fixture.seams.feature.commands);reads=bank.archive.state['reads']
                with fixture.seams.lock.held(),self.assertRaises(NativeUIError):helper.read_feature_original(reader)
                self.assertEqual(commands,len(fixture.seams.feature.commands));self.assertEqual(reads,bank.archive.state['reads'])
