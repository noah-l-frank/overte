"""Actual once-only restart and warm Process source handoff for Lifecycle.

The existing neutral SDK/FD primitives execute. No Chat profile query,
bootstrap, session discard or reader reconstructed from files is available.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid

from adapters.native_feature_observation import NativeFeatureObservation,FILE as NATIVE_FILE,decode,integer,need,number
from adapters.native_process_presence import NativeProcessPresence,FILE as PRESENCE_FILE,command as presence_command
from adapters.pico4.chat_restart_io import PicoChatRestartIO,process,PACKAGE
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_process import native_birth,run_lifecycle_restart
from adapters.restart_inputs import validate_native_restart
from adapters.script_journey.history import same


class PicoLifecycleRestartRuntime:
    def __init__(self,operations,io,old_source,observe):
        from adapters.pico4.lifecycle_operations import PicoLifecycleOperations
        need(type(operations) is PicoLifecycleOperations and type(io) is PicoChatRestartIO
            and isinstance(old_source,NativeFeatureObservation) and callable(observe)
            and same(io.binding,operations.source.binding) and old_source.pid==operations.source.pid)
        self.operations,self.io,self.old_source=operations,io,old_source
        self.process=operations.source.restore.process
        self.observe=observe
        self.lock,self.run_id=operations.lock,operations.source.run
        self.new_sources=self.proof_anchor=self.handoff=None
        self.memo=self.readers=None

    def record(self,kind,value):
        self.operations.restart_record(kind,value)

    def old_reply(self):
        raw=self.old_source.original();value=decode(raw)
        need(value['processId']==self.old_source.pid and value['instance']==self.old_source.instance
            and value['sequence']==self.old_source.sequence and value['lifecycle']==self.old_source.lifecycle
            and native_birth(value)==self.process.inputs.read()['oldNative'])
        self.record('old-native-birth',dict(original=frame(raw),input=self.process.inputs.read()))

    def final_stop(self):
        # This is after the actual RestartInputs CAS and every final SDK guard.
        self.operations.fence.check();self.process.require_stop_ready(self.old_source)

    def final_launch(self):self.operations.fence.check()

    def stop(self):
        self.old_reply()
        return self.io.stop(self.final_stop)

    def stopped(self):
        result=self.io.stopped()
        self.record('os-process-list',dict(result=result,original=self.io.last_process_query))
        self.operations.fence.mark() # Before RestartInputs' actual launch intent CAS.
        return result

    def launch(self):
        result=self.io.launch(self.final_launch)
        self.record('launch-delivery',dict(result=result,processQuery=self.io.last_process_query))
        return result

    def unbound(self):
        io=self.io;io.guard_candidate();adapter,target=io.adapter,io.target
        identity=adapter.controlled_debug_identity(target);pid,start=process(identity)
        need(pid!=io.pid and start>io.start)
        def guard():
            io.guard_candidate()
            need(adapter.controlled_debug_identity(target)==identity and adapter.adb.foreground_package(target)==PACKAGE)
            io.guard_candidate();return True
        def send(command):
            if command.get('action')=='feature-native-observe':
                need(set(command)=={'schemaVersion','commandId','action'} and type(command['schemaVersion']) is int
                    and command['schemaVersion']==1 and type(command['commandId']) is str
                    and re.fullmatch('[0-9a-f]{32}',command['commandId']))
            else:presence_command(command)
            guard();adapter.write_control_command(target,identity,'original unbound Lifecycle restart source',command)
        def read(name):
            guard();return adapter.adb.read_debug_app_file(target,PACKAGE,'files/overte-e2e/'+name,attempts=1)
        clock=lambda:adapter.adb.epoch_milliseconds(target)
        native=NativeFeatureObservation(send,lambda:read(NATIVE_FILE),clock,guard,pid,monotonic=io.monotonic,sleep=io.sleep)
        presence=NativeProcessPresence(send,lambda:read(PRESENCE_FILE),clock,guard,pid,monotonic=io.monotonic,sleep=io.sleep)
        self.new_sources=identity,native,presence

    def fresh_proof(self,*,host_only=False):
        need(self.proof_anchor is not None and self.new_sources is not None)
        started,requested,oldest=self.proof_anchor
        if not host_only:
            for reader in self.new_sources[1:]:need(reader.guard() is not False)
        now=self.io.monotonic();need(number(now,started,started+1.5))
        need(requested-oldest+(now-started)*1000<=1500)
        if not host_only:
            epoch=self.new_sources[1].clock_ms();ended=self.io.monotonic()
            need(integer(epoch,1) and number(ended,now,started+1.5) and -250<=epoch-oldest
                and max(epoch-oldest,requested-oldest+(ended-started)*1000)<=1500)

    def recover(self):
        if self.new_sources is None:self.unbound()
        identity,native,presence=self.new_sources
        if self.io.transfer.pending is not None:
            # A landed/uncertain cursor publication is reconciled through its
            # original held descriptors and original callback/age anchor only.
            observed=self.io.transfer.reconcile();self.fresh_proof()
            self.record('cursor-transferred',observed);return
        started=self.io.monotonic();requested=native.clock_ms()
        first=native.read(native.sequence);validate_native_restart(self.process.inputs.read()['oldNative'],native_birth(first))
        raw=native.original();need(decode(raw)==first);self.record('new-native-before',dict(original=frame(raw)))
        absent=presence.require_absent(self.io.pid)
        raw=presence.original();need(decode(raw)==absent);self.record('old-pid-absence',dict(original=frame(raw)))
        final=native.read(native.sequence);validate_native_restart(self.process.inputs.read()['oldNative'],native_birth(final))
        raw=native.original();need(decode(raw)==final);self.record('new-native-after',dict(original=frame(raw)))
        need(first['instance']==absent['instance']==final['instance'] and final['capturedEpochMs']>=absent['capturedEpochMs'])
        self.proof_anchor=started,requested,min(value['capturedEpochMs'] for value in (first,absent,final))
        self.fresh_proof();self.operations.fence.mark();self.operations.fence.check();self.fresh_proof()
        successor=dict(schemaVersion=1,processIdentity=identity,sessionNonce=uuid.uuid4().hex+uuid.uuid4().hex,nextSequence=1)
        def host_fresh():self.operations.fence.host_fresh();self.fresh_proof(host_only=True)
        def intent(value):
            host_fresh();self.operations.restart_transfer_intent(value);host_fresh()
        observed=self.io.transfer.replace(successor,intent=intent,before_publish=host_fresh)
        self.record('cursor-transferred',observed);self.fresh_proof()

    def run(self):
        def prepare():
            restore=self.operations.source.restore
            restore.bound();need(restore.state['phase']=='prepared')
            self.process.require_stop_ready(self.old_source)
            self.operations.fence.mark() # Before Native birth capture and the actual stop intent CAS.
        result=run_lifecycle_restart(self.process,prepare,lambda:self.old_source,self.stop,self.stopped,
            self.launch,self.recover,self.observe)
        # Retain only the actual successful memo after the restart's real outer
        # exit. Its packets are historical floors, never refreshed by copies.
        memo=self.process._final_delivery;need(type(memo) is dict and type(memo['readers']) is tuple and len(memo['readers'])==6)
        binding=deepcopy(self.process.state['next']['binding'])
        need(binding==self.process.state['next']['binding'] and memo['source'] is memo['readers'][0]
            and all(reader.pid==int(binding['processIdentity'].split(':')[0]) for reader in memo['readers']))
        self.memo,self.readers=memo,memo['readers']
        self.handoff=dict(binding=binding,result=deepcopy(result))
        returned=deepcopy(self.handoff)
        self.process.final_delivery(result)
        return returned

    def final(self):
        need(self.handoff is not None and self.process._final_delivery is self.memo
            and self.memo['readers'] is self.readers)
        return self.process.final_delivery(self.handoff['result'])
