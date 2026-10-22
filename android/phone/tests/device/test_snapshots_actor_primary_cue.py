"""Primary scheduling cues never supply independent Actor effects or receipts.

The public fixture uses actual TLS, service journals and private files with
explicit native/SDK/render producers. Child processes install HostOnlyBoundary
before constructing an adapter; no device or Android build is exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import select
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_feature_journey as harness
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_script_history import pack,unpack


CHILD=harness.ACTOR[:harness.ACTOR.index('started=time.monotonic()')]+r'''
from copy import deepcopy
import overte_phone_snapshots_actor as module
from overte_phone_script_history import pack,unpack
from adapters.normal_ui import NativeUIError
counts=dict(constructors=0,reads=0,posts=0)
real_role=module.PhoneSnapshotsRole
def construct(*args,**kwargs):
    counts['constructors']+=1
    role=real_role(*args,**kwargs);read=role.read
    def reading(*args,**kwargs):counts['reads']+=1;return read(*args,**kwargs)
    role.read=reading;return role
module.PhoneSnapshotsRole=construct
flow=adapter.actor('synthetic',RUN,client)
def foreign_primary():
    store=PrivateFeatureState(flow.feature.store.path.with_name('phone-snapshots-primary-originals.json'))
    before=store.read();binding=dict(before['binding'],targetFingerprint='f'*64)
    store.write(dict(before,binding=binding),before)
print(json.dumps(dict(ready=True)),flush=True)
for line in sys.stdin:
    instruction=json.loads(line);mode=instruction['mode']
    if mode=='exit':break
    if instruction.get('cold'):flow=adapter.actor('synthetic',RUN,client)
    request=client.request;save=flow.save;write=flow.store.write
    once=[]
    def requested(path,*args,**kwargs):
        if path.endswith('/samples'):
            counts['posts']+=1;result=request(path,*args,**kwargs)
            if mode=='lost-post-return':raise RuntimeError('Controlled loss after real accepted POST')
            return result
        return request(path,*args,**kwargs)
    def saved():
        pending=None if flow.state is None else flow.state['pending']
        if mode=='issued-native-mutation' and pending is not None and pending['issued'] and not once:
            bound=flow.feature.bound
            def actual_then_foreign():
                value=bound()
                if not once:once.append(True);foreign_primary()
                return value
            flow.feature.bound=actual_then_foreign
            try:return save()
            finally:flow.feature.bound=bound
        result=save()
        if mode=='pending-stop' and pending is not None and not pending['issued'] and not once:
            once.append(True);raise NativeUIError('Controlled stop after real durable pending sample')
        return result
    def written(value,previous):
        result=write(value,previous)
        state=unpack(value['payload'])[0]
        if mode=='pending-cas-mutation' and state['pending'] is not None and not state['pending']['issued'] and not once:
            once.append(True);foreign_primary()
        return result
    client.request=requested;flow.save=saved;flow.store.write=written
    error=None;result=None
    try:result=flow.step()
    except Exception as caught:error=type(caught).__name__
    finally:client.request=request;flow.save=save;flow.store.write=write
    header=flow.store.read();state=None if header is None else unpack(header['payload'])[0]
    print(json.dumps(dict(error=error,result=result,counts=counts,state=state)),flush=True)
'''


class SnapshotActorPrimaryCueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type=type('PrimaryCueFixture',(harness.SnapshotJourneyTests,),{})
        cls.fixture_type.setUpClass()
    @classmethod
    def tearDownClass(cls):
        try:cls.fixture_type.tearDownClass()
        finally:cls.fixture_type.doClassCleanups()
    def setUp(self):
        self.rig=self.fixture_type('test_original_public_baseline_before_any_input_or_capture')
        self.rig.setUp();self.addCleanup(self.rig.doCleanups)
        self.rig.client.activate('c'*32);self.sequence=0;self.primary()
        path=self.rig.root/'cue-actor-configuration.json'
        PrivateFeatureState(path).write(dict(targetUrl=self.rig.proxy.url,root=str(self.rig.root),fixtureUrl=self.rig.base,actorToken='a'*64),None)
        self.child=subprocess.Popen([sys.executable,'-B','-c',CHILD,json.dumps(sys.path),str(path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def stop():
            if self.child.poll() is None:
                self.child.stdin.write(json.dumps(dict(mode='exit'))+'\n');self.child.stdin.flush()
            try:self.child.communicate(timeout=5)
            except subprocess.TimeoutExpired:self.child.terminate();self.child.communicate(timeout=3)
        self.addCleanup(stop);self.assertEqual(dict(ready=True),self.receive())
        self.primary_store=self.rig.adapter.snapshots_feature_store('test-only-appium')
        self.primary_store=PrivateFeatureState(self.primary_store.path.with_name('phone-snapshots-primary-originals.json'))
    def receive(self):
        ready,_,_=select.select([self.child.stdout],[],[],15)
        if not ready:
            if self.child.poll() is not None:self.fail(self.child.stderr.read()[-4000:])
            self.fail('Bounded controlled actor response missing')
        line=self.child.stdout.readline()
        if not line:self.fail(self.child.stderr.read()[-4000:])
        return json.loads(line)
    def step(self,mode='normal',*,cold=False):
        self.child.stdin.write(json.dumps(dict(mode=mode,cold=cold))+'\n');self.child.stdin.flush();return self.receive()
    def primary(self):
        result=self.rig.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=self.sequence))
        self.sequence=result['sequence'];return result
    def entries(self):return self.rig.client.request('/runs/'+harness.RUN)['entries']

    def test_actual_primary_advance_allows_only_own_fresh_read_and_same_frontier_waits(self):
        first=self.step();self.assertIsNone(first['error']);self.assertEqual(1,len(self.entries()))
        self.assertIsNotNone(first['state']['primaryCue']);self.assertEqual(1,first['counts']['reads'])
        same=self.step();self.assertIsNone(same['error']);self.assertEqual(first['counts'],same['counts'])
        cold=self.step(cold=True);self.assertIsNone(cold['error']);self.assertEqual(first['counts'],cold['counts'])
        self.primary();second=self.step();self.assertIsNone(second['error'])
        self.assertEqual(2,second['counts']['reads']);self.assertEqual(2,len(self.entries()))
        self.assertGreater(second['state']['last']['receipt']['actorSequence'],first['state']['last']['receipt']['actorSequence'])
        self.assertEqual(self.primary_store.read(),second['state']['primaryCue']['header'])

    def test_missing_foreign_and_rollback_primary_are_red_before_new_actor_read_or_post(self):
        initial=deepcopy(self.primary_store.read());first=self.step();self.assertIsNone(first['error'])
        self.primary();second=self.step();self.assertIsNone(second['error']);latest=deepcopy(self.primary_store.read())
        for kind in ('missing','foreign','rollback'):
            with self.subTest(kind=kind):
                if kind=='missing':
                    path=self.primary_store.path;backup=path.with_name(path.name+'.controlled');path.rename(backup)
                elif kind=='foreign':
                    foreign=dict(latest,binding=dict(latest['binding'],targetFingerprint='f'*64));self.primary_store.write(foreign,latest)
                else:self.primary_store.write(initial,latest)
                try:
                    rejected=self.step(cold=True);self.assertEqual('NativeUIError',rejected['error'])
                    self.assertEqual(second['counts'],rejected['counts']);self.assertEqual(2,len(self.entries()))
                    self.assertEqual(second['state']['primaryCue'],rejected['state']['primaryCue'])
                finally:
                    if kind=='missing':backup.rename(path)
                    else:self.primary_store.write(latest,self.primary_store.read())

    def test_actual_accepted_post_lost_return_recovers_cold_without_new_read_or_post(self):
        # The real source-lock boundary translates the lost transport return
        # into NativeUIError; the actual accepted service row is checked below.
        uncertain=self.step('lost-post-return');self.assertEqual('NativeUIError',uncertain['error'])
        self.assertTrue(uncertain['state']['pending']['issued']);self.assertEqual(1,len(self.entries()))
        recovered=self.step(cold=True);self.assertIsNone(recovered['error']);self.assertIsNone(recovered['state']['pending'])
        self.assertEqual(uncertain['counts'],recovered['counts']);self.assertEqual(1,len(self.entries()))
        self.assertEqual(uncertain['state']['primaryCue'],recovered['state']['primaryCue'])

    def test_pending_sample_cold_resume_rechecks_primary_after_first_issued_save_native_guard(self):
        stopped=self.step('pending-stop');self.assertEqual('NativeUIError',stopped['error'])
        self.assertFalse(stopped['state']['pending']['issued']);self.assertEqual([],self.entries())
        rejected=self.step('issued-native-mutation',cold=True);self.assertEqual('NativeUIError',rejected['error'])
        self.assertEqual(stopped['counts'],rejected['counts']);self.assertEqual([],self.entries())
        self.assertEqual(stopped['state']['pending'],rejected['state']['pending'])
        self.assertEqual(stopped['state']['primaryCue'],rejected['state']['primaryCue'])
        self.assertEqual('f'*64,self.primary_store.read()['binding']['targetFingerprint'])

    def test_pending_cas_owner_loss_survives_cold_reconstruction_without_post(self):
        stopped=self.step('pending-cas-mutation');self.assertEqual('NativeUIError',stopped['error'])
        self.assertIsNotNone(stopped['state']['pending']);self.assertIsNotNone(stopped['state']['primaryCue'])
        self.assertEqual([],self.entries())
        cold=self.step(cold=True);self.assertEqual('NativeUIError',cold['error'])
        self.assertEqual(stopped['counts'],cold['counts']);self.assertEqual([],self.entries())
        self.assertEqual(stopped['state']['pending'],cold['state']['pending'])
        self.assertEqual(stopped['state']['primaryCue'],cold['state']['primaryCue'])

    def test_primary_capture_fact_cannot_replace_missing_actual_actor_original_bytes(self):
        self.rig.act('open');self.rig.act('capture',dict(mode='still',format='png'))
        measured=self.primary();self.assertEqual(1,measured['state']['files'])
        path=next(self.rig.model.producer.directory.glob('e2e-'+harness.RUN+'-*.png'))
        backup=path.with_name(path.name+'.controlled');path.rename(backup)
        try:
            rejected=self.step();self.assertIsNotNone(rejected['error']);self.assertEqual([],self.entries())
            self.assertEqual(1,rejected['counts']['reads']);self.assertEqual(0,rejected['counts']['posts'])
        finally:backup.rename(path)


if __name__=='__main__':unittest.main()
