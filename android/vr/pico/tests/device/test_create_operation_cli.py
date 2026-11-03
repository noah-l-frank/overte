"""Continuous normal Parent through the existing real stdio CLI/child boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
from adapter_operation_host import PicoOperationHost
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock,ScriptSourceBusy
from feature_journeys.witness import Client,Journal
from test_create_journey import RUN,URL,VERSION


class PhaseAuthority(Client):
    def __init__(self,path):
        super().__init__(URL.split('/runs/')[0],'private-runner-only-'+'d'*32);self.path=path;self.epoch=20000;self.journal=Journal(lambda:self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('create')
        self.run=RUN;self.area='create';self.closed=False;self.previous=None
    def request(self,path,value=None,method=None,**options):
        assert path=='/runs/'+RUN+'/active' and method is None and not options
        self.journal.activate(RUN,value['ticket'],value['verb'],value['inputs'])
        phase=self.journal.phase(RUN,uuid.uuid4().hex);publication={key:phase[key] for key in ('instance','createdEpochMs','activations')}
        self.path.write(publication,self.previous);self.previous=publication;return {'activated':True}


class CreateOperationCliTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='pico-create-operation-cli-');temporary._finalizer.detach();temporary.cleanup=lambda:None
        self.area=Path(temporary.name);self.area.chmod(0o700);self.host=None;self.addCleanup(self.finish)
        self.authority=PhaseAuthority(PrivateFeatureState(self.area/'phase-publication.json'));self.authority.activate(uuid.uuid4().hex)
        self.manifest=self.area/'adapter.json';self.manifest.write_text(json.dumps(dict(schemaVersion=1,command=['declared-test-only'])));self.manifest.chmod(0o600)
        self.artifacts=self.area/'transport';self.artifacts.mkdir(mode=0o700)
        environment=patch.dict(os.environ,{'OVERTE_PICO_NORMAL_CREATE':'1','OVERTE_PICO_NORMAL_SCRIPTS':'1','OVERTE_ANDROID_E2E_DEBUG':'1',
            'OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'http://controlled.test/scene.json'})
        environment.start();self.addCleanup(environment.stop)
        entry=Path(__file__).with_name('create_operation_cli_host.py');self.prefix=[sys.executable,str(entry),'--model-root',str(self.area)]
        command=patch('adapter_operation_host.pico_command',return_value=self.prefix);command.start();self.addCleanup(command.stop)
        self.host=PicoOperationHost(self.manifest,'host-create-candidate',self.artifacts)
    def finish(self):
        host=self.host
        if host is None or host.process is None:return
        if host.process.returncode is None:
            host.abort()
            if host.process.returncode is None:
                os.kill(host.process.pid,signal.SIGKILL);_,status=os.waitpid(host.process.pid,0);host.process.returncode=os.waitstatus_to_exitcode(status)
    def component(self,operation,arguments=None):return self.host.create_component(RUN,URL,operation,arguments)
    def act(self,verb,inputs=None):
        sample=self.component('sample');self.authority.epoch=sample['sampleAnchor']['nativeEpochMs']
        fields=dict(contractVersion=VERSION,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=URL,verb=verb,inputs={} if inputs is None else inputs)
        with self.host.create_input_context(RUN,URL,'act',fields):
            self.authority.activate(fields['ticket'],verb,fields['inputs']);return self.component('act',fields)
    def test_one_existing_cli_parent_normal_model_real_child_and_final_continuation(self):
        self.component('prepare');self.act('open');self.act('model-create',dict(resource='gltf-bundle/main.gltf'))
        metadata=PrivateFeatureState(self.area/'model-host.json').read();self.assertEqual(1,metadata['factoryCalls'])
        peer=self.area/'peer';peer.mkdir(mode=0o700)
        result=self.component('peer.start',dict(target='synthetic-second-pico',candidateArguments=['--apk','owned.apk'],fixtureUrl=URL.split('/runs/')[0],
            actorToken='explicit-model-actor-'+'b'*32,durationSeconds=30,artifactRoot=str(peer)))
        self.assertTrue(result['hostProcessIdentity'].startswith(str(int(result['hostProcessIdentity'].split(':')[0]))+':'))
        self.act('delete-owned');sample=self.component('sample');self.authority.epoch=sample['sampleAnchor']['nativeEpochMs']
        with self.host.create_input_context(RUN,URL,'cleanup',None):
            self.authority.activate(uuid.uuid4().hex,'cleanup',{});pending=self.component('cleanup');self.assertTrue(pending['peerReturnPending'])
        self.component('peer.accept');self.assertEqual({'performed':True},self.component('cleanup'))
        self.host.close();self.assertEqual(0,self.host.wait_status);self.assertFalse(Path('/proc',str(self.host.process.pid)).exists())
        self.assertEqual(1,PrivateFeatureState(self.area/'model-host.json').read()['factoryCalls'])

    def test_actual_budget_expiry_unwinds_original_lock_without_green_end_or_normal_input(self):
        self.component('prepare');sample=self.component('sample');self.authority.epoch=sample['sampleAnchor']['nativeEpochMs']
        fields=dict(contractVersion=VERSION,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=URL,verb='open',inputs={})
        started=time.monotonic();short=dict(id=uuid.uuid4().hex,startedMonotonic=started,deadlineMonotonic=started+.3)
        self.host.create_component(RUN,URL,'input.begin',dict(operation='act',arguments=fields),budget=short)
        metadata=PrivateFeatureState(self.area/'model-host.json').read();root=Path(metadata['stateRoot'])
        lock=next(root.glob('normal-create-sources-*.lock'));inode=lock.stat().st_ino
        with self.assertRaises(ScriptSourceBusy):
            with ScriptSourceLock(lock,timeout=.05).held():pass
        time.sleep(.4)
        with self.assertRaises(RuntimeError):self.host.create_component(RUN,URL,'input.end',None,budget=short)
        with ScriptSourceLock(lock,timeout=.5).held():self.assertEqual(inode,lock.stat().st_ino)
        original=PrivateFeatureState(next(root.glob('create-feature-owner-*.json'))).read()
        self.assertEqual(0,original['inputCount']);self.assertEqual([],original['calls'])

    def test_consumed_normal_act_with_lost_host_return_is_never_replayed(self):
        self.prefix.extend(['--model-fault','lost-act']);self.component('prepare');self.act('open')
        with self.assertRaises(RuntimeError):self.act('model-create',dict(resource='gltf-bundle/main.gltf'))
        metadata=PrivateFeatureState(self.area/'model-host.json').read();root=Path(metadata['stateRoot']);parent=PrivateFeatureState(next(root.glob('create-feature-owner-*.json'))).read()
        self.assertEqual(1,sum(row['verb']=='model-create' for row in parent['calls']));inputs=parent['inputCount']
        with self.assertRaises(RuntimeError):self.component('reconcile')
        self.assertEqual(inputs,PrivateFeatureState(next(root.glob('create-feature-owner-*.json'))).read()['inputCount'])
        self.assertEqual(1,metadata['factoryCalls'])

    def test_lost_end_return_does_not_renew_scope_or_claim_product_retirement(self):
        self.prefix.extend(['--model-fault','lost-end']);self.component('prepare')
        with self.assertRaises(RuntimeError):self.act('open')
        metadata=PrivateFeatureState(self.area/'model-host.json').read();root=Path(metadata['stateRoot']);lock=next(root.glob('normal-create-sources-*.lock'))
        with ScriptSourceLock(lock,timeout=.5).held():pass
        self.assertTrue(list(root.glob('create-feature-owner-*.json')))
        with self.assertRaises(RuntimeError):self.component('sample')
        self.assertEqual(1,metadata['factoryCalls'])


if __name__=='__main__':unittest.main()
