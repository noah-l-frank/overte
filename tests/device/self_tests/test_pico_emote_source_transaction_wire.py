"""One real shell return and original RawArchive; declared Native wire model.

No TSI, Qt, Native publisher or Source/Parent factory runs in these components.
The six labeled payloads intentionally do not claim valid native observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4 import emote_source_transaction_wire as source
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import canonical

RETAINED=[]


class SourceTransactionWireTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-emote-source-transaction-wire-'))
        self.lock=ScriptSourceLock(self.root/'source.lock');self.now=1.;self.calls=[]
        self.cost=dict(parts=2,storedBytes=source.WIRE_LIMIT+1024,decodedBytes=source.WIRE_LIMIT+1024)
        self.raw=AudioRawArchive(self.root/'source-raw.json',dict(picoEmoteSourceTransactionVersion=1,
            declaredHostModel=True),self.lock,lambda:None,lambda:dict(self.cost),self.clock)
        self.command=dict(schemaVersion=1,action='feature-pico-emote-source-transaction',
            commandId='1'*32,runId='2'*32,originalPolicySha256='3'*64,parentBaselineSha256='4'*64)
        self.literal=self.body();self.first_clock=self.first_guard=self.after_sdk=None;self.partial=False;self.empty_timeout=False;self.nonzero=False
        self.owner=source.PicoEmoteSourceTransactionWire(self.raw,self.exchange,self.guard,self.clock)
        self.addCleanup(self.finalize)
        print('Retained Source transaction Host wire originals:',self.root,flush=True)

    def clock(self):
        if getattr(self,'first_clock',None) is not None:
            callback,self.first_clock=self.first_clock,None;callback()
        return self.now

    def guard(self):
        if self.first_guard is not None:
            callback,self.first_guard=self.first_guard,None;callback()
        return True

    def body(self,overrides=None,pending=0):
        header=dict(self.command,picoEmoteSourceTransactionVersion=1,complete=True,sourceCount=6)
        result=source.HEADER+canonical(header)+b'\n';overrides=overrides or {}
        for label in source.LABELS:
            if label=='native':
                for _ in range(pending):
                    raw=canonical(dict(schemaVersion=1,requestId='a'*32,pending=True))
                    result+=b'nativePending '+str(len(raw)).encode()+b' '+hashlib.sha256(raw).hexdigest().encode()+b'\n'+raw+b'\n'
            raw=overrides.get(label,canonical(dict(declaredNativeModel=True,label=label)))
            result+=label.encode()+b' '+str(len(raw)).encode()+b' '+hashlib.sha256(raw).hexdigest().encode()+b'\n'+raw+b'\n'
        return result+source.FOOTER

    def exchange(self,value,*,timeout):
        self.calls.append(deepcopy(value));self.assertGreater(timeout,0);self.assertLessEqual(timeout,5)
        blob=self.root/'declared-native-wire.bin';blob.write_bytes(self.literal);blob.chmod(0o600)
        command=self.root/'actual-transport-input.json'
        if self.nonzero:
            return subprocess.run(['sh','-c','head -c 211 "$1"; exit 7','declared-nonzero-source',str(blob)],
                input=canonical(value),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=True).stdout
        if self.empty_timeout:
            return subprocess.run([sys.executable,'-S','-c','import time;time.sleep(.2)'],input=canonical(value),
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=.1,check=True).stdout
        if self.partial:
            # One actual SDK-model process, killed and reaped by subprocess.run.
            program='import sys,time;sys.stdout.buffer.write(open(sys.argv[1],"rb").read(173));sys.stdout.flush();time.sleep(.2)'
            return subprocess.run([sys.executable,'-S','-c',program,str(blob)],input=canonical(value),
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=.1,check=True).stdout
        result=subprocess.run(['sh','-c','umask 077; cat > "$1"; cat "$2"','declared-source-wire',str(command),str(blob)],
            input=canonical(value),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=True)
        self.assertEqual(canonical(value),command.read_bytes())
        if self.after_sdk is not None:self.after_sdk(value)
        return result.stdout

    def finalize(self):
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for path in self.root.rglob('*') if path.is_file()}
        before=inventory();self.assertTrue(self.raw.close_host());after=inventory();self.assertEqual(before,after)
        RETAINED.append(dict(root=str(self.root),files=after,actualRawArchiveCloseCalled=True,processesRemaining=0))

    def test_one_actual_return_is_retained_before_first_header_or_source_parser(self):
        parser=source.strict_json;observed=[]
        def parse(text):
            self.assertIsNotNone(self.owner.reference)
            self.assertEqual(self.literal,self.raw.literal(self.owner.reference));observed.append(True)
            return parser(text)
        with self.lock.held(),patch.object(source,'strict_json',side_effect=parse):
            reference,proof,values=self.owner.read(self.command)
            self.assertEqual(self.literal,self.raw.literal(reference))
            with self.assertRaises(NativeUIError):
                self.owner.read(dict(self.command,originalPolicySha256='6'*64))
        self.assertEqual(1,len(self.calls));self.assertEqual(1,self.raw.state['reads'])
        self.assertEqual(source.LABELS,tuple(values));self.assertEqual(6,len(proof.records));self.assertEqual(7,len(observed))

    def test_actual_one_mib_incompressible_nul_return_is_preserved_and_never_retried(self):
        self.literal=os.urandom(source.WIRE_LIMIT-1)+b'\0'
        with self.lock.held(),patch.object(source,'strict_json') as parser:
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
            parser.assert_not_called();self.assertEqual(self.literal,self.raw.literal(self.owner.reference))
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
        self.assertEqual(1,len(self.calls));self.assertEqual(1,self.raw.state['reads'])
        self.assertTrue(all(row['bytes']<=65536 for row in self.raw.state['parts']))

    def test_actual_sdk_timeout_partial_stdout_is_retained_before_any_parser(self):
        self.partial=True
        with self.lock.held(),patch.object(source,'strict_json') as parser:
            with self.assertRaises(subprocess.TimeoutExpired):self.owner.read(self.command)
            parser.assert_not_called();self.assertEqual(self.literal[:173],self.raw.literal(self.owner.reference))
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
        self.assertEqual(1,len(self.calls));self.assertFalse(self.raw.state['pending'])

    def test_second_unknown_reply_cannot_expose_prior_literal_as_current_return(self):
        with self.lock.held():
            old,_,_=self.owner.read(self.command)
            self.empty_timeout=True;next_request=dict(self.command,commandId='5'*32)
            with self.assertRaises(subprocess.TimeoutExpired):self.owner.read(next_request)
            self.assertIsNone(self.owner.reference);self.assertIsNotNone(self.owner.pending)
            self.assertEqual(2,self.raw.state['reads']);self.assertEqual(1,len(self.raw.state['pending']))
            self.assertEqual(self.literal,self.raw.literal(old))
            with self.assertRaises(NativeUIError):self.owner.read(next_request)
        self.assertEqual(2,len(self.calls));self.assertTrue(self.owner.failed)

    def test_actual_nonzero_sdk_process_partial_stdout_remains_original_before_failure(self):
        self.nonzero=True
        with self.lock.held(),patch.object(source,'strict_json') as parser:
            with self.assertRaises(subprocess.CalledProcessError):self.owner.read(self.command)
            parser.assert_not_called();self.assertEqual(self.literal[:211],self.raw.literal(self.owner.reference))
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
        self.assertEqual(1,len(self.calls));self.assertFalse(self.raw.state['pending'])

    def capacity(self,key,limit):
        self.cost[key]=limit
        with self.lock.held(),self.assertRaises(NativeUIError):self.owner.read(self.command)
        self.assertEqual([],self.calls);self.assertEqual(0,self.raw.state['reads'])
        with self.lock.held(),self.assertRaises(NativeUIError):self.owner.read(self.command)
        self.assertEqual([],self.calls) # Sticky refusal; no fresh budget/owner retry.

    def test_same_compound_512_part_cap_refuses_before_real_transport(self):self.capacity('parts',512)
    def test_same_compound_stored_byte_cap_refuses_before_real_transport(self):self.capacity('storedBytes',16777216)
    def test_same_compound_decoded_byte_cap_refuses_before_real_transport(self):self.capacity('decodedBytes',16777216)

    def reentry(self,field):
        claims=[]
        def nested():
            claim=self.owner.active;self.assertIsNotNone(claim)
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
            self.assertIs(claim,self.owner.active);claims.append(claim)
        setattr(self,field,nested)
        with self.lock.held(),self.assertRaises(NativeUIError):self.owner.read(self.command)
        self.assertEqual([],self.calls);self.assertEqual(0,self.raw.state['reads'])
        self.assertEqual(1,len(claims));self.assertIs(claims[0],self.owner.claims[0][0])

    def test_first_clock_reentry_keeps_outer_claim_and_sends_zero_sdk(self):self.reentry('first_clock')
    def test_first_guard_reentry_keeps_outer_claim_and_sends_zero_sdk(self):self.reentry('first_guard')

    def test_already_issued_late_return_precedes_expiry_and_callback_substitution_fences(self):
        self.after_sdk=lambda _value:setattr(self,'now',6.)
        with self.lock.held(),patch.object(source,'strict_json') as parser:
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
            parser.assert_not_called();self.assertEqual(self.literal,self.raw.literal(self.owner.reference))
        self.assertEqual(1,len(self.calls));self.assertTrue(self.owner.failed)

    def test_changed_clock_callback_after_actual_return_cannot_renew_original_window(self):
        self.after_sdk=lambda _value:setattr(self.owner,'clock',lambda:1.)
        with self.lock.held(),patch.object(source,'strict_json') as parser:
            with self.assertRaises(NativeUIError):self.owner.read(self.command)
            parser.assert_not_called();self.assertEqual(self.literal,self.raw.literal(self.owner.reference))
        self.assertEqual(1,len(self.calls))

    def test_issued_original_archive_and_limit_survive_inflight_public_config_swap(self):
        changed=patch.object(source,'WIRE_LIMIT',8)
        def replace(_value):
            changed.start();self.owner.archive=object();self.owner.pending=dict(foreign=True)
        self.after_sdk=replace
        try:
            with self.lock.held(),patch.object(source,'strict_json') as parser:
                with self.assertRaises(NativeUIError):self.owner.read(self.command)
                parser.assert_not_called();self.assertEqual(self.literal,self.raw.literal(self.owner.reference))
                self.assertFalse(self.raw.state['pending']);self.assertIsNone(self.owner._issued)
        finally:changed.stop()
        self.assertEqual(1,len(self.calls));self.assertTrue(self.owner.failed)

    def test_unicode_aggregate_decoded_cap_preserves_whole_wire_without_truncation(self):
        raw=json.dumps(dict(text='\U0001f642'*22500),ensure_ascii=False,separators=(',',':')).encode()
        self.literal=self.body({label:raw for label in ('script','inventory','native','widgets')})
        self.assertLess(len(self.literal),source.WIRE_LIMIT)
        with self.lock.held(),self.assertRaises(NativeUIError):self.owner.read(self.command)
        with self.lock.held():self.assertEqual(self.literal,self.raw.literal(self.owner.reference))
        self.assertEqual(1,len(self.calls));self.assertTrue(self.owner.failed)

    def test_finite_number_expansion_and_all_pending_lexicals_remain_lossless(self):
        self.literal=self.body(dict(script=b'{"number":1e15,"unicode":"\xf0\x9f\x99\x82"}'),pending=51)
        with self.lock.held():
            reference,proof,values=self.owner.read(self.command)
            self.assertEqual(self.literal,self.raw.literal(reference))
        self.assertEqual(1e15,values['script']['number']);self.assertEqual('\U0001f642',values['script']['unicode'])
        self.assertEqual(57,len(proof.records));self.assertEqual(51,sum(row.label=='nativePending' for row in proof.records))
        self.assertEqual(18,len(canonical(values['script']['number'])))
        self.assertLessEqual(source.SIDE_LIMIT,source.EXISTING_SIDE_LIMIT)


if __name__=='__main__':unittest.main()
