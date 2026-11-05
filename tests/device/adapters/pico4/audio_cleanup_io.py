"""Original once-only Pico restart transport for selected Audio cleanup.

The existing transport owns candidate, launcher and Session-transfer custody.
Bounded Android PID-query originals share the original Actor raw bank.
No Phone input, service, decoder or alternate restart backend is introduced.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.native_feature_observation import NativeFeatureObservation,FILE as NATIVE_FILE,need,number
from adapters.native_process_presence import NativeProcessPresence,FILE as PRESENCE_FILE,command as presence_command
from adapters.pico4.audio_settings_source import PicoAudioSettings,FILE as SETTINGS_FILE,ACTION as SETTINGS_ACTION
from adapters.pico4.audio_pages import PicoAudioPages,FILE as PAGES_FILE
from adapters.pico4.chat_restart_io import PicoChatRestartIO,PACKAGE,process
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1
from adapters.script_journey.history import canonical


class PicoAudioCleanupIO1:
    def __init__(self,adapter,target,budget,*,monotonic=time.monotonic,sleep=time.sleep):
        need(type(budget) is AudioCleanupBudget1 and budget.actor is not None
             and callable(monotonic) and callable(sleep))
        budget.require_cleanup_workspace();need(not budget.failed and getattr(budget,'restart_io',None) is None)
        self.budget=budget;budget.restart_io=self
        self.adapter,self.target,self.monotonic,self.sleep=adapter,target,monotonic,sleep
        self.transport=None;self.pending=None;self.failed=False;self.acquired=[];self.references=[]
        self.failure=None
        self.getting=False
        self.source_sets=self._original_source_sets=()
        self.command=None;self.query=None;self.epoch='old';self.role='primary'
        # Strong ownership precedes the existing constructor's descriptor work.
        try:
            self.process_source=budget.create_process_source()
            actual=object.__new__(PicoChatRestartIO);self.transport=actual
            PicoChatRestartIO.__init__(actual,adapter,target,budget.value['binding'],
                monotonic=monotonic,sleep=sleep,process_acquire=self.process_source.acquire)
        except BaseException as error:
            self.poison(error)
            raise

    def poison(self,error):
        # The first real error owns its original traceback through failure.
        # Archival cleanup may still close known handles, never authorize retry.
        if self.failure is None:self.failure=(error,error.__traceback__)
        self.failed=True;self.budget.failed=True

    def business(self):
        try:
            self.budget.guard();need(not self.failed and not self.budget.failed
                and type(self.epoch) is str and self.epoch in ('old','new')
                and type(self.role) is str and self.role in ('primary','actor')
                and type(self.getting) is bool and type(self.source_sets) is tuple
                and self.source_sets is self._original_source_sets and len(self.source_sets)<=4)
            now=self.monotonic()
            need(number(now,self.budget.value['startedMonotonic'],self.budget.value['deadlineMonotonic']))
            self.transport.guard_candidate()
            if self.query is not None:
                started,_requested=self.query
                need(number(self.monotonic(),started,started+1.5))
        except BaseException as error:
            self.poison(error)
            raise

    def stop(self,before_input):
        try:
            self.business();return self.transport.stop(before_input)
        except BaseException as error:
            self.poison(error)
            raise

    def stopped(self):
        try:
            self.business();return self.transport.stopped()
        except BaseException as error:
            self.poison(error)
            raise

    def launch(self,before_input):
        try:
            self.business();return self.transport.launch(before_input)
        except BaseException as error:
            self.poison(error)
            raise

    def begin_query(self,epoch,role):
        try:
            need(epoch in ('old','new') and role in ('primary','actor') and self.query is None)
            self.epoch,self.role=epoch,role
            self.query=(self.monotonic(),self.adapter.adb.epoch_milliseconds(self.target))
            self.business();return self.query
        except BaseException as error:
            self.poison(error)
            raise

    def end_query(self):
        try:
            self.business();self.query=None
        except BaseException as error:
            self.poison(error)
            raise

    def guard_identity(self,identity):
        try:
            self.business()
            need(self.adapter.controlled_debug_identity(self.target)==identity
                 and self.adapter.adb.foreground_package(self.target)==PACKAGE)
            self.business();return True
        except BaseException as error:
            self.poison(error)
            raise

    def _request(self,identity,command):
        try:
            need(not self.getting)
            self.guard_identity(identity)
            action=command.get('action')
            if action=='feature-native-observe':
                need(set(command)=={'schemaVersion','commandId','action'} and type(command['schemaVersion']) is int and command['schemaVersion']==1)
            elif action=='feature-process-presence':presence_command(command)
            else:
                need(action==SETTINGS_ACTION and set(command)=={'schemaVersion','commandId','action','runId'}
                     and type(command['schemaVersion']) is int and command['schemaVersion']==1
                     and command['runId']==self.budget.value['runId'])
            need(self.pending is None)
            self.command=deepcopy(command)
            filename={'feature-native-observe':NATIVE_FILE,'feature-process-presence':PRESENCE_FILE,SETTINGS_ACTION:SETTINGS_FILE}[action]
            association=self.association(identity,filename)
            self.budget.charge_row(self,reserve_follows=True)
            self.pending=self.budget.actor.raws.reserve('audio-cleanup-'+self.epoch+'-'+self.role,association,262144)
            self.business()
            self.adapter.write_control_command(self.target,identity,'original Audio cleanup read-only source',command)
        except BaseException as error:
            self.poison(error)
            raise

    def association(self,identity,filename):
        return dict(audioCleanupWireVersion=1,runId=self.budget.value['runId'],
            epoch=self.epoch,role=self.role,processIdentity=identity,
            filename=filename,request=None if filename==PAGES_FILE else deepcopy(self.command))

    def _literal(self,identity,filename):
        try:
            need(self.query is not None and not self.acquired and not self.getting)
            self.guard_identity(identity);bank=self.budget.actor.raws
            association=self.association(identity,filename)
            if self.pending is None:
                self.budget.charge_row(self,reserve_follows=True)
                limit=65536 if filename==PAGES_FILE else 262144
                self.pending=bank.reserve('audio-cleanup-'+self.epoch+'-'+self.role,association,limit)
            token=self.pending
            need(token['command']==association)
            # The real global reservation and final original clock precede getter.
            self.guard_identity(identity)
            self.getting=True
            raw=self.adapter.adb.read_debug_app_file(self.target,PACKAGE,'files/overte-e2e/'+filename,attempts=1)
            self.acquired.append(raw)
            ref=bank.retain(token,raw)
            self.references.append(dict(association=association,reference=ref))
            self.pending=None
            # Exact literal is already durable. A decoder-capacity refusal keeps it,
            # the actual acquired object and its outstanding decoded resource hold.
            self.budget.hold_decode(self,raw)
            # Exact builtin str is still held by this local and the imminent native
            # decoder; dropping the redundant acquired alias runs no custom cleanup.
            self.acquired.clear();self.getting=False
            self.business()
            return raw
        except BaseException as error:
            self.poison(error)
            raise

    def sources(self,identity,bridge):
        try:
            need(self.query is not None and not self.getting and len(self.source_sets)<4)
            pid,_start=process(identity);self.guard_identity(identity)
            send=lambda command:self._request(identity,command)
            guard=lambda:self.guard_identity(identity)
            clock=lambda:self.adapter.adb.epoch_milliseconds(self.target)
            native=NativeFeatureObservation(send,lambda:self._literal(identity,NATIVE_FILE),clock,guard,pid,
                monotonic=self.monotonic,sleep=self.sleep)
            presence=NativeProcessPresence(send,lambda:self._literal(identity,PRESENCE_FILE),clock,guard,pid,
                monotonic=self.monotonic,sleep=self.sleep)
            settings=PicoAudioSettings(send,lambda:self._literal(identity,SETTINGS_FILE),clock,guard,pid,
                monotonic=self.monotonic,sleep=self.sleep,source_lock=self.budget.lock)
            pages=PicoAudioPages(lambda:self._literal(identity,PAGES_FILE),clock,guard,pid,bridge,self.budget.lock,
                monotonic=self.monotonic,sleep=self.sleep)
            self.business()
            row=(self.epoch,self.role,identity,bridge,native,presence,settings,pages)
            self.source_sets=self._original_source_sets=(*self.source_sets,row)
            return native,presence,settings,pages
        except BaseException as error:
            self.poison(error)
            raise

    def close_host(self):
        # Closing transport handles does not retire journals or resource facts.
        okay=self.transport is not None and self.transport.close_host() is True
        if not okay:self.failed=True;self.budget.failed=True
        return okay
