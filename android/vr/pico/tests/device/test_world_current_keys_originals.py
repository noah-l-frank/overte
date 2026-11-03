"""Real private files/OFDs/codec; no Native UI, input or source-clock facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import random
import zlib
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device'),str(HERE)]
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.script_journey.history import canonical
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4.world_current_keys_originals import (WorldCurrentKeysOriginals,FILE,LITERAL_FRAGMENT,
    decode_reference,historical_literal,historical_original,source_literal,UNRESOLVED_SOURCE_RECORDS)
from adapters.pico4.world_web_prefix import PicoWorldWebPrefix

BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='123:456',sessionId='STORAGE_MODEL',generation=0,targetFingerprint='c'*64)


class WorldCurrentKeysOriginalsTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-world-keys-storage-'));self.root.chmod(0o700)
        print('Retained real World storage originals:',self.root,flush=True)
        owned=self.root/'owned';owned.mkdir(mode=0o700);self.lock=ScriptSourceLock(self.root/'sources.lock')
        self.parent=SimpleNamespace(root=owned,lock=self.lock,scope=dict(declared='STORAGE_MODEL_ONLY'),state=dict(binding=BINDING))
        self.parent.pins=lambda:PicoWorldWebPrefix.pins(self.parent)
        self.expected=None;self.ledger=None;self.fd_before=len(os.listdir('/proc/self/fd'))
    def guard(self):
        self.lock.assert_held()
        if self.ledger is not None and getattr(self.ledger,'pass_window',None) is not None:self.ledger.pass_window.guard()
        elif self.expected is not None:self.assertEqual(self.expected,PicoWorldWebPrefix.pins(self.parent))
    def remember(self):
        if self.ledger is not None and getattr(self.ledger,'pass_window',None) is not None:self.ledger.pass_window.remember()
        else:self.expected=PicoWorldWebPrefix.pins(self.parent)
    def create(self):
        self.ledger=WorldCurrentKeysOriginals(self.parent,self.guard,self.remember);return self.ledger
    def tearDown(self):
        if self.ledger is not None and not self.ledger.closed:
            # Test-owned normal pairs only; never delete any evidence files.
            self.assertTrue(self.ledger.file.close_host())
        self.assertEqual(self.fd_before,len(os.listdir('/proc/self/fd')))

    def test_literal2_utf8_boundary_and_exact_control_bytes_roundtrip_and_host_close(self):
        text='a'*16383+'🧪äΩ東京\0\n\t'+'z'*17000
        with self.lock.held():
            ledger=self.create();ref=ledger.retain_literal(text)
            self.assertEqual(text,ledger.raw(ref));self.assertEqual(2,ledger.store.read()['picoWorldCurrentKeysOriginalsVersion'])
            for i in ref['parts']:
                row=ledger.rows[i];self.assertEqual('world-keyboard-literal-utf8-base64',row['kind'])
                self.assertLessEqual(len(base64.b64decode(row['value'],validate=True)),LITERAL_FRAGMENT)
                self.assertLessEqual(ledger.chunks.store(i).path.stat().st_size,65536)
            ledger.finish_host()
        self.assertEqual(text,historical_literal(ledger.store,ref))

    def test_exact131072_literal_is_retained_without_weakening64k_source_limit(self):
        with self.lock.held():
            ledger=self.create();text='x'*131072;ref=ledger.retain_literal(text)
            self.assertEqual(8,len(ref['parts']));self.assertEqual(text,ledger.raw(ref));before=deepcopy(ledger.state)
            with self.assertRaises(NativeUIError):ledger.retain_literal(text+'x')
            self.assertEqual(before,ledger.state)

    def test_historical1_reads_old_literal_without_warm_owner_adoption(self):
        store=PrivateFeatureState(self.parent.root/FILE);scope=dict(picoWorldCurrentKeysOriginalsVersion=1,
            parentScope=self.parent.scope,binding=BINDING,producerHostProcessIdentity='HISTORICAL_DECLARED_PRODUCER')
        state=dict(scope,phase='reading',chunks=[],records=[],pending=None);store.write(state,None)
        chunks=ChatSourceChunks(store,scope);chunks.load([]);text='{"textUtf16Hex":"d800","oldRaw":"東京"}'
        state['chunks']=chunks.append(dict(kind='world-keyboard-original',value=text),[])
        ref=dict(parts=[0],bytes=len(text.encode()),sha256=hashlib.sha256(text.encode()).hexdigest());state['records']=[ref]
        store.write(state,store.read());self.assertEqual(text,historical_literal(store,ref))
        self.remember()
        with self.lock.held(),self.assertRaises(NativeUIError):WorldCurrentKeysOriginals(self.parent,self.guard,self.remember)
        self.assertEqual('reading',store.read()['phase'])

    def test_strict_byte_codec_refuses_noncanonical_overlong_mixed_and_wrong_extent(self):
        good=dict(kind='world-keyboard-literal-utf8-base64',value=base64.b64encode(b'a').decode())
        ref=dict(parts=[0],bytes=1,sha256=hashlib.sha256(b'a').hexdigest())
        self.assertEqual('a',decode_reference([good],ref))
        cases=[([dict(good,value='YR==')],ref),([dict(good,value='YQ')],ref),
            ([dict(good,value=base64.b64encode(b'x'*(LITERAL_FRAGMENT+1)).decode())],ref),
            ([dict(good,value=base64.b64encode(b'\xff').decode())],dict(ref,sha256=hashlib.sha256(b'\xff').hexdigest())),
            ([good],dict(ref,bytes=True)),([good],dict(ref,parts=[False])),([good],dict(ref,sha256='f'*64)),
            ([good,dict(kind='world-keyboard-original',value='a')],dict(ref,parts=[0,1],bytes=2,sha256=hashlib.sha256(b'aa').hexdigest())),
            ([good,good],dict(ref,parts=[0,1],bytes=2,sha256=hashlib.sha256(b'aa').hexdigest()))]
        for rows,wrong in cases:
            with self.subTest(rows=rows,reference=wrong),self.assertRaises((NativeUIError,ValueError,UnicodeError)):decode_reference(rows,wrong)

    def test_exact_original_reuse_keeps_new_query_requests_and_raws_new(self):
        original=dict(raw='{"actual":"東京"}',request=dict(commandId='a'*32),documentOriginal=dict(raw='{}',request=dict(commandId='b'*32)))
        with self.lock.held():
            ledger=self.create();one=ledger.retain_source(dict(kind='request',request=dict(commandId='1'*32),focusOriginal=original))
            count=len(ledger.rows);held=[original,original['request'],original['documentOriginal']]
            two=ledger.retain_source(dict(kind='request',request=dict(commandId='2'*32),focusOriginal=deepcopy(original)))
            self.assertEqual(count+1,len(ledger.rows));self.assertNotEqual(one,two)
            first=ledger.read(one);second=ledger.read(two)
            self.assertEqual(first['focusOriginalReference'],second['focusOriginalReference']);self.assertNotEqual(first['request'],second['request'])
            a=ledger.retain_source(dict(kind='raw',request=dict(commandId='1'*32),raw='not-json'))
            b=ledger.retain_source(dict(kind='raw',request=dict(commandId='2'*32),raw='not-json'))
            self.assertNotEqual(a,b);self.assertEqual('not-json',source_literal(ledger.read(a),ledger.raw))
            self.assertNotEqual(ledger.read(a)['request'],ledger.read(b)['request'])
            self.assertEqual(original,ledger.original(first['focusOriginalReference']));self.assertEqual(3,len(held))

    def test_forged_reference_cache_or_same_byte_replaced_child_cannot_redirect_original(self):
        with self.lock.held():
            ledger=self.create();value=dict(raw='one',request=dict(commandId='1'*32));a=ledger.intern_original(value)
            b=ledger.intern_original(dict(raw='two',request=dict(commandId='2'*32)))
            digest=json_digest(value);pinned,_old=ledger.original_index[digest];ledger.original_index[digest]=(pinned,canonical(b))
            before=deepcopy(ledger.state)
            with self.assertRaises(NativeUIError):ledger.intern_original(value)
            self.assertEqual(before,ledger.state)
            ledger.original_index[digest]=(pinned,canonical(a))
            child=ledger.chunks.store(a['parts'][0]).path;raw=child.read_bytes();child.rename(self.root/'held-original-child.json')
            child.write_bytes(raw);child.chmod(0o600)
            with self.assertRaises((NativeUIError,AssertionError)):ledger.intern_original(value)

    def test_original_header_capacity_has_zero_new_child_when_global512_is_full(self):
        with self.lock.held():
            ledger=self.create();count=512-len(list(self.parent.root.iterdir()))
            for i in range(count):
                p=self.parent.root/('independent-original-%03d.json'%i);p.write_text('{}\n');p.chmod(0o600)
            self.remember();before=deepcopy(ledger.state)
            with self.assertRaises(NativeUIError):ledger.capacity()
            self.assertEqual(before,ledger.state);self.assertEqual(512,len(list(self.parent.root.iterdir())))

    def test_original_bundle_resolves_actual_originals_in_historical2_after_host_close(self):
        original=dict(raw='{"actual":true}',request=dict(commandId='a'*32),focusOriginal=dict(raw='{}',request=dict(commandId='b'*32)))
        with self.lock.held():
            ledger=self.create();request=ledger.retain_source(dict(request=original['request'],focusOriginal=original['focusOriginal']))
            raw=ledger.retain_source(dict(request=original['request'],raw=original['raw']))
            bundle=ledger.retain(dict(kind='keyboard-original-bundle',references=dict(request=request,raw=raw),sha256=json_digest(original)))
            self.assertEqual(original,ledger.original(bundle));ledger.finish_host()
        self.assertEqual(original,historical_original(ledger.store,bundle))

    def test_bounded_inline_candidate_and_incompressible_maximum_fallback_preserve_actual_raw(self):
        randomizer=random.Random(7721);text=''.join(chr(randomizer.randrange(33,127)) for _ in range(131072))
        with self.lock.held():
            ledger=self.create();small=ledger.retain_source(dict(kind='raw',request=dict(commandId='a'*32),raw='東京'*100))
            inline=ledger.read(small);self.assertEqual(1,inline['literalCodecVersion']);self.assertEqual('utf8-base64-inline',inline['literalEncoding'])
            self.assertEqual(1,len(small['parts']));self.assertEqual('東京'*100,source_literal(inline,ledger.raw))
            large=ledger.retain_source(dict(kind='raw',request=dict(commandId='b'*32),raw=text));fallback=ledger.read(large)
            self.assertNotIn('literalCodecVersion',fallback);self.assertIn('literalReference',fallback)
            self.assertEqual(8,len(fallback['literalReference']['parts']));self.assertEqual(text,source_literal(fallback,ledger.raw))

    def test_exact_actual48k_pack_boundary_selects_inline_or_lossless_fallback(self):
        from adapters.script_journey.history import MAX_PACKED
        randomizer=random.Random(9727);noise=''.join(chr(randomizer.randrange(33,127)) for _ in range(60000));choices=[]
        def size_at(size):
            text=noise[:size];data=text.encode()
            value=dict(kind='raw',request=dict(commandId=('%032x'%size)),literalCodecVersion=1,literalEncoding='utf8-base64-inline',
                literalBytes=len(data),literalSha256=hashlib.sha256(data).hexdigest(),literalData=base64.b64encode(data).decode())
            return len(base64.b64encode(zlib.compress(canonical([dict(kind='world-keyboard-original',value=canonical(value).decode())]),level=9)))
        low,high=30000,60000
        self.assertLessEqual(size_at(low),MAX_PACKED);self.assertGreater(size_at(high),MAX_PACKED)
        while high-low>1:
            middle=(low+high)//2
            if size_at(middle)<=MAX_PACKED:low=middle
            else:high=middle
        with self.lock.held():
            ledger=self.create()
            for size in (low,high):
                text=noise[:size];value=dict(kind='raw',request=dict(commandId=('%032x'%size)),raw=text);data=text.encode()
                inline={k:v for k,v in value.items() if k!='raw'};inline.update(literalCodecVersion=1,literalEncoding='utf8-base64-inline',
                    literalBytes=len(data),literalSha256=hashlib.sha256(data).hexdigest(),literalData=base64.b64encode(data).decode())
                frame=dict(kind='world-keyboard-original',value=canonical(inline).decode())
                predicted=len(base64.b64encode(zlib.compress(canonical([frame]),level=9)))<=MAX_PACKED
                ref=ledger.retain_source(value);stored=ledger.read(ref);self.assertEqual(predicted,'literalCodecVersion' in stored)
                self.assertEqual(text,source_literal(stored,ledger.raw));choices.append(predicted)
                for i in ref['parts']:self.assertLessEqual(ledger.chunks.store(i).path.stat().st_size,65536)
            self.assertEqual([True,False],choices)

    def test_inline_discriminator_false_extent_padding_and_mixed_forms_refuse(self):
        data=b'actual';record=dict(request=dict(commandId='a'*32),literalCodecVersion=1,literalEncoding='utf8-base64-inline',
            literalBytes=len(data),literalSha256=hashlib.sha256(data).hexdigest(),literalData=base64.b64encode(data).decode())
        self.assertEqual('actual',source_literal(record,lambda _ref:None))
        for mutation in (dict(literalCodecVersion=True),dict(literalEncoding='base64'),dict(literalBytes=True),
                dict(literalSha256='f'*64),dict(literalData='YR=='),dict(literalReference=dict(parts=[]))):
            with self.subTest(mutation=mutation),self.assertRaises((NativeUIError,ValueError)):
                source_literal(dict(record,**mutation),lambda _ref:None)

    def test_unknown_actual_header_cas_retains_acquired_raw_and_fails_sticky(self):
        value=dict(kind='raw',request=dict(commandId='a'*32),raw='actual acquired bytes 東京')
        with self.lock.held():
            ledger=self.create();before=ledger.store.path.read_bytes();count=len(ledger.rows)
            with patch.object(ledger.file,'write',side_effect=RuntimeError('DECLARED_LOST_CAS')),self.assertRaises(RuntimeError):ledger.retain_source(value)
            self.assertTrue(ledger.failed);self.assertEqual(count,len(ledger.rows));self.assertEqual(before,ledger.store.path.read_bytes())
            self.assertTrue(any(record is value for record in UNRESOLVED_SOURCE_RECORDS))
            with self.assertRaises(NativeUIError):ledger.retain_source(value)


if __name__=='__main__':unittest.main()
