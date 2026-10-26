"""Real private files/CAS and actual ordinary W3C calls, without a device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.operation_transport_guard import check as final_guard
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_inputs import TabletWebInputs
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters.tablet_web_dom import IOSTabletWebDOM
from ios.self_tests.tablet_web_dom_fixture import packet as envelope
from ios.self_tests.test_ios_tablet_web_packets import BINDING,RUN,ROOT
from ios.self_tests.test_ios_tablet_web_native_input import SDK,REPO


class TabletWebInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        program="const page=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page,p=page();p.doc.activeElement=p.nodes.get('text');p.event('text','focusin');process.stdout.write(JSON.stringify(p.read()));"
        result=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
        if result.returncode:raise AssertionError(result.stderr)
        cls.body=json.loads(result.stdout)
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.held=self.lock.held();self.held.__enter__();self.addCleanup(self.held.__exit__,None,None,None)
        self.client=SDK();self.now=120000;self.mono=0.;self.queries=[];self.raw=None
        original=self.client.call
        def call(*args,**kwargs):final_guard();return original(*args,**kwargs)
        self.client.call=call
    def source(self,**kwargs):
        return TabletWebPackets(self.root,BINDING,RUN,'primary',ROOT,31,'dom',lambda:True,monotonic=lambda:self.mono,epoch_ms=lambda:self.now,**kwargs)
    def reader(self):
        def send(q):
            final_guard();self.queries.append(deepcopy(q));value=envelope(self.body,index=len(self.queries));value['commandId']=q['commandId'];value['source']['dom']['requestId']=q['commandId']
            for key in ('presentationBefore','presentationAfter'):value['source'][key]['responders']=['8'*32]
            self.raw=json.dumps(value)
        calls=[0]
        def clock():calls[0]+=1;return 100000 if calls[0]==1 else 100100
        return IOSTabletWebDOM(send,lambda:self.raw,clock,lambda:True,31,monotonic=lambda:self.mono,sleep=lambda _:None)
    def owner(self):return TabletWebInputs(self.client,self.source(),self.reader(),self.lock,lambda:100100,monotonic=lambda:self.mono,epoch_ms=lambda:self.now)
    def mutations(self):return [row for row in self.client.calls if row[0] in ('POST','DELETE')]

    def test_real_original_DOM_and_touch_input_reconstruct_without_replay_or_effect_claim(self):
        owner=self.owner();ref=owner.perform('b'*32,'submit','tap','bridge')
        self.assertEqual(['POST','DELETE'],[row[0] for row in self.mutations()]);self.assertEqual(1,len(self.queries))
        rebuilt=self.owner();self.assertEqual(ref,rebuilt.perform('b'*32,'submit','tap','bridge'))
        self.assertEqual(1,len(self.queries));self.assertEqual(2,len(self.mutations()))
        row=rebuilt.originals.read(rebuilt.originals.expand(ref));self.assertEqual('returned',row['phase']);self.assertEqual('bridge',row['events'][0]['request']['ownership']['element'])
        self.assertNotIn('delivered',row);self.assertNotIn('bridgeMessages',row);self.assertNotIn('clean',row)
        self.assertEqual(1,len(rebuilt.source.history()))

    def test_unknown_actual_touch_return_releases_owned_actions_once_and_failed_history_blocks_new_input(self):
        owner=self.owner();self.client.fail=True
        with self.assertRaises(NativeUIError):owner.perform('b'*32,'submit','tap','bridge')
        self.assertEqual(['POST','DELETE'],[row[0] for row in self.mutations()]);self.client.fail=False
        rebuilt=self.owner();row=rebuilt.records[0];self.assertEqual('failed',row['phase']);self.assertIsNone(row['events'][0]['returned'])
        self.assertIsNotNone(row['events'][1]['returned'])
        for label in ('submit','another-click'):
            with self.subTest(label=label),self.assertRaises(NativeUIError):rebuilt.perform('b'*32,label,'tap','bridge')
        self.assertEqual(1,len(self.queries));self.assertEqual(2,len(self.mutations()))

    def test_slow_actual_issued_journal_blocks_final_WDA_send_and_never_releases_unattempted_touch(self):
        owner=self.owner();write=owner.store.write
        def slow(value,previous):
            result=write(value,previous)
            if value['pending'] is not None and value['pending']['events']:
                self.mono=2.;self.now+=2000
            return result
        with patch.object(owner.store,'write',side_effect=slow):
            with self.assertRaises(NativeUIError):owner.perform('b'*32,'submit','tap','bridge')
        self.assertEqual([],self.mutations());rebuilt=self.owner();self.assertEqual('failed',rebuilt.records[0]['phase'])
        self.assertEqual(['touch','release'],[row['request']['kind'] for row in rebuilt.records[0]['events']])
        self.assertTrue(all(row['returned'] is None for row in rebuilt.records[0]['events']))

    def test_current_candidate_loss_after_attempted_touch_still_releases_same_owned_session_once(self):
        current=[True]
        def source(**kwargs):
            return TabletWebPackets(self.root,BINDING,RUN,'primary',ROOT,31,'dom',lambda:current[0],
                monotonic=lambda:self.mono,epoch_ms=lambda:self.now,**kwargs)
        self.source=source;owner=self.owner()
        def changed(method,path):
            if method=='POST' and path.endswith('/actions'):current[0]=False
        self.client.after=changed
        with self.assertRaises(NativeUIError):owner.perform('b'*32,'candidate-lost-touch','tap','bridge')
        self.assertEqual(['POST','DELETE'],[method for method,_path,_body in self.mutations()])
        saved=owner.store.read();events=saved['pending']['events']
        self.assertEqual(['touch','release'],[event['request']['kind'] for event in events])
        self.assertIsNone(events[0]['returned']);self.assertIsNotNone(events[1]['returned'])
        current[0]=True;rebuilt=self.owner();calls=deepcopy(self.client.calls);queries=len(self.queries)
        with self.assertRaises(NativeUIError):rebuilt.perform('b'*32,'candidate-lost-touch','tap','bridge')
        self.assertEqual(calls,self.client.calls);self.assertEqual(queries,len(self.queries))
    def test_unknown_owned_release_after_candidate_loss_is_retained_and_never_resent(self):
        current=[True]
        def source(**kwargs):
            return TabletWebPackets(self.root,BINDING,RUN,'primary',ROOT,31,'dom',lambda:current[0],
                monotonic=lambda:self.mono,epoch_ms=lambda:self.now,**kwargs)
        self.source=source;owner=self.owner()
        def changed(method,path):
            if method=='POST' and path.endswith('/actions'):current[0]=False
            if method=='DELETE':raise OSError('Lost actual owned release return')
        self.client.after=changed
        with self.assertRaises(NativeUIError):owner.perform('b'*32,'unknown-release','tap','bridge')
        self.assertEqual(['POST','DELETE'],[method for method,_path,_body in self.mutations()])
        events=owner.store.read()['pending']['events'];self.assertEqual(['touch','release'],[event['request']['kind'] for event in events])
        self.assertIsNone(events[1]['returned']);current[0]=True;self.client.after=None
        rebuilt=self.owner();calls=deepcopy(self.client.calls)
        for label in ('unknown-release','different'):
            with self.subTest(label=label),self.assertRaises(NativeUIError):rebuilt.perform('b'*32,label,'tap','bridge')
        self.assertEqual(calls,self.client.calls)

    def test_foreign_private_CAS_after_touch_cannot_authorize_or_overwrite_release(self):
        owner=self.owner();foreign={}
        def changed(method,path):
            if method=='POST' and path.endswith('/actions'):
                previous=owner.store.read();foreign.update(deepcopy(previous));foreign['role']='actor'
                owner.store.write(foreign,previous)
        self.client.after=changed
        with self.assertRaises(NativeUIError):owner.perform('b'*32,'foreign-release-cas','tap','bridge')
        self.assertEqual(['POST'],[method for method,_path,_body in self.mutations()])
        self.assertEqual(foreign,owner.store.read())

    def test_release_callback_keeps_original_held_lock_and_store_after_public_alias_change(self):
        owner=self.owner();old_store=owner.store;foreign_store=PrivateFeatureState(self.root/'foreign-inputs.json')
        def changed(method,path):
            if method=='POST' and path.endswith('/actions'):
                owner.lock=ScriptSourceLock(self.root/'foreign.lock');owner.store=foreign_store
        self.client.after=changed
        with self.assertRaises(NativeUIError):owner.perform('b'*32,'changed-owner-alias','tap','bridge')
        self.assertEqual(['POST','DELETE'],[method for method,_path,_body in self.mutations()])
        events=old_store.read()['pending']['events'];self.assertEqual(['touch','release'],[event['request']['kind'] for event in events])
        self.assertIsNotNone(events[-1]['returned']);self.assertFalse(foreign_store.path.exists())

    def test_lost_query_return_keeps_owned_source_intent_without_touch_or_query_resend(self):
        owner=self.owner()
        def lost(q):self.queries.append(deepcopy(q));raise OSError('Actual query return lost')
        owner.reader.send=lost
        with self.assertRaises(NativeUIError):owner.perform('b'*32,'focus','tap','text')
        self.assertEqual([],self.mutations());rebuilt=self.owner();self.assertEqual(1,len(self.queries));self.assertIsNotNone(rebuilt.source.state['pending'])
        with self.assertRaises(NativeUIError):rebuilt.perform('b'*32,'focus','tap','text')
        self.assertEqual(1,len(self.queries))

    def test_read_only_original_decoder_creates_no_SDK_and_blocks_all_mutations(self):
        owner=self.owner();ref=owner.perform('b'*32,'submit','tap','bridge');calls=deepcopy(self.client.calls)
        source=self.source(historical=True)
        historical=TabletWebInputs(None,source,None,self.lock,lambda:(_ for _ in ()).throw(AssertionError('native clock forbidden')),historical=True)
        self.assertEqual('returned',historical.decode()[0]['phase'])
        self.assertEqual(ref,historical.state['records'][0]);self.assertEqual(calls,self.client.calls)
        for mutate in (historical.archive,historical.recover_record,lambda:historical.perform('c'*32,'other','tap','bridge')):
            with self.assertRaises(NativeUIError):mutate()
        self.assertEqual(calls,self.client.calls)

    def test_lost_completed_original_return_recovers_only_actual_bytes_without_input_replay(self):
        owner=self.owner();write=owner.originals.write
        def lost(*args,**kwargs):write(*args,**kwargs);raise OSError('Actual completed record return lost')
        with patch.object(owner.originals,'write',side_effect=lost):
            with self.assertRaises(OSError):owner.perform('b'*32,'submit','tap','bridge')
        rebuilt=self.owner();self.assertTrue(rebuilt.inspect_original()['complete']);self.assertIsNotNone(rebuilt.state['pending'])
        before=deepcopy(self.client.calls);ref=rebuilt.recover_record()
        self.assertEqual(ref,rebuilt.perform('b'*32,'submit','tap','bridge'));self.assertEqual(before,self.client.calls)
        self.assertEqual(1,len(self.queries));self.assertIsNone(rebuilt.state['pending'])

    def test_actual_opened_empty_record_is_retained_and_cannot_be_replayed_or_recovered_as_complete(self):
        owner=self.owner();intent=owner.originals.intent
        def lost(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='opened':raise OSError('Actual record write interrupted after open')
            return result
        with patch.object(owner.originals,'intent',side_effect=lost):
            with self.assertRaises(OSError):owner.perform('b'*32,'submit','tap','bridge')
        rebuilt=self.owner();partial=rebuilt.inspect_original();self.assertEqual(0,partial['bytes']);self.assertFalse(partial['complete'])
        path=rebuilt.originals.path(rebuilt.state['original']);before=(path.stat().st_ino,path.read_bytes(),deepcopy(self.client.calls))
        for attempt in (rebuilt.recover_record,lambda:rebuilt.perform('b'*32,'submit','tap','bridge')):
            with self.assertRaises(NativeUIError):attempt()
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes(),self.client.calls));self.assertEqual(1,len(self.queries))

    def test_held_foreign_lock_cannot_initialize_owner_journal_or_send_any_request(self):
        source=self.source();foreign=ScriptSourceLock(self.root/'foreign.lock')
        with foreign.held(),self.assertRaises(NativeUIError):
            TabletWebInputs(self.client,source,self.reader(),foreign,lambda:100100)
        self.assertFalse((self.root/('tabletweb-inputs-'+RUN+'-primary.json')).exists())
        self.assertEqual([],self.client.calls);self.assertEqual([],self.queries)

    def test_rehashed_duplicate_text_transcript_cannot_qualify_historical_input_owner(self):
        owner=self.owner();ref=owner.perform('c'*32,'unicode','replace','text',text='owned text')
        row=owner.originals.read(owner.originals.expand(ref));duplicate=deepcopy(row['events'][0]);duplicate['request']['id']='d'*32;row['events'].append(duplicate)
        writer=OriginalFrameStore(self.root,BINDING,RUN,'primary',lambda:True,lambda *_:None,namespace='tabletweb-input',schema_prefix='tabletWebInput',kind='inputs')
        rewritten=writer.write(1,row);self.assertNotEqual(ref['sha256'],rewritten['sha256'])
        previous=deepcopy(owner.state);owner.state['records']=[rewritten];owner.store.write(owner.state,previous)
        calls=deepcopy(self.client.calls)
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(calls,self.client.calls)

    def test_focus_change_after_clear_stays_failed_across_reconstruction_without_any_input_replay(self):
        from ios.self_tests import test_ios_tablet_web_native_input as fixture
        fixture.TabletWebNativeInputTests.setUpClass()
        self.body=deepcopy(fixture.TabletWebNativeInputTests.bodies[1]);self.client.value='old fixture text'
        def changed(method,path):
            if path.endswith('/clear'):self.client.active='actual-other-field'
        self.client.after=changed;owner=self.owner()
        with self.assertRaises(NativeUIError):owner.perform('c'*32,'nonempty-unicode','replace','text',text='Überte 🙂')
        self.assertEqual(['clear'],[path.rsplit('/',1)[-1] for _,path,_ in self.mutations()])
        rebuilt=self.owner();self.assertTrue(rebuilt.blocked);self.assertEqual('failed',rebuilt.records[0]['phase'])
        self.assertEqual(['clear'],[event['request']['kind'] for event in rebuilt.records[0]['events']])
        queries=len(self.queries);calls=deepcopy(self.client.calls)
        for label in ('nonempty-unicode','new-label'):
            with self.subTest(label=label),self.assertRaises(NativeUIError):rebuilt.perform('c'*32,label,'replace','text',text='Überte 🙂')
        self.assertEqual(queries,len(self.queries));self.assertEqual(calls,self.client.calls)

    def test_closed_text_grammar_is_checked_by_record_decoder_before_source_or_input_delivery(self):
        owner=self.owner();base=dict(tabletWebInputVersion=1,index=1,ticket='c'*32,label='invalid',kind='replace',control='text',text='owned',
            phase='reading',sourceIndex=1,sourceRef=None,sourceSha256=None,events=[],before=owner.stamp(),after=None)
        for field,text in (('password','secret'),('text','x'*513),('foreign','x'*8193),('text','\ue007'),('text','line\nfeed'),('text','\ud800')):
            row=dict(base,control=field,text=text)
            with self.subTest(field=field,length=len(text)),self.assertRaises(NativeUIError):owner.record(row,1)
        self.assertEqual([],self.client.calls);self.assertEqual([],self.queries)

    def test_actual_unicode_text_is_bound_to_original_native_field_and_persists_once(self):
        owner=self.owner();ref=owner.perform('c'*32,'unicode','replace','text',text='Überte 🙂');rebuilt=self.owner()
        self.assertEqual(ref,rebuilt.perform('c'*32,'unicode','replace','text',text='Überte 🙂'))
        self.assertEqual(1,len(self.mutations()));self.assertEqual('Überte 🙂',self.mutations()[0][2]['text'])
        row=rebuilt.records[0];self.assertEqual('text',row['events'][0]['request']['kind']);self.assertEqual(1,len(self.queries))
        original=rebuilt.originals.read(rebuilt.originals.expand(ref));bad=deepcopy(original);bad['events'][0]['request']['body']['text']='different'
        with self.assertRaises(NativeUIError):rebuilt.record(bad,1)


if __name__=='__main__':unittest.main()
