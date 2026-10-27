"""Pure KeySource reuse retains packet checks and the actual enclosing budget."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile
import json
import pstats
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_keys as keys,world_web_api_clock as api
from ios.self_tests import test_ios_world_web_keys as fixture


class WorldWebKeyValidationTests(unittest.TestCase):
    def packet(self):
        qt=fixture.QtKeys();qt.finish(qt.enter('key-press'));qt.finish(qt.enter('key-release'))
        return qt.packet()
    def counted(self,action):
        profile=cProfile.Profile();profile.enable(subcalls=False,builtins=False)
        try:action()
        finally:profile.disable()
        code=keys._source.__code__
        return pstats.Stats(profile).stats[(code.co_filename,code.co_firstlineno,code.co_name)][1]
    def test_default_and_unbudgeted_round_always_execute_literal_validation(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        def repeat():
            with keys.validation_round():
                self.assertIs(value,keys.source(value,epoch));self.assertIs(value,keys.source(value,epoch))
                self.assertIsNone(keys._SOURCE_VALIDATION.get())
        self.assertEqual(2,self.counted(repeat))
    def test_equal_inputs_share_only_pure_success_and_return_current_independent_input(self):
        packet=self.packet();value=packet['source'];other=deepcopy(value);epoch=packet['clockBefore']['epochMs']
        def repeat():
            with api.scope(lambda:0.):
                self.assertIs(value,keys.source(value,epoch));self.assertIs(other,keys.source(other,epoch))
                self.assertEqual(1,len(keys._SOURCE_VALIDATION.get()['entries']))
                other['complete']=False
                self.assertTrue(value['complete']);self.assertIs(other,keys.source(other,epoch))
        self.assertEqual(2,self.counted(repeat));self.assertIsNone(keys._SOURCE_VALIDATION.get())
    def test_new_call_and_exception_discard_all_successes(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        def repeat():
            with self.assertRaisesRegex(RuntimeError,'sentinel'),api.scope(lambda:0.):
                keys.source(value,epoch);raise RuntimeError('sentinel')
            self.assertIsNone(keys._SOURCE_VALIDATION.get())
            with api.scope(lambda:0.):keys.source(value,epoch)
        self.assertEqual(2,self.counted(repeat))
    def test_independent_json_reads_and_retained_scalar_aliases_keep_identical_input_keys(self):
        packet=self.packet();value=json.loads(json.dumps(packet['source']));other=json.loads(json.dumps(value))
        epoch=packet['clockBefore']['epochMs'];held=[];clock=dict(calls=0,retain=None)
        def monotonic():
            clock['calls']+=1
            if clock['calls']==clock['retain']:held.append(other['instance'])
            return 0.
        def repeat():
            with api.scope(monotonic):
                self.assertIs(value,keys.source(value,epoch))
                clock['retain']=clock['calls']+2
                self.assertIs(other,keys.source(other,epoch))
                self.assertEqual([other['instance']],held)
        self.assertEqual(1,self.counted(repeat))
    def test_nested_round_keeps_original_deadline_and_warm_hit_cannot_extend_it(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs'];clock=[0.]
        with self.assertRaises(NativeUIError),api.scope(lambda:clock[0]):
            keys.source(value,epoch);cache=keys._SOURCE_VALIDATION.get();clock[0]=24.
            with api.scope(lambda:0.):
                self.assertIs(cache,keys._SOURCE_VALIDATION.get());keys.source(value,epoch)
                clock[0]=25.;keys.source(value,epoch)
        self.assertIsNone(keys._SOURCE_VALIDATION.get());self.assertFalse(api.active())
    def test_boolean_scalar_and_changed_epoch_never_borrow_a_success(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        with api.scope(lambda:0.):
            keys.source(value,epoch)
            for field in ('iosWorldWebKeySourceVersion','eventSequence','pendingDispatches','qtModifiers'):
                changed=deepcopy(value);changed[field]=bool(changed[field])
                with self.subTest(field=field),self.assertRaises(NativeUIError):keys.source(changed,epoch)
            with self.assertRaises(NativeUIError):keys.source(value,value['bornEpochMs']-1)
            self.assertEqual(1,len(keys._SOURCE_VALIDATION.get()['entries']))
    def test_changed_helper_code_or_constants_keep_literal_rejection(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        with api.scope(lambda:0.):
            keys.source(value,epoch)
            with patch.object(keys,'nonce',side_effect=NativeUIError('Changed helper')):
                with self.assertRaisesRegex(NativeUIError,'Changed helper'):keys.source(value,epoch)
            with patch.object(keys,'READS',(1,)):
                with self.assertRaises(NativeUIError):keys.source(value,epoch)
            function=keys.nonce;code=function.__code__
            def changed(_value):raise ValueError('Changed code')
            function.__code__=changed.__code__
            try:
                with self.assertRaisesRegex(ValueError,'Changed code'):keys.source(value,epoch)
            finally:function.__code__=code
            def repeated_clone():
                function.__code__=code.replace()
                try:keys.source(value,epoch);keys.source(value,epoch)
                finally:function.__code__=code
            self.assertEqual(2,self.counted(repeated_clone))
    def test_equal_comparing_reader_object_cannot_impersonate_literal_function_identity(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs'];original=keys.exact
        class Changed:
            __code__=original.__code__
            __defaults__=original.__defaults__
            __kwdefaults__=original.__kwdefaults__
            def __eq__(self,other):return True
            def __call__(self,*args):raise NativeUIError('Different exact reader')
        with api.scope(lambda:0.):
            keys.source(value,epoch)
            with patch.object(keys,'exact',Changed()):
                with self.assertRaisesRegex(NativeUIError,'Different exact reader'):keys.source(value,epoch)
    def test_serialization_and_hash_replacement_cannot_transfer_success_to_different_input(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        with api.scope(lambda:0.):
            keys.source(value,epoch);changed=deepcopy(value);changed['pendingDispatches']+=1
            old_key=next(iter(keys._SOURCE_VALIDATION.get()['entries']))
            class ConstantDigest:
                def digest(self):return old_key
            with patch.object(keys.hashlib,'sha256',return_value=ConstantDigest()):
                with self.assertRaises(NativeUIError):keys.source(changed,epoch)
            marshal=keys.marshal.dumps;encoded=marshal((value,epoch),2)
            def selective(arguments,version):
                if type(arguments) is tuple and len(arguments)==2 and arguments[0] is changed:return encoded
                return marshal(arguments,version)
            with patch.object(keys.marshal,'dumps',side_effect=selective):
                with self.assertRaises(NativeUIError):keys.source(changed,epoch)
    def test_budget_callable_cannot_mutate_cold_or_warm_input_after_validation(self):
        for warm in (False,True):
            packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs'];clock=dict(calls=0,mutate=None)
            def monotonic():
                clock['calls']+=1
                if clock['calls']==clock['mutate']:value['pendingDispatches']+=1
                return 0.
            with self.subTest(warm=warm),self.assertRaises(NativeUIError),api.scope(monotonic):
                if warm:keys.source(value,epoch)
                clock['mutate']=clock['calls']+2
                keys.source(value,epoch)
    def test_unsupported_serialization_and_capacity_fall_back_without_verdict_cache(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        def repeat():
            with api.scope(lambda:0.):
                with patch.object(keys.marshal,'dumps',side_effect=TypeError('Unsupported')):
                    keys.source(value,epoch);keys.source(value,epoch)
                self.assertEqual(set(),keys._SOURCE_VALIDATION.get()['entries'])
                with patch.object(keys,'_SOURCE_ENTRIES',1):
                    keys.source(value,epoch);keys.source(value,epoch+1);keys.source(value,epoch+1)
                self.assertEqual(1,len(keys._SOURCE_VALIDATION.get()['entries']))
        self.assertEqual(5,self.counted(repeat))
    def test_outer_packet_headers_freshness_and_previous_relations_still_run(self):
        packet=self.packet();query=dict(schemaVersion=1,action=keys.ACTION,commandId=packet['requestId'],runId=packet['runId'])
        with api.scope(lambda:0.):
            keys.source(packet['source'],packet['clockBefore']['epochMs'])
            self.assertIs(packet,keys.validate(packet,query,42,packet['clockAfter']['epochMs']))
            with self.assertRaises(NativeUIError):keys.validate(packet,query,43)
            with self.assertRaises(NativeUIError):keys.validate(packet,query,42,packet['clockAfter']['epochMs']+1501)
            with self.assertRaises(NativeUIError):keys.validate(packet,query,42,previous=deepcopy(packet))
    def test_memory_budget_charges_only_retained_digests_and_input_limit_stays_separate(self):
        packet=self.packet();value=packet['source'];epoch=packet['clockBefore']['epochMs']
        def repeat():
            with api.scope(lambda:0.),patch.object(keys,'_SOURCE_BYTES',32):
                keys.source(value,epoch);cache=keys._SOURCE_VALIDATION.get()
                self.assertEqual(32,cache['bytes']);self.assertEqual(1,len(cache['entries']))
                keys.source(value,epoch+1);keys.source(value,epoch+1)
                self.assertEqual(32,cache['bytes']);self.assertEqual(1,len(cache['entries']))
            with api.scope(lambda:0.),patch.object(keys,'_SOURCE_INPUT_BYTES',1):
                keys.source(value,epoch);keys.source(value,epoch)
                self.assertEqual(0,keys._SOURCE_VALIDATION.get()['bytes'])
        self.assertEqual(5,self.counted(repeat))


if __name__=='__main__':unittest.main()
