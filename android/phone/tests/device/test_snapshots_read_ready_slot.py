"""Causal cleanup slots schedule a separate owner, never borrow its effects.

Actual public SDK26 inputs, private originals, TLS credentials and a separate
Actor process execute here. Native/Android/render values remain explicit host
producers; this module qualifies neither an APK nor physical device behavior.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshot_documents_journey_boundary as documents
import test_snapshots_feature_journey as harness
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_feature import PhoneSnapshotsFeature
from overte_phone_snapshots_role import PhoneSnapshotsRole,validate_read_ready_slot
from overte_phone_snapshots_retirement import start_identity


# The existing guarded child installs HostOnlyBoundary before its adapter.
# Only the controller/lifetime is specialized; every measurement and POST uses
# the production Actor with its independently provisioned publisher credential.
CHILD=harness.ACTOR[:harness.ACTOR.index('started=time.monotonic()')]
CHILD=CHILD.replace('configuration=PrivateFeatureState',
    'from snapshot_documents_journey_boundary import install_proxy_documents\n'
    'install_proxy_documents(SnapshotProxy)\nconfiguration=PrivateFeatureState')+r'''
import overte_phone_snapshots_actor as module
from overte_phone_script_history import unpack
counts=dict(reads=0,posts=0)
original_role=module.PhoneSnapshotsRole
request=client.request
def requested(path,*args,**kwargs):
    if path.endswith('/samples'):counts['posts']+=1
    return request(path,*args,**kwargs)
client.request=requested
def construct(*args,**kwargs):
    role=original_role(*args,**kwargs);read=role.read
    def reading(*args,**kwargs):
        role.feature.lock.assert_held();counts['reads']+=1
        return read(*args,**kwargs)
    role.read=reading;return role
module.PhoneSnapshotsRole=construct
flow=adapter.actor('synthetic',RUN,client)
print(json.dumps(dict(ready=True,pid=__import__('os').getpid())),flush=True)
for line in sys.stdin:
    instruction=json.loads(line)
    if instruction['mode']=='exit':break
    error=None;trace=None
    try:
        started=time.monotonic()
        while True:
            flow.step()
            state=flow.state
            if instruction['mode']=='once':break
            last=state['last']
            if (last is not None and last['receipt']['ticket']==instruction['ticket']
                    and state['pending'] is None and state['quiet'] is not None and state['quiet']['complete']):break
            if time.monotonic()-started>=18:raise RuntimeError('Bounded real cleanup receipt missing')
            time.sleep(flow.poll_delay())
    except Exception as caught:
        import traceback;trace=traceback.format_exc()
        error=type(caught).__name__
    header=flow.store.read();state=None if header is None else unpack(header['payload'])[0]
    print(json.dumps(dict(error=error,trace=trace,counts=counts,state=state)),flush=True)
'''


class SnapshotReadReadySlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type=type('ReadReadyDocumentsFixture',(documents.SnapshotDocumentsCommonJourneyTests,),{})
        cls.fixture_type.setUpClass()
        output=harness.ROOT/'build/snapshot-read-ready-slot-contract'
        output.mkdir(parents=True,exist_ok=True)
        cls.build=Path(tempfile.mkdtemp(prefix='check-',dir=output))
        compile_original=documents.OriginalDocumentsProcess.compile
        cls.compiler_patch=patch.object(documents.OriginalDocumentsProcess,'compile',
            classmethod(lambda _cls,_requested:compile_original(cls.build)))
        cls.compiler_patch.start()
    @classmethod
    def tearDownClass(cls):
        try:cls.fixture_type.tearDownClass()
        finally:
            cls.compiler_patch.stop();cls.fixture_type.doClassCleanups()
            failures=cls.fixture_type.tearDown_exceptions
            if failures:
                _kind,error,traceback=failures[0]
                raise error.with_traceback(traceback)

    def receive(self,child):
        readable,_,_=select.select([child.stdout],[],[],22)
        if not readable:
            if child.poll() is not None:self.fail(child.stderr.read()[-5000:])
            self.fail('Bounded independent Actor IPC response missing')
        line=child.stdout.readline()
        if not line:self.fail(child.stderr.read()[-5000:])
        return json.loads(line)

    def step(self,rig,mode='once'):
        child=rig.slot_child
        child.stdin.write(json.dumps(dict(mode=mode,ticket='d'*32))+'\n');child.stdin.flush()
        value=self.receive(child);self.assertIsNone(value['error'],value)
        return value

    @contextmanager
    def cleaned(self):
        rig=self.fixture_type('test_normal_public_document_picker_open_cancel_and_success_acquires_original')
        rig.setUp()
        try:
            rig.client.activate('c'*32)
            value=rig.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))
            rig.act('open');rig.act('capture',dict(mode='still',format='png'))
            value=rig.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=value['sequence']))
            self.assertEqual(1,value['state']['files']);rig.slot_sequence=value['sequence']
            configuration=rig.root/'read-ready-child.json'
            PrivateFeatureState(configuration).write(dict(targetUrl=rig.proxy.url,root=str(rig.root),
                fixtureUrl=rig.base,actorToken='a'*64),None)
            child=subprocess.Popen([sys.executable,'-B','-c',CHILD,json.dumps(sys.path),str(configuration)],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            rig.slot_child=child
            try:
                ready=self.receive(child);self.assertTrue(ready['ready']);self.assertEqual(child.pid,ready['pid'])
                initial=self.step(rig);self.assertEqual(1,initial['counts']['posts'])
                rig.client.activate('d'*32,'cleanup',{})
                result=rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,
                    runId=harness.RUN))
                self.assertTrue(result['performed'])
                rig.slot_feature_store=rig.adapter.snapshots_feature_store('test-only-appium')
                header=rig.slot_feature_store.read();state=unpack(header['payload'])[0]
                self.assertEqual('cleaned',state['phase'])
                self.assertEqual(dict(pid=child.pid,start=start_identity(child.pid)),state['cleanupStages']['readReadyMode']['actorProcess'])
                rig.slot_actor_store=PrivateFeatureState(rig.root/'phone-snapshots-actor-lifecycle.json')
                rig.slot_primary_store=PrivateFeatureState(rig.root/'phone-snapshots-primary-originals.json')
                yield rig
            finally:
                if child.poll() is None:
                    child.stdin.write(json.dumps(dict(mode='exit'))+'\n');child.stdin.flush()
                timed_out=False
                try:out,err=child.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    timed_out=True;child.terminate()
                    try:out,err=child.communicate(timeout=3)
                    except subprocess.TimeoutExpired:
                        child.kill();out,err=child.communicate(timeout=3)
                self.assertFalse(timed_out,'Independent Actor missed its explicit-exit deadline: '+err[-5000:])
                self.assertEqual(0,child.returncode,err[-5000:])
        finally:self.assertTrue(rig.doCleanups(),'Owned fixture cleanup failed')

    def launch(self,rig,*,before_wait=None,after_wait=None,drive=True,expect_wait=True):
        """Run public observe while the real Actor owns the other process.

        The IPC hook pauses only before the original unlocked await, never
        supplies a receipt, changes an epoch or bypasses a native guard.
        """
        entered=threading.Event();released=threading.Event();done=threading.Event()
        seen=dict(current=[],sdkWhileAwait=[],filtered=[],feature=None,slot=None,header=None,
            actor=None,result=None,error=None,awaitThread=None,awaitActive=False)
        original_wait=PhoneSnapshotsFeature.await_read_ready
        original_read=PhoneSnapshotsRole.read;original_call=rig.proxy.call
        def current(role,*args,**kwargs):
            if role.role=='primary' and role.feature.state['phase']=='cleaned':
                role.feature.lock.assert_held();seen['current'].append(True)
                self.assertFalse(seen['awaitActive'])
            return original_read(role,*args,**kwargs)
        def rpc(*args,**kwargs):
            if seen['awaitActive'] and threading.get_ident()==seen['awaitThread']:
                seen['sdkWhileAwait'].append(args[0]);raise AssertionError('Unlocked await requested current target authority')
            return original_call(*args,**kwargs)
        def waiting(feature,history,role,header,actor):
            self.assertIsNone(feature.lock._owner);self.assertEqual([],seen['current'])
            self.assertIsInstance(feature.phase.client,AdapterFixtureClient)
            access=feature.phase.client.request('/adapter-reader')
            self.assertFalse(access['peerFactsVisible']);self.assertFalse(access['canPublish'])
            filtered=feature.phase.client.request('/runs/'+harness.RUN);self.assertEqual([],filtered['entries'])
            seen.update(feature=feature,history=history,role=role,slot=deepcopy(role.frames[-1]),
                header=deepcopy(header),actor=deepcopy(actor),awaitThread=threading.get_ident(),awaitActive=True)
            seen['filtered'].append(filtered);entered.set()
            try:
                if not released.wait(22):raise AssertionError('Controller did not release actual await')
                original_wait(feature,history,role,header,actor)
            finally:seen['awaitActive']=False
            if after_wait is not None:after_wait(seen)
        def observe():
            try:seen['result']=rig.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,
                runId=harness.RUN,afterSequence=rig.slot_sequence))
            except Exception as error:
                import traceback
                seen['error']=error;seen['trace']=traceback.format_exc()
            finally:done.set()
        with patch.object(PhoneSnapshotsFeature,'await_read_ready',waiting),patch.object(PhoneSnapshotsRole,'read',current),patch.object(rig.proxy,'call',rpc):
            thread=threading.Thread(target=observe,name='public-read-ready-observe');thread.start()
            try:
                if expect_wait:
                    deadline=time.monotonic()+12
                    while not entered.wait(.025) and not done.is_set() and time.monotonic()<deadline:pass
                    self.assertTrue(entered.is_set(),seen.get('trace',repr(seen['error'])))
                    if drive:seen['child']=self.step(rig,'receipt')
                    if before_wait is not None:before_wait(seen)
                released.set();thread.join(25)
                self.assertFalse(thread.is_alive(),'Bounded public observe did not return')
            finally:
                released.set();thread.join(25)
        self.assertEqual([],seen['sdkWhileAwait'])
        return seen

    def good(self,rig,seen):
        self.assertIsNone(seen['error'],seen.get('trace',repr(seen['error'])))
        self.assertEqual([True],seen['current']);self.assertTrue(seen['filtered'])
        validate_read_ready_slot(seen['slot'],harness.RUN,actor_process=seen['actor'])
        state=unpack(seen['header']['payload'])[0]
        self.assertEqual(seen['slot']['readReadySlot']['preparedRoleSequence']+1,state['sequence'])
        self.assertEqual(state['sequence']+1,seen['result']['sequence'])
        actor=unpack(rig.slot_actor_store.read()['payload'])[0]
        self.assertEqual(seen['header'],actor['primaryCue']['header']);self.assertTrue(actor['quiet']['complete'])
        entries=rig.client.observe()['entries']
        self.assertIn(actor['last']['receipt'],entries)
        self.assertEqual(0,seen['result']['state']['files'])
        rig.slot_sequence=seen['result']['sequence']

    def test_real_child_receipt_and_filtered_adapter_clock_precede_fresh_locked_primary_read(self):
        with self.cleaned() as rig:self.good(rig,self.launch(rig))

    def test_next_actual_slot_requires_another_real_child_receipt_and_nonce(self):
        with self.cleaned() as rig:
            first=self.launch(rig);self.good(rig,first)
            second=self.launch(rig);self.good(rig,second)
            self.assertNotEqual(first['slot']['readReadySlot']['slotId'],second['slot']['readReadySlot']['slotId'])
            self.assertGreater(second['child']['state']['last']['receipt']['actorSequence'],first['child']['state']['last']['receipt']['actorSequence'])
            self.assertGreater(second['child']['counts']['reads'],first['child']['counts']['reads'])

    def test_own_cas_ack_archives_only_diagnostic_slot_and_preserves_every_old_original_byte(self):
        with self.cleaned() as rig:
            old=deepcopy(rig.slot_primary_store.read())
            paths=[path for path in rig.root.iterdir() if path.is_file() and
                (path.name.startswith('emote-frame-snapshots-') or path.name.startswith('emote-index-snapshots-')
                 or path.suffix in ('.png','.bin'))]
            originals={path:path.read_bytes() for path in paths}
            seen=self.launch(rig);self.good(rig,seen)
            slot=seen['slot'];self.assertEqual(old,slot['readReadySlot']['preparedRoleHeader'])
            self.assertEqual({'ticket','phaseBefore','phaseAfter','diagnostic','image','binaries','retirement','readReadySlot'},set(slot))
            self.assertTrue(slot['diagnostic']);self.assertIsNone(slot['image']);self.assertEqual([],slot['binaries'])
            self.assertIsNone(slot['retirement'])
            for path,raw in originals.items():self.assertEqual(raw,path.read_bytes(),path.name)

    def test_ignored_actual_slot_cas_and_absent_actual_actor_receipt_cannot_reach_current(self):
        with self.subTest(kind='ignored-slot-cas'),self.cleaned() as rig:
            before=deepcopy(rig.slot_primary_store.read());write=PrivateFeatureState.write;ignored=[]
            def omit(store,value,previous):
                if store.path==rig.slot_primary_store.path:
                    state=unpack(value['payload'])[0];pending=state.get('pending')
                    if pending is not None and 'readReadySlot' in pending['work']:
                        ignored.append(True);return None
                return write(store,value,previous)
            with patch.object(PrivateFeatureState,'write',omit):seen=self.launch(rig,drive=False,expect_wait=False)
            self.assertTrue(ignored);self.assertIsInstance(seen['error'],NativeUIError)
            self.assertEqual([],seen['current']);self.assertEqual(before,rig.slot_primary_store.read())
            self.assertEqual(1,len(rig.client.observe()['entries']))
        with self.subTest(kind='no-cleanup-receipt'),self.cleaned() as rig:
            seen=self.launch(rig,drive=False)
            self.assertIsInstance(seen['error'],NativeUIError);self.assertEqual([],seen['current'])
            self.assertEqual(1,len(rig.client.observe()['entries']))

    def test_actual_stale_foreign_missing_and_incomplete_actor_journals_are_not_receipts(self):
        for kind in ('stale','foreign-receipt','foreign-process','missing','incomplete-quiet'):
            with self.subTest(kind=kind),self.cleaned() as rig:
                restore=[]
                def corrupt(seen):
                    store=rig.slot_actor_store;header=store.read()
                    if kind=='stale':time.sleep(1.6);return
                    if kind=='missing':
                        backup=store.path.with_suffix('.controlled');store.path.rename(backup)
                        restore.append(lambda:backup.rename(store.path));return
                    state=unpack(header['payload'])[0]
                    if kind=='foreign-receipt':state['last']['receipt']['actorSequence']+=1
                    elif kind=='foreign-process':state['process']=dict(pid=os.getpid(),start=start_identity(os.getpid()))
                    else:state['quiet']['complete']=False
                    changed=dict(header,payload=pack([state]));store.write(changed,header)
                    restore.append(lambda:store.write(header,store.read()))
                try:
                    seen=self.launch(rig,before_wait=corrupt)
                    self.assertIsInstance(seen['error'],NativeUIError);self.assertEqual([],seen['current'])
                    self.assertEqual(2,len(rig.client.observe()['entries']))
                finally:
                    for callback in reversed(restore):callback()

    def test_postwait_old_file_manifest_sdk_and_phase_mutations_reject_before_current(self):
        for kind in ('old-bytes','manifest-mode','sdk','phase','clock'):
            with self.subTest(kind=kind),self.cleaned() as rig:
                restore=[]
                def mutate(seen):
                    feature=seen['feature']
                    if kind in ('old-bytes','manifest-mode'):
                        pattern='emote-frame-snapshots-'+harness.RUN+'-primary-*.json' if kind=='old-bytes' else 'emote-index-snapshots-'+harness.RUN+'-primary-*.json'
                        path=sorted(rig.root.glob(pattern))[0];raw=path.read_bytes();mode=path.stat().st_mode&0o777
                        if kind=='old-bytes':path.write_bytes(raw+b' ')
                        else:path.chmod(0o644)
                        def reset():path.write_bytes(raw);path.chmod(mode)
                        restore.append(reset)
                    elif kind=='sdk':
                        scope=feature.adapter._existing_input_scope;old=deepcopy(scope)
                        scope['generation']=scope.get('generation',0)+1
                        restore.append(lambda:(scope.clear(),scope.update(old)))
                    elif kind=='phase':rig.client.activate('e'*32,'cleanup',{})
                    else:
                        # The next actual source guard must see a real target
                        # clock rollback, not a rewritten archived receipt.
                        now=rig.model.now
                        rig.model.now=lambda:now()-10000
                        restore.append(lambda:setattr(rig.model,'now',now))
                try:
                    seen=self.launch(rig,after_wait=mutate)
                    self.assertIsInstance(seen['error'],NativeUIError)
                    if kind=='clock':
                        # The FG owner guard has no clock fact. The actual
                        # current reader must reject rollback without sealing
                        # a new measured frame or borrowing the Actor's fact.
                        self.assertIsNone(seen['result']);self.assertLessEqual(len(seen['current']),1)
                        actual=unpack(rig.slot_primary_store.read()['payload'])[0]
                        prepared=unpack(seen['header']['payload'])[0]
                        self.assertEqual(prepared['sequence'],actual['sequence'])
                        self.assertEqual(2,len(rig.client.observe()['entries']))
                    else:self.assertEqual([],seen['current'])
                finally:
                    for callback in reversed(restore):callback()


if __name__=='__main__':unittest.main()
