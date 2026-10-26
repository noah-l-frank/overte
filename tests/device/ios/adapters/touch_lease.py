"""Bounded host responsibility for one ordinary CoreDevice touch contact.

No native held/released fact is supplied here. One retained worker owns the
original HID context through Down, ordinary Up and context exit. A returned
exit is not independent proof of SDK/media/socket absence. The watchdog is a
bounded host release request, not a hard physical contact-lifetime guarantee:
an unknown pending Down keeps its original worker until that call settles.
This source-only primitive has no device selector, RPC or capability wiring.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from contextlib import suppress
from copy import deepcopy
import math
import re
import inspect
import uuid
from adapters.normal_feature_state import PrivateFeatureState,context
from ios.adapters.hid_session import touch_session
from ios.adapters.touch import validate_actions

VERSION=1
PHASES={'opening','down-issued','holding','up-issued','draining','closed','failed'}
FAILURES={'acquire','down','up','drain','journal','deadline','cancelled','continuity'}


class TouchLeaseError(RuntimeError):pass
class TouchLeasePending(TouchLeaseError):pass


class TouchLease:
    @staticmethod
    def _same_binding(value,expected):
        try:return context(value)==expected
        except Exception:return False

    def __init__(self,store,session_factory,*,binding,run,check):
        if not isinstance(store,PrivateFeatureState) or not callable(session_factory) or not callable(check):raise TouchLeaseError('Touch lease owner is unavailable')
        try:self.binding=deepcopy(context(binding))
        except Exception:raise TouchLeaseError('Touch lease source binding is unavailable') from None
        if type(run) is not str or re.fullmatch('[0-9a-f]{32}',run) is None:raise TouchLeaseError('Touch lease run is unavailable')
        self.run,self.check=run,check;self._binding,self._expected_run,self._check_callback=deepcopy(self.binding),run,check
        self.store,self.session_factory=store,session_factory;self._session_factory=session_factory
        self.previous=store.read();self.state=deepcopy(self.previous)
        if self.state is not None:
            if (type(self.state) is not dict or set(self.state)!={'iosTouchLeaseVersion','binding','runId','leaseId','position','startedMonotonic','deadlineMonotonic','phase','failure'}
                    or type(self.state['iosTouchLeaseVersion']) is not int or self.state['iosTouchLeaseVersion']!=VERSION
                    or not self._same_binding(self.state['binding'],self.binding) or self.state['runId']!=self.run
                    or type(self.state['phase']) is not str or self.state['phase'] not in PHASES
                    or type(self.state['leaseId']) is not str or re.fullmatch('[0-9a-f]{32}',self.state['leaseId']) is None
                    or type(self.state['position']) is not list or len(self.state['position'])!=2
                    or not all(type(n) is int and 0<=n<=65535 for n in self.state['position'])
                    or not all(type(self.state[key]) in (int,float) and math.isfinite(self.state[key]) and self.state[key]>=0 for key in ('startedMonotonic','deadlineMonotonic'))
                    or not 0<self.state['deadlineMonotonic']-self.state['startedMonotonic']<=12
                    or self.state['failure'] is not None and (type(self.state['failure']) is not str or self.state['failure'] not in FAILURES)
                    or self.state['phase']=='closed' and self.state['failure'] in ('up','drain','journal')):raise TouchLeaseError('Touch lease journal is unavailable')
        self.worker=None;self.context=None;self.hid=None;self.deadline=None
        self.down_issued=False;self.up_issued=False;self.context_exit_returned=False;self.closed=self.state is not None and self.state['phase']=='closed'
        self.failure=None if self.state is None else self.state['failure'];self.journal_failed=False
        self.ready=asyncio.Event();self.request_release=asyncio.Event()

    @classmethod
    def for_tunnel(cls,store,rsd,local_address,*,binding,run,check):
        # Constructing this owner opens no stream or service.
        return cls(store,lambda:touch_session(rsd,local_address),binding=binding,run=run,check=check)

    async def _continuity(self):
        # Required caller contract: acquire fresh selected-candidate, session,
        # PID and foreground continuity. No source values are supplied here.
        try:
            if not self._same_binding(self.binding,self._binding) or self.run!=self._expected_run or self.check is not self._check_callback or self.session_factory is not self._session_factory:raise TouchLeaseError('Touch lease source scope changed')
            result=self.check()
            if inspect.isawaitable(result):result=await result
            if result is False:raise TouchLeaseError('Touch lease source continuity failed')
            if not self._same_binding(self.binding,self._binding) or self.run!=self._expected_run or self.check is not self._check_callback or self.session_factory is not self._session_factory:raise TouchLeaseError('Touch lease source scope changed')
        except BaseException as error:
            self.failure=self.failure or ('cancelled' if isinstance(error,asyncio.CancelledError) else 'continuity')
            raise TouchLeaseError('Original touch source continuity failed') from None

    def _record(self,phase):
        value=dict(self.state,phase=phase,failure=self.failure)
        try:
            self.store.write(value,self.previous)
            if self.store.read()!=value:raise TouchLeaseError('Touch lease journal changed')
        except Exception:
            self.journal_failed=True
            raise TouchLeaseError('Original touch journal update remains unresolved') from None
        self.previous=deepcopy(value);self.state=value

    def inspect(self):
        if self.store.read()!=self.previous:raise TouchLeaseError('Touch lease journal changed')
        # Archived open responsibility cannot recreate its absent live worker.
        responsibility=self.state is not None and (not self.closed or self.journal_failed)
        return dict(hostResponsibility=responsibility,workerRunning=self.worker is not None and not self.worker.done(),
            downIssued=self.down_issued,upIssued=self.up_issued,contextExitReturned=self.context_exit_returned,
            failure=self.failure,journal=deepcopy(self.state))

    async def _wait(self,task):
        if not task.done():
            remaining=max(0.,self.deadline-asyncio.get_running_loop().time())
            done,_pending=await asyncio.wait({task},timeout=remaining)
            if not done:
                self.request_release.set()
                raise TouchLeasePending('Original touch worker still owns cleanup')
        return task.result()

    async def begin(self,width,height,x,y,*,seconds):
        if self.state is not None or self.worker is not None:raise TouchLeaseError('Touch intent cannot be repeated')
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0<seconds<=12:raise TouchLeaseError('Touch lease duration is unavailable')
        # Reuse the unchanged ordinary touch coordinate codec. No event is
        # dispatched by this closed validation-only skeleton.
        actions=validate_actions({'actions':[dict(type='pointer',id='owned-touch',parameters=dict(pointerType='touch'),actions=[
            dict(type='pointerMove',duration=0,origin='viewport',x=x,y=y),dict(type='pointerDown',button=0),dict(type='pointerUp',button=0)])]},width,height)
        started=asyncio.get_running_loop().time();self.deadline=started+seconds
        self.state=dict(iosTouchLeaseVersion=VERSION,binding=deepcopy(self.binding),runId=self.run,leaseId=uuid.uuid4().hex,position=list(actions[0][1]),
            startedMonotonic=started,deadlineMonotonic=self.deadline,phase='opening',failure=None)
        self._record('opening')
        self.worker=asyncio.create_task(self._run())
        waiter=asyncio.create_task(self.ready.wait())
        try:
            await self._wait(waiter)
            if self.failure is not None or self.closed or self.request_release.is_set():raise TouchLeaseError('Original touch did not enter a current holding state')
            return self.inspect()
        except BaseException as error:
            if isinstance(error,asyncio.CancelledError):self.failure=self.failure or 'cancelled'
            self.request_release.set()
            raise
        finally:
            waiter.cancel()
            with suppress(asyncio.CancelledError):await waiter

    async def release(self):
        if self.closed and not self.journal_failed:return self.inspect()
        if self.worker is None:raise TouchLeasePending('Archived touch intent has no retained live HID object')
        self.request_release.set()
        await self._wait(self.worker)
        if not self.closed or self.journal_failed:raise TouchLeasePending('Original touch release or drainage remains owned')
        return self.inspect()

    async def _watchdog(self):
        await asyncio.sleep(max(0.,self.deadline-asyncio.get_running_loop().time()))
        self.failure=self.failure or 'deadline';self.request_release.set()

    async def _run(self):
        timer=asyncio.create_task(self._watchdog());entered=False;release_failed=False
        factory=self._session_factory;actual_context=actual_hid=None;position=tuple(self.state['position'])
        try:
            await self._continuity()
            actual_context=factory();self.context=actual_context
            actual_hid=await actual_context.__aenter__();self.hid=actual_hid;entered=True
            await self._continuity()
            if self.request_release.is_set() or asyncio.get_running_loop().time()>=self.deadline:
                self.failure=self.failure or 'deadline'
            else:
                await self._continuity()
                if self.request_release.is_set() or asyncio.get_running_loop().time()>=self.deadline:
                    self.failure=self.failure or 'deadline';return
                self._record('down-issued')
                await self._continuity()
                if self.request_release.is_set() or asyncio.get_running_loop().time()>=self.deadline:
                    self.failure=self.failure or 'deadline';return
                self.down_issued=True
                try:await actual_hid.send_touchscreen(0xC2,*position)
                except BaseException as error:
                    self.failure='cancelled' if isinstance(error,asyncio.CancelledError) else 'down'
                else:
                    self._record('holding');self.ready.set()
                    await self.request_release.wait()
        except BaseException as error:
            self.failure=self.failure or ('cancelled' if isinstance(error,asyncio.CancelledError) else 'acquire')
        finally:
            # A lost Down acknowledgement stays owned by this same worker.
            # It is never resent; ordinary Up follows once the original call
            # settles. An indefinitely pending original retains its owner.
            if self.down_issued and not self.up_issued:
                self.up_issued=True
                try:self._record('up-issued')
                except BaseException:self.failure=self.failure or 'journal'
                try:await actual_hid.send_touchscreen(0x02,*position)
                except BaseException:
                    self.failure='up';release_failed=True
            if entered:
                try:self._record('draining')
                except BaseException:self.failure=self.failure or 'journal'
                try:
                    await actual_context.__aexit__(None,None,None);self.context_exit_returned=True
                except BaseException:
                    self.failure='drain';release_failed=True
            # A failed __aenter__ owns its context's own cleanup contract. No
            # missing handle is recreated and no second service is acquired.
            elif actual_context is not None:
                self.failure=self.failure or 'acquire';release_failed=True
            try:
                self._record('failed' if release_failed or self.journal_failed else 'closed')
                self.closed=not release_failed and not self.journal_failed
            except BaseException:self.failure=self.failure or 'journal'
            self.ready.set();timer.cancel()
            with suppress(asyncio.CancelledError):await timer
