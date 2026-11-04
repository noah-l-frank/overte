"""Real Common Parent, production coordinator child and real Actor6 process.

All native/candidate/VR/GPU producers and the primary facade factory are
explicit existing host models. This is coordinator integration, not a complete
canonical candidate/router/CLI or physical headset qualification.
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
import tempfile
import time
from types import MethodType, SimpleNamespace
import uuid

ENTRY = Path(__file__).resolve()
REPOSITORY = ENTRY.parents[3]
ROOT = Path(os.environ['OVT_BROWSER_COORDINATOR_ROOT'])


def pin(path):
    s = path.lstat()
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), physical=[s.st_dev,
        s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns])


def sources():
    names = subprocess.check_output(['git','ls-files','-co','--exclude-standard','-z'],cwd=REPOSITORY).split(b'\0')
    return {str((REPOSITORY/os.fsdecode(name)).resolve()):pin(REPOSITORY/os.fsdecode(name))
        for name in names if name.endswith(b'.py') and (REPOSITORY/os.fsdecode(name)).is_file()}


def finish_sources(before, name):
    loaded = {Path(m.__file__).resolve() for m in list(sys.modules.values())
        if getattr(m,'__file__',None) and Path(m.__file__).resolve().is_relative_to(REPOSITORY)}
    after = {str(path):pin(path) for path in loaded}
    changed = [name for name,value in after.items() if before.get(name)!=value]
    (ROOT/(name+'-sources.json')).write_text(json.dumps(dict(before={n:before.get(n) for n in after},after=after,changed=changed)))
    assert not changed


def retained_temporaries():
    original = tempfile.TemporaryDirectory
    class Retained(original):
        def cleanup(self): self._finalizer.detach()
    tempfile.TemporaryDirectory = Retained
    tempfile.tempdir = str(ROOT)


def emit(value):
    raw=json.dumps(value,separators=(',',':'),allow_nan=False).encode()+b'\n'
    assert len(raw)<=4*1024*1024
    sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()


def child():
    before=sources();retained_temporaries()
    from unittest.mock import patch
    from adapters.normal_feature_state import PrivateFeatureState
    from adapters.pico4.browser_operation_owner import PicoBrowserOperationOwner
    from adapters.pico4.operation_host import process_identity
    from adapters.pico4.tablet_web_binding import PicoTabletWebBinding,archive_sentry_prefix
    from adapters.script_journey.lock import ScriptSourceLock
    from contextlib import contextmanager
    from self_tests import test_pico_tablet_web_flow as flow
    from self_tests import test_pico_tablet_web_stereo_flow as stereo
    from self_tests import test_pico_browser_capture_retirement as capture
    from self_tests.pico_browser_fixture import PicoTarget
    from self_tests.pico_browser_host_clock import BrowserHostClock
    from self_tests.pico_browser_process_fixture import ProductSources
    held=ScriptSourceLock.held
    @contextmanager
    def diagnostic_held(lock):
        import time
        requested=time.monotonic()
        with held(lock):
            acquired=time.monotonic()
            try:yield
            except BaseException:
                import traceback
                with (ROOT/'original-lock-failure.txt').open('a') as stream:
                    stream.write(traceback.format_exc())
                raise
            finally:
                with (ROOT/'actual-source-lock-intervals.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(pid=os.getpid(),requested=requested,acquired=acquired,released=time.monotonic()))+'\n')
    ScriptSourceLock.held=diagnostic_held
    class DirectoryFixture(flow.PicoTabletWebFlowTests):
        def setUp(self):
            # Select before any server, source reader, frame or input exists.
            # Earlier fixed-clock scopes retain their original qualification.
            with patch.object(flow,'Clock',BrowserHostClock):super().setUp()
        def make_target(self):
            state=self.path/archive_sentry_prefix('target').removesuffix('-archive-owner-')
            state.mkdir(mode=0o700)
            return PicoTarget(self.clock,self.client,self.foreign,state,
                source_lock=ScriptSourceLock(self.path/'script-sources.lock'))
    class Stereo(stereo.PicoTabletWebStereoFlowTests): fixture_type=DirectoryFixture
    h=Stereo('runTest');h.setUp();f,model=h.fixture,h.model
    batch=capture.PicoBrowserCaptureRetirementTests('runTest')
    batch.f,batch.model=f,model
    batch.batches=[];batch.raw='';batch.batch_sequence=0;batch.mutate=None;batch.lose=False
    f.target._tablet_web_retired_captures_observer=batch.reader
    f.target.check_flow=MethodType(PicoTabletWebBinding.check_flow,f.target)
    f.target._lock=lambda target,source_lock=None:f.target.lock
    f.target._tablet_web_actor_return=MethodType(PicoTabletWebBinding._tablet_web_actor_return,f.target)
    service=ProductSources(f,model,independent_clock=True)
    (ROOT/'native-model.json').write_text(json.dumps(service.configuration()))
    startup=ROOT/'startup';startup.mkdir(mode=0o700)
    (startup/'sitecustomize.py').write_text(
        'from self_tests.pico_browser_coordinator_model_bootstrap import install\ninstall()\n')
    os.environ.update(OVT_BROWSER_COORDINATOR_MODEL_ROOT=str(ROOT),
        PYTHONPATH=str(startup)+os.pathsep+str(REPOSITORY/'tests/device'),
        OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',
        OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL=f.target.scene_url,
        OVERTE_E2E_FEATURE_FIXTURE_URL=f.url)
    access=PrivateFeatureState(ROOT/'adapter-access.json')
    access.write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=f.url,adapterToken=f.adapter_token),None)
    os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']=str(access.path)
    adapter=SimpleNamespace(pico_configuration=('declared-host-model',f.path),
        _script_journey=lambda:SimpleNamespace(_lock=lambda *_args:f.target.lock),
        _native_feature_observer=lambda target:model._native_feature_observer(target,read_only=True))
    whole=json.loads((ROOT/'whole.json').read_text());nonce=uuid.uuid4().hex;current_budget=None
    def request(operation,arguments=None):
        now=time.monotonic()
        return dict(picoBrowserOperationRequestVersion=2,requestId=uuid.uuid4().hex,
            runId=f.run,fixtureUrl=f.fixture_url,operation=operation,wholeBudget=whole,
            actionBudget=(dict(id=uuid.uuid4().hex,startedMonotonic=now,
                deadlineMonotonic=min(now+60,whole['deadlineMonotonic'])) if current_budget is None else current_budget),arguments=arguments)
    initial=request('begin',dict(artifactRoot=str(f.artifacts),foreignFixtureUrl=f.foreign,nonce=nonce))
    owner=None;error=None
    try:
        # Only this existing model facade factory is substituted. All owner,
        # feature, consumption, Actor6 and return/retirement objects are real.
        with patch.object(PicoTabletWebBinding,'feature',return_value=f.primary):
            owner=PicoBrowserOperationOwner(adapter,'target',initial,process_identity(os.getppid()),runner_entry=ENTRY)
        begin=owner.dispatch(initial)
        emit(dict(ready=True,run=f.run,url=f.fixture_url,fixtureBase=f.url,reader=f.reader,
            artifacts=str(f.artifacts),nonce=nonce,begin=begin))
        while True:
            raw=sys.stdin.buffer.readline(4*1024*1024+1)
            if not raw:break
            assert len(raw)<=4*1024*1024
            command=json.loads(raw);assert set(command)=={'operation','arguments','actionBudget'}
            operation,arguments=command['operation'],command['arguments']
            if operation=='stop':emit(dict(stopped=True));break
            current_budget=command['actionBudget'];owner.control()
            if operation=='prepare':owner.guard();result=True
            elif operation=='actor.start':
                result=owner.dispatch(request(operation,dict(target='target',candidateArguments=['--declared-host-model'],
                    fixtureUrl=f.url,actorToken=f.actor_token,durationSeconds=120,artifactRoot=str(f.artifacts))))
            elif operation.startswith('feature.tablet-web.'):
                call=dict(requestId=uuid.uuid4().hex,operation=operation,arguments=arguments,
                    deadlineMonotonic=min(time.monotonic()+60,whole['deadlineMonotonic'],
                        whole['deadlineMonotonic'] if current_budget is None else current_budget['deadlineMonotonic']))
                with owner.public_context(call):result=owner.invoke(operation,arguments)
            elif operation in ('consume','actor.return','finalize','input.begin','input.end'):result=owner.dispatch(request(operation,arguments))
            elif operation=='close':owner.close_host();result=True
            elif operation=='epoch':result=f.clock.epoch()
            elif operation=='host':result=f.clock.now()
            elif operation=='sleep':f.clock.sleep(arguments);result=None
            else:raise ValueError('Unknown coordinator model operation')
            emit(dict(result=result))
    except BaseException as failure:
        error=type(failure).__name__
        import traceback
        (ROOT/'child-failure.txt').write_text(traceback.format_exc())
        emit(dict(error=error,where=None if owner is None else owner.state['pending']))
    finally:
        if owner is not None:
            owner.unwind()
            if owner.worker is not None:
                if owner.worker.poll() is None:
                    # Test shutdown only: the original known owned process is
                    # terminated without claiming product/feature retirement.
                    owner.worker_owner.guard();owner.worker.terminate()
                owner.worker.wait(timeout=10);owner.collect()
                for pipe in owner.worker_pipes:pipe.close()
                for held in owner.worker_pins:
                    if not held.owner.closed:held.close()
                if owner.worker_owner is not None:owner.worker_owner.close()
            if owner.origin is not None:owner.origin.close()
            owner.file.close_host()
            (ROOT/'owner-outcome.json').write_text(json.dumps(dict(error=error,phase=owner.state['phase'],
                pending=owner.state['pending'],calls=len(owner.state['calls']),actorExit=None if owner.worker is None else owner.worker.returncode,
                commonComplete=owner.common.complete,commonFailed=owner.common.failed)))
        service.close();h.doCleanups();finish_sources(before,'child')


def parent():
    before=sources();retained_temporaries()
    from adapters.pico4.browser_common_export import JourneyConsumptionExport
    from feature_journeys.engine import Journey
    from feature_journeys.evidence import read_private_artifact
    from feature_journeys.stereo_browser_evidence import PROFILE
    from feature_journeys.witness import Client
    from self_tests.test_stereo_navigation_evidence import POLICY
    now=time.monotonic();whole=dict(id=uuid.uuid4().hex,startedMonotonic=now,deadlineMonotonic=now+120)
    (ROOT/'whole.json').write_text(json.dumps(whole))
    p=subprocess.Popen([sys.executable,str(ENTRY),'--child'],stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    journal=(ROOT/'model-transport.jsonl').open('ab',buffering=0);selected_budget=None
    def receive():
        assert select.select([p.stdout],[],[],min(65,max(.001,whole['deadlineMonotonic']-time.monotonic()+5)))[0]
        raw=p.stdout.readline(4*1024*1024+1);journal.write(raw)
        assert raw and len(raw)<=4*1024*1024,'Coordinator child ended'
        result=json.loads(raw)
        if 'error' in result:raise RuntimeError('Coordinator failure: '+str(result))
        return result
    def call(operation,arguments=None):
        raw=json.dumps(dict(operation=operation,arguments=arguments,actionBudget=selected_budget),separators=(',',':')).encode()+b'\n'
        journal.write(raw);p.stdin.write(raw);p.stdin.flush()
        return receive()['result']
    from contextlib import contextmanager
    @contextmanager
    def input_context(operation,arguments):
        nonlocal selected_budget
        assert selected_budget is None
        now=time.monotonic();selected_budget=dict(id=uuid.uuid4().hex,startedMonotonic=now,
            deadlineMonotonic=min(now+60,whole['deadlineMonotonic']))
        try:
            call('input.begin',dict(operation=operation,arguments=arguments));yield
            call('input.end')
        finally:selected_budget=None
    export=None;client=None;fixture_close_started=False
    try:
        ready=receive();assert ready['ready']
        client=Client(ready['fixtureBase'],ready['reader']);client.run=ready['run'];client.area='tablet-web'
        call('prepare');call('actor.start')
        artifacts=Path(ready['artifacts'])
        def bound():assert time.monotonic()<whole['deadlineMonotonic'] and p.poll() is None
        export=JourneyConsumptionExport(artifacts,'tablet-web',ready['run'],ready['url'],ready['nonce'],
            lambda fields:call('consume',fields),bound)
        policy=deepcopy(POLICY);policy['profile']=PROFILE;reports=[]
        journey=Journey('tablet-web',ready['run'],ready['url'],invoke=call,witness=client.observe,
            activate=client.activate,read_artifact=lambda name:read_private_artifact(artifacts,name),
            image_policy=dict(screen=policy),continuity=lambda *_args:None,
            monotonic=lambda:call('host'),epoch_ms=lambda:call('epoch'),sleep=lambda seconds:call('sleep',seconds),
            report=reports.append,after_cleanup_baseline=export.callback,input_context=input_context,
            poll_work_inclusive=True)
        export.attach(journey);journey.execute()
        assert export.complete and reports[-1]['sequenceCompleted'] and len(journey.phases)==28
        fixture_close_started=True;client.close();client=None
        call('actor.return');final=call('finalize');assert final['sequenceCompleted'] and final['hostReleased']
        assert export.close_host();call('close')
        p.stdin.write(b'{"operation":"stop","arguments":{},"actionBudget":null}\n');p.stdin.flush();assert receive()['stopped']
        (ROOT/'coordinator-result.json').write_text(json.dumps(dict(sequenceCompleted=True,
            actualCoordinator=True,actualActorSix=True,canonicalCandidateRouter=False,deviceAcceptance=False,
            phases=len(journey.phases),elapsed=time.monotonic()-now)))
    finally:
        try:
            if client is not None and not fixture_close_started:
                try:fixture_close_started=True;client.close()
                except (OSError,ValueError):pass
        finally:
            if not p.stdin.closed:p.stdin.close()
            p.wait(timeout=15)
            (ROOT/'child.stderr.bin').write_bytes(p.stderr.read());p.stdout.close();p.stderr.close()
            journal.close()
            if export is not None:export.close_host()
            finish_sources(before,'parent')


if __name__=='__main__':
    if sys.argv[1:]==['--child']:child()
    elif sys.argv[1:]==['--area','tablet-web']:parent()
    else:raise ValueError('Closed coordinator worker argv')
