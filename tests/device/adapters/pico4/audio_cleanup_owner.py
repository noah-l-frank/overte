"""Selected Audio cleanup custody around original once-only RestartInputs.

This owner retains the old Audio source forest. A process transition is not a
physical acoustic verdict or permission to delete source journals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
import uuid
import json

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import NativeFeatureObservation,need,number,fresh,decode
from adapters.pico4.navigation import validate_snapshot
from adapters.pico4.audio_pages import FILE as PAGES_FILE
from adapters.pico4.chat_restart_io import process
from adapters.normal_feature_state import PrivateFeatureState
from adapters.observer_return import state as original_file
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1,PART
from adapters.pico4.audio_cleanup_io import PicoAudioCleanupIO1
from adapters.pico4.audio_pc_start import PicoAudioPCStartCoordinator
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.restart_inputs import RestartInputs,validate_native_restart
from adapters.script_journey.history import canonical
from feature_journeys.contract import arguments

VERSION=1


def reference(store):
    value,raw,physical=original_file(store)
    return dict(name=store.path.name,sha256=hashlib.sha256(raw).hexdigest(),physical=physical)


def birth(packet):
    return dict(pid=packet['processId'],instance=packet['instance'],lifecycle=deepcopy(packet['lifecycle']))


class PicoAudioCleanupOwner1:
    def __init__(self,coordinator,budget,phase_source,*,action_started,monotonic=time.monotonic):
        need(type(coordinator) is PicoAudioPCStartCoordinator and type(budget) is AudioCleanupBudget1
             and coordinator.actor is budget.actor and coordinator.recipe is budget.recipe
             and phase_source is coordinator.recipe.source and callable(monotonic))
        budget.guard();need(not budget.failed and getattr(budget,'cleanup_owner',None) is None)
        budget.cleanup_owner=self
        self.failed=False;self.failure=None;self.io=self.physical=None
        try:
            self.coordinator,self.budget,self.source=coordinator,budget,phase_source
            self.recipe,self.actor,self.lock=coordinator.recipe,coordinator.actor,coordinator.lock
            self.monotonic=monotonic;self.previous=self.state=None;self.failed=False
            self.io=self.physical=None;self.action_started=action_started;self.last_clock=None
            need(number(action_started,budget.value['startedMonotonic'],budget.value['deadlineMonotonic']))
            self.now()
            self.store=PrivateFeatureState(self.recipe.store.path.with_name('audio-cleanup-owner.json'))
            self.input_store=PrivateFeatureState(self.store.path.with_name('audio-cleanup-inputs.json'))
            self.inputs=RestartInputs(self.input_store,(self.recipe.store,coordinator.store,self.actor.header),monotonic=monotonic)
            self.scope=dict(picoAudioCleanupOwnerVersion=VERSION,profileSha256=budget.sha,
                runId=self.recipe.run,binding=deepcopy(self.recipe.binding),
                originalRootNames=[store.path.name for store in self.inputs.owners])
            self.scope_sha=json_digest(self.scope)
            try:
                with self.lock.held():
                    need(self.store.read() is None and self.input_store.read() is None)
                    physical=object.__new__(LifecycleProcessFile);self.physical=physical
                    LifecycleProcessFile.__init__(physical,self.store)
            except BaseException:
                self.failed=True;budget.failed=True
                raise
        except BaseException as error:
            self.poison(error)
            raise

    def poison(self,error):
        # Fix the FIRST original error and traceback before any later guard,
        # callback, cleanup or diagnostics can fail. Never replace or replay it.
        if self.failure is None:self.failure=(error,error.__traceback__)
        self.failed=True;self.budget.failed=True

    def now(self):
        self.budget.guard();value=self.monotonic()
        need(number(value,self.budget.value['startedMonotonic'],self.budget.value['deadlineMonotonic'])
             and (self.last_clock is None or value>=self.last_clock)
             and (self.action_started is None or value-self.action_started<20))
        self.last_clock=value;return value

    def resource_guard(self):
        self.budget.guard();need(self.budget.cleanup_owner is self
            and self.recipe is self.budget.recipe and self.actor is self.budget.actor
            and json_digest(self.scope)==self.scope_sha)
        self.physical.guard();need(self.store.read()==self.previous)
        if self.state is not None:need(json_digest(self.state)==self.state_sha)
        self.actor.raws.verify()

    def guard(self):
        need(not self.failed and not self.budget.failed)
        self.resource_guard();self.now()

    def save(self,state):
        self.guard();raw=canonical(state);need(len(raw)+4096<=PART)
        # Exact global current/overlap bill remains authoritative; the selected
        # budget has already held root/profile/prepared CAS copies since cold IO.
        self.budget.check_global(self.io)
        value=dict(picoAudioCleanupOwnerVersion=VERSION,scope=deepcopy(self.scope),state=deepcopy(state))
        try:
            self.physical.write(value,self.previous)
            need(self.store.read()==value)
            self.previous=value;self.state=deepcopy(state);self.state_sha=json_digest(self.state)
            self.guard()
        except BaseException:
            self.failed=True;self.budget.failed=True
            raise

    def exact_cleanup(self,call):
        call=arguments('feature.audio.cleanup',call)
        need(call['runId']==self.recipe.run)
        phase=self.source.read()
        need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['status']['active'])
        return deepcopy(call),phase

    def prepare(self,call,io):
        try:
            need(type(io) is PicoAudioCleanupIO1 and io.budget is self.budget and self.state is None)
            self.io=io;self.now()
            with self.lock.held():
                self.guard();self.coordinator.bound();self.recipe.load();self.recipe.resources()
                need(self.recipe.state['cursor']==14 and self.recipe.state['pending'] is None
                     and len(self.coordinator.state['completed'])==14 and self.coordinator.state['pending'] is None
                     and self.coordinator.state['digitalRetired'] is True
                     and self.actor.state['quiet'] is not None and self.actor.state['quiet']['complete']
                     and all(job['retired'] for job in self.actor.state['jobs'])
                     and self.actor.executor is None and all(future.done() for future in self.actor.jobs.values()))
                call,phase=self.exact_cleanup(call)
                self.budget.freeze_old_acquisition(self)
                roots=[reference(store) for store in self.inputs.owners]
                baseline_frame=next(row for row in self.actor.frames if row['kind']=='observation')
                baseline=dict(actual=deepcopy(baseline_frame['actual']),settings=deepcopy(baseline_frame['settings']['source']),
                    pages=deepcopy(baseline_frame['pages']['picoAudioPages']['originals']))
                need(len(canonical(baseline))<=16384)
                self.save(dict(phase='prepared',cleanupCall=call,fixture=phase['status'],baseline=baseline,
                    oldRoots=roots,restart=None,bindingTransfer=None,newBinding=None,newProof=None,
                    roleQuiet=None,receipt=None))
            return deepcopy(self.state)
        except BaseException as error:
            self.poison(error)
            raise

    def phase(self):
        self.guard();phase=self.source.read(self.state['fixture'])
        need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['status']['active']
             and phase['ticket']==self.state['fixture']['activations'][-1]['ticket'])
        return phase

    def issue(self,phase):
        value=deepcopy(self.state);value['phase']=phase;self.save(value)

    def final_input(self):
        # This callback runs directly before the existing single SDK input.
        self.phase();self.io.business();self.now()

    def old_roots(self):
        self.resource_guard()
        need([reference(store) for store in self.inputs.owners]==self.state['oldRoots'])
        self.recipe.sources.load(self.recipe.disk['chunks'])
        self.actor.history.verify()

    def process_transition(self,old_native):
        """Actual original transaction, not an ACK-derived process result.

        Sources and post-transition quiet are composed separately and must both
        complete before a receipt can be published. Unknown input never retries.
        """
        try:
            self.guard();need(self.state['phase']=='prepared' and type(old_native) is NativeFeatureObservation
                and self.io.query is None and any(row[0]=='old' and row[1]=='primary'
                    and row[2]==self.recipe.binding['processIdentity'] and row[4] is old_native
                    for row in self.io.source_sets))
            with self.lock.held():
                self.old_roots();self.phase()
                self.io.begin_query('old','primary')
                original=self.inputs.capture(self.recipe.binding,old_native)
                value=deepcopy(self.state);value['restart']=reference(self.input_store);self.save(value)
                self.issue('stop-issued')
                self.inputs.stop(lambda:self.io.stop(self.final_input))
                self.io.end_query()
                stopped=self.io.stopped();need(stopped==dict(running=False,identity=None))
                value=deepcopy(self.state);value['phase']='stopped';value['restart']=reference(self.input_store);value['stopProcessQuery']=deepcopy(self.io.transport.last_process_query);self.save(value)
                self.issue('launch-issued')
                self.inputs.launch(self.io.stopped,lambda:self.io.launch(self.final_input))
                value=deepcopy(self.state);value['restart']=reference(self.input_store);self.save(value)
            return original
        except BaseException as error:
            self.poison(error)
            raise

    def bind_new_process(self,identity,native,presence):
        try:
            self.guard();need(self.state['phase']=='launch-issued' and self.io.query is not None
                and any(row[0]=='new' and row[1]=='primary' and row[2]==identity
                    and row[4] is native and row[5] is presence for row in self.io.source_sets))
            old_pid,old_start=process(self.recipe.binding['processIdentity']);new_pid,new_start=process(identity)
            need(new_pid!=old_pid and new_start>old_start)
            began=self.now();first=native.read(native.sequence,require_recorded_history=True)
            old=self.inputs.read()['oldNative'];validate_native_restart(old,birth(first))
            absent=presence.require_absent(old['pid']);after=native.read(native.sequence,require_recorded_history=True)
            need(first['instance']==absent['instance']==after['instance'] and after['processId']==first['processId'])
            oldest=min(first['capturedEpochMs'],absent['capturedEpochMs'],after['capturedEpochMs'])
            proof=dict(identity=identity,native=first,absence=absent,nativeAfter=after)
            self.phase();self.io.business();fresh(oldest,native.clock_ms());need(self.now()-began<=1.5)
            # No process/HTTP/SDK operation is permitted inside the cursor lock.
            successor=dict(schemaVersion=1,processIdentity=identity,sessionNonce=uuid.uuid4().hex+uuid.uuid4().hex,nextSequence=1)
            def host_fresh():need(self.now()-began<=1.5)
            def intent(value):
                host_fresh();current=deepcopy(self.state);current.update(phase='binding-transfer-issued',bindingTransfer=deepcopy(value))
                # Intentionally pure original host CAS; no source/global SDK guard.
                physical=dict(picoAudioCleanupOwnerVersion=VERSION,scope=deepcopy(self.scope),state=current)
                self.physical.write(physical,self.previous);self.previous=physical;self.state=current;self.state_sha=json_digest(current)
                host_fresh()
            observed=self.io.transport.transfer.replace(successor,intent=intent,before_publish=host_fresh)
            host_fresh()
            return proof,observed,began
        except BaseException as error:
            self.poison(error)
            raise

    def observe_and_bind_new_process(self):
        """Real selected sources and original once-only cursor publication.

        This reaches a known binding, not quiet/resource/account retirement or
        a full feature cleanup receipt. Every decoder charge stays retained.
        """
        try:
            self.guard();need(self.state['phase']=='launch-issued' and self.io.query is None)
            identity=self.io.adapter.controlled_debug_identity(self.io.target)
            query_anchor=self.io.begin_query('new','primary')
            raw=self.io._literal(identity,PAGES_FILE)
            navigation=decode(raw)
            validate_snapshot(navigation,int(identity.split(':')[0]),self.io.adapter.adb.epoch_milliseconds(self.io.target))
            native,presence,_settings,_pages=self.io.sources(identity,navigation['bridgeId'])
            proof,observed,began=self.bind_new_process(identity,native,presence)
            # The original host generation remains monotonic. The measured new PID
            # and bridge replace their own fields; a process birth is no reason
            # to reset the independently owned context generation.
            binding=dict(self.recipe.binding,processIdentity=identity,sessionId=navigation['bridgeId'])
            post=self.inputs.observe(binding,native)
            need(post['instance']==proof['native']['instance'] and post['processId']==proof['native']['processId'])
            self.phase();self.io.guard_identity(identity)
            with self.lock.held():
                value=deepcopy(self.state)
                value.update(phase='new-bound',newBinding=binding,
                    newProof=dict(native=proof,transfer=observed,navigation=navigation,nativeAfterTransfer=post),
                    restart=reference(self.input_store))
                self.save(value)
            self.io.end_query();self.guard()
            need(self.now()-query_anchor[0]<=1.5)
            fresh(min(proof['native']['capturedEpochMs'],proof['absence']['capturedEpochMs'],
                proof['nativeAfter']['capturedEpochMs'],post['capturedEpochMs'],navigation['updatedEpochMs']),native.clock_ms())
            return deepcopy(self.state)
        except BaseException as error:
            self.poison(error)
            raise

    def observe_idempotent_cleanup(self,call):
        """Reobserve the same replacement; never deliver Stop or Launch again."""
        try:
            self.guard()
            need(type(self.state) is dict and self.state['phase']=='new-bound' and self.io.query is None
                 and arguments('feature.audio.cleanup',call)==self.state['cleanupCall'])
            self.phase();binding=self.state['newBinding']
            self.io.guard_identity(binding['processIdentity'])
            rows=[row for row in self.io.source_sets if row[0]=='new' and row[1]=='primary'
                  and row[2]==binding['processIdentity'] and row[3]==binding['sessionId']]
            need(rows)
            native=rows[0][4]
            began=self.io.begin_query('new','primary')
            observed=self.inputs.observe(binding,native)
            need(observed['instance']==self.state['newProof']['native']['native']['instance'])
            self.io.end_query();self.io.guard_identity(binding['processIdentity']);self.phase()
            with self.lock.held():
                self.old_roots();value=deepcopy(self.state)
                value['restart']=reference(self.input_store);self.save(value)
            need(self.now()-began[0]<=1.5)
            fresh(observed['capturedEpochMs'],native.clock_ms())
            return deepcopy(binding)
        except BaseException as error:
            self.poison(error)
            raise

    def quiet_projection(self,sampler,encoded):
        # Only immutable compact bytes leave this exact bounded parse frame.
        need(any(sampler is item for item in self.budget.new_samplers)
            and encoded is sampler.last_output and type(encoded) is bytes and len(encoded)<=16384)
        value=json.loads(encoded)
        need(value['picoAudioCleanupSnapshotVersion']==2 and value['epoch']=='new'
            and value['role']==sampler.role and value['baselineRestored'] is True
            and value['processIdentity']==self.state['newBinding']['processIdentity']
            and value['nativeInstance']==self.state['newProof']['native']['native']['instance']
            and len(value['originalClocks'])==7)
        projected=dict(role=value['role'],sequence=value['sequence'],instance=value['nativeInstance'],
            key=value['quietStateSha256'],clocks=value['originalClocks'])
        raw=canonical(projected);need(len(raw)<=4096);return raw

    def quiet_tokens(self,start):
        need(type(start) is int and 0<=start<41)
        for ordinal in range(start,min(start+8,41)):
            command=dict(audioCleanupDerivedQuietPairVersion=1,runId=self.recipe.run,
                scopeSha256=self.scope_sha,ordinal=ordinal,processIdentity=self.state['newBinding']['processIdentity'])
            token=self.actor.raws.reserve('audio-cleanup-derived-quiet-pair',command,2*16384+32)
            self._quiet_tokens.append(token)

    def observe_new_quiet(self):
        """Two measured G1 readers, original3s/500ms/1.5/20/120 boundaries.

        Derived pair receipts are named as such; SDK literals remain separately
        archived. Preparing8 reservations precedes the quiet window. Per-pair
        Raw receipts are durable; the Owner completion CAS follows the window.
        This neither grants Actor credentials nor retires any source resource.
        """
        try:
            self.guard();need(type(self.state) is dict and self.state['phase']=='new-bound' and self.io.query is None)
            self.phase();self.budget.admit_new_quiet(self)
            self._quiet_tokens=[];self._quiet_rows=[];self._quiet_compact=[]
            self.quiet_tokens(0)
            self.issue('quiet-reading')
            first=previous=None;first_host=previous_host=None;keys=None;windows=0
            for attempt in range(41):
                if attempt>=len(self._quiet_tokens):self.quiet_tokens(attempt)
                polled=self.now();raws=[];compact=[]
                for sampler in self.budget.new_samplers:
                    encoded=sampler.sample();raws.append(encoded)
                    compact.append(self.quiet_projection(sampler,encoded))
                framed=(b'AudioQuietPair1\x00'+len(raws[0]).to_bytes(4,'big')+raws[0]
                    +len(raws[1]).to_bytes(4,'big')+raws[1])
                need(len(framed)<=2*16384+32)
                ref=self.actor.raws.retain(self._quiet_tokens[attempt],framed)
                self._quiet_rows.append(ref);self._quiet_compact=compact
                # Compact graphs are bounded by the permanent quiet credit.
                measured=[json.loads(raw) for raw in compact]
                clocks=[stamp for row in measured for stamp in row['clocks']]
                current_keys=[row['key'] for row in measured];now=self.now()
                need(all(number(stamp,1,1e15) for stamp in clocks))
                if first is None:
                    first=list(clocks);first_host=now;keys=current_keys
                else:
                    need(current_keys==keys and all(a>=b for a,b in zip(clocks,previous)))
                    if now-previous_host>.5 or any(a-b>500 for a,b in zip(clocks,previous)):
                        windows+=1;need(windows<8);first=list(clocks);first_host=now
                complete=now-first_host>=3 and all(a-b>=3000 for a,b in zip(clocks,first))
                previous=list(clocks);previous_host=now
                if complete and attempt+1==len(self._quiet_tokens):
                    # Unused genuinely issued reservations remain owned/pending;
                    # a completed window must use its entire prepared cohort.
                    need(attempt+1==len(self._quiet_tokens))
                    self.phase();self.io.guard_identity(self.state['newBinding']['processIdentity'])
                    value=deepcopy(self.state);value.update(phase='new-quiet',roleQuiet=dict(
                        version=1,first=first,last=clocks,firstHost=first_host,lastHost=now,
                        keys=keys,incompleteWindows=windows,references=deepcopy(self._quiet_rows),complete=True))
                    self.save(value);self.guard()
                    oldest=min(clocks);fresh(oldest,self.budget.new_samplers[0].native.clock_ms())
                    return deepcopy(self.state)
                need(attempt<40)
                # Actual Source/Root work consumes the period; no timestamp is
                # renewed. Sleep0 still yields when the original work exceeds it.
                self.io.sleep(max(0,.45-(self.now()-polled)))
            need(False)
        except BaseException as error:
            self.poison(error)
            raise

    def close_host(self):
        # Strongly registered budget/owner/IO remains retained on any unknown.
        okay=self.physical is not None and self.physical.close_host() is True
        if self.io is not None:okay=(self.io.close_host() is True) and okay
        if not okay:self.failed=True;self.budget.failed=True
        return okay
