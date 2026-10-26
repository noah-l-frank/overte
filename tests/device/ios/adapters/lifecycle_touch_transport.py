"""Closed production admission and actual retained touch-worker checks.

No authenticated touchscreen broker exists in the canonical pinned adapter.
Configuration cannot mint one from endpoints, selectors, expected PID values
or arbitrary callbacks. A retained source/test worker can be inspected and
released, but context exit is never upgraded to original resource retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from adapters.normal_ui import NativeUIError
from ios.adapters.touch_lease import TouchLease,TouchLeasePending


class TouchTransportUnavailable(NativeUIError):pass


def metadata():
    return dict(nativeTouchSupport=False,availability='missing-authenticated-broker')


def admit(configuration=None):
    if configuration is not None:
        exact(configuration,{'nativeTouchSupport'});need(type(configuration['nativeTouchSupport']) is bool and configuration['nativeTouchSupport'] is False)
    raise TouchTransportUnavailable('Authenticated retained touch transport is unavailable')


def current_loop():
    try:return asyncio.get_running_loop()
    except RuntimeError:raise TouchTransportUnavailable('Original touch worker event loop is unavailable') from None


def intent(journal):return {key:deepcopy(value) for key,value in journal.items() if key not in ('phase','failure')}


class RetainedTouchWorker:
    """Keep the actual lease/task/loop; this is not a transport authenticator."""
    def __init__(self,lease):
        need(type(lease) is TouchLease and isinstance(lease.worker,asyncio.Task))
        self._lease,self._worker,self._loop,self._store=lease,lease.worker,lease.worker.get_loop(),lease.store
        need(current_loop() is self._loop)
        status=lease.inspect();need(status['journal'] is not None)
        self._intent=intent(status['journal']);self._binding=deepcopy(lease.binding);self._run=lease.run
        self._factory,self._check=lease._session_factory,lease._check_callback
    def _status(self):
        need(current_loop() is self._loop and self._worker.get_loop() is self._loop
             and self._lease.worker is self._worker and self._lease.store is self._store
             and same(self._lease.binding,self._binding) and self._lease.run==self._run
             and self._lease._session_factory is self._factory and self._lease._check_callback is self._check)
        status=self._lease.inspect();need(status['journal'] is not None and same(intent(status['journal']),self._intent))
        return status
    def inspect(self):
        status=self._status()
        return dict(nativeTouchSupport=False,hostResponsibility=status['hostResponsibility'],workerRunning=status['workerRunning'],
                    contextExitReturned=status['contextExitReturned'],retirementEstablished=False)
    async def release(self):
        self._status()
        await self._lease.release()
        return self.inspect()
    def ensure_teardown(self):
        status=self.inspect()
        if status['hostResponsibility'] or status['workerRunning']:
            raise TouchLeasePending('Original retained touch worker still owns input or cleanup')
        # The existing SDK/context has no independent original resource census.
        # Even a returned context exit cannot establish media/SDK/native absence.
        raise TouchTransportUnavailable('Original touch transport retirement is unavailable')
