"""Actual TLS activation races, immutable Role IO and separate actor ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_feature_journey as harness
from adapters.normal_feature_state import PrivateFeatureState
from overte_phone_script_history import pack,unpack

NEW='e'*32
SCRIPT=r'''
import overte_phone_snapshots_actor as module
from overte_phone_script_history import pack,unpack
mode=sys.argv[3]
constructors=[];reads=[];acquisitions=[];original=module.PhoneSnapshotsRole;gate=[False]
def report(value):print(json.dumps(value),flush=True)
def command():
    value=sys.stdin.readline().strip()
    if not value:raise RuntimeError('Controlled parent command missing')
    return value

def construct(*args,**kwargs):
    role=original(*args,**kwargs);constructors.append(role)
    for owner,name in ((role,'batch'),(role.native,'read'),(role.avatar,'read')):
        if owner is not None:
            actual=getattr(owner,name)
            def measured(*args,_actual=actual,_name=name,**kwargs):
                acquisitions.append(_name);return _actual(*args,**kwargs)
            setattr(owner,name,measured)
    read=role.read
    def current(*args,**kwargs):reads.append(True);return read(*args,**kwargs)
    role.read=current
    if not gate[0]:
        gate[0]=True
        report(dict(ready=True,roleHeader=role.previous,actorHeader=flow.previous));assert command()=='read'
    return role
module.PhoneSnapshotsRole=construct
flow=adapter.actor('synthetic',RUN,client)
try:
    result=flow.step()
    report(dict(stage='transition',result=result,rows=len(flow.state['transitions']),pending=flow.state['pending'],
        constructors=len(constructors),reads=len(reads),acquisitions=len(acquisitions),frame=constructors[-1].frames[-1],actorHeader=flow.previous))
    started=time.monotonic();checks=[0];bound=flow.feature.bound
    def counted():checks[0]+=1;return bound()
    flow.feature.bound=counted
    try:
        with flow.feature.lock.held():module.validate_transition_history(flow.feature,flow.state,expected_actor=flow.previous)
    finally:flow.feature.bound=bound
    report(dict(stage='history-cost',targetChecks=checks[0],seconds=time.monotonic()-started))
    assert command()=='unacknowledged'
    result=flow.step()
    report(dict(stage='unacknowledged',result=result,constructors=len(constructors),reads=len(reads),pending=flow.state['pending']))
    instruction=command()
    if instruction in ('mutated','mutated-reopen'):
        if instruction=='mutated-reopen':flow=adapter.actor('synthetic',RUN,client)
        try:flow.step()
        except Exception as error:
            report(dict(rejected=True,error=type(error).__name__,constructors=len(constructors)));sys.exit(0)
        report(dict(rejected=False,constructors=len(constructors)));sys.exit(0)
    assert instruction=='acknowledged'
    deadline=time.monotonic()+15
    while True:
        result=flow.step()
        if flow.state['last'] is not None:break
        assert time.monotonic()<deadline
        time.sleep(.25)
    report(dict(stage='fresh',result=result,constructors=len(constructors),reads=len(reads),last=flow.state['last'],
        transitionSequence=flow.state['transitions'][0]['frameSequence']))
    instruction=command()
    if instruction=='cleanup':
        deadline=time.monotonic()+15
        while True:
            result=flow.step()
            if flow.state['last']['receipt']['ticket']!=flow.state['transitions'][0]['confirmed']['activations'][-1]['ticket']:break
            assert time.monotonic()<deadline
            time.sleep(.25)
        report(dict(stage='cleanup',last=flow.state['last']));instruction=command()
    if instruction=='close':
        assert flow.step();report(dict(stage='retired',phase=flow.state['phase']));sys.exit(0)
    assert instruction=='exit'
except Exception as error:
    report(dict(rejected=True,error=type(error).__name__,message=str(error),constructors=len(constructors),reads=len(reads)))
'''


JOURNAL_SCRIPT=r'''
from copy import deepcopy
from unittest.mock import patch
import overte_phone_snapshots_actor as source
from overte_phone_script_history import pack,unpack
flow=adapter.actor('synthetic',RUN,client);f=flow.feature
with f.lock.held():
    f.load();flow.load();previous=deepcopy(flow.previous)
    state=unpack(previous['payload'])[0];state.pop('transitions');state.pop('primaryCue')
    legacy=dict(previous,snapshotsActorVersion=1,payload=pack([state]))
    if sys.argv[3]=='foreign-shape':
        state['unknownLegacyField']=True;legacy['payload']=pack([state])
    flow.store.write(legacy,previous)
    resumed=source.PhoneSnapshotsActor(f)
    if sys.argv[3]=='foreign-shape':
        try:resumed.load()
        except Exception:
            assert resumed.store.read()==legacy
            print(json.dumps(dict(rejected=True,preserved=True)),flush=True)
        else:raise AssertionError('Unknown legacy journal shape was adopted')
    else:
        resumed.load();assert resumed.state==dict(state,transitions=[],primaryCue=None)
        with patch.object(f,'bound',side_effect=AssertionError('Empty history queried the target')):
            source.validate_transition_history(f,resumed.state)
            try:source.validate_transition_history(f,resumed.state,current_guard=lambda:True)
            except Exception:pass
            else:raise AssertionError('Explicit current guard accepted without immutable owner authority')
        resumed.save();assert resumed.previous['snapshotsActorVersion']==source.ACTOR_VERSION
        assert unpack(resumed.previous['payload'])[0]==dict(state,transitions=[],primaryCue=None)
        print(json.dumps(dict(migrated=True,lossless=True,emptyHistoryTargetQueries=0)),flush=True)
'''


class SnapshotPhaseTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):harness.SnapshotJourneyTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):harness.SnapshotJourneyTests.tearDownClass.__func__(cls)
    def setUp(self):
        self.rig=harness.SnapshotJourneyTests('test_original_public_baseline_before_any_input_or_capture')
        self.rig.cert,self.rig.server_context=self.cert,self.server_context
        self.addCleanup(self.rig.doCleanups);self.rig.setUp()
        self.rig.client.activate('c'*32)
        self.rig.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))
        self.child=None
    def start(self,*,baseline=False):
        r=self.rig
        if not baseline:
            r.act('open');r.act('capture',dict(mode='still',format='png'))
            self.observe_primary()
        prefix=harness.ACTOR[:harness.ACTOR.index('started=time.monotonic();flow=None')]
        config=r.root/'transition-actor-config.json'
        PrivateFeatureState(config).write(dict(targetUrl=r.proxy.url,root=str(r.root),fixtureUrl=r.base,actorToken='a'*64),None)
        self.child=subprocess.Popen([sys.executable,'-c',prefix+SCRIPT,json.dumps(sys.path),str(config),'ordinary'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def stop():
            if self.child.poll() is None:self.child.terminate()
            self.child.communicate(timeout=5)
        self.addCleanup(stop)
        ready=self.receive();self.assertTrue(ready.get('ready'),ready);return ready
    def observe_primary(self):
        return self.rig.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))
    def receive(self):
        self.assertTrue(select.select([self.child.stdout],[],[],25)[0],'Actual independent actor response timed out')
        raw=self.child.stdout.readline()
        if not raw:
            _out,err=self.child.communicate(timeout=3);self.fail('Actual child ended: '+err[-4000:])
        return json.loads(raw)
    def send(self,value):self.child.stdin.write(value+'\n');self.child.stdin.flush()
    def activate(self,verb='share-open'):
        self.rig.client.activate(NEW,verb,{});self.send('read')
        result=self.receive();return result
    def assert_transition(self,result):
        self.assertEqual('transition',result.get('stage'),result);self.assertFalse(result['result'])
        self.assertEqual(1,result['rows']);self.assertIsNone(result['pending']);self.assertEqual(1,result['reads'])
        self.assertEqual(0,result['acquisitions'])
        self.assertEqual({'ticket','phaseBefore','phaseAfter','phaseAdmission','diagnostic','image','binaries','retirement'},set(result['frame']))
        self.assertTrue(result['frame']['diagnostic']);self.assertIsNone(result['frame']['image'])
        self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])
        cost=self.receive();self.assertEqual('history-cost',cost['stage']);self.assertEqual(2,cost['targetChecks'])
        self.history_cost=cost
        self.send('unacknowledged');unack=self.receive()
        self.assertEqual('unacknowledged',unack['stage']);self.assertEqual(1,unack['constructors']);self.assertEqual(1,unack['reads'])
        self.assertIsNone(unack['pending']);self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])
    def test_actual_phase_extension_defers_then_own_ack_new_sources_and_real_close_retire(self):
        self.start();self.assert_transition(self.activate())
        self.rig.invoke('feature.snapshots.act',dict(contractVersion=harness.VERSION,runId=harness.RUN,
            fixtureUrl=self.rig.fixture_url,ticket=NEW,verb='share-open',inputs={}))
        self.observe_primary()
        self.send('acknowledged');fresh=self.receive();self.assertEqual('fresh',fresh.get('stage'),fresh)
        self.assertGreater(fresh['last']['original']['sample']['actorSequence'],fresh['transitionSequence'])
        self.assertEqual(NEW,fresh['last']['receipt']['ticket']);self.assertTrue(fresh['last']['receipt']['facts']['shareSheet'])
        self.assertEqual(2,fresh['reads'])
        self.rig.client.activate('d'*32,'cleanup',{})
        self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN))
        self.observe_primary()
        self.send('cleanup');cleaned=self.receive();self.assertEqual('cleanup',cleaned.get('stage'),cleaned)
        self.rig.client.close();self.send('close');self.assertEqual('retired',self.receive()['stage'])
        self.child.wait(timeout=5);self.assertEqual(0,self.child.returncode)
        for _ in range(2):self.assertEqual({'performed':True},self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN)))


    def test_actual_logged_in_capture_to_cleanup_is_admitted_before_account_or_native_sources(self):
        self.start();self.assertTrue(self.rig.model.account['loggedIn'])
        self.assert_transition(self.activate('cleanup'))
        self.assertTrue(self.rig.model.account['loggedIn'])
        self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN))
        self.observe_primary()
        self.assertFalse(self.rig.model.account['loggedIn'])
        self.send('acknowledged');fresh=self.receive();self.assertEqual('fresh',fresh.get('stage'),fresh)
        self.assertEqual(NEW,fresh['last']['receipt']['ticket'])
        self.rig.client.close();self.send('close');self.assertEqual('retired',self.receive()['stage'])
        self.child.wait(timeout=5);self.assertEqual(0,self.child.returncode)
        for _ in range(2):self.assertEqual({'performed':True},self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN)))

    def test_actual_baseline_to_cleanup_activation_defers_without_cleanup_authority(self):
        self.start(baseline=True);self.assert_transition(self.activate('cleanup'))
        self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN))
        self.observe_primary()
        self.send('acknowledged');fresh=self.receive();self.assertEqual('fresh',fresh.get('stage'),fresh)
        self.assertGreater(fresh['last']['original']['sample']['actorSequence'],fresh['transitionSequence'])
        self.assertEqual(NEW,fresh['last']['receipt']['ticket'])
        self.rig.client.close();self.send('close');retired=self.receive();self.assertEqual(dict(stage='retired',phase='retired'),retired)
        self.child.wait(timeout=5);self.assertEqual(0,self.child.returncode)
        for _ in range(2):
            self.assertEqual({'performed':True},self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN)))
        self.assertIsNone(PrivateFeatureState(self.rig.root/'phone-snapshots-actor-lifecycle.json').read())

    def test_actual_phase_prefix_rewrite_remains_fatal(self):
        self.start();self.rig.client.activate(NEW,'share-open',{})
        with self.rig.server.journal.lock:
            self.rig.server.journal.runs[harness.RUN]['phaseActivations'][0]['ticket']='f'*32
        self.send('read');value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])

    def test_actual_phase_instance_replacement_remains_fatal(self):
        self.start();self.rig.client.activate(NEW,'share-open',{})
        self.rig.server.journal.phase_instance='f'*32
        self.send('read');value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])

    def test_actual_two_activation_extension_cannot_skip_an_unacknowledged_phase(self):
        self.start();self.rig.client.activate('f'*32,'share-open',{});self.rig.client.activate(NEW,'share-open',{})
        self.send('read');value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])

    def test_actual_foreign_feature_header_is_preserved_and_never_published(self):
        self.start();self.rig.client.activate(NEW,'share-open',{})
        store=PrivateFeatureState(self.rig.root/'phone-snapshots-feature.json');old=store.read();foreign=deepcopy(old)
        state=unpack(foreign['payload'])[0];state['cleanupStages']['foreign-transition']='f'*32;foreign['payload']=pack([state]);store.write(foreign,old)
        self.send('read');value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertEqual(foreign,store.read());self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])

    def test_actual_changed_original_pid_binding_remains_fatal(self):
        self.start();self.rig.client.activate(NEW,'share-open',{})
        self.rig.model.model_binding['processIdentity']='32:foreign-original-start'
        self.send('read');value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])

    def test_actual_closed_phase_cannot_be_recovered_as_ordinary_transition(self):
        self.start();self.rig.client.close();self.send('read');value=self.receive()
        self.assertTrue(value.get('rejected'),value)
        header=PrivateFeatureState(self.rig.root/'phone-snapshots-actor-lifecycle.json').read()
        state=unpack(header['payload'])[0];self.assertIsNone(state['pending']);self.assertEqual([],state['transitions'])
        self.assertNotIn(harness.RUN,self.rig.server.journal.runs)

    def test_existing_cleanup_authority_cannot_defer_a_new_ordinary_activation(self):
        self.rig.client.activate('d'*32,'cleanup',{})
        self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN))
        self.start(baseline=True);self.rig.client.activate(NEW,'share-open',{});self.send('read')
        value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])

    def journal_probe(self,mode):
        r=self.rig;prefix=harness.ACTOR[:harness.ACTOR.index('started=time.monotonic();flow=None')]
        path=r.root/'journal-actor-config.json'
        PrivateFeatureState(path).write(dict(targetUrl=r.proxy.url,root=str(r.root),fixtureUrl=r.base,actorToken='a'*64),None)
        result=subprocess.run([sys.executable,'-c',prefix+JOURNAL_SCRIPT,json.dumps(sys.path),str(path),mode],
            capture_output=True,text=True,timeout=25,check=False)
        self.assertEqual(0,result.returncode,result.stderr[-4000:]);return json.loads(result.stdout)
    def test_exact_process_bound_v1_migrates_losslessly_and_empty_history_adds_no_target_queries(self):
        self.assertEqual(dict(migrated=True,lossless=True,emptyHistoryTargetQueries=0),self.journal_probe('migration'))
    def test_unknown_v1_journal_fields_remain_red_and_original_is_preserved(self):
        self.assertEqual(dict(rejected=True,preserved=True),self.journal_probe('foreign-shape'))

    def mutate_transition(self,kind):
        ready=self.start();result=self.activate();self.assert_transition(result)
        store=PrivateFeatureState(self.rig.root/'phone-snapshots-actor-lifecycle.json');header=store.read();state=unpack(header['payload'])[0]
        if kind=='scope':state['transitions'][0]['scope']=dict(kind='handoff',handoffId='f'*32)
        elif kind=='frame-missing':
            from overte_phone_snapshots_evidence import SnapshotsOriginals
            binding=header['binding'];host=SnapshotsOriginals(self.rig.root,binding,harness.RUN,'actor',lambda:True,lambda *_:None,kind='snapshots')
            rows=host.manifest(state['transitions'][0]['manifest']);host.path(host.expand(rows[-1])).unlink()
        elif kind in ('role-rollback','both-rollback'):
            role=PrivateFeatureState(self.rig.root/'phone-snapshots-actor-originals.json');role.write(ready['roleHeader'],role.read())
            if kind=='both-rollback':
                store.write(ready['actorHeader'],header)
        else:raise AssertionError('Unknown controlled mutation')
        if kind=='scope':store.write(dict(header,payload=pack([state])),header)
        before=store.read();self.send('mutated-reopen' if kind=='scope' else 'mutated');value=self.receive();self.assertTrue(value.get('rejected'),value)
        self.assertEqual(before,store.read());self.assertFalse(self.rig.client.request('/runs/'+harness.RUN)['entries'])
    def test_transition_scope_must_join_actual_frame_handoff_originals(self):self.mutate_transition('scope')
    def test_missing_actual_transition_original_remains_fatal(self):self.mutate_transition('frame-missing')
    def test_actual_active_role_header_cannot_roll_back_below_transition_original(self):self.mutate_transition('role-rollback')
    def test_retained_flow_cannot_adopt_formal_actor_and_role_header_rollback(self):self.mutate_transition('both-rollback')


if __name__=='__main__':unittest.main()
