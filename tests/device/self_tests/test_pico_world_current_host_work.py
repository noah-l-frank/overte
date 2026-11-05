"""Eight new pure work-bound cases. No old reader suite/owner/SDK runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json,math,sys,unittest
from pathlib import Path
from adapters.pico4.world_json_work import project,WorldJsonWorkRefused,MAX_WIRE,LEXICAL_SLOT
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.native_feature_observation import decode,NativeUIError
from self_tests.pico_world_current_host_fixture import fixture


def has_surrogate(value):
    if type(value) is str:return any(0xd800<=ord(c)<=0xdfff for c in value)
    if type(value) is list:return any(has_surrogate(v) for v in value)
    if type(value) is dict:return any(has_surrogate(k) or has_surrogate(v) for k,v in value.items())
    return False


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

def wire_with_echo(message):
    request,value=fixture()
    original=value['source']['dom']
    original['echoes']=[dict(sequence=1,surface='world',message=message,receivedEpochMs=10001,observedEpochMs=10002)]
    transaction=json.loads(value['source']['domRaw'])
    transaction['domRaw']=json.dumps(json.dumps(original))
    value['source']['domRaw']=json.dumps(transaction)
    return json.dumps(value)


class WorkTests(unittest.TestCase):
    def test_strings_unicode_escape_and_key_exact_lengths(self):
        values=['','ascii','a"/\\b','\b\f\n\r\t\0\x1f\x7f','ä Ω 東京','😀a'*30,'a'*1000+'😀',
            {'ä😀':'東京','escaped':'\\u1234'},['\ud800','\udfff','\ud800\udfff']]
        for value in values:
            for ensure_ascii in (True,False):
                # JSON literals containing actual unpaired surrogate UTF8 are
                # invalid transport bytes. Escaped originals remain admitted.
                if not ensure_ascii and has_surrogate(value):continue
                raw=json.dumps(value,ensure_ascii=ensure_ascii)
                work=project(raw)
                self.assertEqual(canonical_size(json.loads(raw)),work.max_canonical)
                if type(json.loads(raw)) is str:self.assertLessEqual(sys.getsizeof(json.loads(raw))-128,4*work.max_canonical)
        escaped=r'{"\u0061":"\/\u007f\u0008\u0022\u005c"}'
        self.assertEqual(canonical_size(json.loads(escaped)),project(escaped).max_canonical)

    def test_integer_float_extremes_signed_zero_and_overflow_bound(self):
        values=[0,-1,2**64-1,-(2**64),-0.,1e15,1e16,1e-4,1e-5,sys.float_info.max,sys.float_info.min,5e-324]
        for value in values:
            raw=json.dumps(value,allow_nan=False)
            self.assertGreaterEqual(project(raw).max_canonical,canonical_size(json.loads(raw)))
        for raw in ('-0','-0.0','1e15','1e-4','1e309','1e-999'):
            work=project(raw);parsed=json.loads(raw)
            if type(parsed) is float and not math.isfinite(parsed):
                with self.assertRaises((ValueError,NativeUIError)):canonical_size(parsed)
                self.assertEqual(32,work.max_canonical)
            else:self.assertGreaterEqual(work.max_canonical,canonical_size(parsed))

    def test_original_document_all_actual_nested_streams(self):
        request,value=fixture();raw=json.dumps(value);work=project(raw)
        counts=dict(work.streams)
        self.assertEqual({'outer':1,'transaction':1,'quoted-dom':1,'dom':1,'echo':0,'frame':0},counts)
        self.assertGreaterEqual(work.max_canonical,canonical_size(value))
        self.assertGreater(work.total_nodes,100)
        self.assertGreater(work.combined_depth,4)
        self.assertEqual(48*work.max_canonical,work.decoded_data)

    def test_echo_float_unicode_and_escaped_real_field_keys(self):
        message=canonical(dict(contract='overte-web-parity-v1',action='echo',sequence=1e15,surface='world'))
        raw=wire_with_echo(message)
        # Exact decoded field names still select the real nested stream.
        raw=raw.replace('"source":',r'"\u0073ource":',1)
        raw=raw.replace('"domRaw":',r'"dom\u0052aw":',1)
        work=project(raw)
        self.assertEqual(1,dict(work.streams)['echo'])
        self.assertGreaterEqual(work.max_canonical,canonical_size(json.loads(message)))
        self.assertGreaterEqual(work.max_canonical,canonical_size(json.loads(raw)))

    def test_malformed_literals_and_nested_literals_refuse_without_dto(self):
        for raw in ('{','[0,]','{"x":}','"unterminated','01','NaN','Infinity','[true false]'):
            with self.subTest(raw=raw),self.assertRaises(WorldJsonWorkRefused):project(raw)
        for nested in ('','{"domRaw":"bad"}','{"domRaw":"\\"{\\""}'):
            raw=json.dumps({'source':{'domRaw':nested}})
            with self.subTest(nested=nested),self.assertRaises(WorldJsonWorkRefused):project(raw)

    def test_duplicate_fields_are_counted_not_forgiven_and_wrong_raw_type(self):
        raw='{"x":1,"x":2}'
        work=project(raw)
        self.assertGreater(work.max_canonical,canonical_size(json.loads(raw)))
        with self.assertRaises(NativeUIError):decode(raw)
        for value in (True,None,{},b'{}'):
            with self.assertRaises(WorldJsonWorkRefused):project(value)
        with self.assertRaises(WorldJsonWorkRefused):project(' '*MAX_WIRE+'0')

    def test_only_integer_plan_escapes_and_metadata_is_explicit(self):
        raw=wire_with_echo(canonical(dict(contract='overte-web-parity-v1',action='echo',sequence=1,surface='world')))
        work=project(raw)
        self.assertTrue(all(type(getattr(work,name)) is int for name in ('utf8_bytes','max_canonical','total_nodes','combined_depth','decoded_data','decoded_metadata','lexical_slot')))
        self.assertEqual(12*256*(work.total_nodes+1)+1024*(work.combined_depth+1)+4096,work.decoded_metadata)
        self.assertEqual(LEXICAL_SLOT,work.lexical_slot)
        self.assertTrue(all(type(k) is str and type(v) is int for k,v in work.streams))
        self.assertEqual(12*MAX_WIRE+max(52*MAX_WIRE,work.decoded_data+work.decoded_metadata)+8*4096,work.call_work)
        # Ordinary actual CPython container metadata, not a universal RSS
        # theorem. JSON node counts include container,keys and scalar values.
        for count in (0,1,2,5,8,16,32,64,256,512,1000):
            keys=[str(i) for i in range(count)]
            pairs=[(key,None) for key in keys];mapping=dict(pairs)
            key_headers=sum(sys.getsizeof(key)-len(key) for key in keys)
            pairmeta=sys.getsizeof(pairs)+sum(sys.getsizeof(pair) for pair in pairs)+key_headers
            dictmeta=sys.getsizeof(mapping)+key_headers
            nodes=2*count+1
            self.assertLessEqual(pairmeta,256*(nodes+1))
            self.assertLessEqual(dictmeta,256*(nodes+1))


    def test_large_valid_shape_demands_capacity_and_empty_is_not_null(self):
        raw='['+','.join('0' for _ in range(6000))+']'
        work=project(raw)
        self.assertGreater(work.call_work,16777216)
        self.assertGreaterEqual(work.max_canonical,canonical_size(json.loads(raw)))
        empty=project('');self.assertEqual(0,empty.max_canonical)
        self.assertNotEqual(empty.max_canonical,project('null').max_canonical)

if __name__=='__main__':unittest.main()
