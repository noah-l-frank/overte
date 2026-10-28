#!/usr/bin/env python3
"""Keep the current PyMobileDevice3 XCTest handshake alive for one WDA run."""

# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import ctypes
from importlib.metadata import version
import ipaddress
import inspect
import weakref
import json
import os
import re
import signal
import time
import uuid
from urllib.parse import quote
import sys

from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.exceptions import ConnectionTerminatedError
from pymobiledevice3.services.dvt.testmanaged.xcuitest import TestConfig, XCUITestService
from pymobiledevice3.services.wda import WdaServiceClient


MAX_REQUEST_BYTES = 16 * 1024
READY_TIMEOUT_SECONDS = 34.0
GRACEFUL_STOP_TIMEOUT_SECONDS = 10.0
BUNDLE_ID = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9-]*(?:[.][A-Za-z0-9][A-Za-z0-9-]*)+"
)
ENVIRONMENT_KEYS = {"USE_PORT", "WDA_PRODUCT_BUNDLE_IDENTIFIER"}
FAILURE_PHASES = {
    "host-platform",
    "parent-death-signal",
    "parent-lost",
    "request",
    "request-endpoint",
    "request-environment",
    "runtime-version",
    "rsd-connect",
    "rsd-identity",
    "xctest-config",
    "xctest-start",
    "wda-ready",
    "wda-ready-runner-disconnected",
    "wda-ready-runner-error",
    "wda-ready-runner-returned",
    "wda-ready-runner-runtime",
    "wda-ready-runner-timeout",
    "wda-ready-timeout",
    "session-lifetime",
    "session-lifetime-runner-disconnected",
    "session-lifetime-runner-error",
    "session-lifetime-runner-returned",
    "session-lifetime-runner-runtime",
    "session-lifetime-runner-timeout",
    "unexpected",
}


class LaunchError(RuntimeError):
    """The private WDA launch contract could not be satisfied."""

    def __init__(self, phase: str) -> None:
        if phase not in FAILURE_PHASES:
            phase = "unexpected"
        self.phase = phase
        super().__init__(phase)


class AppiumKeepAliveEvent(asyncio.Event):
    """Keep WDA's XCTest transport open until Appium ends the session.

    WebDriverAgent's bootstrap test plan may report completion after its HTTP
    server is ready.  A normal PyMobileDevice3 run closes all DTX providers at
    that point, which also tears down the preinstalled runner.  Appium owns the
    longer session lifetime, so only an explicit keeper signal or a real DTX
    disconnect may end this run.
    """

    def set(self) -> None:
        pass

    def stop(self) -> None:
        """Complete the test plan only when Appium releases its ownership.

        XCTest's own completion callback must not end WDA while the Appium
        session is alive.  Conversely, cancelling XCUITestService.run during
        Appium cleanup closes its DTX providers abruptly and can leave
        testmanagerd unable to accept the next runner.  This explicit path
        lets the service unwind all three providers in protocol order.
        """
        super().set()


def completed_runner_phase(runner: asyncio.Task, prefix: str) -> str:
    """Reduce a completed XCTest task to an allowlisted, value-free phase."""
    if runner.cancelled():
        return f"{prefix}-runner-error"
    error = runner.exception()
    if error is None:
        return f"{prefix}-runner-returned"
    if isinstance(error, ConnectionTerminatedError):
        return f"{prefix}-runner-disconnected"
    if isinstance(error, TimeoutError):
        return f"{prefix}-runner-timeout"
    if isinstance(error, RuntimeError):
        return f"{prefix}-runner-runtime"
    return f"{prefix}-runner-error"


def parent_death_signal() -> None:
    """Ensure a crashed Appium parent cannot orphan an XCTest session."""
    if not sys.platform.startswith("linux"):
        raise LaunchError("host-platform")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:
        raise LaunchError("parent-death-signal")
    if os.getppid() == 1:
        raise LaunchError("parent-lost")


def read_request() -> dict:
    line = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
    if (not line.endswith(b"\n") or len(line) > MAX_REQUEST_BYTES
            or b"\r" in line or b"\0" in line):
        raise LaunchError("request")
    try:
        value = json.loads(line)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LaunchError("request") from error
    if type(value) is dict and type(value.get("schemaVersion")) is int and value["schemaVersion"]==2:
        value=decode_owner_packet(line)
        if (set(value)!={"schemaVersion","creatorMode","udid","stateRoot"}
                or value["creatorMode"]!="original-userspace-owner" or type(value["udid"]) is not str
                or not 8<=len(value["udid"])<=128 or any(ch in value["udid"] for ch in "\0\r\n")
                or type(value["stateRoot"]) is not str or not value["stateRoot"].startswith("/")
                or any(ch in value["stateRoot"] for ch in "\0\r\n")):
            raise LaunchError("request")
        return value
    keys = {"schemaVersion", "udid", "rsdHost", "rsdPort", "wdaBundleId",
            "wdaPort", "environment"}
    if (not isinstance(value, dict) or set(value) != keys
            or value.get("schemaVersion") != 1
            or isinstance(value.get("schemaVersion"), bool)
            or not isinstance(value.get("udid"), str)
            or not 8 <= len(value["udid"]) <= 128
            or any(character in value["udid"] for character in "\0\r\n")
            or not isinstance(value.get("rsdHost"), str)
            or not 2 <= len(value["rsdHost"]) <= 128
            or not isinstance(value.get("rsdPort"), int)
            or isinstance(value.get("rsdPort"), bool)
            or not 1 <= value["rsdPort"] <= 65535
            or not isinstance(value.get("wdaPort"), int)
            or isinstance(value.get("wdaPort"), bool)
            or value["wdaPort"] != 8100
            or not isinstance(value.get("wdaBundleId"), str)
            or len(value["wdaBundleId"]) > 255
            or not BUNDLE_ID.fullmatch(value["wdaBundleId"])):
        raise LaunchError("request")
    try:
        ipaddress.ip_address(value["rsdHost"].split("%", 1)[0])
    except ValueError as error:
        raise LaunchError("request-endpoint") from error
    environment = value.get("environment")
    if (not isinstance(environment, dict) or set(environment) != ENVIRONMENT_KEYS
            or any(not isinstance(item, str) or len(item) > 255
                   or any(character in item for character in "\0\r\n")
                   for item in environment.values())
            or environment.get("USE_PORT") != "8100"
            or environment.get("WDA_PRODUCT_BUNDLE_IDENTIFIER")
            != value["wdaBundleId"]):
        raise LaunchError("request-environment")
    return value


class OriginalKeeperSource:
    """Same-loop borrow from the ORIGINAL creator; construction opens nothing.

    The creator must already have selected its exclusive userspace path before
    any external Node tunnel is created. Nothing in this class can prove that
    missing cross-process selection or the Appium session route.
    """
    def __init__(self, tunnel):
        from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
        if type(tunnel) is not UserspaceRsdTunnel:
            raise LaunchError("rsd-connect")
        self._tunnel = weakref.ref(tunnel)
        self._source = tunnel.original_source()
        self._loop = asyncio.get_running_loop()
        self._creator_task=weakref.ref(asyncio.current_task());self._native_motion_key=object()
        self._leases = []
        self._born = []
        self._native_reads = []
        self._native_queries = []
        self._native_current_tasks = []
        self._closing = False

    def current(self):
        tunnel = self._tunnel()
        if (tunnel is None or asyncio.get_running_loop() is not self._loop
                or tunnel.original_source() is not self._source):
            raise LaunchError("rsd-connect")
        return self._source.current()

    def _birth(self, lease, task):
        from ios.adapters.lifecycle_touch_transport import RetainedTouchWorker
        # Capture the ACTUAL born Task before validation can fail. Even a
        # changed public worker slot cannot erase this original responsibility.
        existing = next((row for row in self._born if row['lease'] is lease), None)
        if existing is not None:
            if existing['worker'] is not task:
                raise LaunchError("session-lifetime")
            if existing['owner'] is None:
                raise LaunchError("session-lifetime")
            existing['owner']._status()
            return existing
        row = dict(lease=lease, worker=task, loop=task.get_loop(),
                   release=lease.request_release, owner=None)
        self._born.append(row)
        if asyncio.get_running_loop() is not self._loop or row['loop'] is not self._loop:
            raise LaunchError("session-lifetime")
        row['owner'] = RetainedTouchWorker(lease)
        resource=getattr(lease,'_original_motion_resource',None)
        if resource is not None:
            from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner,_NativeMotionWorkerGuard
            if type(resource) is not LifecycleTouchResourceOwner or type(resource._native_step) is not _NativeMotionWorkerGuard:
                raise LaunchError('session-lifetime')
            resource._native_step.born(lease,task)
        return row

    def touch_lease(self, store, *, binding, run, check, resource_owner=None):
        from ios.adapters.touch_lease import TouchLease
        from ios.adapters.hid_session import touch_session
        def admission():
            if self._closing:
                raise LaunchError("session-lifetime")
            self.current()
            return True
        admission()
        async def continuity():
            self._birth(lease, asyncio.current_task())
            # Only forward acquisition/Down is gated. Existing worker finally
            # sends its original ordinary Up/drain without this admission.
            admission()
            result = check()
            if inspect.isawaitable(result):
                result = await result
            admission()
            return result
        @asynccontextmanager
        async def session():
            admission()
            rsd, local_address = self.current()
            async with touch_session(rsd, local_address,
                                     socket_factory=self._source.udp_socket) as hid:
                admission()
                yield hid
        if resource_owner is None:
            lease = TouchLease(store, session, binding=binding, run=run, check=continuity,
                               admit_begin=admission, on_worker_birth=self._birth)
        else:
            from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner
            if (type(resource_owner) is not LifecycleTouchResourceOwner
                    or resource_owner.binding!=binding or resource_owner.run!=run
                    or resource_owner.store.path.parent!=store.path.parent):
                raise LaunchError("session-lifetime")
            rsd,local_address=self.current()
            # The existing resource owner runs INSIDE the original lease
            # worker. Actual auth/RSD/stack/loop remain owned here, not in JSON.
            lease=resource_owner.make_lease(store,rsd,local_address,check=continuity,
                options={'socket_factory':self._source.udp_socket},admit_begin=admission,
                on_worker_birth=self._birth,worker_lock=True)
        self._leases.append(lease)
        return lease

    def prepare_motion(self,resource,owner_instance,original,*,seconds):
        from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner,_NativeMotionReference
        if (type(self) is not OriginalKeeperSource or self._closing or type(resource) is not LifecycleTouchResourceOwner
                or type(original) is not _NativeMotionReference or asyncio.get_running_loop() is not self._loop):raise LaunchError('session-lifetime')
        self.current()
        # This actual Source object/loop remains local. The serialized owner ID
        # is correlation only, never a callable or authentication capability.
        original.bind(self,resource,owner_instance)
        return resource.prepare_motion(self,owner_instance,original,seconds=seconds)

    async def _close_native_read(self,row):
        # Cleanup uses the ORIGINAL retained bound method on the ORIGINAL
        # service/loop. A changed current SDK/session cannot redirect it.
        service,close,task,loop,closed,lock=row
        if asyncio.get_running_loop() is not self._loop or loop is not self._loop or task.get_loop() is not loop or close.__self__ is not service:
            return False
        async with lock:
            if closed.is_set():return True
            try:
                await close()
                if service._service is not None or service._afc_reader_task is not None or service._afc_pending:return False
            except BaseException:return False
            closed.set();return True

    async def settle_touches(self):
        # Close ALL future begin/acquire/Down admission before any await.
        self._closing = True
        failure = None
        for row in tuple(self._born):
            lease, worker, owner = row['lease'], row['worker'], row['owner']
            try:
                if (row['loop'] is not self._loop or worker.get_loop() is not self._loop
                        or lease.request_release is not row['release'] or owner is None):
                    raise LaunchError("session-lifetime")
                await owner.release()
            except BaseException as error:
                failure = failure or error
                # Request cleanup on the ORIGINAL worker's retained event. A
                # failed source check never cancels or replaces that worker.
                row['release'].set()
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except BaseException as error:
                    failure = failure or error
        for task in tuple(getattr(self,'_native_current_tasks',())):
            if not isinstance(task,asyncio.Task) or task.get_loop() is not self._loop:raise LaunchError('session-lifetime')
            while not task.done():
                try:await asyncio.shield(task)
                except BaseException as error:failure=failure or error
            # Current acceptance already failed at its caller. Harvest the
            # actual completed Task error, never convert it to current/end.
            if not task.cancelled():task.exception()
        for task,thread,finished,loop in tuple(getattr(self,'_native_queries',())):
            if loop is not self._loop or task.get_loop() is not loop:raise LaunchError('session-lifetime')
            while not task.done() or thread.is_alive():
                try:await asyncio.sleep(.01)
                except BaseException as error:failure=failure or error
            if thread.ident is not None:thread.join(timeout=0)
        # Same original native-read Task/service remains owned until the
        # actual bound AFC close returned. Unknown read/close never permits
        # this Source context to unwind its original RSD/tunnel underneath it.
        for row in tuple(getattr(self,'_native_reads',())):
            service,close,task,loop,closed,lock=row
            if loop is not self._loop or task.get_loop() is not self._loop or close.__self__ is not service:
                raise LaunchError('session-lifetime')
            while not task.done():
                try:await asyncio.shield(task)
                except BaseException as error:failure=failure or error
            await self._close_native_read(row)
            # Another explicit existing cleanup call may retry this exact close.
            # Unknown close never becomes permission to unwind the original RSD.
            while not closed.is_set():
                try:await closed.wait()
                except BaseException as error:failure=failure or error
            if service._service is not None or service._afc_reader_task is not None or service._afc_pending:
                raise LaunchError('session-lifetime')
        if failure is not None:
            raise failure


