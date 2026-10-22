"""Actual separate host actor and credentialed loopback journal, no device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.server import make_server
from feature_journeys.witness import Client
from feature_journeys.phase_fixture import PhaseFixtureReader
from fixture.messages_mixer import start_identity
from overte_phone_script_history import unpack,pack
from overte_phone_snapshots_actor import PhoneSnapshotsActor
from test_snapshots_role import SnapshotRolesBoundary,RUN,TICKET


def actor_once(boundary,url,token,queue):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:None
        phase=PhaseFixtureReader(Client(url,token),RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        result=PhoneSnapshotsActor(f).step();queue.put(dict(result=result,pid=os.getpid(),start=start_identity(os.getpid())))
    except Exception as error:queue.put(dict(error=type(error).__name__,message=str(error)))


def actor_until_closed(boundary,url,queue,command,report_progress=False):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:None
        phase=PhaseFixtureReader(Client(url,'a'*64),RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        f.phase.provider=lambda:dict(boundary.provider,active=phase.status()['active'])
        # Exercise the production quiet window with real elapsed host time.
        f.monotonic,f.sleep=time.monotonic,time.sleep
        actor=PhoneSnapshotsActor(f)
        handed=[False]
        def sleep(seconds):
            if report_progress and not handed[0] and f.lock._owner is None:
                handed[0]=True;queue.put(dict(progress=True,quiet=deepcopy(actor.state['quiet'])))
                if not command.poll(5):raise RuntimeError('Quiet progress handoff missing')
                instruction=command.recv()
                if instruction=='foreign-binding':f.binding['processIdentity']='32:foreign-start'
                elif instruction!='continue':raise RuntimeError('Quiet progress handoff missing')
            time.sleep(seconds)
        f.sleep=sleep
        deadline=time.monotonic()+15
        for _attempt in range(100):
            if time.monotonic()>=deadline:raise RuntimeError('Independent quiet deadline exceeded')
            result=actor.step()
            if actor.state['quiet'] is not None and actor.state['quiet']['complete']:break
            time.sleep(.1)
        else:raise RuntimeError('Independent original actor quiet never completed')
        queue.put(dict(ready=True,pid=os.getpid(),start=start_identity(os.getpid()),quiet=deepcopy(actor.state['quiet'])))
        if not command.poll(10):raise RuntimeError('Explicit host close seam timed out')
        assert command.recv()=='closed'
        result=actor.step();queue.put(dict(result=result,phase=actor.state['phase'],closure=deepcopy(actor.state['closure'])))
        if not command.poll(10):raise RuntimeError('Explicit post-close seam timed out')
        next_command=command.recv()
        if next_command=='late':actor.step();raise AssertionError('Late original unexpectedly passed retired actor')
        assert next_command=='exit'

    except Exception as error:queue.put(dict(error=type(error).__name__,message=str(error)))


class SnapshotsActorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-actor-');self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.boundary=SnapshotRolesBoundary(self.root);f=self.boundary.feature;f.state['hostProcess']=dict(pid=os.getpid(),start=start_identity(os.getpid()))
        f.state['actions']=[dict(ticket=TICKET,phase='acknowledged')]
        self.server=make_server('r'*64,'a'*64,adapter_token='b'*64);self.server.journal.clock=lambda:self.boundary.epoch
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        def stop():self.server.shutdown();self.server.server_close();self.thread.join(3)
        self.addCleanup(stop);self.url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1';self.reader=Client(self.url,'r'*64)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.reader.register('snapshots')
        self.reader.activate(TICKET,'capture',dict(mode='still',format='png'))
    def run_actor(self,token='a'*64):
        # Fork only after stopping the loopback server thread; restart that
        # same listener immediately in the parent before any actor I/O.
        self.server.shutdown();self.thread.join(3);self.assertFalse(self.thread.is_alive())
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();process=ctx.Process(target=actor_once,args=(self.boundary,self.url,token,queue));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();process.join(15)
        if process.is_alive():process.terminate();process.join(3);self.fail('Explicit host actor seam exceeded its bounded completion')
        self.assertEqual(0,process.exitcode);return queue.get(timeout=2)
    def test_actual_separate_process_publishes_own_originals_with_actor_credentials(self):
        result=self.run_actor();self.assertNotIn('error',result);self.assertIs(result['result'],False);self.assertNotEqual(os.getpid(),result['pid'])
        value=self.reader.request('/runs/'+RUN);self.assertEqual(1,len(value['entries']));self.assertEqual(1,value['entries'][0]['facts']['files'])
        header=PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read();state=unpack(header['payload'])[0]
        self.assertEqual(dict(pid=result['pid'],start=result['start']),state['process']);self.assertIsNone(state['pending']);self.assertEqual('watching',state['phase'])
        self.assertFalse(PrivateFeatureState(self.root/'phone-snapshots-primary-originals.json').read())
        self.assertTrue(list(self.root.glob('snapshots-file-'+RUN+'-actor-*.bin')))
    def test_reader_credentials_cannot_publish_even_after_actual_independent_measurement(self):
        result=self.run_actor('r'*64);self.assertIn('error',result);self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
        state=unpack(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read()['payload'])[0]
        self.assertTrue(state['pending']['issued']);self.assertIsNone(state['last']);self.assertEqual('watching',state['phase'])
    def test_own_original_quiet_and_actual_closed_phase_precede_actor_retirement(self):
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        self.server.shutdown();self.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=actor_until_closed,args=(b,self.url,queue,receive));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        try:
            ready=queue.get(timeout=25);self.assertNotIn('error',ready);self.assertGreaterEqual(ready['quiet']['last']-ready['quiet']['started'],3)
            self.assertGreaterEqual(len(ready['quiet']['sequences']),3);self.reader.close();send.send('closed')
            final=queue.get(timeout=15);self.assertNotIn('error',final);self.assertIs(final['result'],True);self.assertEqual('retired',final['phase']);self.assertFalse(final['closure']['active'])
            # A stored retired plan must not hide actual late target work.
            late=b.producer.directory/('e2e-'+RUN+'-late.png');late.write_bytes(b.raw);send.send('late')
            rejected=queue.get(timeout=10);self.assertEqual('NativeUIError',rejected.get('error'));self.assertEqual(b.raw,late.read_bytes())
            process.join(3);self.assertEqual(0,process.exitcode)
        finally:
            if process.is_alive():process.terminate();process.join(3)
        state=unpack(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read()['payload'])[0]
        self.assertEqual('retired',state['phase']);self.assertIsNone(state['partialClosure']);self.assertIsNone(state['pending'])
    def test_incomplete_actual_quiet_sample_releases_lock_before_another_role_read(self):
        from overte_phone_script_lock import PhoneScriptSourceLock
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        self.server.shutdown();self.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=actor_until_closed,args=(b,self.url,queue,receive,True));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        try:
            progress=queue.get(timeout=15);self.assertNotIn('error',progress);self.assertTrue(progress['progress'])
            self.assertIsNone(progress['quiet'])
            self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
            # A genuinely separate process remains alive with unfinished quiet
            # work while the primary can acquire the original OS source lock.
            self.assertTrue(process.is_alive())
            with PhoneScriptSourceLock(b.feature.lock.path,timeout=.1).held():pass
            send.send('continue');ready=queue.get(timeout=25);self.assertNotIn('error',ready)
            self.assertGreaterEqual(ready['quiet']['last']-ready['quiet']['started'],3)
            self.assertGreaterEqual(len(ready['quiet']['sequences']),3)
            self.reader.close();send.send('closed');final=queue.get(timeout=15);self.assertNotIn('error',final)
            self.assertTrue(final['result']);send.send('exit');process.join(3);self.assertEqual(0,process.exitcode)
        finally:
            if process.is_alive():process.terminate();process.join(3)

    def between_lock_counter(self,mutation):
        b=self.boundary;b.clean();self.reader.activate('d'*32,'cleanup',{});b.feature.state['actions']=[dict(ticket='d'*32,phase='acknowledged')]
        b.provider.update(ticket='d'*32,activations=[dict(ticket=TICKET,verb='capture',capturedEpochMs=19000),dict(ticket='d'*32,verb='cleanup',capturedEpochMs=20000)])
        self.server.shutdown();self.thread.join(3)
        ctx=multiprocessing.get_context('fork');queue=ctx.Queue();receive,send=ctx.Pipe(duplex=False)
        process=ctx.Process(target=actor_until_closed,args=(b,self.url,queue,receive,True));process.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        foreign_store=None;foreign=None
        try:
            progress=queue.get(timeout=15);self.assertNotIn('error',progress);self.assertIsNone(progress['quiet'])
            if mutation=='closed':self.reader.close()
            elif mutation=='ticket':self.reader.activate('e'*32,'cleanup',{})
            elif mutation=='late-file':
                late=b.producer.directory/('e2e-'+RUN+'-late-between-locks.png');late.write_bytes(b.raw)
            elif mutation in ('feature','role'):
                foreign_store=b.feature.store if mutation=='feature' else PrivateFeatureState(b.root/'phone-snapshots-actor-originals.json')
                previous=foreign_store.read();foreign=dict(foreignActualHeader=True);foreign_store.write(foreign,previous)
            elif mutation=='actor':
                foreign_store=PrivateFeatureState(b.root/'phone-snapshots-actor-lifecycle.json');previous=foreign_store.read()
                state=unpack(previous['payload'])[0];state['dropped'].append(dict(foreign=True));foreign=dict(previous,payload=pack([state]))
                foreign_store.write(foreign,previous)
            else:self.assertEqual('pid',mutation)
            send.send('foreign-binding' if mutation=='pid' else 'continue')
            rejected=queue.get(timeout=15);self.assertEqual('NativeUIError',rejected.get('error'),rejected)
            process.join(3);self.assertEqual(0,process.exitcode)
            if mutation!='closed':self.assertFalse(self.reader.request('/runs/'+RUN)['entries'])
            if foreign_store is not None:self.assertEqual(foreign,foreign_store.read())
            if mutation=='late-file':self.assertEqual(b.raw,late.read_bytes())
        finally:
            if process.is_alive():process.terminate();process.join(3)

    def test_actual_closed_phase_between_preparation_and_quiet_is_red(self):self.between_lock_counter('closed')
    def test_new_actual_cleanup_ticket_between_preparation_and_quiet_is_red(self):self.between_lock_counter('ticket')
    def test_changed_feature_owner_between_preparation_and_quiet_is_red(self):self.between_lock_counter('feature')
    def test_changed_actor_journal_cannot_be_loaded_as_the_prepared_owner(self):self.between_lock_counter('actor')
    def test_changed_role_journal_cannot_be_loaded_as_the_prepared_floor(self):self.between_lock_counter('role')
    def test_changed_original_process_binding_between_locks_is_red(self):self.between_lock_counter('pid')
    def test_late_actual_owned_file_between_preparation_and_quiet_is_red(self):self.between_lock_counter('late-file')

    def test_partial_cleanup_records_only_the_owner_proof_after_actual_close(self):
        b=self.boundary;f=b.feature;f.role='actor';f.load=lambda:None;f.state.update(phase='partial-cleaned',partial=True)
        f.state['hostProcess']=dict(pid=os.getpid()+100,start='explicit-host-identity-seam')
        phase=PhaseFixtureReader(Client(self.url,'a'*64),RUN,'snapshots',epoch_ms=lambda:b.epoch);f.phase.client=phase.client;f.phase.status=phase.status
        proof=dict(originalScope='zero-issued',kernelBinding=deepcopy(f.binding));calls=[]
        f.partial_restored=lambda:calls.append('original-proof') or deepcopy(proof)
        actor=PhoneSnapshotsActor(f);self.assertIs(actor.step(),False);self.assertFalse(calls);self.reader.close()
        def refused():raise NativeUIError('Original owner still has an unresolved partial obligation')
        f.partial_restored=refused
        with self.assertRaises(NativeUIError):actor.step()
        self.assertEqual('watching',actor.state['phase']);self.assertIsNone(actor.state['partialClosure'])
        f.partial_restored=lambda:calls.append('original-proof') or deepcopy(proof)
        self.assertIs(actor.step(),True);self.assertEqual(['original-proof'],calls);self.assertEqual(proof,actor.state['partialClosure'])
        self.assertIsNone(actor.state['last']);self.assertIsNone(actor.state['quiet']);self.assertIsNone(actor.state['pending'])
        self.assertFalse(list(self.root.glob('snapshots-file-'+RUN+'-actor-*')))
    def test_primary_process_cannot_claim_separate_actor_identity(self):
        b=self.boundary;f=b.feature;f.role='actor';f.load=lambda:None;f.phase.client=Client(self.url,'a'*64)
        with self.assertRaises(NativeUIError):PhoneSnapshotsActor(f).step()
        self.assertIsNone(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read())

if __name__=='__main__':unittest.main()
