"""Actual TLS closure between an Actor's outer and inner cleanup phase reads.

Only the existing native/SDK/render target producers are synthetic. The child
uses the original Actor program, real monotonic quiet, original journals and
the actual fixture close API. IPC controls scheduling, never source contents.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_feature_journey as journey
import test_snapshots_full_retirement_audit as retirement_audit
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Journal
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_script_history import unpack
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshots_retirement import NAMES,terminated


INTERPOSE=r'''
from copy import deepcopy
import select
from overte_phone_snapshots_actor import PhoneSnapshotsActor
from overte_phone_snapshots_role import PhoneSnapshotsRole
race_counts=dict(reads=0,sources=0,posts=0)
race_paused=False
race_reported=False
race_before=None
race_active_role=None
race_init=PhoneSnapshotsActor.__init__
race_quiet=PhoneSnapshotsActor.quiet_batch
race_read=PhoneSnapshotsRole.read
race_request=client.request
race_call=adapter.call
def race_source(kind,value):
    if kind=='source':race_counts['sources']+=1
    return race_call(kind,value)
adapter.call=race_source
def race_publish(path,*args,**kwargs):
    if path.endswith('/samples') and args and args[0] is not None:race_counts['posts']+=1
    return race_request(path,*args,**kwargs)
client.request=race_publish
def race_pause(actor,role,status,where):
    global race_paused,race_before
    race_paused=True;race_before=dict(race_counts)
    quiet=actor.state['quiet'];complete=quiet is not None and quiet['complete']
    assert status['active'] and status['activations'][-1]['stimulus']['verb']=='cleanup'
    assert actor.feature.lock._owner is not None
    if RACE_COMPLETE:
        assert actor.state['last'] is not None and actor.state['pending'] is None
        assert quiet['last']-quiet['started']>=3 and len(quiet['sequences'])>=3
    print(json.dumps(dict(event='paused',complete=complete,quiet=deepcopy(quiet),
        outerActive=status['active'],actorRoleSequence=role.state['sequence'],pid=os.getpid(),
        hadReceipt=actor.state['last'] is not None,where=where,
        enteredRead=role._host_publication)),flush=True)
    if not select.select([sys.stdin],[],[],20)[0]:raise RuntimeError('Actual close IPC timed out')
    if sys.stdin.readline().strip()!='closed':raise RuntimeError('Unexpected close IPC instruction')
def race_constructor(self,*args,**kwargs):
    race_init(self,*args,**kwargs)
    original=self.feature.phase.status
    def status(*a,**kw):
        result=original(*a,**kw);self._race_last_status=deepcopy(result)
        if (RACE_DURING and not race_paused and race_active_role is not None
                and race_active_role._host_publication and self.state['quiet'] is not None
                and self.state['quiet']['complete'] and result['active']):
            race_pause(self,race_active_role,result,'actual-phase-before-return')
        return result
    self.feature.phase.status=status
PhoneSnapshotsActor.__init__=race_constructor
def race_current(self,*args,**kwargs):
    global race_active_role
    race_counts['reads']+=1;race_active_role=self
    try:return race_read(self,*args,**kwargs)
    finally:race_active_role=None
PhoneSnapshotsRole.read=race_current
def race_inner(self,role,prepared,started):
    global race_reported
    complete=self.state['quiet'] is not None and self.state['quiet']['complete']
    if not RACE_DURING and not race_paused and (complete if RACE_COMPLETE else not complete):
        race_pause(self,role,self._race_last_status,'before-inner-read')
    try:result=race_quiet(self,role,prepared,started)
    except Exception as error:
        if race_paused and not race_reported:
            race_reported=True
            print(json.dumps(dict(event='rejected',error=type(error).__name__,
                delta={k:race_counts[k]-race_before[k] for k in race_before})),flush=True)
        raise
    if race_paused and not race_reported:
        race_reported=True
        print(json.dumps(dict(event='returned',result=result,
            delta={k:race_counts[k]-race_before[k] for k in race_before},
            rolePhase=role.state['phase'])),flush=True)
    return result
PhoneSnapshotsActor.quiet_batch=race_inner
'''


class SnapshotCleanupCloseRaceTests(unittest.TestCase):
    SDK=29
    invoke=journey.SnapshotJourneyTests.invoke
    act=journey.SnapshotJourneyTests.act
    normal_cleanup=retirement_audit.FullRetirementAuditTests.normal_cleanup
    cleanup_public=retirement_audit.FullRetirementAuditTests.cleanup_public

    @classmethod
    def setUpClass(cls):journey.SnapshotJourneyTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):journey.SnapshotJourneyTests.tearDownClass.__func__(cls)

    def setUp(self):
        original_target=journey.SnapshotTarget
        def actual_clock_target(*args,**kwargs):
            model=original_target(*args,**kwargs);original_rpc=model.rpc
            batch=threading.local()
            # Sample the real integer host clock for each synthetic native
            # query; keep that single query internally ordered. Historical
            # DTOs are never edited, and no packet supplies the clock value.
            model.now=lambda:getattr(batch,'epoch',time.time_ns()//1000000)
            def rpc(kind,value):
                with model.lock:
                    batch.epoch=time.time_ns()//1000000
                    try:return original_rpc(kind,value)
                    finally:del batch.epoch
            model.rpc=rpc
            return model
        with patch.object(journey,'SnapshotTarget',side_effect=actual_clock_target):
            journey.SnapshotJourneyTests.setUp(self)
        # Reuse the original Journal default, before any action, receipt or
        # closure. The target continues to report integer acquisition epochs.
        self.server.journal.clock=Journal().clock

    def close_original(self):
        self.client.close()
        phase=PhaseFixtureReader(self.client,journey.RUN,'snapshots').status()
        self.assertFalse(phase['active'])
        self.assertIs(type(phase['retiredEpochMs']),float)
        return phase

    def start_race(self,complete,*,during=False):
        split=journey.ACTOR.index('started=time.monotonic()')
        script=journey.ACTOR[:split]+'\nimport os\nRACE_COMPLETE='+repr(complete)+'\nRACE_DURING='+repr(during)+'\n'+INTERPOSE+'\n'+journey.ACTOR[split:]
        path=self.root/'actor-configuration.json'
        PrivateFeatureState(path).write(dict(targetUrl=self.proxy.url,root=str(self.root),fixtureUrl=self.base,actorToken='a'*64),None)
        self.actor=subprocess.Popen([sys.executable,'-c',script,json.dumps(sys.path),str(path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def stop():
            if self.actor.poll() is None:self.actor.terminate()
            self.actor.communicate(timeout=5)
        self.addCleanup(stop)

    def event(self):
        self.assertTrue(select.select([self.actor.stdout],[],[],25)[0],'Original Actor IPC deadline exceeded')
        line=self.actor.stdout.readline()
        if not line:
            _,error=self.actor.communicate(timeout=5)
            self.fail('Original Actor exited before IPC: '+error[-3000:])
        return json.loads(line)

    def setup_cleanup(self):
        self.normal_cleanup()
        # This is a genuine fresh Primary observation, not a reducer fixture.
        value=self.invoke('feature.snapshots.observe',dict(contractVersion=journey.VERSION,runId=journey.RUN,afterSequence=0))
        self.assertEqual([],value['resources']);self.assertEqual(0,value['state']['files'])

    def completed_close(self,*,during=False):
        self.setup_cleanup();self.start_race(True,during=during);paused=self.event()
        self.assertEqual('paused',paused['event']);self.assertTrue(paused['complete']);self.assertTrue(paused['outerActive'])
        self.assertTrue(paused['hadReceipt']);self.assertNotEqual(os.getpid(),paused['pid'])
        self.assertGreaterEqual(paused['quiet']['last']-paused['quiet']['started'],3)
        self.assertGreaterEqual(len(paused['quiet']['sequences']),3)
        closed=self.close_original();self.actor.stdin.write('closed\n');self.actor.stdin.flush()
        returned=self.event();self.assertEqual('returned',returned['event']);self.assertIs(returned['result'],False)
        self.assertEqual(during,paused['enteredRead'])
        self.assertEqual(0,returned['delta']['reads']);self.assertEqual(0,returned['delta']['posts'])
        if during:
            self.assertGreater(returned['delta']['sources'],0);self.assertEqual('reading',returned['rolePhase'])
        else:self.assertEqual(0,returned['delta']['sources'])
        _,error=self.actor.communicate(timeout=25);self.assertEqual(0,self.actor.returncode,error[-3000:])
        actor=unpack(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read()['payload'])[0]
        self.assertEqual('retired',actor['phase']);self.assertFalse(actor['closure']['active']);self.assertTrue(terminated(actor['process']))
        self.assertIs(type(actor['last']['receipt']['receivedEpochMs']),float)
        self.assertIs(type(actor['closure']['retiredEpochMs']),float)
        self.assertEqual(closed['retiredEpochMs'],actor['closure']['retiredEpochMs'])
        header=PrivateFeatureState(self.root/'phone-snapshots-actor-originals.json').read();state=unpack(header['payload'])[0]
        self.assertEqual('retired',state['phase']);self.assertGreater(state['sequence'],paused['actorRoleSequence'])
        feature=self.adapter._snapshots_feature('test-only-appium',journey.RUN)
        with feature.lock.held():
            feature.load()
            originals=SnapshotsOriginals(self.root,feature.binding,journey.RUN,'actor',feature.bound,
                lambda *_:self.fail('Read-only original inspection attempted a write'),kind='snapshots')
            frames=originals.restore(state['manifests'],state['sequence'])
        self.assertFalse(frames[-1]['phaseBefore']['active']);self.assertFalse(frames[-1]['phaseAfter']['active'])
        self.assertFalse(frames[-1].get('diagnostic'));self.assertEqual(0,frames[-1]['state']['files'])
        if during:self.assertTrue(frames[-2].get('diagnostic'))
        self.assertEqual({'performed':True},self.cleanup_public())
        archives=list(self.root.glob('emote-frame-snapshots-retirement-*.json'));self.assertEqual(1,len(archives))
        original=(archives[0].stat().st_ino,hashlib.sha256(archives[0].read_bytes()).hexdigest())
        self.assertTrue(all(PrivateFeatureState(self.root/name).read() is None for name in NAMES))
        self.assertEqual({'performed':True},self.cleanup_public())
        self.assertEqual(original,(archives[0].stat().st_ino,hashlib.sha256(archives[0].read_bytes()).hexdigest()))

    def test_completed_own_quiet_defers_close_before_inner_read_then_retires(self):self.completed_close()

    def test_completed_own_quiet_recovers_actual_mid_read_close_before_fresh_retirement(self):self.completed_close(during=True)

    def test_incomplete_quiet_rejects_real_close_and_preserves_original_controls(self):
        self.setup_cleanup();self.start_race(False);paused=self.event()
        self.assertEqual('paused',paused['event']);self.assertFalse(paused['complete']);self.assertTrue(paused['outerActive'])
        names=['phone-snapshots-'+name+'.json' for name in ('feature','primary-originals','actor-originals','actor-lifecycle')]
        before={name:(self.root/name).read_bytes() for name in names}
        closed=self.close_original();self.actor.stdin.write('closed\n');self.actor.stdin.flush()
        rejected=self.event();self.assertEqual('rejected',rejected['event'])
        self.assertEqual(dict(reads=0,sources=0,posts=0),rejected['delta'])
        _,error=self.actor.communicate(timeout=20);self.assertNotEqual(0,self.actor.returncode,error[-3000:])
        self.assertEqual(before,{name:(self.root/name).read_bytes() for name in names})
        actor=unpack(PrivateFeatureState(self.root/'phone-snapshots-actor-lifecycle.json').read()['payload'])[0]
        self.assertEqual('watching',actor['phase']);self.assertTrue(actor['quiet'] is None or not actor['quiet']['complete'])
        self.assertFalse(list(self.root.glob('emote-frame-snapshots-retirement-*.json')))


if __name__=='__main__':unittest.main()