@asynccontextmanager
async def create_original_keeper_source(udid):
    """Original creator extension, only after exclusive creator selection.

    Not wired to main or Node: their kernel creator must be excluded BEFORE
    this function is called. It must never be used as a second-tunnel fallback.
    """
    from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
    tunnel = UserspaceRsdTunnel(
        serial=udid, autopair=False, remotepairing_fallback=False,
        require_validated_source=True)
    async with tunnel:
        source = OriginalKeeperSource(tunnel)
        source.current()
        try:
            yield source
        finally:
            await source.settle_touches()


@asynccontextmanager
async def original_service_provider(request, original_source):
    if original_source is None:
        async with RemoteServiceDiscoveryService(
                (request["rsdHost"], request["rsdPort"])) as service_provider:
            yield service_provider
        return
    if type(original_source) is not OriginalKeeperSource:
        raise LaunchError("rsd-connect")
    service_provider, _address = original_source.current()
    if service_provider.udid != request["udid"]:
        raise LaunchError("rsd-identity")
    # The original creator retains its AsyncExitStack through this await; the
    # keeper never closes/recreates its borrowed RSD or tunnel.
    yield service_provider


async def run_xctest(request: dict, *, original_source=None, owned_stop=None, owned_ready=None) -> None:
    stop = asyncio.Event() if owned_stop is None else owned_stop
    loop = asyncio.get_running_loop()
    if owned_stop is None:
        for signal_number in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signal_number, stop.set)

    phase = "rsd-connect"
    try:
        async with original_service_provider(request, original_source) as service_provider:
            if service_provider.udid != request["udid"]:
                raise LaunchError("rsd-identity")
            if original_source is not None:
                original_source.current()
            phase = "xctest-config"
            configuration = await TestConfig.create_for(
                service_provider, runner_bundle_id=request["wdaBundleId"]
            )
            configuration.runner_app_env = request["environment"]
            keep_alive = AppiumKeepAliveEvent()
            phase = "xctest-start"
            runner = asyncio.create_task(
                XCUITestService(service_provider).run(
                    configuration, test_done_event=keep_alive
                ),
                name="overte-wda-xctest",
            )
            client = WdaServiceClient(
                service_provider=service_provider,
                port=request["wdaPort"],
                timeout=2.0,
            )
            deadline = loop.time() + READY_TIMEOUT_SECONDS
            phase = "wda-ready"
            while True:
                if original_source is not None:
                    original_source.current()
                if runner.done():
                    failure_phase = completed_runner_phase(runner, "wda-ready")
                    raise LaunchError(failure_phase)
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise LaunchError("wda-ready-timeout")
                try:
                    status = await asyncio.wait_for(
                        client.get_status(), timeout=min(2.5, remaining)
                    )
                    if original_source is not None:
                        original_source.current()
                except Exception:
                    await asyncio.sleep(min(0.1, max(0.0, deadline - loop.time())))
                    continue
                if (isinstance(status, dict)
                        and isinstance(status.get("value"), dict)
                        and status["value"].get("ready") is True):
                    break
                await asyncio.sleep(0.1)

            if owned_ready is None:
                sys.stdout.write("READY\n")
                sys.stdout.flush()
            else:
                owned_ready.set_result(None)
            phase = "session-lifetime"
            stopped = asyncio.create_task(stop.wait(), name="overte-wda-stop")
            done, _pending = await asyncio.wait(
                {runner, stopped}, return_when=asyncio.FIRST_COMPLETED
            )
            if runner in done and not stop.is_set():
                failure_phase = completed_runner_phase(runner, "session-lifetime")
                raise LaunchError(failure_phase)
            if stop.is_set():
                keep_alive.stop()
                try:
                    await asyncio.wait_for(
                        asyncio.shield(runner),
                        timeout=GRACEFUL_STOP_TIMEOUT_SECONDS,
                    )
                except TimeoutError as error:
                    raise LaunchError("session-lifetime-runner-timeout") from error
                failure_phase = completed_runner_phase(runner, "session-lifetime")
                if failure_phase != "session-lifetime-runner-returned":
                    raise LaunchError(failure_phase)
    except LaunchError:
        raise
    except BaseException as error:
        raise LaunchError(phase) from error
    finally:
        if "runner" in locals() and not runner.done():
            runner.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await runner


