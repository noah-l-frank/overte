"""Canonical physical iOS adapter guarded by actual original installed app bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import stat

from contracts import validate_operation_arguments
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.adapter import IOSNativeMixin
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.installed_code import InstalledCodeBinding, need, source


class ArtifactLease:
    """Bounded original kernel metadata around full candidate preflight.

    No digest is derived from metadata. The original verifier hashes the files;
    unchanged original kernel records allow cheap guards during native input.
    Complete provenance/inputs are revalidated before returning each operation.
    """
    def __init__(self, root):
        self.root = Path(root)
        need(self.root.is_absolute() and self.root.resolve(strict=True) == self.root)
        self.rows = self.snapshot()

    def snapshot(self):
        rows = {}
        def visit(path, depth):
            need(depth <= 64 and len(rows) < 50000)
            before = path.lstat()
            need(stat.S_ISDIR(before.st_mode) or stat.S_ISREG(before.st_mode) and before.st_nlink == 1)
            key = str(path.relative_to(self.root))
            record = lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
            rows[key] = record(before)
            if stat.S_ISDIR(before.st_mode):
                with os.scandir(path) as children:
                    names = sorted(item.name for item in children)
                for name in names:visit(path / name, depth + 1)
            need(record(path.lstat()) == rows[key])
        visit(self.root, 0)
        return rows

    def guard(self):
        need(self.snapshot() == self.rows)


def create_physical_adapter(args, base_class, preflight, *, cleanup_only=False):
    lease = candidate = None
    if not cleanup_only:
        lease = ArtifactLease(args.artifact_root)
        candidate = preflight(args)
        lease.guard()
        need(candidate.get('physicalHandoffVersion') == 1)

    if cleanup_only and getattr(args,'physical_candidate_metadata',None) and getattr(args,'artifact_root',None):
        try:
            lease=ArtifactLease(args.artifact_root);candidate=preflight(args);lease.guard()
            need(candidate.get('physicalHandoffVersion')==1)
        except (OSError,RuntimeError,ValueError,TypeError,KeyError):
            lease=candidate=None

    class IOSInstalledAdapter(IOSNativeMixin, base_class):
        def __init__(self):
            self._operation = None
            self._session_recreation_forbidden = False
            self._preparing = self._retiring = self._recovering = None
            super().__init__()

        @classmethod
        def advertised_capabilities(cls, target):
            # One selected candidate cannot authorize a signed upgrade pair.
            from ios.adapters.feature_configuration import capabilities
            features=capabilities(target) if candidate is not None else []
            return sorted((set(super().advertised_capabilities(target)) | set(features)) - {'app.install','app.upgrade'})

        def _candidate_guard(self, *, complete=False):
            if candidate is None or lease is None:
                raise ValueError('OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE')
            lease.guard()
            if complete:
                need(preflight(args) == candidate)
                lease.guard()

        def _native_source_scope(self,*args,**kwargs):
            self._candidate_guard()
            return super()._native_source_scope(*args,**kwargs)

        def _scripts(self, selector):
            self._candidate_guard()
            return super()._scripts(selector)

        def _script_runtime(self, selector):
            self._candidate_guard()
            return super()._script_runtime(selector)

        def _script_missing_manager(self, selector):
            self._candidate_guard()
            return super()._script_missing_manager(selector)

        def _script_manager_status(self, selector):
            self._candidate_guard()
            return super()._script_manager_status(selector)

        def _bound_script_files(self, *args, **kwargs):
            self._candidate_guard()
            return super()._bound_script_files(*args, **kwargs)

        def _script_restart_handoff(self, *args, **kwargs):
            self._candidate_guard()
            return super()._script_restart_handoff(*args, **kwargs)

        def _script_restart_prepare(self, *args, **kwargs):
            self._candidate_guard()
            return super()._script_restart_prepare(*args, **kwargs)

        def _script_restart_adopt(self, *args, **kwargs):
            self._candidate_guard()
            return super()._script_restart_adopt(*args, **kwargs)

        def _script_restart_inputs(self, *args, **kwargs):
            self._candidate_guard()
            return super()._script_restart_inputs(*args, **kwargs)

        def _script_restart_source(self, selector):
            self._candidate_guard()
            owned = self._binding_store(selector).read()
            if owned is not None and owned.get('phase') == 'preparing':
                self._recover_script_restart_launch(selector)
            return super()._script_restart_source(selector)

        def _recover_script_restart_launch(self, selector, *, inputs=None):
            # Only the explicit restart coordinator may enter this read-only
            # recovery path. Ordinary ensure_session/describe/launch still fail
            # on abandoned launch intent, without delivering another SDK input.
            self._candidate_guard(complete=True)
            need(self._recovering is None)
            inputs = self._script_restart_inputs(selector) if inputs is None else inputs
            from adapters.restart_inputs import RestartInputs
            need(isinstance(inputs, RestartInputs))
            client, state, target = self._script_restart_session(selector, inputs=inputs)
            session = state['sessionId']
            gate = self._binding(selector, client, session, state, target)
            actual = gate.original_process()
            need(actual is not None)
            pid = actual['pid']
            def process():
                return gate.preparing_continuity(pid)
            observer = FeatureObservation(client, session, target, process)
            def ready(measured, native_after):
                need(measured == actual and state.get('processIdentity') in
                     (None, str(inputs.read()['oldNative']['pid']), str(pid)))
                state['processIdentity'] = str(pid)
                # Compare original device probe time to an original native
                # fence; neither AFC metadata nor host UTC supplies freshness.
                self.wait_first_ios_probe(selector, client, session, state, target, str(pid), native_after)
                state.update(iosE2ELaunchCompleted=True,
                    iosE2ESceneUrl=target['testBuild']['fixtureOrigin'] + target['testBuild']['scenePath'])
                self.save_session(selector, state)
            self._recovering = (selector, session, pid)
            try:
                gate.recover_prepared(inputs, observer.native_observer(),
                    observer.process_presence(), ready)
                self._candidate_guard(complete=True)
            finally:
                self._recovering = None

        def _script_restart(self, *args, **kwargs):
            self._candidate_guard()
            return super()._script_restart(*args, **kwargs)

        def _script_restart_stopped(self, selector):
            self._candidate_guard()
            client, state, target = self._script_restart_session(selector)
            gate = self._binding(selector, client, state['sessionId'], state, target)
            record = gate.record()
            if record is not None and record['phase'] == 'retiring':
                # Recover host retirement after a lost terminateApp receipt;
                # never deliver terminateApp again or bypass original source.
                gate.finish_retirement()
            gate.retired_absence()
            self.reset_launch_state(selector, state)
            return {'running': False, 'identity': None}

        def _private_login_input(self, *args, **kwargs):
            self._candidate_guard()
            return super()._private_login_input(*args, **kwargs)

        def _login_controls(self, *args, **kwargs):
            self._candidate_guard()
            return super()._login_controls(*args, **kwargs)

        def _target(self, selector):
            self._candidate_guard()
            target = self.target(selector)
            need(target.get('platform') == 'ios' and target.get('physical') is True
                 and target.get('artifactMode') == 'personal-team-preinstalled'
                 and target.get('_artifactMode') == 'personal-team-preinstalled'
                 and target.get('appId') == candidate['bundleIdentity']['bundleId']
                 and target.get('testBuild') and target.get('probe') == {'kind':'ios-documents'})
            return target

        def _scope(self, selector, session, state, target):
            self._candidate_guard()
            actual = self.read_session(selector)
            fingerprint = hashlib.sha256(json.dumps(target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            need(actual is not None and state.get('sessionId') == session == actual.get('sessionId')
                 and state.get('generation') == actual.get('generation')
                 and state.get('targetFingerprint') == fingerprint == actual.get('targetFingerprint')
                 and hashlib.sha256(json.dumps(self.target(selector),sort_keys=True,separators=(',',':')).encode()).hexdigest() == fingerprint)
            return dict(sourceRevision=candidate['artifactIdentity']['sourceRevision'],
                        artifactSha256=candidate['artifactIdentity']['artifactSha256'],sessionId=session,
                        generation=state['generation'],targetFingerprint=fingerprint)

        def _binding_store(self, selector):
            return PrivateFeatureState(self.state_path(selector).with_name('installed-code-binding.json'))

        def _binding(self, selector, client, session, state, target):
            scope = self._scope(selector, session, state, target)
            def process():
                need(self._scope(selector, session, state, target) == scope)
                return IOSNativeMixin.native_process(client, session, target)
            def source():
                need(self._scope(selector, session, state, target) == scope)
                return client.execute(session,'mobile: overteProcessSourceInfo',{'bundleId':target['appId']})
            observer = FeatureObservation(client,session,target,process)
            return InstalledCodeBinding(self._binding_store(selector),scope,candidate['bundleIdentity'],
                                        process,source,lambda:observer.installed_bundle().read())

        def ensure_session(self, selector):
            target = self._target(selector)
            owned = self._binding_store(selector).read()
            if owned is not None:
                persisted = self.read_session(selector)
                need(persisted is not None)
                need(owned.get('scope') == self._scope(selector,persisted['sessionId'],persisted,target))
                if owned.get('phase') in ('preparing','retiring'):
                    need(self._retiring == (selector,persisted['sessionId']))
            existing_only = self._session_recreation_forbidden
            self._session_recreation_forbidden = existing_only or owned is not None
            try:
                client, session, state = super().ensure_session(selector)
            finally:
                self._session_recreation_forbidden = existing_only
            gate = self._binding(selector,client,session,state,target)
            record = gate.record()
            if self._retiring == (selector,session):
                need(record is not None and record['phase'] == 'retiring')
                gate.retirement_continuity()
            elif record is None or record['phase'] == 'retired':
                if record is not None and self._operation == 'app.process':
                    gate.retired_absence()
                    return client,session,state
                need(self._operation in ('describe','app.launch'))
                provenance = source(gate.process_source())
                gate.begin()
                self._preparing = (selector,session)
                try:
                    self.launch_ios_test_build(selector,client,session,state,target)
                    need(source(gate.process_source()) == provenance)
                    gate.bind()
                finally:self._preparing = None
            elif record['phase'] == 'bound':
                if self._operation in ('app.foreground','app.launch'):gate.continuity(allow_background=True)
                else:gate.verify()
            else:
                raise ValueError('OVT_IOS_INSTALLED_CODE_BINDING_REJECTED')
            return client,session,state

        def assert_ios_process_identity(self, selector, client, session, state, target):
            gate = self._binding(selector,client,session,state,target)
            if self._recovering is not None and self._recovering[:2] == (selector, session):
                actual = gate.preparing_continuity(self._recovering[2])
                need(state.get('processIdentity') in (None, str(actual['pid'])))
                return str(actual['pid'])
            if self._preparing == (selector,session):
                need(gate.record()['phase'] == 'preparing')
                return super().assert_ios_process_identity(selector,client,session,state,target)
            actual = gate.retirement_continuity() if self._retiring == (selector,session) else gate.continuity()
            need(actual['foreground'] is True)
            need(state.get('processIdentity') == str(actual['pid']))
            return str(actual['pid'])

        def describe(self, selector):
            self._candidate_guard(complete=True)
            self._operation = 'describe'
            try:
                client,session,state = self.ensure_session(selector)
                result = super().describe(selector)
                result['executionIdentity'] = self._binding(selector,client,session,state,self._target(selector)).verify()
                self._candidate_guard(complete=True)
                return result
            finally:self._operation = None

        def invoke(self, selector, operation, values):
            validate_operation_arguments(operation,values)
            need(operation not in ('app.install','app.upgrade'))
            if operation.startswith('feature.'):
                from ios.adapters.feature_configuration import OPERATIONS,configuration,capabilities
                from ios.adapters.script_runtime import IOSScriptRuntime
                need(operation in OPERATIONS and configuration() is not None and self._operation is None)
                self._candidate_guard(complete=True)
                need(operation in capabilities(self._target(selector)))
                self._operation=operation
                try:
                    runtime=IOSScriptRuntime(self)
                    flow=runtime._script_feature(selector,values['runId'])
                    result=getattr(flow,operation.rsplit('.',1)[1])(values)
                    client,session,state,target,_scope=runtime._existing(selector)
                    self._binding(selector,client,session,state,target).verify()
                    self._candidate_guard(complete=True)
                    return result
                finally:self._operation=None
            if self._operation is not None:
                need(self._operation in ('permission.snapshot','permission.set') and operation == 'voice.exchange')
                return super().invoke(selector,operation,values)
            self._candidate_guard(complete=True)
            self._operation = operation
            try:
                client,session,state = self.ensure_session(selector)
                target = self._target(selector)
                gate = self._binding(selector,client,session,state,target)
                if operation in ('app.stop','app.crash'):
                    gate.begin_retirement();self._retiring = (selector,session)
                result = super().invoke(selector,operation,values)
                if self._retiring:
                    gate.finish_retirement()
                elif operation == 'lifecycle.background':
                    need(gate.continuity(allow_background=True)['foreground'] is False)
                elif operation == 'app.process' and gate.record()['phase'] == 'retired':
                    gate.retired_absence()
                elif operation == 'app.foreground':gate.continuity(allow_background=True)
                else:gate.verify()
                self._candidate_guard(complete=True)
                return result
            finally:
                self._operation = self._retiring = None

        def cleanup(self, selector):
            # Preserve the original component cleanup and independent native
            # process/session teardown even if all candidate inputs are lost.
            store = self._binding_store(selector)
            previous = store.read()
            feature_error=False
            from ios.adapters.script_runtime import IOSScriptRuntime
            runtime=IOSScriptRuntime(self)
            owner=runtime.script_feature_store(selector).read()
            retirement=runtime.script_retirement_store(selector).read()
            if owner is not None or retirement is not None:
                try:
                    original=owner if owner is not None else retirement
                    runtime._script_feature(selector,original['runId']).finalize()
                except Exception:feature_error=True
            result = super().cleanup(selector)
            need(not feature_error)
            need(type(result) is dict and result == {'cleaned':True} and self.read_session(selector) is None)
            if previous is not None:store.discard(previous)
            return result

    return IOSInstalledAdapter()
