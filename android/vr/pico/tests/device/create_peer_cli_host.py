"""Real production main/factory/loop with explicit SDK/Native/phase/time models.

This owned process opens no socket and never starts a device, service or Domain.
All Native replica/renderer producers are reused from the existing host fixture.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import time
import traceback
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'tests/device'),str(Path(__file__).resolve().parent)]
from create_peer_originals_host import model_inputs
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4 import feature_observer,create_peer_actor
from adapters.android import adapter as android_adapter
from adapters.script_journey.lock import ScriptSourceLock


def main():
    path=Path(sys.argv[2]);config=PrivateFeatureState(path).read();directory=path.parent
    original=PrivateFeatureState(Path(config['peerOwner'])).read();binding=deepcopy(original['scope']['binding'])
    binding.update(processIdentity='456:explicit-second-model-client',sessionId='8'*32,targetFingerprint='e'*64)
    world_store=PrivateFeatureState(directory/'replica-model.json')
    def world():
        with ScriptSourceLock(directory/'fixture-replica.lock').held():return world_store.read()
    b,reader,Phases=model_inputs(dict(scope=original['scope'],binding=binding,worldPath=str(world_store.path)),directory)
    calls=[]
    def record(name):
        calls.append(name)
        store=PrivateFeatureState(directory/'factory-calls.json');store.write(dict(calls=calls),store.read())
    class Adapter:
        pico_configuration=(12345,directory)
        def _installation(self,target):
            assert target==config['target'];return {key:binding[key] for key in ('sourceRevision','artifactSha256')}
        def _script_runtime(self,target):
            assert target==config['target'];record('runtime-read')
            return SimpleNamespace(io=SimpleNamespace(capture=lambda:dict(bridgeId=binding['sessionId']))),None,deepcopy(binding)
        def _native_feature_observer(self,target):
            assert target==config['target'];record('native-reader')
            return SimpleNamespace(pid=456,guard=lambda:True,clock_ms=b.epoch,monotonic=b.now,sleep=b.ui.sleep)
        def _create_entity_observer(self,target,run):
            assert target==config['target'] and run==config['runId'];record('entity-reader');return reader('entities')
        def _create_model_resources_observer(self,target,run):
            assert target==config['target'] and run==config['runId'];record('resource-reader');return reader('resources')
        def invoke(self,*_a,**_k):raise AssertionError('No product input in the observer')
    def parsed(arguments):
        assert arguments==['--kind','pico','--native-binding',*config['candidateArguments'],'describe','--target',config['target']]
        record('candidate-describe-only')
        return SimpleNamespace(native_binding=True,kind='pico',action='describe',target=config['target'],operation=None,arguments='{}'),\
            SimpleNamespace(create_adapter=lambda _candidate,_base:Adapter())
    android_adapter.cli=parsed;create_peer_actor.Client=Phases
    original_run=feature_observer.run
    def run(journey,value,**options):
        def wait(seconds):b.ui.sleep(seconds);time.sleep(.01)
        try:return original_run(journey,value,sleep=wait,**options)
        except Exception:traceback.print_exc();raise
    feature_observer.run=run
    control=create_peer_actor.PicoCreatePeerWorker.control
    def controlled(worker):
        value=world();sender=worker.sender
        if sender is not None and sender.previous is not None and sender.previous['phase']=='consumed':
            if value.get('afterEchoExpired',False):
                worker.admission.monotonic=lambda:worker.admission.deadline+1;worker.admission.budget()
            if value.get('afterEchoFailure',False):raise NativeUIError('Explicit model refusal after original consumed echo')
        return control(worker)
    create_peer_actor.PicoCreatePeerWorker.control=controlled
    failed=create_peer_actor.PicoCreatePeerWorker.fail
    def failed_with_marker(worker):
        failed(worker)
        if world().get('closedLookingFailure',False):
            before=worker.store.read();worker.store.write(before|dict(phase='closed'),before)
    create_peer_actor.PicoCreatePeerWorker.fail=failed_with_marker
    return feature_observer.main()


if __name__=='__main__':raise SystemExit(main())