class OriginalKeeperOperations:
    """Versioned existing-pipe dispatch; JSON routes, live originals admit."""
    def __init__(self, source, state_root):
        self.source=source;self.instance=uuid.uuid4().hex;self.session=None
        self.wda=None;self.wda_stop=None;self.wda_session=None;self.wda_binding_claimed=False;self.touch=None;self.closed=False;self.draining=False
        self.issued={};self.operations=set();self.state_root=state_root;self.touch_resources=None
        self.native_query_task=None;self.native_query_journals={}
        self.native_acquisition=None;self.native_acquisition_journals={};self.native_current_cuts={}

    def scope(self, session):
        if self.closed or self.draining or self.session is None or session!=self.session['sessionId']:
            raise LaunchError('session-lifetime')
        return self.source.current()[0]

    async def process(self, bundle, original_pid=0, *, terminate=False):
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl
        from pymobiledevice3.services.dvt.instruments.device_info import DeviceInfo
        rsd=self.source.current()[0];before=dict(epochMs=time.time()*1000,monotonicMs=time.monotonic()*1000)
        provider=DvtProvider(rsd)
        async with provider:
            async with ProcessControl(provider) as control:
                first=await control.process_identifier_for_bundle_identifier(bundle)
                if type(first) is not int or not 0<=first<=2147483647:raise LaunchError('session-lifetime')
                if terminate and self.draining:raise LaunchError('session-lifetime')
                if terminate and first:await control.kill(first)
                second=await control.process_identifier_for_bundle_identifier(bundle)
                if type(second) is not int or not 0<=second<=2147483647:raise LaunchError('session-lifetime')
                checks=[]
                if original_pid:
                    async with DeviceInfo(provider) as device:
                        checks=[await device.is_running_pid(original_pid),await device.is_running_pid(original_pid)]
                        if any(type(value) is not bool for value in checks):raise LaunchError('session-lifetime')
        self.source.current()
        # Exact new source type: an awaited Python provider exit is not the
        # v1 Node socket close event or independent native resource retirement.
        return dict(iosOriginalKeeperProcessVersion=1,source='pmd-original-rsd-dvt',
                    ownerInstance=self.instance,bundlePids=[first,second],pidChecks=checks,
                    clockDomain='python-original-keeper-host',clockBefore=before,
                    clockAfter=dict(epochMs=time.time()*1000,monotonicMs=time.monotonic()*1000),
                    providerExitReturned=True,providerDtxCleared=provider._dtx is None,
                    resourceRetirementEstablished=False)

    async def fresh_touch_scope(self, binding):
        rsd=self.scope(binding['sessionId'])
        observation=await self.process(self.session['archiveBundleId'])
        if observation['bundlePids']!=[int(binding['processIdentity'])]*2:
            raise LaunchError('session-lifetime')
        # Existing WDA HTTP service uses its ordinary USB transport. It does
        # not create a new RSD/auth/tunnel or a new WDA session here.
        if self.wda_session is None:raise LaunchError('session-lifetime')
        state=await WdaServiceClient(rsd,port=8100,timeout=2.0)._request_json(
            'POST','/session/'+quote(self.wda_session,safe='')+'/wda/apps/state',{'bundleId':self.session['archiveBundleId']})
        if type(state.get('value')) is not int or state['value']!=4:
            raise LaunchError('session-lifetime')
        if self.scope(binding['sessionId']) is not rsd:raise LaunchError('session-lifetime')
        after=await self.process(self.session['archiveBundleId'])
        if (self.scope(binding['sessionId']) is not rsd
                or after['bundlePids']!=[int(binding['processIdentity'])]*2):
            raise LaunchError('session-lifetime')
        return True

    async def _selected_ipa_original(self,selector,binding,session):
        """Independently read selected IPA bytes; input path is ONLY a selector.

        No expected bundle/source revision/verdict is received. Existing IPA
        reader hashes the complete original archive; original native bundle
        equality is checked later by the same Source's actual file operation.
        """
        from copy import deepcopy
        from pathlib import Path
        import threading,stat
        from ios.adapters.installed_adapter import ArtifactLease
        from ios.adapters.bundle_identity import artifact_bundle
        if (type(selector) is not dict or set(selector)!={'root','relative'}
                or any(type(selector[k]) is not str or not selector[k] or len(selector[k])>4096
                       or any(c in selector[k] for c in '\0\r\n') for k in selector)):
            raise LaunchError('request')
        root=Path(selector['root']);relative=Path(selector['relative']);path=root/relative
        if (not root.is_absolute() or relative.is_absolute() or '..' in relative.parts or '.' in relative.parts
                or root.resolve(strict=True)!=root or path.resolve(strict=True)!=path or not path.is_relative_to(root)):
            raise LaunchError('request')
        file_info=path.lstat()
        # Same4GiB selected-IPA limit as existing immutable artifact verifier.
        if not stat.S_ISREG(file_info.st_mode) or file_info.st_nlink!=1 or not 1<=file_info.st_size<=4*1024**3:raise LaunchError('request')
        source=self.source;loop=asyncio.get_running_loop();task=asyncio.current_task();rsd=self.scope(session)
        claim=self.session;claim_value=deepcopy(claim);creator_reference=source._creator_task;creator=creator_reference()
        selected_function=self._selected_ipa_original.__func__;source_function=source.current.__func__
        if (loop is not source._loop or not isinstance(task,asyncio.Task) or not isinstance(creator,asyncio.Task)
                or creator.done() or creator.get_loop() is not loop or self.touch is not None or self.touch_resources is not None
                or source._born or source._leases or len(source._native_queries)>=32):raise LaunchError('session-lifetime')
        # Retain weak identity, not an alternate SDK owner. The existing Source
        # owns this actual Task/Thread through _native_queries until true return.
        source_ref=weakref.ref(source);rsd_ref=weakref.ref(rsd);task_ref=weakref.ref(task);creator_ref=weakref.ref(creator);owner_ref=weakref.ref(self)
        state={'revoked':False,'returned':False,'capture':task_ref,'creator':creator_ref,'motionTarget':None};result={};finished=threading.Event()
        def guard():
            try:
                actual=source_ref();owner=owner_ref();original_task=task_ref();original_creator=creator_ref()
                if (state['revoked'] or state['capture'] is not task_ref or state['creator'] is not creator_ref or actual is None or owner is None or original_task is None or original_creator is None
                        or asyncio.get_running_loop() is not loop or actual._closing or owner.draining or owner.closed
                        or owner.source is not actual or actual._loop is not loop or actual._creator_task is not creator_reference
                        or owner._selected_ipa_original.__func__ is not selected_function or actual.current.__func__ is not source_function
                        or owner.session is not claim or owner.session!=claim_value
                        or owner.scope(session) is not rsd_ref() or original_creator.done()
                        or original_task.cancelled() or original_task.get_loop() is not loop
                        or (original_task.done() and original_task.exception() is not None)
                        or (state['motionTarget'] is None and owner.touch_resources is not None)
                        or (state['motionTarget'] is not None and (state['motionTarget']() is None or owner.touch_resources is not state['motionTarget']()))):
                    raise LaunchError('session-lifetime')
                worker_guard=state.get('motionGuard')
                if worker_guard is None:
                    if owner.touch is not None or actual._born or actual._leases:raise LaunchError('session-lifetime')
                else:
                    from ios.adapters.lifecycle_touch_resource_owner import _NativeMotionWorkerGuard
                    bridge=worker_guard()
                    if type(bridge) is not _NativeMotionWorkerGuard or bridge._source() is not actual or bridge._owner() is not owner:
                        raise LaunchError('session-lifetime')
                    bridge._scope_without_ref()
                if state['returned']:result['lease'].guard()
            except BaseException:
                state['revoked']=True;raise
        guard();await self.fresh_touch_scope(binding);guard()
        def read_original():
            try:
                lease=ArtifactLease(root);lease.guard()
                measured=artifact_bundle(path,binding['artifactSha256']);lease.guard()
                result.update(lease=lease,bundle=deepcopy(measured))
            except BaseException as error:result['error']=error
            finally:finished.set()
        thread=threading.Thread(target=read_original,name='original-selected-ipa-read',daemon=False)
        source._native_queries.append((task,thread,finished,loop));failure=None
        try:
            thread.start()
            while thread.is_alive():
                try:await asyncio.sleep(.01)
                except BaseException as error:failure=failure or error
            if thread.ident is not None:thread.join(timeout=0)
            if failure is not None:raise failure
            if not finished.is_set() or 'error' in result:
                if 'error' in result:raise result['error']
                raise LaunchError('session-lifetime')
            state['returned']=True;guard();await self.fresh_touch_scope(binding);guard()
            # Actual locally born closure/object is kept only in this original
            # live journal; no JSON or persisted file can recreate its guard.
            return (object(),guard,deepcopy(result['bundle']),state)
        except BaseException:
            state['revoked']=True;raise
        finally:
            while thread.is_alive():
                try:await asyncio.sleep(.01)
                except BaseException:pass
            if thread.ident is not None:thread.join(timeout=0)

    async def native_query(self,args,session):
        """Own ONE diagnostic query nonce/intent; never candidate/motion authority."""
        from concurrent.futures import Future
        from copy import deepcopy
        import threading
        from adapters.normal_feature_state import PrivateFeatureState,context
        from adapters.script_feature.lock import ScriptSourceLock
        from adapters.operation_transport_guard import scope as transport_scope
        from ios.adapters.appium_adapter import AppiumAdapter
        from ios.adapters.feature_observation import send_original_command
        bundle_profile=type(args) is dict and 'nativeBundleProfileVersion' in args
        selected_profile=bundle_profile and type(args.get('nativeBundleProfileVersion')) is int and args['nativeBundleProfileVersion']==2
        expected={'binding','runId','resultsDirectory','origin','action'}|({'nativeBundleProfileVersion'} if bundle_profile else set())|({'selectedArtifact'} if selected_profile else set())
        if (type(args) is not dict or set(args)!=expected or (bundle_profile and
                (type(args['nativeBundleProfileVersion']) is not int or args['nativeBundleProfileVersion'] not in (1,2) or args['action']!='ios-bundle-observe'))):raise LaunchError('request')
        binding=deepcopy(context(args['binding']));run=args['runId'];directory=args['resultsDirectory'];origin=args['origin'];action=args['action']
        if (binding['sessionId']!=session or type(run) is not str or re.fullmatch('[0-9a-f]{32}',run) is None
                or type(directory) is not str or len(directory)>128 or re.fullmatch('[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',directory) is None
                or action not in (('ios-bundle-observe',) if bundle_profile else ('feature-native-observe','feature-ios-lifecycle-world','native-geometry-snapshot'))
                or AppiumAdapter.normalized_http_origin(origin,'original native fixture')!=origin):raise LaunchError('request')
        loop=asyncio.get_running_loop();task=asyncio.current_task();source=self.source;rsd=self.scope(session)
        claim_owner=self.session;claim=deepcopy(self.session);touch=self.touch;resource=self.touch_resources
        if loop is not source._loop or not isinstance(task,asyncio.Task) or self.native_query_task is not None:raise LaunchError('session-lifetime')
        acquisition=self.native_acquisition
        if acquisition is not None and acquisition[0] is not task:raise LaunchError('session-lifetime')
        selected=None
        if selected_profile:
            # Reserve the EXISTING query owner before original FS/SDK awaits.
            # Concurrent requests cannot slip a second query into this birth.
            self.native_query_task=task
            try:selected=await self._selected_ipa_original(args['selectedArtifact'],binding,session)
            except BaseException:
                if self.native_query_task is task:self.native_query_task=None
                raise
        started=loop.time();deadline=started+1.5
        journal=None;issued_query=None;query=None;owns_task=selected_profile
        def current():
            if selected is not None:selected[1]()
            if acquisition is not None:
                if self.native_acquisition is not acquisition:raise LaunchError('session-lifetime')
                acquisition[1]()
            if (asyncio.get_running_loop() is not loop or self.source is not source or source._closing or self.closed or self.draining
                    or self.session is not claim_owner or self.session!=claim or self.scope(session) is not rsd
                    or self.touch is not touch or self.touch_resources is not resource or loop.time()>=deadline
                    or (owns_task and self.native_query_task is not task)):raise LaunchError('session-lifetime')
            if journal is not None:
                if self.native_query_journals.get(run) is not journal or journal['pending'] is not None or query!=issued_query:raise LaunchError('session-lifetime')
                with journal['lock'].held():
                    if journal['store'].read()!=journal['previous']:raise LaunchError('session-lifetime')
            if resource is not None and resource.version in (2,3):
                with resource.lock.held():resource.motion_current()
            if touch is not None:
                born=next((row for row in source._born if row['lease'] is touch),None)
                if (born is None or born['owner'] is None or born['worker'] is not touch.worker or born['loop'] is not loop
                        or born['release'] is not touch.request_release or touch.request_release.is_set()
                        or loop.time()>=touch._deadline() or touch.binding!=binding):raise LaunchError('session-lifetime')
                status=born['owner']._status()
                if not status['workerRunning'] or not status['hostResponsibility']:raise LaunchError('session-lifetime')
        try:current()
        except BaseException:
            if selected is not None:selected[3]['revoked']=True
            if self.native_query_task is task:self.native_query_task=None
            raise
        self.native_query_task=task;owns_task=True;thread=None;query=None;packet=None;record=None;store=None;lock=None;outcome={}
        def save():
            # A lost write/readback never grants adoption or delivery permission.
            # Retain the exact attempted envelope in THIS original owner.
            previous=journal['previous']
            with lock.held():
                if journal['pending'] is not None or store.read()!=previous:raise LaunchError('session-lifetime')
                attempted=deepcopy(packet);journal['pending']=attempted
                store.write(attempted,previous)
                if store.read()!=attempted:raise LaunchError('session-lifetime')
                journal['previous']=deepcopy(attempted);journal['pending']=None
        try:
            await self.fresh_touch_scope(binding);current()
            store=PrivateFeatureState(self.state_root/('ios-lifecycle-native-query-owner-'+run+'.json'))
            lock=ScriptSourceLock(self.state_root/'script-feature-sources.lock')
            journal=self.native_query_journals.get(run)
            if journal is None:
                if acquisition is not None:
                    owned=self.native_acquisition_journals.get(run)
                    if (owned is None or owned['source'] is not source or owned['rsd'] is not rsd or owned['loop'] is not loop
                            or owned['claim'] is not claim_owner or owned['binding']!=binding
                            or type(owned['lock']) is not ScriptSourceLock or owned['lock'].path!=lock.path):raise LaunchError('session-lifetime')
                    self._native_acquisition_current(owned,session)
                    # Reuse the ACTUAL existing source owner lock. A second
                    # object at this same file would self-contend in worker.
                    lock=owned['lock']
                # Never adopt a pre-existing JSON history as source ownership.
                with lock.held():
                    if store.read() is not None:raise LaunchError('session-lifetime')
                journal=dict(source=source,rsd=rsd,loop=loop,claim=claim_owner,binding=deepcopy(binding),
                    origin=origin,directory=directory,store=store,lock=lock,previous=None,pending=None)
                self.native_query_journals[run]=journal
            else:
                if (journal['source'] is not source or journal['rsd'] is not rsd or journal['loop'] is not loop
                        or journal['claim'] is not claim_owner or journal['binding']!=binding or journal['origin']!=origin
                        or journal['directory']!=directory or journal['pending'] is not None):raise LaunchError('session-lifetime')
                store=journal['store'];lock=journal['lock']
                with lock.held():
                    if store.read()!=journal['previous']:raise LaunchError('session-lifetime')
            packet=deepcopy(journal['previous']) if journal['previous'] is not None else dict(
                originalKeeperNativeQueryOwnerVersion=1,binding=deepcopy(binding),runId=run,ownerInstance=self.instance,records=[])
            if bundle_profile:packet['originalKeeperNativeQueryOwnerVersion']=3 if selected_profile else max(2,packet['originalKeeperNativeQueryOwnerVersion'])
            if len(packet['records'])>=32:raise LaunchError('session-lifetime')
            query=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action=action)
            if action=='feature-ios-lifecycle-world':query['runId']=run
            issued_query=deepcopy(query)
            record=dict(index=len(packet['records'])+1,query=deepcopy(query),origin=origin,resultsDirectory=directory,phase='intent',
                hostStartedMonotonic=started,hostDeadlineMonotonic=deadline)
            packet['records'].append(record);save();current()
            if selected is not None:journal.setdefault('selectedOriginals',{})[query['commandId']]=selected
            # All SDK/source/release checks execute on the ORIGINAL loop.
            # This local bridge never serializes a callable or queries SDK in
            # the HTTP worker. No new event loop/session/endpoint is created.
            bridges=[];finished=threading.Event()
            def worker_guard():
                future=Future();bridges.append(future)
                def check():
                    try:current();future.set_result(None)
                    except BaseException as error:future.set_exception(error)
                loop.call_soon_threadsafe(check)
                return future.result()
            def worker():
                try:
                    with transport_scope(worker_guard):send_original_command(origin,query,4096,before_send=worker_guard,after_send=worker_guard)
                    outcome['returned']=True
                except BaseException as error:outcome['error']=error
                finally:finished.set()
            thread=threading.Thread(target=worker,name='original-native-query',daemon=False)
            source._native_queries.append((task,thread,finished,loop))
            current();thread.start()
            # Waiting is responsibility, NOT accepted native acquisition. Never
            # cancel or mark a live/uncertain worker as completed on timeout.
            failure=None
            while thread.is_alive():
                try:await asyncio.sleep(.01)
                except BaseException as error:failure=failure or error
            if thread.ident is not None:thread.join(timeout=0)
            if not finished.is_set() or any(not future.done() for future in bridges):raise LaunchError('session-lifetime')
            record['phase']='http-returned' if outcome.get('returned') is True else 'http-uncertain'
            save()
            if failure is not None:raise failure
            if 'error' in outcome:raise outcome['error']
            current();await self.fresh_touch_scope(binding);current()
            if selected is not None:selected[3]['queryReturned']=True
            return dict(originalKeeperNativeQueryVersion=(3 if selected_profile else 2) if bundle_profile else 1,ownerInstance=self.instance,index=record['index'],query=deepcopy(issued_query),
                queryIntentOwned=True,httpReturnObserved=True,nativeDeliveryAcknowledged=False,freshNativeAcquisitionEstablished=False,
                installedCandidateBound=False,nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)
        finally:
            if selected is not None and not selected[3].get('queryReturned'):selected[3]['revoked']=True
            if thread is not None:
                while thread.is_alive():
                    try:await asyncio.sleep(.01)
                    except BaseException:pass
                if thread.ident is not None:thread.join(timeout=0)
            if self.native_query_task is task:self.native_query_task=None

    async def native_original_read(self,args,session):
        """Read a fixed native original through THIS original RSD/provider.

        The caller's nonce is correlation only: this method does not own its
        HTTP query issuance and CANNOT establish a fresh native acquisition,
        installed-candidate binding, motion permit or resource retirement.
        """
        from pymobiledevice3.services.house_arrest import HouseArrestService
        from copy import deepcopy
        import hashlib
        from adapters.normal_feature_state import context
        from adapters.native_feature_observation import decode,validate as native_packet
        from ios.adapters import lifecycle_world as world,native_geometry
        bundle_profile=type(args) is dict and 'nativeBundleProfileVersion' in args
        expected={'binding','runId','resultsDirectory','query'}|({'nativeBundleProfileVersion'} if bundle_profile else set())
        if (type(args) is not dict or set(args)!=expected or (bundle_profile and
                (type(args['nativeBundleProfileVersion']) is not int or args['nativeBundleProfileVersion'] not in (1,2)))):
            raise LaunchError('request')
        binding=deepcopy(context(args['binding']));query=deepcopy(args['query']);directory=args['resultsDirectory']
        if (binding['sessionId']!=session or type(args['runId']) is not str or re.fullmatch('[0-9a-f]{32}',args['runId']) is None
                or type(directory) is not str or len(directory)>128 or re.fullmatch('[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',directory) is None
                or type(query) is not dict or type(query.get('schemaVersion')) is not int or query['schemaVersion']!=1
                or type(query.get('commandId')) is not str or re.fullmatch('ios-[0-9a-f]{32}',query['commandId']) is None):
            raise LaunchError('request')
        action=query.get('action')
        if bundle_profile:
            from ios.adapters import bundle_observation
            bundle_observation.command(query);filename=bundle_observation.FILE;limit=262144
        elif action==world.ACTION:
            world.command(query)
            if query['runId']!=args['runId']:raise LaunchError('request')
            filename=world.FILE;limit=world.LIMIT
        elif action in ('feature-native-observe','native-geometry-snapshot') and set(query)=={'schemaVersion','commandId','action'}:
            filename='feature-native-observation.json' if action=='feature-native-observe' else 'ios-ui-request-result.json'
            limit=262144 if action=='feature-native-observe' else 65536
        else:raise LaunchError('request')
        loop=asyncio.get_running_loop();task=asyncio.current_task()
        if loop is not self.source._loop or not isinstance(task,asyncio.Task):raise LaunchError('session-lifetime')
        original_source=self.source;rsd=self.scope(session);original_claim=self.session;claim=deepcopy(self.session);touch=self.touch;resource=self.touch_resources
        acquisition=self.native_acquisition
        if acquisition is not None and acquisition[0] is not task:raise LaunchError('session-lifetime')
        started=loop.time();deadline=started+1.5
        query_journal=None;query_previous=None;selected=None
        selected_profile=bundle_profile and args['nativeBundleProfileVersion']==2
        if bundle_profile:
            query_journal=self.native_query_journals.get(args['runId'])
            if (query_journal is None or query_journal['source'] is not original_source or query_journal['rsd'] is not rsd
                    or query_journal['loop'] is not loop or query_journal['claim'] is not original_claim
                    or query_journal['binding']!=binding or query_journal['directory']!=directory or query_journal['pending'] is not None):
                raise LaunchError('session-lifetime')
            query_previous=deepcopy(query_journal['previous'])
            if (query_previous is None or query_previous['originalKeeperNativeQueryOwnerVersion'] not in (2,3)
                    or not any(row['query']==query and row['phase']=='http-returned' for row in query_previous['records'])):
                raise LaunchError('session-lifetime')
        if (bundle_profile and not selected_profile and query['commandId'] in query_journal.get('selectedOriginals',{})):
            # An actual selected-IPA query cannot be downgraded to raw-only
            # bundle profile1 by omitting the original selected guard.
            raise LaunchError('request')
        if selected_profile:
            selected=query_journal.get('selectedOriginals',{}).get(query['commandId'])
            if type(selected) is not tuple or len(selected)!=4 or not selected[3].get('queryReturned'):raise LaunchError('session-lifetime')
            selected[1]()
        def current():
            try:
                if selected is not None:
                    if query_journal.get('selectedOriginals',{}).get(query['commandId']) is not selected:raise LaunchError('session-lifetime')
                    selected[1]()
                if query_journal is not None:
                    if (self.native_query_journals.get(args['runId']) is not query_journal or query_journal['pending'] is not None
                            or query_journal['previous']!=query_previous):raise LaunchError('session-lifetime')
                    with query_journal['lock'].held():
                        if query_journal['store'].read()!=query_previous:raise LaunchError('session-lifetime')
                if acquisition is not None:
                    if self.native_acquisition is not acquisition:raise LaunchError('session-lifetime')
                    acquisition[1]()
                if (asyncio.get_running_loop() is not loop or self.source is not original_source or original_source._closing or self.draining or self.closed
                        or self.session is not original_claim or self.session!=claim or self.scope(session) is not rsd or self.touch is not touch
                        or self.touch_resources is not resource or loop.time()>=deadline):raise LaunchError('session-lifetime')
                if resource is not None and resource.version in (2,3):
                    with resource.lock.held():resource.motion_current()
                if touch is not None:
                    born=next((row for row in self.source._born if row['lease'] is touch),None)
                    if (born is None or born['owner'] is None or born['loop'] is not loop or born['worker'] is not touch.worker
                            or born['release'] is not touch.request_release or touch.request_release.is_set()
                            or loop.time()>=touch._deadline() or touch.binding!=binding):raise LaunchError('session-lifetime')
                    status=born['owner']._status()
                    if not status['workerRunning'] or not status['hostResponsibility']:raise LaunchError('session-lifetime')
            except BaseException:
                if selected is not None:selected[3]['revoked']=True
                raise
        async def fresh_scope():
            try:await self.fresh_touch_scope(binding)
            except BaseException:
                if selected is not None:selected[3]['revoked']=True
                raise
        current();await fresh_scope();current()
        if len(original_source._native_reads)>=32:raise LaunchError('request')
        service=HouseArrestService(rsd,documents_only=False);close=service.aclose;closed=asyncio.Event()
        # The ORIGINAL service/task/close are retained BEFORE its first await.
        # This is local lifetime responsibility, never a serialized capability.
        row=(service,close,task,loop,closed,asyncio.Lock());original_source._native_reads.append(row)
        handle=None;failure=None;raw=None
        try:
            # Vend plist MUST precede __aenter__: AFC entry starts its demux
            # reader, which must never race the original HouseArrest handshake.
            current();await service.send_command(claim['archiveBundleId'],'VendContainer');current()
            actual=await service.__aenter__();current()
            if actual is not service:raise LaunchError('session-lifetime')
            path='/Documents/'+directory+'/'+filename
            before=await service.stat(path);current()
            if (type(before) is not dict or before.get('st_ifmt')!='S_IFREG' or before.get('st_nlink')!=1
                    or type(before.get('st_size')) is not int or not 2<=before['st_size']<=limit):raise LaunchError('request')
            handle=await service.fopen(path,'r');current()
            raw=await service.fread(handle,before['st_size']);current()
            after=await service.stat(path);current()
            if type(raw) is not bytes or len(raw)!=before['st_size'] or before!=after:raise LaunchError('request')
            text=raw.decode('utf-8');packet=decode(text,limit=limit)
            if bundle_profile:
                bundle_observation.validate(packet,query,int(binding['processIdentity']))
                if selected is not None:
                    from ios.adapters.bundle_identity import compare
                    if packet['status']!='ready':raise LaunchError('session-lifetime')
                    compare(packet['bundle'],selected[2])
            elif action==world.ACTION:world.validate(packet,query,int(binding['processIdentity']))
            elif action=='feature-native-observe':native_packet(packet,query['commandId'],int(binding['processIdentity']),packet['capturedEpochMs'])
            else:native_geometry.validate(packet,query['commandId'],native_epoch_ms=packet['observation']['sampleEpochMs'])
            current()
        except BaseException as error:
            if selected is not None:selected[3]['revoked']=True
            failure=error;raise
        finally:
            try:
                try:
                    # AFC.fclose lazily calls connect(); do not recreate a
                    # service if its original connection has already vanished.
                    if handle is not None and service._service is not None:await service.fclose(handle)
                finally:
                    # Original SDK AFC-reader cancellation is its actual close
                    # contract; it is never a touch Up or native-end proof.
                    if not await original_source._close_native_read(row):
                        raise LaunchError('session-lifetime')
            except BaseException:
                if selected is not None:selected[3]['revoked']=True
                if failure is None:raise
                failure.add_note('Original native file cleanup is unresolved; original Source responsibility retained.')
        current();await fresh_scope();current()
        result=dict(originalKeeperNativeFileVersion=(3 if selected_profile else 2) if bundle_profile else 1,ownerInstance=self.instance,source='original-rsd-house-arrest',
            action=action,requestId=query['commandId'],rawJson=text,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            queryIssuanceOwned=False,freshNativeAcquisitionEstablished=False,installedCandidateBound=False,
            physicalFileIdentityEstablished=False,nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)
        if len(json.dumps(result,separators=(',',':'),ensure_ascii=True).encode('ascii'))>12000:
            if selected is not None:selected[3]['revoked']=True
            raise LaunchError('request')
        return result

    def _native_motion_window_function(self):return WdaServiceClient._request_json

    def _native_acquisition_owner(self,binding,run,session):
        from copy import deepcopy
        from adapters.normal_feature_state import PrivateFeatureState,context
        from adapters.script_feature.lock import ScriptSourceLock
        if (context(binding)['sessionId']!=session or type(run) is not str or re.fullmatch('[0-9a-f]{32}',run) is None
                or asyncio.get_running_loop() is not self.source._loop):raise LaunchError('session-lifetime')
        source=self.source;rsd=self.scope(session);loop=source._loop;claim=self.session;claim_value=deepcopy(claim)
        journal=self.native_acquisition_journals.get(run)
        if journal is None:
            store=PrivateFeatureState(self.state_root/('ios-lifecycle-native-acquisition-'+run+'.json'))
            lock=ScriptSourceLock(self.state_root/'script-feature-sources.lock')
            query_owner=self.native_query_journals.get(run)
            if query_owner is not None:
                if (query_owner['source'] is not source or query_owner['rsd'] is not rsd or query_owner['loop'] is not loop
                        or query_owner['claim'] is not claim or query_owner['binding']!=binding or query_owner['pending'] is not None
                        or type(query_owner['lock']) is not ScriptSourceLock or query_owner['lock'].path!=lock.path
                        or self.native_query_task is not None and self.native_query_task is not asyncio.current_task()):
                    raise LaunchError('session-lifetime')
                lock=query_owner['lock']
                with lock.held():
                    if query_owner['store'].read()!=query_owner['previous']:raise LaunchError('session-lifetime')
            with lock.held():
                if store.read() is not None:raise LaunchError('session-lifetime')
            journal=dict(source=source,rsd=rsd,loop=loop,claim=claim,claimValue=claim_value,binding=deepcopy(binding),
                run=run,store=store,lock=lock,previous=None,unacknowledged=None)
            self.native_acquisition_journals[run]=journal
        elif (journal['source'] is not source or journal['rsd'] is not rsd or journal['loop'] is not loop
                or journal['claim'] is not claim or journal['claimValue']!=claim or journal['binding']!=binding):raise LaunchError('session-lifetime')
        self._native_acquisition_current(journal,session)
        if journal['previous'] is None:
            self._native_acquisition_save(journal,dict(originalKeeperNativeAcquisitionOwnerVersion=1,
                binding=deepcopy(binding),runId=run,ownerInstance=self.instance,frames=[],pending=None))
        return journal

    def _native_acquisition_current(self,journal,session):
        if (asyncio.get_running_loop() is not journal['loop'] or self.source is not journal['source']
                or self.source._closing or self.closed or self.draining or self.session is not journal['claim']
                or self.session!=journal['claimValue'] or self.scope(session) is not journal['rsd']
                or self.native_acquisition_journals.get(journal['run']) is not journal or journal['unacknowledged'] is not None):
            raise LaunchError('session-lifetime')
        with journal['lock'].held():
            if journal['store'].read()!=journal['previous']:raise LaunchError('session-lifetime')

    def _native_acquisition_save(self,journal,value):
        from copy import deepcopy
        with journal['lock'].held():
            if journal['unacknowledged'] is not None or journal['store'].read()!=journal['previous']:raise LaunchError('session-lifetime')
            attempted=deepcopy(value);journal['unacknowledged']=attempted
            journal['store'].write(attempted,journal['previous'])
            if journal['store'].read()!=attempted:raise LaunchError('session-lifetime')
            journal['previous']=deepcopy(attempted);journal['unacknowledged']=None

    def _native_acquisition_files(self,journal,guard):
        from copy import deepcopy
        from adapters.original_frame_store import OriginalFrameStore
        def intent(kind,reference):
            if kind!='original':raise LaunchError('request')
            value=deepcopy(journal['previous']);old=value['pending']
            if old is None:
                if reference['phase']!='planned' or reference['index']!=len(value['frames'])+1:raise LaunchError('request')
            elif (reference['phase']!={'planned':'opened','opened':'saved'}.get(old['phase'])
                    or any(old[key]!=reference[key] for key in old if key not in ('phase','file'))
                    or (old['phase']!='planned' and reference['file']!=old['file'])):raise LaunchError('request')
            value['pending']=deepcopy(reference)
            task=asyncio.current_task();cut=self.native_current_cuts.get(task)
            if cut is not None and len(cut)==6:
                from ios.adapters.lifecycle_touch_resource_owner import _NativeMotionWorkerGuard,_NativeMotionPendingWrite
                step=cut[4]
                if (type(step) is not _NativeMotionWorkerGuard or type(step._pending_write) is not _NativeMotionPendingWrite
                        or step._pending_write._files() is not files):raise LaunchError('session-lifetime')
                step._pending_write.record(reference)
            self._native_acquisition_save(journal,value)
        files=OriginalFrameStore(self.state_root,journal['binding'],journal['run'],'primary',guard,intent,
            namespace='lifecycle-native-acquisition',schema_prefix='iosLifecycleNativeAcquisition')
        return files

    async def native_acquire(self,args,session,*,_motion_window=False,_current_resource=None):
        """Four actual owned query/file pairs; immutable raw originals, no motion."""
        from copy import deepcopy
        from adapters.native_feature_observation import decode
        from adapters.native_clock_join import validate_join,digest
        from adapters.normal_feature_state import context
        from adapters.script_feature.history import canonical
        from ios.adapters import lifecycle_world as world,native_geometry
        from ios.adapters.lifecycle_world_attempt import source_frame_original
        selected_profile=_motion_window and type(args) is dict and 'selectedQueryId' in args
        expected={'binding','runId','resultsDirectory','origin'}|({'selectedQueryId'} if selected_profile else set())
        if type(args) is not dict or set(args)!=expected:raise LaunchError('request')
        from ios.adapters.appium_adapter import AppiumAdapter
        args=deepcopy(args);selected_id=args.pop('selectedQueryId') if selected_profile else None
        if selected_profile and (type(selected_id) is not str or re.fullmatch('ios-[0-9a-f]{32}',selected_id) is None):raise LaunchError('request')
        binding=deepcopy(context(args['binding']));run=args['runId']
        directory=args['resultsDirectory'];origin=args['origin']
        if (type(directory) is not str or len(directory)>128 or re.fullmatch('[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*',directory) is None
                or AppiumAdapter.normalized_http_origin(origin,'original native fixture')!=origin):raise LaunchError('request')
        loop=asyncio.get_running_loop();task=asyncio.current_task()
        if self.native_acquisition is not None or not isinstance(task,asyncio.Task):raise LaunchError('session-lifetime')
        current_cut=None;worker_step=None;pending_write=None
        if _current_resource is not None:
            from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner
            current_cut=self.native_current_cuts.get(task)
            if (not _motion_window or not selected_profile or type(_current_resource) is not LifecycleTouchResourceOwner
                    or _current_resource is not self.touch_resources or _current_resource.version!=4
                    or current_cut is None or current_cut[0] is not _current_resource
                    or _current_resource.state['selectedQueryId']!=selected_id):raise LaunchError('session-lifetime')
            _current_resource.file_guard()
            if len(current_cut)==6:
                from ios.adapters.lifecycle_touch_resource_owner import _NativeMotionWorkerGuard
                worker_step=current_cut[4]
                if type(worker_step) is not _NativeMotionWorkerGuard or _current_resource._native_step is not worker_step:raise LaunchError('session-lifetime')
                worker_step.scope()
            elif len(current_cut)!=4:raise LaunchError('session-lifetime')
        journal=self._native_acquisition_owner(binding,run,session);touch=self.touch;resource=self.touch_resources
        selected=None;selected_owner=None
        if selected_profile:
            selected_owner=self.native_query_journals.get(run)
            if (selected_owner is None or selected_owner['source'] is not journal['source'] or selected_owner['rsd'] is not journal['rsd']
                    or selected_owner['loop'] is not loop or selected_owner['binding']!=binding or selected_owner['pending'] is not None):raise LaunchError('session-lifetime')
            selected=selected_owner.get('selectedOriginals',{}).get(selected_id)
            if (type(selected) is not tuple or len(selected)!=4 or not selected[3].get('queryReturned')
                    or type(selected[3].get('capture')) is not weakref.ReferenceType):raise LaunchError('session-lifetime')
            selected_capture=selected[3]['capture']()
            if (not isinstance(selected_capture,asyncio.Task) or selected_capture.get_loop() is not loop or not selected_capture.done()
                    or selected_capture.cancelled() or selected_capture.exception() is not None):raise LaunchError('session-lifetime')
            selected[1]()
        if _motion_window:
            creator=journal['source']._creator_task()
            if (((worker_step is None and (touch is not None or journal['source']._leases or journal['source']._born))
                    or (resource is not None and resource is not _current_resource))
                    or not isinstance(creator,asyncio.Task) or creator.done() or creator.get_loop() is not loop
                    or not isinstance(self.wda,asyncio.Task) or self.wda.done() or self.wda.get_loop() is not loop
                    or self.wda_session is None or not self.wda_binding_claimed):raise LaunchError('session-lifetime')
        if journal['previous']['pending'] is not None or len(journal['previous']['frames'])>=8:raise LaunchError('session-lifetime')
        started=loop.time();epoch=time.time()*1000;deadline=started+1.5;token=None
        if current_cut is not None:started,epoch,deadline=current_cut[1:4]
        def current():
            if current_cut is not None:
                if self.native_current_cuts.get(task) is not current_cut:raise LaunchError('session-lifetime')
                _current_resource.file_guard()
                if worker_step is not None:worker_step.scope()
            if selected is not None:
                if (self.native_query_journals.get(run) is not selected_owner
                        or selected_owner.get('selectedOriginals',{}).get(selected_id) is not selected):raise LaunchError('session-lifetime')
                selected[1]()
            self._native_acquisition_current(journal,session)
            if (self.native_acquisition is not token or self.touch is not touch or self.touch_resources is not resource
                    or task.done() or loop.time()>=deadline):raise LaunchError('session-lifetime')
        token=(task,current);self.native_acquisition=token
        reads=[]
        try:
            async def original(action):
                current();profile={'nativeBundleProfileVersion':1} if action=='ios-bundle-observe' else {}
                issued=await self.native_query(dict(args,action=action,**profile),session);current()
                # This is the actual ORIGINAL source-built live nonce journal,
                # not a nonce accepted from JSON as ownership authority.
                owner=self.native_query_journals[run];record=owner['previous']['records'][issued['index']-1]
                if (owner['source'] is not journal['source'] or owner['rsd'] is not journal['rsd']
                        or owner['loop'] is not loop or record['query']!=issued['query'] or record['phase']!='http-returned'):
                    raise LaunchError('session-lifetime')
                value=await self.native_original_read(dict(binding=binding,runId=run,
                    resultsDirectory=args['resultsDirectory'],query=deepcopy(record['query']),**profile),session);current()
                reads.append(dict(query=deepcopy(record['query']),queryIndex=issued['index'],original=deepcopy(value)))
                return decode(value['rawJson'],limit=262144)
            first=await original('feature-native-observe')
            geometry=await original('native-geometry-snapshot')
            sdk_window=None;window_task=None;window_function=None
            if _motion_window:
                from copy import deepcopy
                from adapters.native_feature_observation import number
                await self.fresh_touch_scope(binding);current()
                wda=self.wda;wda_session=self.wda_session;client=WdaServiceClient(journal['rsd'],port=8100,timeout=2.0)
                read=client._request_json;window_function=self._native_motion_window_function()
                if read.__self__ is not client or read.__func__ is not window_function:raise LaunchError('session-lifetime')
                path='/session/'+quote(wda_session,safe='')+'/window/rect';before=loop.time()
                window_task=asyncio.create_task(read('GET',path),name='original-native-motion-window')
                failure=None
                # SDK's timeout attribute is not an enforced deadline. Keep
                # THIS actual operation Task alive until its original return.
                while not window_task.done():
                    try:await asyncio.shield(window_task)
                    except BaseException as error:failure=failure or error
                reply=deepcopy(window_task.result())
                if failure is not None:raise failure
                current();await self.fresh_touch_scope(binding);current()
                if (self.wda is not wda or self.wda_session!=wda_session or wda.done()
                        or self._native_motion_window_function() is not window_function):raise LaunchError('session-lifetime')
                rect=reply.get('value') if type(reply) is dict else None
                if (type(rect) is not dict or set(rect)!={'x','y','width','height'}
                        or not all(number(rect[k],-10000,10000) for k in ('x','y'))
                        or not all(number(rect[k],1,10000) for k in ('width','height'))):raise LaunchError('request')
                sdk_window=dict(method='GET',path=path,reply=reply,hostBeforeMonotonic=before,hostAfterMonotonic=loop.time())
            bundle=None;selected_read=None
            if selected is not None:
                from ios.adapters.bundle_observation import validate as validate_bundle
                from ios.adapters.bundle_identity import compare
                bundle=await original('ios-bundle-observe');selected_read=deepcopy(reads[-1])
                validate_bundle(bundle,selected_read['query'],int(binding['processIdentity']))
                if bundle['status']!='ready':raise LaunchError('session-lifetime')
                compare(bundle['bundle'],selected[2]);current()
            packet=await original(world.ACTION)
            last=await original('feature-native-observe');current()
            if bundle is not None and not first['capturedEpochMs']<=bundle['capturedEpochMs']<=last['capturedEpochMs']:raise LaunchError('request')
            originals=dict(world=packet,worldClock=dict(capturedEpochMs=packet['clockAfter']['epochMs']),geometry=geometry)
            if _motion_window:originals['window']=deepcopy(sdk_window['reply']['value'])
            joined=dict(clockJoinVersion=1,hostBeforeEpochMs=epoch,hostAfterEpochMs=time.time()*1000,
                hostBeforeMonotonic=started,hostAfterMonotonic=loop.time(),nativeBefore=first,nativeAfter=last,
                sourceTimes=[dict(source='worldClock',field='capturedEpochMs',epochMs=packet['clockAfter']['epochMs'])],
                originalsSha256=digest(originals))
            validate_join(joined,originals);source_frame_original(dict(originals=originals,clockJoin=joined),binding,run)
            native_geometry.validate(geometry,geometry['commandId'],native_epoch_ms=last['capturedEpochMs'])
            if not first['capturedEpochMs']<=geometry['observation']['sampleEpochMs']<=packet['clockBefore']['epochMs']:
                raise LaunchError('request')
            current();files=self._native_acquisition_files(journal,current)
            # Canonical frame retains exact RAW file strings and their original
            # byte hashes as well as typed join. Aggregate bytes stay on disk;
            # no result/pipe cap is enlarged or original truncated.
            frame=dict(originalKeeperNativeAcquisitionFrameVersion=(3 if selected is not None else 2) if _motion_window else 1,originals=originals,clockJoin=joined,reads=reads)
            if _motion_window:frame['sdkWindow']=sdk_window
            if selected is not None:frame['selectedCandidate']=dict(originalKeeperSelectedMotionCandidateVersion=1,selectionQueryId=selected_id,
                bundleRead=selected_read,selectedArtifactBundle=deepcopy(selected[2]),reads=deepcopy(reads))
            if worker_step is not None:
                from ios.adapters.lifecycle_touch_resource_owner import _NativeMotionPendingWrite
                pending_write=_NativeMotionPendingWrite(worker_step,task,current_cut,token,journal,files,len(journal['previous']['frames'])+1,frame)
                worker_step._pending_write=pending_write
            reference=files.write(len(journal['previous']['frames'])+1,frame);current()
            value=deepcopy(journal['previous']);value['frames'].append(reference);value['pending']=None
            self._native_acquisition_save(journal,value);current();files.read(files.expand(reference));current()
            if _motion_window:
                from ios.adapters.lifecycle_touch_resource_owner import _NativeMotionReference
                receipt=_NativeMotionReference(self,journal,reference,window_task,window_function,started,selected=selected,selected_id=selected_id)
                if current_cut is not None:receipt._target=weakref.ref(_current_resource)
                if worker_step is not None:receipt._worker_guard=worker_step;receipt._worker_phase=current_cut[5]
            payload=canonical(dict(binding=binding,runId=run,reference=reference)).decode('ascii')
            result=dict(originalKeeperNativeAcquisitionVersion=(3 if selected is not None else 2) if _motion_window else 1,ownerInstance=self.instance,encoding='canonical-json-ascii',
                acquisitionJson=payload,nativeAcquisitionBound=False,installedCandidateBound=False,nativeMotionGuardAvailable=False,
                nativeTouchSupport=False,resourceRetirementEstablished=False)
            if len(json.dumps(result,separators=(',',':'),ensure_ascii=True).encode('ascii'))>12000:raise LaunchError('request')
            current()
            if _motion_window:journal.setdefault('motionOriginals',{})[reference['sha256']]=receipt
            return receipt if current_cut is not None else result
        except BaseException:
            if selected is not None:selected[3]['revoked']=True
            raise
        finally:
            # Nested original query/file helpers retain and await their actual
            # HTTP Thread/AFC close even on cancellation or scope/deadline loss.
            if worker_step is not None and worker_step._pending_write is pending_write:worker_step._pending_write=None
            if self.native_acquisition is token:self.native_acquisition=None

    def motion_worker_lease(self,resource):
        """Private local source integration; no RPC/configuration capability."""
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner,_NativeMotionWorkerGuard
        if (type(resource) is not LifecycleTouchResourceOwner or resource is not self.touch_resources
                or self.touch is not None or self.source._born or self.source._leases):raise LaunchError('session-lifetime')
        with resource.lock.held():
            step=_NativeMotionWorkerGuard(resource,self.source,self)
            try:
                lease=self.source.touch_lease(PrivateFeatureState(resource.store.path.with_name('ios-lifecycle-touch-lease-'+resource.run+'.json')),
                    binding=resource.binding,run=resource.run,check=step.continuity,resource_owner=resource)
                self.touch=lease;step.scope();return lease
            except BaseException:
                step.fail();raise

    async def native_motion_step(self,resource,step,phase):
        """OWN native original interval at each actual Down/Move boundary."""
        from copy import deepcopy
        from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner,_NativeMotionWorkerGuard,_NativeMotionReference
        from ios.adapters import lifecycle_world as world,native_geometry
        if (type(resource) is not LifecycleTouchResourceOwner or type(step) is not _NativeMotionWorkerGuard
                or resource._native_step is not step or phase not in ('before-down','after-down')
                or asyncio.current_task() is not step._worker()):raise LaunchError('session-lifetime')
        step.scope();lease=step._lease()
        if ((phase=='before-down' and (lease.down_issued or lease.previous['phase']!='down-issued'))
                or (phase=='after-down' and (not lease.down_issued or lease.up_issued))):raise LaunchError('session-lifetime')
        loop=asyncio.get_running_loop();started=loop.time();epoch=time.time()*1000;deadline=min(started+1.5,lease._deadline())
        original=resource._motion_original
        try:
            anchor=original.anchor(self.source,resource,self.instance);step.scope()
            owner=self.native_query_journals[resource.run]
            args=dict(binding=deepcopy(resource.binding),runId=resource.run,resultsDirectory=owner['directory'],origin=owner['origin'],selectedQueryId=resource.state['selectedQueryId'])
            if len(self.source._native_current_tasks)>=8 or any(not t.done() for t in self.source._native_current_tasks):raise LaunchError('session-lifetime')
            async def acquire():
                try:return await self.native_acquire(args,resource.binding['sessionId'],_motion_window=True,_current_resource=resource)
                finally:self.native_current_cuts.pop(asyncio.current_task(),None)
            task=asyncio.create_task(acquire(),name='original-native-motion-'+phase)
            self.native_current_cuts[task]=(resource,started,epoch,deadline,step,phase)
            self.source._native_current_tasks.append(task);self.operations.add(task);task.add_done_callback(self.operations.discard)
            done,_=await asyncio.wait({task},timeout=max(0.,deadline-loop.time()))
            if task not in done:raise LaunchError('session-lifetime')
            receipt=task.result()
            if type(receipt) is not _NativeMotionReference:raise LaunchError('session-lifetime')
            current=receipt.original(self.source,resource,self.instance);step.scope()
            old,new=anchor['originals']['world'],current['originals']['world']
            if world.context(old)!=world.context(new) or anchor['originals']['window']!=current['originals']['window']:raise LaunchError('session-lifetime')
            geometry=[]
            for frame in (anchor,current):
                raw=frame['originals']['geometry'];doc,view=native_geometry.validate(raw,raw['commandId'],native_epoch_ms=frame['clockJoin']['nativeAfter']['capturedEpochMs'])
                geometry.append((doc['nativeUi'],doc['window'],view))
            if geometry[0]!=geometry[1]:raise LaunchError('session-lifetime')
            a,b=world.touch.pad(old['source']['pad']),world.touch.pad(new['source']['pad'])
            if (a is None or b is None or not b['active'] or not b['enabled'] or b['hidden'] or not b['fixed']
                    or any(a[k]!=b[k] for k in ('objectId','viewport','fixed','center','radius'))):raise LaunchError('session-lifetime')
            facts=world.measure(old,new)
            if facts['heldInputs'] or facts['worldDisplacement']>.025 or any(new['source']['drive']['raw']):raise LaunchError('session-lifetime')
            if phase=='before-down':
                if b['moveValid'] or new['source']['touch']['active']:raise LaunchError('session-lifetime')
            else:
                contact=world.contact_attempt(old,new)
                if (new['source']['touch']['active']!=[contact['contactId']] or contact['ended'] is not None
                        or contact['route']!='world' or contact['lastRoute']!='world' or not b['moveValid']
                        or contact['nativeId']!=b['moveNativeId'] or b['moveOrigin']!=a['center']
                        or contact['position']!=b['movePoint']
                        or any(abs(x-y)>1 for x,y in zip(contact['position'],a['center']))):raise LaunchError('session-lifetime')
                events=[e for e in new['source']['touch']['events'] if any(p['id']==contact['contactId'] for p in e['points'])]
                if not events or any(e['route']!='world' for e in events):raise LaunchError('session-lifetime')
                step._contact=contact['contactId']
            if loop.time()>=deadline:raise LaunchError('session-lifetime')
            return receipt
        except BaseException:
            step.fail();raise

    async def native_before_down(self,resource):
        """Real fresh native cut, still NO worker/input/Down permission.

        Identity/historical intent survive an old preparation interval; ALL
        current facts below are newly acquired on the original Source loop.
        """
        from copy import deepcopy
        from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner,_NativeMotionReference
        from ios.adapters.lifecycle_world_hold import coordinates
        from ios.adapters import lifecycle_world as world
        if (type(resource) is not LifecycleTouchResourceOwner or resource.version!=4 or self.touch_resources is not resource
                or self.touch is not None or self.source._born or self.source._leases
                or type(resource._motion_original) is not _NativeMotionReference
                or resource._motion_original._owner() is not self or resource._motion_original._source() is not self.source
                or type(getattr(self.source,'_native_current_tasks',None)) is not list
                or len(self.source._native_current_tasks)>=8 or any(not task.done() for task in self.source._native_current_tasks)):
            raise LaunchError('session-lifetime')
        resource.file_guard();loop=asyncio.get_running_loop();started=loop.time();epoch=time.time()*1000;deadline=started+1.5
        original=resource._motion_original;task=None
        try:
            # This is an immutable intent anchor, NOT a claim of current time.
            anchor=original.anchor(self.source,resource,self.instance)
            query_owner=self.native_query_journals.get(resource.run)
            if (query_owner is None or query_owner.get('selectedOriginals',{}).get(resource.state['selectedQueryId']) is not original._selected
                    or loop is not self.source._loop or loop.time()>=deadline):raise LaunchError('session-lifetime')
            args=dict(binding=deepcopy(resource.binding),runId=resource.run,resultsDirectory=query_owner['directory'],
                origin=query_owner['origin'],selectedQueryId=resource.state['selectedQueryId'])
            async def acquire_original_current():
                try:return await self.native_acquire(args,resource.binding['sessionId'],_motion_window=True,_current_resource=resource)
                finally:self.native_current_cuts.pop(asyncio.current_task(),None)
            task=asyncio.create_task(acquire_original_current(),name='original-native-before-down-cut')
            self.native_current_cuts[task]=(resource,started,epoch,deadline)
            # Actual ownership BEFORE first SDK await. Timeout/caller cancel is
            # never original task/SDK completion; original Source waits later.
            self.source._native_current_tasks.append(task);self.operations.add(task);task.add_done_callback(self.operations.discard)
            done,_=await asyncio.wait({task},timeout=max(0.,deadline-loop.time()))
            if task not in done:raise LaunchError('session-lifetime')
            receipt=task.result()
            if type(receipt) is not _NativeMotionReference:raise LaunchError('session-lifetime')
            current=receipt.original(self.source,resource,self.instance);resource.file_guard()
            old,new=anchor['originals']['world'],current['originals']['world']
            if (coordinates(anchor)!=coordinates(current) or world.context(old)!=world.context(new)
                    or old['source']['pad'] is None or new['source']['pad'] is None):raise LaunchError('session-lifetime')
            pad=world.touch.pad(new['source']['pad'])
            if (not pad['active'] or not pad['enabled'] or pad['hidden'] or not pad['fixed'] or pad['moveValid']
                    or new['source']['touch']['active']):raise LaunchError('session-lifetime')
            measured=world.measure(old,new)
            if measured['heldInputs'] or measured['worldDisplacement']>.025 or loop.time()>=deadline:raise LaunchError('session-lifetime')
            # Opaque local source receipt, no JSON/callback/True substitution.
            # Resource.make_lease4 intentionally remains CLOSED separately.
            return receipt
        except BaseException:
            original.revoke();resource._motion_failed=True
            raise

    def native_acquisition_read(self,args,session):
        """Historical immutable FD bytes; never a fresh native query/verdict."""
        import base64,hashlib,os
        from copy import deepcopy
        from adapters.script_feature.history import canonical
        if (type(args) is not dict or set(args)!={'binding','runId','referenceJson','offset'}
                or type(args['referenceJson']) is not str or len(args['referenceJson'])>2048
                or type(args['offset']) is not int or args['offset']<0):raise LaunchError('request')
        # Reuse existing strict duplicate/constant-free owner request parser.
        reference=decode_owner_packet(args['referenceJson'])
        if args['runId'] not in self.native_acquisition_journals:raise LaunchError('session-lifetime')
        journal=self._native_acquisition_owner(args['binding'],args['runId'],session)
        if reference not in journal['previous']['frames']:raise LaunchError('request')
        def current():self._native_acquisition_current(journal,session)
        files=self._native_acquisition_files(journal,current);full=files.expand(reference)
        files.read(full);path=files.path(full);offset=args['offset']
        if offset>=reference['bytes'] or offset%4096:raise LaunchError('request')
        current();descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            files.file(path,stream.fileno(),full);stream.seek(offset);chunk=stream.read(min(4096,reference['bytes']-offset))
            files.file(path,stream.fileno(),full)
        current();files.read(full);current()
        if len(chunk)!=min(4096,reference['bytes']-offset):raise LaunchError('request')
        payload=canonical(dict(reference=reference,offset=offset,contentBase64=base64.b64encode(chunk).decode('ascii'))).decode('ascii')
        result=dict(originalKeeperNativeAcquisitionReadVersion=1,ownerInstance=self.instance,encoding='canonical-json-ascii',
            originalJson=payload,nativeAcquisitionBound=False,installedCandidateBound=False,nativeMotionGuardAvailable=False,
            nativeTouchSupport=False,resourceRetirementEstablished=False)
        if len(json.dumps(result,separators=(',',':'),ensure_ascii=True).encode('ascii'))>12000:raise LaunchError('request')
        current();return result

    def pre_session_rsd(self):
        if self.closed or self.draining or self.session is not None:raise LaunchError('session-lifetime')
        return self.source.current()[0]

    async def preflight_apps(self, args):
        from pymobiledevice3.services.installation_proxy import InstallationProxyService
        if (type(args) is not dict or set(args)!={'overteBundleId','wdaBundleId','discoverRemappedBundleIds'}
                or type(args['discoverRemappedBundleIds']) is not bool
                or any(type(args[key]) is not str or len(args[key])>255 or BUNDLE_ID.fullmatch(args[key]) is None
                       for key in ('overteBundleId','wdaBundleId'))
                or args['overteBundleId']==args['wdaBundleId']):raise LaunchError('request')
        rsd=self.pre_session_rsd()
        attributes=['CFBundleIdentifier','CFBundleExecutable','ApplicationType','ProfileValidated','SignerIdentity',
                    'UIFileSharingEnabled','OverteE2ETestBuildContractVersion','Entitlements',
                    'OverteE2EWebDriverAgentVersion','OverteE2EXCUITestDriverVersion']
        query={'ApplicationType':'User','ReturnAttributes':attributes}
        if not args['discoverRemappedBundleIds']:query['BundleIDs']=[args['overteBundleId'],args['wdaBundleId']]
        async with InstallationProxyService(rsd) as proxy:
            applications=await proxy.lookup(query)
        if self.pre_session_rsd() is not rsd or type(applications) is not dict:raise LaunchError('session-lifetime')
        if args['discoverRemappedBundleIds']:
            values=list(applications.values())
            overte=[app for app in values if type(app) is dict
                    and type(app.get('OverteE2ETestBuildContractVersion')) is int and app['OverteE2ETestBuildContractVersion']==1
                    and app.get('UIFileSharingEnabled') is True]
            wda=[app for app in values if type(app) is dict and app.get('OverteE2EWebDriverAgentVersion')=='16.8.0'
                 and app.get('OverteE2EXCUITestDriverVersion')=='12.8.0' and type(app.get('CFBundleExecutable')) is str
                 and app['CFBundleExecutable'].endswith('-Runner')]
            if len(overte)!=1 or len(wda)!=1:raise LaunchError('request')
            selected=[overte[0],wda[0]]
        else:
            if set(applications)!={args['overteBundleId'],args['wdaBundleId']}:raise LaunchError('request')
            selected=[applications[args['overteBundleId']],applications[args['wdaBundleId']]]
        output={}
        for app in selected:
            if type(app) is not dict:raise LaunchError('request')
            bundle=app.get('CFBundleIdentifier')
            if type(bundle) is not str or len(bundle)>255 or BUNDLE_ID.fullmatch(bundle) is None or bundle in output:
                raise LaunchError('request')
            value={key:app[key] for key in attributes if key in app}
            # Transport only fields actually consumed by existing validation,
            # preserving their observed values; no inferred signing result.
            entitlements=value.get('Entitlements')
            if type(entitlements) is dict:
                value['Entitlements']={key:entitlements[key] for key in
                    ('com.apple.developer.team-identifier','application-identifier') if key in entitlements}
            output[bundle]=value
        if len(json.dumps(output,separators=(',',':'),ensure_ascii=True).encode())>12000:raise LaunchError('request')
        if self.pre_session_rsd() is not rsd:raise LaunchError('session-lifetime')
        return dict(originalKeeperPreflightVersion=1,ownerInstance=self.instance,applications=output,
                    source='original-rsd-installation-proxy',nativeTouchSupport=False,resourceRetirementEstablished=False)

    async def ddi_status(self, args):
        from pymobiledevice3.services.mobile_image_mounter import PersonalizedImageMounter
        if (type(args) is not dict or set(args)!={'imageSha384'} or type(args['imageSha384']) is not str
                or re.fullmatch('[0-9a-f]{96}',args['imageSha384']) is None):raise LaunchError('request')
        rsd=self.pre_session_rsd()
        async with PersonalizedImageMounter(rsd) as mounter:
            # Same SDK LookupImage exchange as public lookup_image, retaining
            # ALL returned signatures rather than silently selecting first.
            original=await mounter._send_recv({'Command':'LookupImage','ImageType':'Personalized'})
        if self.pre_session_rsd() is not rsd or type(original) is not dict or original.get('ImagePresent') is False:
            raise LaunchError('session-lifetime')
        signatures=original.get('ImageSignature')
        if type(signatures) is bytes:signatures=[signatures]
        if (type(signatures) is not list or not signatures or any(type(value) is not bytes for value in signatures)
                or bytes.fromhex(args['imageSha384']) not in signatures):raise LaunchError('request')
        ports={}
        for name in ('com.apple.dt.testmanagerd.remote','com.apple.instruments.dtservicehub'):
            if self.pre_session_rsd() is not rsd:raise LaunchError('session-lifetime')
            port=rsd.get_service_port(name)
            if type(port) is not int or not 1<=port<=65535:raise LaunchError('request')
            # Read-only actual TCP connect through the original pinned dialer;
            # not a new RSD, tunnel, pairing or developer application session.
            connection=await rsd.create_service_connection(port)
            try:
                if self.pre_session_rsd() is not rsd:raise LaunchError('session-lifetime')
            finally:
                await connection.close()
            if self.pre_session_rsd() is not rsd:raise LaunchError('session-lifetime')
            ports[name]=port
        return dict(originalKeeperDdiStatusVersion=1,ownerInstance=self.instance,imageSignatureMatched=True,
                    serviceTcpEndpointsConnected=True,serviceProtocolReadinessEstablished=False,
                    source='original-rsd-personalized-image-and-tcp',nativeTouchSupport=False,
                    resourceRetirementEstablished=False)

    async def execute(self, operation, args, session):
        if operation=='owner-drain':
            if args or session is not None or asyncio.get_running_loop() is not self.source._loop:
                raise LaunchError('session-lifetime')
            self.draining=True
            # Close all forward input before the first await. Actual retained
            # workers settle without cancellation or fresh SDK admission.
            await self.source.settle_touches()
            current=asyncio.current_task()
            for row in tuple(self.issued.values()):
                task=row.get('task')
                if (task is None or task is current or row['request']['operation'] in
                        ('owner-drain','touch-release','touch-inspect','touch-settle')):continue
                while not task.done():await asyncio.shield(task)
            return dict(originalKeeperDrainVersion=1,ownerInstance=self.instance,inputAdmissionClosed=True,
                        originalTouchWorkersSettled=True,originalOperationsSettled=True,
                        nativeTouchSupport=False,resourceRetirementEstablished=False)
        if operation=='touch-native-motion-acquire':return await self.native_acquire(args,session,_motion_window=True)
        if operation=='touch-native-acquire':return await self.native_acquire(args,session)
        if operation=='touch-native-acquisition-read':return self.native_acquisition_read(args,session)
        if operation=='touch-native-query':return await self.native_query(args,session)
        if operation=='touch-native-original-read':return await self.native_original_read(args,session)
        if operation in ('apps-preflight','ddi-status'):
            if session is not None:raise LaunchError('request')
            return await (self.preflight_apps(args) if operation=='apps-preflight' else self.ddi_status(args))
        if operation=='inspect':
            if args or session is not None:raise LaunchError('request')
            self.source.current()
            return dict(originalKeeperOwnerVersion=1,creatorMode='userspace-keeper',
                        ownerInstance=self.instance,sourceLive=True,nativeTouchSupport=False)
        if operation=='claim':
            if (self.closed or self.draining or self.session is not None or type(args) is not dict
                    or set(args)!={'sessionId','archiveBundleId','wdaBundleId'} or session!=args['sessionId']
                    or any(type(args[key]) is not str or not args[key] or len(args[key])>255
                           or any(ch in args[key] for ch in '\0\r\n') for key in args)
                    or any(BUNDLE_ID.fullmatch(args[key]) is None for key in ('archiveBundleId','wdaBundleId'))):
                raise LaunchError('request')
            if re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',args['sessionId']) is None:raise LaunchError('request')
            self.source.current();self.session=dict(args)
            return dict(originalKeeperClaimVersion=1,ownerInstance=self.instance)
        if operation in ('touch-release','touch-inspect','touch-settle'):
            # Original claim/session and retained worker identity are sufficient
            # for OLD handle cleanup. No current SDK/RSD/PID is reacquired and
            # no new input/process/WDA mutation is admitted by this branch.
            if (args or self.session is None or session!=self.session['sessionId']
                    or asyncio.get_running_loop() is not self.source._loop):raise LaunchError('session-lifetime')
            if operation!='touch-settle' and self.touch is None:raise LaunchError('request')
            if operation in ('touch-release','touch-settle'):
                await self.source.settle_touches()
            inspection=None
            if self.touch is not None:
                row=next((row for row in self.source._born if row['lease'] is self.touch),None)
                if row is None or row['owner'] is None:raise LaunchError('session-lifetime')
                inspection=row['owner']._status()
            return dict(iosOriginalKeeperTouchVersion=1,ownerInstance=self.instance,inspection=inspection,
                        nativeTouchSupport=False,resourceRetirementEstablished=False)
        rsd=self.scope(session)
        if operation=='wda-start':
            if set(args)!={'environment','wdaPort'} or self.wda is not None or args['wdaPort']!=8100:
                raise LaunchError('request')
            env=args['environment']
            if (type(env) is not dict or set(env)!=ENVIRONMENT_KEYS or env['USE_PORT']!='8100'
                    or env['WDA_PRODUCT_BUNDLE_IDENTIFIER']!=self.session['wdaBundleId']):raise LaunchError('request-environment')
            ready=asyncio.get_running_loop().create_future();self.wda_stop=asyncio.Event()
            request=dict(udid=rsd.udid,wdaBundleId=self.session['wdaBundleId'],wdaPort=8100,environment=dict(env))
            self.wda=asyncio.create_task(run_xctest(request,original_source=self.source,
                                      owned_stop=self.wda_stop,owned_ready=ready),name='original-owner-wda')
            done,_=await asyncio.wait({ready,self.wda},return_when=asyncio.FIRST_COMPLETED)
            if ready not in done:self.wda.result();raise LaunchError('wda-ready')
            await ready;self.scope(session)
            return dict(originalKeeperWdaVersion=1,ownerInstance=self.instance,ready=True)
        if operation=='wda-bind':
            if (set(args)!={'wdaSessionId'} or self.wda_binding_claimed or self.wda_session is not None or self.wda is None or self.wda.done()
                    or type(args['wdaSessionId']) is not str
                    or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}',args['wdaSessionId']) is None):
                raise LaunchError('request')
            # Correlated JSON is NOT a session birth producer. The Appium
            # original proxy receipt is held in its owning process; this side
            # independently queries that EXISTING FBSession on original target.
            self.wda_binding_claimed=True
            original=await WdaServiceClient(rsd,port=8100,timeout=2.0)._request_json(
                'GET','/session/'+quote(args['wdaSessionId'],safe=''))
            if (self.scope(session) is not rsd or self.wda.done() or type(original.get('value')) is not dict
                    or original['value'].get('sessionId')!=args['wdaSessionId']):
                raise LaunchError('session-lifetime')
            self.wda_session=args['wdaSessionId']
            return dict(originalKeeperWdaSessionVersion=1,ownerInstance=self.instance,existingSessionBound=True,
                        nativeTouchSupport=False,resourceRetirementEstablished=False)
        if operation in ('process-read','process-terminate'):
            allowed={self.session['archiveBundleId'],self.session['archiveBundleId']+'.receiver'}
            if operation=='process-terminate':allowed={self.session['wdaBundleId']}
            if set(args)!={'bundleId','originalPid'} or args['bundleId'] not in allowed or type(args['originalPid']) is not int or not 0<=args['originalPid']<=2147483647:
                raise LaunchError('request')
            result=await self.process(args['bundleId'],args['originalPid'],terminate=operation=='process-terminate')
            self.scope(session);return result
        if operation=='touch-motion-prepare':
            # Old RPC Frame JSON is deliberately refused. Only THIS live
            # Source's exact actual immutable acquisition ref can be loaded.
            if (type(args) is not dict or set(args)!={'binding','runId','referenceJson','seconds'}
                    or self.touch is not None or self.touch_resources is not None):raise LaunchError('request')
            from adapters.normal_feature_state import PrivateFeatureState,context
            from adapters.native_feature_observation import number
            from adapters.script_feature.history import canonical
            from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner,_NativeMotionReference
            binding=context(args['binding']);run=args['runId']
            if (binding['sessionId']!=session or type(run) is not str or re.fullmatch('[0-9a-f]{32}',run) is None
                    or type(args['referenceJson']) is not str or len(args['referenceJson'])>2048
                    or not number(args['seconds'],0,12) or args['seconds']<=0):raise LaunchError('request')
            reference=decode_owner_packet(args['referenceJson'])
            if canonical(reference).decode('ascii')!=args['referenceJson']:raise LaunchError('request')
            journal=self.native_acquisition_journals.get(run)
            if journal is None or journal['binding']!=binding:raise LaunchError('session-lifetime')
            receipt=journal.get('motionOriginals',{}).get(reference.get('sha256') if type(reference) is dict else None)
            if type(receipt) is not _NativeMotionReference or receipt.reference!=reference:raise LaunchError('session-lifetime')
            try:
                # One actual SDK/PID fence encloses ALL original frame reads
                # and the preparation CAS. No fresh values replace that frame.
                await self.fresh_touch_scope(binding);receipt.original(self.source,None,self.instance)
                original_session=self.session;original_source=self.source
                def resource_current():
                    if self.session is not original_session or self.source is not original_source:raise LaunchError('session-lifetime')
                    original_source.current();return True
                lock=journal['lock']
                with lock.held():
                    resource=LifecycleTouchResourceOwner(PrivateFeatureState(self.state_root/('ios-lifecycle-touch-resources-'+run+'.json')),
                        binding,run,lock,resource_current)
                    self.touch_resources=resource # Retain actual duty before any saved ACK can be lost.
                    self.source.prepare_motion(resource,self.instance,receipt,seconds=args['seconds'])
                await self.fresh_touch_scope(binding);receipt._check()
            except BaseException:
                receipt.revoke() # Observed SDK/read/ACK uncertainty cannot revive.
                raise
            return dict(originalKeeperMotionPreparationVersion=3 if receipt._selected is not None else 2,ownerInstance=self.instance,preparationRecorded=True,
                nativeMotionGuardAvailable=False,nativeTouchSupport=False,resourceRetirementEstablished=False)
        if operation in ('touch-resource-capture','touch-resource-recover'):
            resource=self.touch_resources
            if type(args) is not dict or set(args)!={'binding','runId'} or resource is None or resource.version!=1:
                raise LaunchError('request')
            from adapters.normal_feature_state import context
            if context(args['binding'])!=resource.binding or args['runId']!=resource.run:
                raise LaunchError('session-lifetime')
            # Existing live candidate/session checks apply to NEW captures.
            # Saved-only metadata recovery performs no SDK query or input.
            if operation=='touch-resource-capture':
                await self.fresh_touch_scope(self.touch._binding)
                if self.scope(session) is not rsd:raise LaunchError('session-lifetime')
            with resource.lock.held():
                value=resource.capture() if operation=='touch-resource-capture' else resource.recover_capture()
                original=resource.files.read(resource.files.expand(resource.state['frames'][-1]))
                if original!=value:raise LaunchError('session-lifetime')
                owner=resource.previous
            # Lossless transport through Node JSON: original uint64 device/
            # inode metadata stays inside canonical JSON TEXT, never JS Number.
            resource_json=json.dumps(dict(capture=value,owner=owner),sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
            if len(resource_json)>12288:raise LaunchError('request')
            result=dict(originalKeeperTouchResourceVersion=2,ownerInstance=self.instance,
                        encoding='canonical-json-ascii',resourceJson=resource_json,
                        nativeTouchSupport=False,resourceRetirementEstablished=False)
            # The escaped string itself must fit the existing 16KiB pipe frame,
            # leaving room for its unchanged outer request/status envelope.
            if len(json.dumps(result,separators=(',',':'),ensure_ascii=True).encode('ascii'))>12000:
                raise LaunchError('request')
            return result
        if operation=='touch-begin':
            if self.touch is not None or self.touch_resources is not None or set(args)!={'binding','runId','width','height','x','y','seconds'}:raise LaunchError('request')
            from adapters.normal_feature_state import PrivateFeatureState,context
            binding=context(args['binding'])
            if binding['sessionId']!=session or not re.fullmatch('[1-9][0-9]{0,9}',binding['processIdentity']):raise LaunchError('request')
            if type(args['runId']) is not str or re.fullmatch('[0-9a-f]{32}',args['runId']) is None:raise LaunchError('request')
            from adapters.script_feature.lock import ScriptSourceLock
            from ios.adapters.lifecycle_touch_resource_owner import LifecycleTouchResourceOwner
            original_session=self.session;original_source=self.source
            def resource_current():
                if self.session is not original_session or self.source is not original_source:
                    raise LaunchError('session-lifetime')
                original_source.current();return True
            lock=ScriptSourceLock(self.state_root/'script-feature-sources.lock')
            with lock.held():
                resource=LifecycleTouchResourceOwner(PrivateFeatureState(self.state_root/('ios-lifecycle-touch-resources-'+args['runId']+'.json')),
                    binding,args['runId'],lock,resource_current)
                # Retain the actual owner before an original factory/ACK can
                # fail. No restored WAL recreates an absent source or worker.
                self.touch_resources=resource
                self.touch=self.source.touch_lease(PrivateFeatureState(self.state_root/('ios-lifecycle-touch-lease-'+args['runId']+'.json')),
                    binding=binding,run=args['runId'],check=lambda:self.fresh_touch_scope(binding),resource_owner=resource)
            value=await self.touch.begin(args['width'],args['height'],args['x'],args['y'],seconds=args['seconds'])
            return dict(iosOriginalKeeperTouchVersion=1,ownerInstance=self.instance,inspection=value,
                        nativeTouchSupport=False,resourceRetirementEstablished=False)
        if operation=='wda-stop':
            if args or self.wda is None:raise LaunchError('request')
            await self.source.settle_touches();self.wda_stop.set()
            await asyncio.shield(self.wda)
            return dict(originalKeeperWdaVersion=1,ownerInstance=self.instance,stopReturned=True,
                        resourceRetirementEstablished=False)
        raise LaunchError('request')

    async def finish(self):
        self.closed=True
        failure=None
        try:await self.source.settle_touches()
        except BaseException as error:failure=error
        for task in tuple(self.operations):
            while not task.done():
                try:await asyncio.shield(task)
                except BaseException as error:failure=failure or error
        if self.wda is not None:
            self.wda_stop.set()
            while not self.wda.done():
                try:await asyncio.shield(self.wda)
                except BaseException as error:failure=failure or error
        if failure is not None:raise failure


def decode_owner_packet(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise LaunchError('request')
            result[key]=value
        return result
    def constant(_value):raise LaunchError('request')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def write_owner_packet(value):
    raw=json.dumps(value,separators=(',',':'),ensure_ascii=True)
    if len(raw.encode())>MAX_REQUEST_BYTES:raise LaunchError('request')
    sys.stdout.write(raw+'\n');sys.stdout.flush()


async def run_original_owner(request):
    from pathlib import Path
    root=Path(request['stateRoot']);value=root.lstat()
    if (not root.is_absolute() or root.is_symlink() or root.resolve()!=root or not root.is_dir()
            or value.st_uid!=os.geteuid() or value.st_mode&0o077):raise LaunchError('request')
    stop=asyncio.Event();loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(sig,stop.set)
    reader=asyncio.StreamReader(limit=MAX_REQUEST_BYTES+1)
    await loop.connect_read_pipe(lambda:asyncio.StreamReaderProtocol(reader),sys.stdin.buffer)
    async with create_original_keeper_source(request['udid']) as source:
        operations=OriginalKeeperOperations(source,root)
        write_owner_packet(dict(schemaVersion=2,event='owner-ready',ownerInstance=operations.instance))
        async def dispatch(value):
            request_id=value['requestId'];row=operations.issued[request_id]
            try:
                result=await operations.execute(value['operation'],value['args'],value['sessionId'])
                packet=dict(schemaVersion=2,requestId=request_id,ownerInstance=operations.instance,status='complete',result=result)
            except BaseException:
                packet=dict(schemaVersion=2,requestId=request_id,ownerInstance=operations.instance,status='failed',result=None)
            row['original']=packet
            write_owner_packet(packet)
        stopping=asyncio.create_task(stop.wait())
        try:
            while not stop.is_set():
                reading=asyncio.create_task(reader.readline())
                done,_=await asyncio.wait({reading,stopping},return_when=asyncio.FIRST_COMPLETED)
                if stopping in done:
                    reading.cancel()
                    with suppress(asyncio.CancelledError):await reading
                    break
                raw=reading.result()
                if not raw:break
                if len(raw)>MAX_REQUEST_BYTES or not raw.endswith(b'\n') or b'\0' in raw or b'\r' in raw:raise LaunchError('request')
                value=decode_owner_packet(raw)
                if (type(value) is not dict or set(value)!={'schemaVersion','requestId','ownerInstance','sessionId','operation','args'}
                        or type(value['schemaVersion']) is not int or value['schemaVersion']!=2
                        or type(value['requestId']) is not str or re.fullmatch('[0-9a-f]{32}',value['requestId']) is None
                        or value['ownerInstance']!=operations.instance or type(value['operation']) is not str
                        or type(value['args']) is not dict):raise LaunchError('request')
                prior=operations.issued.get(value['requestId'])
                if prior is not None:
                    if prior['request']!=value:raise LaunchError('request')
                    # Delivery of ORIGINAL bytes only; never rerun a touch or
                    # retime an old result as a fresh observation.
                    if prior['original'] is not None:write_owner_packet(prior['original'])
                    continue
                if len(operations.issued)>=4096 or len(operations.operations)>=32:raise LaunchError('request')
                operations.issued[value['requestId']]=dict(request=value,original=None,task=None)
                task=asyncio.create_task(dispatch(value));operations.issued[value['requestId']]['task']=task;operations.operations.add(task)
                task.add_done_callback(operations.operations.discard)
        finally:
            stopping.cancel()
            with suppress(asyncio.CancelledError):await stopping
            await operations.finish()


def main() -> int:
    try:
        parent_death_signal()
        if version("pymobiledevice3") != "11.1.5":
            raise LaunchError("runtime-version")
        request=read_request()
        asyncio.run(run_original_owner(request) if request["schemaVersion"]==2 else run_xctest(request))
        return 0
    except BaseException as error:
        phase = error.phase if isinstance(error, LaunchError) else "unexpected"
        sys.stderr.write(
            f"error: immutable Fedora XCTest keeper failed phase={phase}\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
