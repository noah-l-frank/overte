"""Closed source grammar and actual outer lock-exit counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.world_current_document import validate,command,PicoWorldCurrentDocument
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock

RUN='1'*32;OWNER='2'*32;URL='http://127.0.0.1/feature-fixture/v1/runs/'+RUN+'/'


def fixture(request=None):
    request=request or dict(schemaVersion=1,commandId='3'*32,action='pico-world-web',runId=RUN,
                            fixtureUrl=URL,operation='observe-current-document',ownerToken=OWNER)
    url=URL+'tickets/'+'4'*32+'/index.html'
    base=dict(handle='1',creation=3,grant=6,page=1,url=url,sourceUrl=url)
    native=dict(base,itemInstance='5'*32,sourceIdentity='web-entity:12345678-1234-1234-1234-123456789abc',
                created=True,authorized=True,sessionActive=True,suspended=False,loading=False,capturedEpochMs=10000,capturedMonotonicMs=20000)
    java=dict(base,ownerCurrent=True,active=True,foreground=True,windowFocused=True,destroyed=False,closing=False,loading=False,
              capturedEpochMs=10001,capturedElapsedMs=30000)
    before=dict(native=deepcopy(native),java=deepcopy(java));native.update(capturedEpochMs=10003,capturedMonotonicMs=20003)
    java.update(capturedEpochMs=10003,capturedElapsedMs=30002);after=dict(native=native,java=java)
    finish=dict(handle='1',creation=3,grant=4,page=1,url=url,finishedEpochMs=9000)
    dom=dict(webDOMVersion=1,requestId=request['commandId'],instance='6'*32,sequence=1,capturedEpochMs=10002,
             document=dict(runId=RUN,href=url,responseId='7'*32,readyState='complete'),editor=dict(text='',focused=False),attempts=[],echoes=[])
    transaction=dict(before=before['java'],domRaw=json.dumps(json.dumps(dom)),after=after['java'])
    value=dict(picoWorldCurrentDocumentVersion=1,commandId=request['commandId'],runId=RUN,ownerToken=OWNER,instance='8'*32,
               sequence=1,processId=123,requestedEpochMs=10000,requestedMonotonicMs=20000,capturedEpochMs=10004,capturedMonotonicMs=20004,
               status='ready',source=dict(authorityBefore=before,authorityAfter=after,originalFinish=finish,documents=[deepcopy(finish)],
                                        domRaw=json.dumps(transaction),dom=dom))
    return request,value


class WorldCurrentDocumentReaderTests(unittest.TestCase):
    def test_exact_retained_finish_independent_bookends_and_new_finish(self):
        request,value=fixture();self.assertIs(value,validate(value,request,123,10004))
        self.assertNotEqual(value['source']['originalFinish']['grant'],value['source']['authorityAfter']['native']['grant'])
        fresh=deepcopy(value['source']['originalFinish']);fresh.update(grant=6,finishedEpochMs=10000)
        value['source']['documents'].append(fresh);value['source']['originalFinish']=deepcopy(fresh)
        validate(value,request,123,10004)

    def test_status_grammar_bool_foreign_and_unsupported_fields(self):
        for status in ('pending','unavailable'):
            request,value=fixture();value.update(status=status,source={});validate(value,request,123,10004)
        mutations=[lambda v:v.update(status='cached'),lambda v:v.update(picoWorldCurrentDocumentVersion=True),
            lambda v:v.update(processId=True),lambda v:v.update(ownerToken='a'*32),lambda v:v.update(unexpected=1),
            lambda v:v['source']['authorityAfter']['native'].update(grant=True),lambda v:v['source']['authorityAfter']['java'].update(loading=0),
            lambda v:v['source']['originalFinish'].update(finishedEpochMs=True),lambda v:v['source'].update(documents=[])]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                request,value=fixture();mutation(value)
                with self.assertRaises((NativeUIError,ValueError)):validate(value,request,123,10004)
        request,value=fixture();request['action']='pico-tablet-web'
        with self.assertRaises(NativeUIError):command(request)

    def test_full_raw_duplicate_key_bool_alias_or_changed_dom_refused(self):
        for case in ('duplicate','bool','changed','wrapper-bool','finish-bool','subclass'):
            request,value=fixture();source=value['source']
            if case=='duplicate':source['domRaw']=source['domRaw'].replace('"before":','"before":{},"before":',1)
            if case=='bool':source['dom']['sequence']=True
            if case=='changed':source['dom']['editor']['text']='unproven'
            if case=='wrapper-bool':
                transaction=json.loads(source['domRaw']);transaction['before']['creation']=True;source['domRaw']=json.dumps(transaction)
            if case=='finish-bool':source['originalFinish']['page']=True
            if case=='subclass':
                class Dict(dict):pass
                source['authorityBefore']['java']=Dict(source['authorityBefore']['java'])
            with self.subTest(case=case),self.assertRaises((NativeUIError,ValueError)):validate(value,request,123,10004)

    def test_original_finish_exact_epoch_scope_and_complete_ledger(self):
        for case in ('epoch','foreign','duplicate','future','unrelated'):
            request,value=fixture();source=value['source']
            if case=='epoch':source['originalFinish']['finishedEpochMs']+=1
            if case=='foreign':source['originalFinish']['handle']='2'
            if case=='duplicate':source['documents'].append(deepcopy(source['documents'][0]))
            if case=='future':source['documents'][0]['finishedEpochMs']=12000
            if case=='unrelated':source['originalFinish']['url']='http://foreign.invalid/'
            with self.subTest(case=case),self.assertRaises(NativeUIError):validate(value,request,123,10004)

    def test_native_java_monotonic_future_and_changed_authority_refused(self):
        for change in (lambda v:v.update(capturedMonotonicMs=20002),lambda v:v.update(requestedEpochMs=12000),
                       lambda v:v['source']['authorityAfter']['java'].update(capturedElapsedMs=32000),
                       lambda v:v['source']['authorityAfter']['java'].update(grant=7),
                       lambda v:v['source']['authorityAfter']['native'].update(itemInstance='a'*32)):
            request,value=fixture();change(value)
            with self.assertRaises(NativeUIError):validate(value,request,123,10004)

    def reader(self,stage):
        state=dict(host=1.,epoch=10004,valid=True,raw='',sends=[],guards=0)
        lock=ScriptSourceLock(Path(stage)/'script-sources.lock')
        def send(request):
            state['sends'].append(deepcopy(request));state['raw']=json.dumps(fixture(request)[1])
        def guard():state['guards']+=1;return state['valid']
        reader=PicoWorldCurrentDocument(send,lambda:state['raw'],lambda:state['epoch'],guard,123,lock,
            monotonic=lambda:state['host'],sleep=lambda delay:state.update(host=state['host']+delay))
        return reader,state,lock

    def test_one_send_same_nonce_pending_and_immutable_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory).chmod(0o700);reader,state,lock=self.reader(directory)
            original_reader=reader.read_raw;reads=[]
            def pending_once():
                raw=original_reader();reads.append(True)
                if len(reads)==1:
                    pending=json.loads(raw);ready=deepcopy(pending);ready['sequence']+=1;state['raw']=json.dumps(ready)
                    pending.update(status='pending',source={});return json.dumps(pending)
                return raw
            reader.read_raw=pending_once
            result=reader.read(RUN,URL,OWNER);self.assertIsNone(lock._owner);self.assertEqual(1,len(state['sends']));self.assertEqual(2,len(reads))
            result['source']['dom']['editor']['text']='mutable return';self.assertEqual('',reader.last['source']['dom']['editor']['text'])
            original=reader.original();original['request']['ownerToken']='a'*32;self.assertEqual(OWNER,reader.original()['request']['ownerToken'])
            self.assertEqual(state['raw'],reader.original()['raw'])

    def test_real_outer_exit_native_host_guard_and_future_refused_without_requery(self):
        for case in ('native','host','guard','future'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                Path(directory).chmod(0o700);reader,state,lock=self.reader(directory);held=lock.held;exits=[]
                @contextmanager
                def actual_exit():
                    with held():yield
                    self.assertIsNone(lock._owner);exits.append(True)
                    if case=='native':state['epoch']+=2000
                    if case=='future':state['epoch']-=2000
                    if case=='host':state['host']+=2
                    if case=='guard':state['valid']=False
                with patch.object(lock,'held',actual_exit),self.assertRaises(NativeUIError):reader.read(RUN,URL,OWNER)
                self.assertEqual([True],exits);self.assertEqual(1,len(state['sends']));self.assertIsNone(reader.last);self.assertIsNone(reader.raw)

    def test_final_grammar_work_is_covered_before_last_clock_commit(self):
        import adapters.pico4.world_current_document as module
        for clock in ('host','epoch'):
            with self.subTest(clock=clock),tempfile.TemporaryDirectory() as directory:
                Path(directory).chmod(0o700);reader,state,lock=self.reader(directory);original=module.validate;late=[]
                def validation(*args,**kwargs):
                    result=original(*args,**kwargs)
                    if lock._owner is None:
                        state[clock]+=2 if clock=='host' else 2000;late.append(True)
                    return result
                with patch.object(module,'validate',validation),self.assertRaises(NativeUIError):reader.read(RUN,URL,OWNER)
                self.assertEqual([True],late);self.assertIsNone(reader.last);self.assertEqual(1,len(state['sends']))

    def test_last_guard_copy_age_and_nested_lock_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory).chmod(0o700);reader,state,lock=self.reader(directory)
            guard=reader.guard
            def late_guard():
                result=guard()
                if lock._owner is None and state['sends']:state['host']+=2
                return result
            reader.guard=late_guard
            with self.assertRaises(NativeUIError):reader.read(RUN,URL,OWNER)
            self.assertIsNone(reader.last);self.assertEqual(1,len(state['sends']))
        with tempfile.TemporaryDirectory() as directory:
            Path(directory).chmod(0o700);reader,state,lock=self.reader(directory)
            with lock.held():
                with self.assertRaises(NativeUIError):reader.read(RUN,URL,OWNER)
            self.assertEqual([],state['sends'])


if __name__=='__main__':unittest.main()
