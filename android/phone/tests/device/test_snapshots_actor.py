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
from overte_phone_script_history import unpack
from overte_phone_snapshots_actor import PhoneSnapshotsActor
from test_snapshots_role import SnapshotRolesBoundary,RUN,TICKET


def actor_once(boundary,url,token,queue):
    try:
        f=boundary.feature;f.role='actor';f.load=lambda:None
        phase=PhaseFixtureReader(Client(url,token),RUN,'snapshots',epoch_ms=lambda:boundary.epoch)
        f.phase.client=phase.client;f.phase.status=phase.status
        result=PhoneSnapshotsActor(f).step();queue.put(dict(result=result,pid=os.getpid(),start=start_identity(os.getpid())))
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
    def test_primary_process_cannot_claim_separate_actor_identity(self):
        b=self.boundary;f=b.feature;f.role='actor';f.load=lambda:None;f.phase.client=Client(self.url,'a'*64)
        with self.assertRaises(NativeUIError):PhoneSnapshotsActor(f).step()
        self.assertIsNone(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read())

if __name__=='__main__':unittest.main()
