"""One warm Browser graph on the existing original Pico operation host.

Only this explicit coordinator launches its own reviewed read-only observer.
Native effects, Witness, stereo and retirement come from the existing owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time
import uuid

from adapters.chat_journey.source_chunks import json_digest
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_common_process import OriginalBrowserRunnerProcess
from adapters.pico4.browser_common_return import OriginalBrowserConsumptionReturn
from adapters.pico4.browser_execution_budget import BrowserExecutionBudget
from adapters.pico4.browser_operation_protocol import validate
from adapters.pico4.browser_remote_consumption import PicoBrowserRemoteCleanupConsumption
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.operation_host import process_identity
from adapters.pico4.operation_protocol import STRIPPED_ENV, dto_bytes
from adapters.pico4.tablet_web_binding import PicoTabletWebBinding, archive_sentry_prefix, retained
from feature_journeys.phase_fixture import PhaseFixtureReader
from fixture.chat_observer_process import LinuxChatObserverProcess

VERSION = 1
RUNNER_ENTRY = Path(__file__).resolve().parents[2] / 'modules/feature_journey.py'
UNRESOLVED = []


class PicoBrowserOperationOwner:
    def __init__(self, adapter, target, request, parent_identity, *, runner_entry=RUNNER_ENTRY):
        validate(request); need(request['operation'] == 'begin')
        self.whole = self._whole = BrowserExecutionBudget(request['wholeBudget'])
        need(not retained(adapter, target))
        self.adapter = self._adapter = adapter
        self.target, self.run, self.url = target, request['runId'], request['fixtureUrl']
        self.host, self.thread, self.parent_identity = host_identity(), threading.get_ident(), parent_identity
        self.whole_raw = self._whole_raw = json_digest(request['wholeBudget'])
        self.path = Path(adapter.pico_configuration[1]) / (archive_sentry_prefix(target) + self.run + '-operation.json')
        self.store = self._store = PrivateFeatureState(self.path)
        self.file = self._file = object.__new__(LifecycleProcessFile)
        self.failed = False; self.state = None; self.state_sha = json_digest(None)
        self.feature = self._feature = None
        self.origin = self._origin = None
        self.worker = self._worker = self.worker_owner = self._worker_owner = None
        self.actor_return = self._actor_return = self.common_return = self._common_return = None
        self.worker_pins = []; self.worker_pipes = []; self.pending_owners = []
        self.worker_identity = self._worker_identity = None
        self.worker_config_pin = self._worker_config_pin = None
        self.diagnostics = [b'', b'']; self.config = None
        self.nonce = request['arguments']['nonce']; self.action = self._action = None
        self.begin_sha = json_digest(request); self.begin_delivered = False
        self.public = self._public = None
        try:
            LifecycleProcessFile.__init__(self.file, self.store)
            need(self.file.file is None and process_identity(os.getppid()) == parent_identity)
            self._write(dict(picoBrowserOperationOwnerVersion=VERSION, runId=self.run, fixtureUrl=self.url,
                parentHostProcessIdentity=parent_identity, hostProcessIdentity=self.host,
                targetFingerprint=hashlib.sha256(target.encode()).hexdigest(), phase='admitting',
                wholeBudget=deepcopy(request['wholeBudget']), calls=[], pending=None,
                workerStdoutHex='', workerStderrHex='', result=None))
            entry = Path(runner_entry).resolve(strict=True)
            executable = Path('/proc') / str(os.getppid()) / 'exe'
            def owned(pid):
                return pid == os.getppid() and process_identity(pid) == self.parent_identity and host_identity() == self.host
            self.origin = self._origin = object.__new__(OriginalBrowserRunnerProcess)
            self.pending_owners.append(self.origin)
            OriginalBrowserRunnerProcess.__init__(self.origin, parent_identity, entry,
                Path(request['arguments']['artifactRoot']), hashlib.sha256(executable.read_bytes()).hexdigest(),
                hashlib.sha256(entry.read_bytes()).hexdigest(), owned)
            from adapters.feature_fixture_access import client
            access = client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
            need(access.url + '/runs/' + self.run + '/' == self.url)
            facade = PicoTabletWebBinding(adapter)
            source = PhaseFixtureReader(access, self.run, 'tablet-web',
                epoch_ms=lambda:adapter._native_feature_observer(target).clock_ms(), monotonic=self.whole.check)
            self.feature = self._feature = facade.feature(target, source, request['arguments']['artifactRoot'],
                request['arguments']['foreignFixtureUrl'])
            self.common = self._common = PicoBrowserRemoteCleanupConsumption(self.feature)
            self.feature.cleanup_consumption = self.common
            self._write(dict(self.state, phase='ready'))
            self.guard()
        except BaseException:
            self.failed = True; UNRESOLVED.append(self); raise

    def _write(self, value):
        dto_bytes(value, 65536)
        self.file.write(value, self.state)
        need(json_digest(self.store.read()) == json_digest(value))
        self.state = deepcopy(value); self.state_sha = json_digest(self.state)

    def guard(self):
        need(not self.failed and self.adapter is self._adapter and self.feature is self._feature
            and self.origin is self._origin and self.file is self._file and self.store is self._store
            and self.whole is self._whole and self.common is self._common
            and self.worker is self._worker and self.worker_owner is self._worker_owner
            and self.actor_return is self._actor_return and self.common_return is self._common_return
            and self.action is self._action
            and self.public is self._public
            and self.worker_identity is self._worker_identity
            and self.worker_config_pin is self._worker_config_pin
            and host_identity() == self.host and threading.get_ident() == self.thread
            and process_identity(os.getppid()) == self.parent_identity
            and json_digest(self.state) == self.state_sha and self.whole_raw is self._whole_raw)
        self.whole.same(self.state['wholeBudget']); self.file.guard()
        need(json_digest(self.store.read()) == self.state_sha)
        if self.worker is not None:
            need(type(self.worker_identity) is tuple and len(self.worker_identity) == 5
                and self.worker.pid == self.worker_identity[0]
                and (self.worker.stdin, self.worker.stdout, self.worker.stderr) == self.worker_identity[2:])
            if self.worker_owner is not None:
                need(self.worker_owner.pid == self.worker_identity[0]
                    and self.worker_owner.process_identity == self.worker_identity[1])
            need(self.worker_config_pin is not None and self.config.path == self.worker_config_pin.path)
            if self.worker_config_pin.owner.closed:
                need(self.worker.returncode == 0 and self.actor_return is not None and self.actor_return.complete)
            else: self.worker_config_pin.check()
        if self.origin is not None:
            if self.state['phase'] in ('completed', 'closing'):
                need(self.origin.entry_owner.closed and self.origin.fd_owner.closed and not self.origin.lost)
            else: self.origin.guard()
        if self.feature is not None:
            need(self.feature.run == self.run and self.feature.fixture_url == self.url
                and self.feature.selector == self.target and self.feature.cleanup_consumption is self.common)

    def control(self):
        self.guard()
        if self.action is not None: self.action.check()

    def _issued(self, identifier, operation, action):
        self.guard(); self.action = self._action = action; self.action.check()
        need(identifier not in self.state['calls'] and len(self.state['calls']) < 512 and self.state['pending'] is None)
        self._write(dict(self.state, calls=self.state['calls'] + [identifier], pending=operation))

    def _returned(self, phase='ready', **changes):
        self.control(); self._write(dict(self.state, phase=phase, pending=None, **changes))
        self.control(); self.action = self._action = None

    @contextmanager
    def public_context(self, request):
        operation, arguments = request['operation'], request['arguments']
        need(operation in ('feature.tablet-web.act', 'feature.tablet-web.observe', 'feature.tablet-web.cleanup')
            and self.worker_owner is not None and self.state['phase'] == 'ready' and self.public is None)
        now = time.monotonic()
        action = BrowserExecutionBudget(dict(id=request['requestId'], startedMonotonic=now,
            deadlineMonotonic=min(request['deadlineMonotonic'], self.whole.value['deadlineMonotonic'])), maximum=60)
        try:
            self._issued(request['requestId'], operation, action)
            self.public = self._public = (request['requestId'], operation, json_digest(arguments), action)
            self.public_guard(operation, arguments)
            yield
            self.public_guard(operation, arguments); self._returned()
        except BaseException:
            self.failed = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            raise
        finally: self.public = self._public = None

    def public_guard(self, operation, arguments):
        self.control()
        need(type(self.public) is tuple and len(self.public) == 4
            and self.public[1] == operation and self.public[2] == json_digest(arguments)
            and self.public[3] is self.action and self.state['pending'] == operation)
        self.worker_owner.guard()  # Before the canonical router can query its SDK.

    def invoke(self, operation, arguments):
        self.public_guard(operation, arguments); self.worker_owner.guard()
        return getattr(self.feature, operation.rsplit('.', 1)[1])(arguments)

    def start_actor(self, spec):
        from adapter_operation_host import PinnedFile, PipeOwner
        from adapters.pico4.feature_observer import configuration
        self.control()
        need(self.worker is self.worker_owner is None and spec['target'] == self.target
            and spec['fixtureUrl'] + '/runs/' + self.run + '/' == self.url
            and Path(spec['artifactRoot']) == self.feature.artifact_root)
        entry = Path(__file__).with_name('feature_observer.py').resolve(strict=True)
        executable = Path(sys.executable).resolve(strict=True)
        for path, limit in ((entry, 1024*1024), (executable, 128*1024*1024)):
            pin = object.__new__(PinnedFile); self.worker_pins.append(pin)
            PinnedFile.__init__(pin, path, limit)
        self.actor_request = uuid.uuid4().hex
        config = dict(spec, picoFeatureObserverVersion=6, area='tablet-web', runId=self.run,
            originalRequestId=self.actor_request, foreignFixtureUrl=self.feature.foreign_url.rsplit('/runs/', 1)[0],
            browserOwnerBudget=deepcopy(self.whole.value), browserParentHostProcessIdentity=self.host)
        self.config = PrivateFeatureState(self.feature.artifact_root/('pico-browser-actor-config-'+self.run+'.json'))
        need(self.config.read() is None); self.config.write(config, None); configuration(self.config.path)
        self.worker_config_pin = self._worker_config_pin = object.__new__(PinnedFile)
        self.worker_pins.append(self.worker_config_pin)
        PinnedFile.__init__(self.worker_config_pin, self.config.path, 65536)
        self.control()
        environment = {key:value for key,value in os.environ.items() if key not in STRIPPED_ENV}
        self.worker = self._worker = subprocess.Popen([str(executable), str(entry), '--config', str(self.config.path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        identity = process_identity(self.worker.pid); pid = self.worker.pid
        self.worker_identity = self._worker_identity = (pid, identity,
            self.worker.stdin, self.worker.stdout, self.worker.stderr)
        for stream in (self.worker.stdout, self.worker.stderr):
            owner = object.__new__(PipeOwner); self.worker_pipes.append(owner); PipeOwner.__init__(owner, stream)
        def owned(current):
            fields = Path(f'/proc/{current}/stat').read_text().rsplit(')', 1)[1].split()
            return current == pid and int(fields[1]) == os.getpid() and process_identity(current) == identity
        self.worker_owner = self._worker_owner = object.__new__(LinuxChatObserverProcess)
        LinuxChatObserverProcess.__init__(self.worker_owner, identity, entry, self.config.path,
            self.worker_pins[1].digest, self.worker_pins[0].digest, owned)
        self.worker_owner.guard(); self.control()
        return dict(picoBrowserActorHostVersion=VERSION, hostProcessIdentity=identity, originalRequestId=self.actor_request)

    def collect(self):
        if self.worker is None: return
        for index, stream in enumerate((self.worker.stdout, self.worker.stderr)):
            if stream.closed: continue
            if not select.select([stream], [], [], 0)[0]: continue
            self.worker_pipes[index].check()
            raw = os.read(stream.fileno(), 8193-len(self.diagnostics[index]))
            if raw:
                self.diagnostics[index] += raw
                self._write(dict(self.state, workerStdoutHex=self.diagnostics[0].hex(), workerStderrHex=self.diagnostics[1].hex()))
                need(len(self.diagnostics[index]) <= 8192)

    def return_actor(self):
        self.control(); need(self.common.complete and not self.common.failed and self.actor_return is None)
        root = PrivateFeatureState(self.feature.store.path.with_name('pico-tablet-web-actor-return.json'))
        while True:
            self.control(); self.collect(); self.worker_owner.guard()
            with self.feature.lock.held():
                ready = root.read()
                if ready is not None and ready.get('phase') == 'ready': break
            time.sleep(.01)
        with self.feature.lock.held(): owner = self.feature.owner()
        expected = dict(runId=self.run, fixtureUrl=self.url, foreignFixtureUrl=self.feature.foreign_url,
            artifactRoot=str(self.feature.artifact_root), sceneUrl=self.feature.adapter.scene_url,
            binding=owner['binding'], ownerToken=owner['ownerToken'],
            producerHostProcessIdentity=self.worker_owner.process_identity, originalRequestId=self.actor_request)
        self.actor_return = self._actor_return = self.feature.adapter._tablet_web_actor_return(self.target, self.feature, self.worker_owner, expected)
        self.actor_return.acknowledge()
        while True:
            self.control(); self.collect()
            event = os.waitid(os.P_PID, self.worker.pid, os.WEXITED|os.WNOWAIT|os.WNOHANG)
            if event is not None: break
            time.sleep(.01)
        need(event.si_status == 0)
        pid, status = os.waitpid(self.worker.pid, 0); self.worker.returncode = os.waitstatus_to_exitcode(status)
        need(pid == self.worker.pid and self.worker.returncode == 0)
        self.control(); self.collect()
        need(not any(self.diagnostics)); result = self.actor_return.finish()
        for owner in self.worker_pipes: owner.close()
        for pin in self.worker_pins: need(pin.close())
        return result

    def finalize(self):
        self.control(); need(self.actor_return is not None and self.actor_return.complete
            and self.common.complete and self.common_return is not None)
        self.feature.retire_returned_actor_captures(self.actor_return)
        self.feature.archive_retired_sources(directory_retirement=True)
        self.feature.close_archived_host()
        result = self.feature.finalize()
        self.whole.check()
        need(result['hostReleased'] and result['sequenceCompleted'])
        return result

    def dispatch(self, request):
        validate(request); self.guard()
        need(request['runId'] == self.run and request['fixtureUrl'] == self.url
            and json_digest(request['wholeBudget']) == self.whole_raw)
        action = BrowserExecutionBudget(request['actionBudget'], maximum=60)
        operation, fields = request['operation'], request['arguments']
        try:
            self._issued(request['requestId'], operation, action)
            if operation == 'begin':
                need(not self.begin_delivered and json_digest(request) == self.begin_sha)
                self.begin_delivered = True
                result = dict(picoBrowserOperationBeginVersion=VERSION, nonce=self.nonce,
                    producerHostProcessIdentity=self.parent_identity, wholeBudget=deepcopy(self.whole.value))
            elif operation == 'actor.start': result = self.start_actor(fields)
            elif operation == 'consume':
                need(self.common_return is None)
                self.common_return = self._common_return = object.__new__(OriginalBrowserConsumptionReturn)
                OriginalBrowserConsumptionReturn.__init__(self.common_return, self.origin, fields,
                    self.run, self.url, self.nonce, self.control)
                result = self.common.consume(self.common_return)
            elif operation == 'actor.return': result = self.return_actor()
            elif operation == 'finalize':
                result = self.finalize()
                self._write(dict(self.state, phase='completed', pending=None, result=deepcopy(result)))
                self.action.check(); self.action = self._action = None; self.guard(); return result
            else: need(False)
            self._returned(); return result
        except BaseException:
            self.failed = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            raise

    def unwind(self):
        # No input retry or native repair. Actual children retain their own
        # original Parent/budget; losing this process makes their admission fail.
        if self.failed and not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)

    def close_host(self):
        self.guard(); need(self.state['phase'] == 'completed' and self.state['pending'] is None
            and self.worker.returncode == 0 and self.feature.browser_host_close.completed)
        result = dict(picoBrowserOperationCloseVersion=VERSION, runId=self.run, result=deepcopy(self.state['result']))
        receipt = PrivateFeatureState(self.feature.artifact_root/('pico-browser-operation-complete-'+self.run+'.json'))
        need(receipt.read() is None); receipt.write(result, None)
        self._write(dict(self.state, phase='closing')); self.guard()
        try:
            self.file.guard(); self.file.parent.require(self.file.parent.fd)
            os.unlink(self.path.name, dir_fd=self.file.parent.fd)
            os.fsync(self.file.parent.fd); self.file.parent.require(self.file.parent.fd)
            need(self.store.read() is None and self.file.close_host()); self.whole.check()
        except BaseException:
            self.failed=True
            if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)
            if self.store.read() is None:self.store.write(dict(self.state,phase='close-unavailable'),None)
            raise
