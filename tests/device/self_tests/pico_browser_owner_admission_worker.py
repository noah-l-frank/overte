"""Real original Parent/child admission; candidate/native effects are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ENTRY = Path(__file__).resolve()
REPOSITORY = ENTRY.parents[3]


def pin(path):
    s = path.lstat()
    return dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        physical=[s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns])


def child():
    root = Path(os.environ['OVT_BROWSER_ADMISSION_ROOT'])
    names = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=REPOSITORY).split(b'\0')
    before = {str((REPOSITORY/os.fsdecode(name)).resolve()):pin(REPOSITORY/os.fsdecode(name))
        for name in names if name.endswith(b'.py') and (REPOSITORY/os.fsdecode(name)).is_file()}
    # Keep every actual task-owned fixture original after registered cleanup.
    original_temporary = tempfile.TemporaryDirectory
    class Retained(original_temporary):
        def cleanup(self): self._finalizer.detach()
    tempfile.TemporaryDirectory = Retained; tempfile.tempdir = str(root)
    from adapters.normal_feature_state import PrivateFeatureState
    from adapters.normal_ui import NativeUIError
    from adapters.pico4.browser_operation_owner import PicoBrowserOperationOwner
    from adapters.pico4.operation_host import process_identity
    from adapters.pico4.tablet_web_binding import archive_retained
    from self_tests.test_pico_tablet_web_flow import PicoTabletWebFlowTests
    fixture = PicoTabletWebFlowTests('runTest'); fixture.setUp()
    owner = None
    try:
        native_reads = []
        state = root/'candidate-state'; state.mkdir(mode=0o700)
        adapter = SimpleNamespace(pico_configuration=('declared-host-model', state),
            _script_journey=lambda:SimpleNamespace(_lock=lambda *_args:fixture.target.lock),
            _native_feature_observer=lambda target:native_reads.append(target))
        access = PrivateFeatureState(root/'adapter-access.json')
        access.write(dict(fixtureAdapterAccessVersion=1, fixtureUrl=fixture.url,
            adapterToken=fixture.adapter_token), None)
        os.environ.update(OVERTE_PICO_NORMAL_SCRIPTS='1', OVERTE_ANDROID_E2E_DEBUG='1',
            OVERTE_PICO_OPENXR_INPUT='1', OVERTE_E2E_SCENE_URL=fixture.target.scene_url,
            OVERTE_PICO_FEATURE_FIXTURE_CONFIG=str(access.path), OVERTE_E2E_FEATURE_FIXTURE_URL=fixture.url)
        now = time.monotonic()
        fault=os.environ.get('OVT_BROWSER_ADMISSION_FAULT','normal')
        request = dict(picoBrowserOperationRequestVersion=2 if fault.startswith('input-') else 1, requestId='a'*32, runId=fixture.run,
            fixtureUrl=fixture.fixture_url, operation='begin',
            wholeBudget=dict(id='b'*32, startedMonotonic=now, deadlineMonotonic=now+120),
            actionBudget=dict(id='c'*32, startedMonotonic=now, deadlineMonotonic=now+60),
            arguments=dict(artifactRoot=str(fixture.artifacts), foreignFixtureUrl=fixture.foreign, nonce='d'*32))
        # Only the reviewed fixture entry override differs from production's
        # fixed canonical module. No DTO can select that entry override.
        owner = PicoBrowserOperationOwner(adapter, 'declared-model', request,
            process_identity(os.getppid()), runner_entry=ENTRY)
        begin = owner.dispatch(request); owner.guard()
        assert owner.origin.guard() and owner.state['phase'] == 'ready'
        assert owner.state['calls'] == [request['requestId']] and owner.state['pending'] is None
        assert archive_retained(adapter, 'declared-model') and not native_reads
        refused_close = False
        try: owner.close_host()
        except NativeUIError: refused_close = True
        assert refused_close and owner.path.exists()
        duplicate = os.environ.get('OVT_BROWSER_ADMISSION_FAULT') == 'duplicate'
        actor_failure = os.environ.get('OVT_BROWSER_ADMISSION_FAULT') == 'actor-parser'
        holder_swap = os.environ.get('OVT_BROWSER_ADMISSION_FAULT') == 'holder-swap'
        input_result=None
        if fault.startswith('input-'):
            from feature_journeys.scenarios import VERSION
            from unittest.mock import patch
            def locked():
                code='''import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR|os.O_NOFOLLOW)
try:
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('held')
 else:print('free')
finally:os.close(fd)
'''
                probe=subprocess.run([sys.executable,'-c',code,str(owner.feature.lock.path)],capture_output=True,timeout=5)
                assert probe.returncode==0 and probe.stderr==b''
                return probe.stdout==b'held\n'
            now=time.monotonic()
            selected=dict(id='3'*32,startedMonotonic=now,deadlineMonotonic=now+60)
            operation='act' if fault=='input-empty-act' else 'prepare'
            fields=(dict(contractVersion=VERSION,runId=fixture.run,fixtureUrl=fixture.fixture_url,
                ticket='4'*32,verb='open',inputs={}) if operation=='act' else None)
            opening=dict(request,requestId='5'*32,operation='input.begin',actionBudget=selected,
                arguments=dict(operation=operation,arguments=fields))
            if fault=='input-cas':
                write=owner._write
                def unknown(value):
                    write(value)
                    if value.get('inputBoundary') is not None:raise OSError('Declared lost original input context CAS')
                with patch.object(owner,'_write',side_effect=unknown):
                    try:owner.dispatch(opening)
                    except OSError:pass
                    else:raise AssertionError('Lost context CAS was accepted')
            else:owner.dispatch(opening)
            held=locked();assert held
            if fault=='input-prepare':
                fixture.activate();assert locked()
                owner.dispatch(dict(request,requestId='6'*32,operation='input.end',actionBudget=selected,arguments=None))
                owner.guard();assert owner.state['inputBoundary'] is None
            elif fault!='input-cas':
                budget=dict(selected,id='7'*32) if fault=='input-budget' else selected
                try:owner.dispatch(dict(request,requestId='6'*32,operation='input.end',actionBudget=budget,arguments=None))
                except NativeUIError:pass
                else:raise AssertionError('Unavailable input scope was completed')
            if fault!='input-prepare':
                assert owner.failed and owner.path.exists();owner.unwind()
                try:owner.guard()
                except NativeUIError:pass
                else:raise AssertionError('Unknown context resumed after host unlock')
            input_result=dict(heldBefore=held,freeAfter=not locked(),unavailable=owner.failed)
            assert input_result['freeAfter'] and not native_reads
        if holder_swap:
            original = owner.store
            foreign = PrivateFeatureState(original.path)
            owner.store = foreign
            try: owner.guard()
            except NativeUIError: pass
            else: raise AssertionError('Foreign holder was accepted')
            owner.store = original
            try: owner.guard()
            except NativeUIError: pass
            else: raise AssertionError('Restoring the holder resumed an unavailable owner')
            assert owner.failed and owner.path.exists() and not native_reads
        if duplicate:
            try: owner.dispatch(request)
            except NativeUIError: pass
            else: raise AssertionError('Duplicate begin was accepted')
            assert owner.failed and owner.path.exists() and not native_reads
        actor_exit = None
        public_attempted = False
        if actor_failure:
            now = time.monotonic()
            actor = dict(request, requestId='e'*32, operation='actor.start',
                actionBudget=dict(id='f'*32, startedMonotonic=now, deadlineMonotonic=now+60),
                arguments=dict(target='declared-model', candidateArguments=['--this-option-is-invalid'],
                    fixtureUrl=fixture.url, actorToken=fixture.actor_token, durationSeconds=120,
                    artifactRoot=str(fixture.artifacts)))
            try: owner.dispatch(actor)
            except (NativeUIError, OSError, ValueError): pass
            assert owner.worker is not None
            actor_exit = owner.worker.wait(timeout=5); assert actor_exit == 2
            owner.collect()
            assert b'OVT_ADAPTER_ARGUMENTS_REJECTED' in owner.diagnostics[1]
            if not owner.failed:
                public_attempted = True
                from feature_journeys.scenarios import VERSION
                call = dict(requestId='1'*32, operation='feature.tablet-web.observe',
                    arguments=dict(contractVersion=VERSION,runId=fixture.run,afterSequence=0),
                    deadlineMonotonic=time.monotonic()+60)
                try:
                    with owner.public_context(call): native_reads.append('escaped-public-admission')
                except (NativeUIError, OSError, ValueError): pass
                else: raise AssertionError('Dead Actor allowed public SDK admission')
            assert owner.failed and owner.path.exists() and not native_reads
            for pipe in owner.worker_pipes: pipe.close()
            for held in owner.worker_pins:
                if not held.owner.closed: assert held.close()
            if owner.worker_owner is not None: assert owner.worker_owner.close()
        result = dict(actualOperationOwner=True, actualParentProgram=True, originalBegin=True,
            nativeReads=len(native_reads), normalInputs=0, markerRetained=owner.path.exists(),
            duplicateRefused=duplicate, completeProductionJourney=False, nativeQualified=False,
            actorParserRefused=actor_failure, actorExitCode=actor_exit,
            actualPublicAdmissionAttempted=public_attempted,
            holderSwapRefused=holder_swap,
            inputBoundary=input_result,
            producerHostProcessIdentity=begin['producerHostProcessIdentity'])
        (root/'admission-result.json').write_text(json.dumps(result))
        assert owner.file.close_host() and owner.origin.close()
        owner = None
        fixture.client.close()
        return result
    finally:
        if owner is not None:
            owner.file.close_host()
            if owner.origin is not None: owner.origin.close()
        fixture.doCleanups()
        loaded = {Path(module.__file__).resolve() for module in list(sys.modules.values())
            if getattr(module, '__file__', None) and Path(module.__file__).resolve().is_relative_to(REPOSITORY)}
        after = {str(path):pin(path) for path in loaded}
        assert all(name in before and before[name] == value for name,value in after.items())
        (root/'child-source-pins.json').write_text(json.dumps(dict(
            currentSHA8=True, before={name:before[name] for name in after}, after=after)))


def main():
    if sys.argv[1:] == ['--child']:
        child(); return
    if sys.argv[1:] != ['--area', 'tablet-web']: raise ValueError('Closed admission worker argv')
    root = Path(os.environ['OVT_BROWSER_ADMISSION_ROOT'])
    result = subprocess.run([sys.executable, str(ENTRY), '--child'], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=20, check=False)
    (root/'child.stdout.bin').write_bytes(result.stdout); (root/'child.stderr.bin').write_bytes(result.stderr)
    if result.returncode != 0: raise RuntimeError('Owned admission child failed; raw diagnostics retained')
    print((root/'admission-result.json').read_text(), flush=True)


if __name__ == '__main__': main()
