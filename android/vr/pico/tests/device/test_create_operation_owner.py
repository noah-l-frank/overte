"""Original warm Parent and direct real worker; existing Native/SDK producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import time
import types
import unittest
import uuid
sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
import test_create_journey as original
from test_create_peer_source import native_primary
from adapters.pico4.create_journey import PicoCreateJourney
from adapters.pico4.create_operation_owner import PicoCreateOperationOwner,CreateActionBudget,CreatePeerReturnPending
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_peer_source import FAMILY
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.lock import ScriptSourceLock


def budget():
    started=time.monotonic();return dict(id=uuid.uuid4().hex,startedMonotonic=started,deadlineMonotonic=started+60)


class CreateOperationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original.CreateJourneyTests();fixture=self.fixture;self.owner=None;self.addCleanup(fixture.doCleanups)
        fixture._before_prepare=lambda:native_primary(fixture)
        def make():
            def factory(adapter,target,run):return PicoCreateJourney(adapter,target,run,fixture.source())
            fixture.adapter._create_journey=types.MethodType(factory,fixture.adapter)
            initial=budget();self.owner=PicoCreateOperationOwner(fixture.adapter,fixture.adapter.target,original.RUN,original.URL)
            parent=self.owner.admit(CreateActionBudget(initial))
            fixture.root=fixture.b.root=parent
            actual=parent.invoke
            def prepare(operation,values=None):
                if operation=='prepare':return self.owner.component(operation,values,initial)
                return actual(operation,values)
            parent.invoke=prepare;return parent
        fixture.make=make;fixture.setUp();self.owner.parent.invoke=types.MethodType(PicoCreateJourney.invoke,self.owner.parent)
        self.worker_directory=fixture.path/'operation-peer';self.worker_directory.mkdir(mode=0o700)
        self.world=PrivateFeatureState(self.worker_directory/'replica-model.json');self.previous=None
        self.addCleanup(self.finish)
    def finish(self):
        owner=self.owner
        if owner is not None and owner.worker is not None and owner.worker.returncode is None:
            # Failed ownership is retained. The unchanged worker's original
            # thirty-second bound ends it; teardown sends no product input.
            owner.worker.wait(timeout=35)
        if owner is not None and owner.worker is not None:
            for name,stream in (('stdout',owner.worker.stdout),('stderr',owner.worker.stderr)):
                if stream is not None and not stream.closed:
                    raw=stream.read()
                    if raw:(self.fixture.path/('peer-original-'+name+'.bin')).write_bytes(raw)
    def update(self):
        b=self.fixture.b
        value=dict(clock=b.now(),rows=deepcopy(b.rows),births=deepcopy(b.domain_births),phase=self.fixture.journal.phase(original.RUN,uuid.uuid4().hex))
        with ScriptSourceLock(self.worker_directory/'fixture-replica.lock').held():self.world.write(value,self.previous);self.previous=deepcopy(value)
    def act(self,verb,inputs=None):
        fields=dict(contractVersion=original.VERSION,runId=original.RUN,ticket=uuid.uuid4().hex,fixtureUrl=original.URL,verb=verb,inputs={} if inputs is None else inputs)
        measured=budget();self.owner.begin(dict(operation='act',arguments=fields,budget=measured))
        self.fixture.journal.activate(original.RUN,fields['ticket'],verb,fields['inputs'])
        try:
            value=self.owner.component('act',fields,measured)
            if self.owner.worker is not None:self.update()
            return value
        finally:self.owner.end(measured)
    def test_continuous_original_prepare_open_model_delete_cleanup_and_direct_child_acceptance(self):
        owner=self.owner;parent=owner.parent;readers=parent.readers
        self.act('open');self.act('model-create',dict(resource='gltf-bundle/main.gltf'))
        self.update();entry=Path(__file__).with_name('create_operation_peer_host.py')
        spec=dict(target='synthetic-second-pico',candidateArguments=['--apk','owned.apk'],fixtureUrl=original.URL.split('/runs/')[0],
            actorToken='explicit-model-actor-'+'b'*32,durationSeconds=30,artifactRoot=str(self.worker_directory))
        spawned=owner.start_peer(spec,budget(),entry=entry)
        self.assertNotEqual(os.getpid(),owner.worker.pid);self.assertEqual(owner.host,owner.peer_scope['parentHostProcessIdentity'])
        self.assertEqual(1,owner.factory_calls);self.assertIs(parent,owner.parent);self.assertIs(readers,parent.readers)
        self.act('delete-owned');measured=budget();owner.begin(dict(operation='cleanup',arguments=None,budget=measured))
        self.fixture.journal.activate(original.RUN,uuid.uuid4().hex,'cleanup',{})
        result=owner.component('cleanup',None,measured);self.assertTrue(result['peerReturnPending']);self.update();owner.end(measured)
        inputs=len(self.fixture.b.inputs);receipt=owner.accept_peer(budget());self.assertEqual(FAMILY,receipt['family'])
        self.assertEqual(0,owner.worker.returncode);self.assertFalse(Path('/proc',str(owner.worker.pid)).exists())
        self.assertEqual({'performed':True},owner.component('cleanup',None,budget()))
        self.assertEqual(inputs,len(self.fixture.b.inputs));self.assertIsNone(parent.store.read());self.assertEqual('retired',owner.state['phase'])
        self.assertEqual(1,owner.factory_calls);self.assertIs(parent,owner.parent)

    def test_original_worker_guard_failure_is_not_classified_as_peer_pending_or_replayed(self):
        owner=self.owner;self.act('open');self.act('model-create',dict(resource='gltf-bundle/main.gltf'));self.update()
        spec=dict(target='synthetic-second-pico',candidateArguments=['--apk','owned.apk'],fixtureUrl=original.URL.split('/runs/')[0],
            actorToken='explicit-model-actor-'+'b'*32,durationSeconds=30,artifactRoot=str(self.worker_directory))
        owner.start_peer(spec,budget(),entry=Path(__file__).with_name('create_operation_peer_host.py'))
        original_config=owner.peer_config.read();owner.peer_config.write(original_config,original_config)
        inputs=len(self.fixture.b.inputs)
        with self.assertRaises(NativeUIError) as refused:owner.begin(dict(operation='cleanup',arguments=None,budget=budget()))
        self.assertNotIsInstance(refused.exception,CreatePeerReturnPending);self.assertTrue(owner.failed)
        self.assertEqual(inputs,len(self.fixture.b.inputs));self.assertEqual('issued',owner.parent.peer_state()['phase'])
        with self.assertRaises(NativeUIError):owner.begin(dict(operation='cleanup',arguments=None,budget=budget()))
        self.assertEqual(inputs,len(self.fixture.b.inputs))


if __name__=='__main__':unittest.main()
