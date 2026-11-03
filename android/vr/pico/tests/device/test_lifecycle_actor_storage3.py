"""Same seven normal actions and independent Actor with opt-in Background3.

Only the existing private factory constructor option changes. The original
inputs, source counts, worker ownership, waits and required image gaps remain.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import time
import traceback
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundHistory
from adapters.script_journey.history import canonical
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
import test_lifecycle_actor_world as original


class LifecycleActorStorage3Tests(unittest.TestCase):
    baseline=original.LifecycleActorWorldTests.baseline
    fields=original.LifecycleActorWorldTests.fields
    act=original.LifecycleActorWorldTests.act

    def setUp(self):
        self.stage=original.operations_fixture.composition_fixture.LifecycleActorCompositionTests()
        self.stage.setUp();self.addCleanup(self.stage.doCleanups)
        adapter=self.stage.editor.adapter;factory=adapter._lifecycle_background_owner
        self.background=None
        def actual_background(target,run,**arguments):
            need('raw_layout' not in arguments and self.background is None)
            self.background=factory(target,run,raw_layout=True,**arguments)
            self.addCleanup(self.background.close_storage_host)
            return self.background
        # Constructor selection precedes coordinator/child admission. No
        # fixture mode or admitted owner is changed after construction.
        adapter._lifecycle_background_owner=actual_background
        self.graph=original.operations_fixture.CanonicalLifecycleOperationGraph(self,self.stage)
        before=self.stage.configuration.read()
        self.stage.configuration.write(dict(before,traceWorldOwnership=True),before);self.stage.start()

    def test_same_seven_normal_actions_and_actual_worker_exit_with_background_raw_ranges(self):
        try:
            original.LifecycleActorWorldTests.test_actual_common_source_prefix_includes_normal_world_attempt_from_own_native_events(self)
            background=self.background;self.assertIsNotNone(background)
            self.assertEqual(3,background.version)
            with background.lock.held():
                background.originals.seal();namespace=background.raw_namespace()
                raw=background.originals.archive.bill()
            history=LifecycleBackgroundHistory(background.store.path);self.addCleanup(history.close)
            self.assertEqual(background.state,history.read())
            report=dict(lifecycleActorBackgroundStorageVersion=3,actualNormalActions=7,
                raw=raw,otherNamespace=namespace,maximumOtherNamespace=background.raw_namespace.maximum,
                rawLiteralReceipts=background.originals.archive.state['reads'],
                stageCurrentRootPending=deepcopy(background.originals.archive.state['pending']),
                capacityOnlySessionMutexObservations=len(background.raw_namespace.mutex_observations),
                capacityOnlyMutexMetadataBytes=background.raw_namespace.metadata_bytes(),
                sourceGroups=24,actorSixSourceQueries=144,whole16Proved=False)
            print('Background3 exact final bill: '+canonical(report).decode(),flush=True)
        finally:
            if self.background is not None:
                raw=self.background.originals.archive
                diagnostics=dict(lifecycleActorBackgroundStorageDiagnosticVersion=3,
                    phase=None if self.background.state is None else self.background.state['phase'],
                    raw=raw.bill(),rawFailed=raw.failed,rawStopped=raw.stopped,
                    readReservations=raw.state['reads'],pending=deepcopy(raw.state['pending']),
                    lastOtherNamespace=self.background.raw_namespace.last,
                    maximumOtherNamespace=self.background.raw_namespace.maximum)
                # Diagnostic is external to the measured ownership namespace;
                # it never affects admission, source clocks or owner grammar.
                print('Background3 retained diagnostic: '+canonical(diagnostics).decode(),flush=True)


class LifecycleActorStorage3EntryTests(unittest.TestCase):
    setUp=LifecycleActorStorage3Tests.setUp
    baseline=LifecycleActorStorage3Tests.baseline
    fields=LifecycleActorStorage3Tests.fields
    act=LifecycleActorStorage3Tests.act

    def storage_failure_receipt(self,error):
        chain=[];seen=set();current=error
        while current is not None and id(current) not in seen:
            seen.add(id(current));frames=[]
            for frame,lineno in traceback.walk_tb(current.__traceback__):
                scalars={key:value for key,value in frame.f_locals.items()
                    if key in ('name','role','size','decoded','stored','held','peak','parts','count','old','new','raw','metadata')
                    and type(value) in (str,int,float,bool,type(None))}
                budgets={key:deepcopy(value) for key,value in frame.f_locals.items()
                    if key in ('budget','current','ours','result') and type(value) is dict
                    and all(type(k) is str and type(v) in (int,float,bool,type(None)) for k,v in value.items())}
                physical={key:list(value) for key,value in frame.f_locals.items()
                    if key in ('before','after') and type(value) in (list,tuple) and len(value)==8
                    and all(type(v) is int for v in value)}
                frames.append(dict(file=frame.f_code.co_filename,line=lineno,function=frame.f_code.co_name,
                    scalars=scalars,budgets=budgets,physical=physical))
            chain.append(dict(type=type(current).__name__,message=str(current),frames=frames));current=current.__context__
        owner=self.background;raw=owner.originals;namespace=owner.raw_namespace
        active=namespace._write
        report=dict(lifecycleBackgroundFailureDiagnosticVersion=1,phase=owner.state['phase'],exceptionChain=chain,
            raw=raw.archive.bill(),rawFailed=raw.failed,archiveFailed=raw.archive.failed,archiveStopped=raw.archive.stopped,
            pending=deepcopy(raw.archive.state['pending']),rawCapacityBytes=raw.metadata_capacity(),lastOtherNamespace=namespace.last,
            maximumOtherNamespace=namespace.maximum,admittedOtherNamespace=dict(namespace._admitted_bill),
            mutexTransitions=len(namespace.mutex_observations),mutexBytes=namespace.metadata_bytes(),
            latestMutexTransitions=deepcopy(namespace.mutex_observations[-6:]),
            gates={role:dict(receipts=len(gate.receipts),metadataBytes=gate.metadata_bytes(),poisoned=gate.poisoned,
                pendingKind=None if gate.pending is None else gate.pending.kind,heldValues=len(gate.held),
                preparedChildren=sum(len(permit.prepared or {}) for permit in gate.held),maximumReservedPeak=gate.peak)
                for role,gate in raw.write_gates.items()},
            activeWrite=None if active is None else dict(role=active[0].role,kind=active[1].kind,
                parts=active[2],storedBytes=active[3],decodedBytes=active[4],remainingMetadataBytes=active[6]),
            worldFrames=len(self.graph.world.state['frames']),sourceRecords=len(self.graph.source.disk['records']),
            normalOsInputs=deepcopy(self.stage.editor.background.inputs))
        path=self.stage.root.parent/'lifecycle-storage3-entry-failure.json'
        path.write_bytes(canonical(report)+b'\n');path.chmod(0o600)
        print('Retained exact Background3 failure diagnostic: '+str(path),flush=True)

    def test_actual_canonical_factory_normal_background_entry_and_original_process_return(self):
        self.baseline()
        try:
            for index in range(7):self.act(index)
        except BaseException as error:
            self.storage_failure_receipt(error);raise
        owner=self.background;self.assertIs(owner,self.graph.source.background)
        self.assertEqual('released',owner.state['phase']);self.assertEqual(3,owner.version)
        self.assertTrue(owner.raw_namespace.mutex_observations)
        self.assertEqual(['lifecycle.background','app.launch'],
            [row['operation'] for row in self.stage.editor.background.inputs])
        self.assertFalse(self.stage.editor.background.history.active)
        with owner.lock.held():
            other=owner.originals.other_bill();namespace=deepcopy(owner.raw_namespace.last);raw=owner.originals.archive.bill()
            report=dict(lifecycleActorBackgroundEntryVersion=3,actualNormalActions=7,
                raw=raw,otherNamespace=namespace,otherWithActualRawOverlap=other,maximumOtherNamespace=owner.raw_namespace.maximum,
                capacityOnlySessionMutexObservations=len(owner.raw_namespace.mutex_observations),
                capacityOnlyMutexMetadataBytes=owner.raw_namespace.metadata_bytes(),
                writerReceiptCounts={role:len(gate.receipts) for role,gate in owner.originals.write_gates.items()},
                writerMetadataBytes={role:gate.metadata_bytes() for role,gate in owner.originals.write_gates.items()},
                whole24SourceGroupsProved=False,whole16Proved=False)
        print('Background3 strong-lease canonical entry bill: '+canonical(report).decode(),flush=True)
        self.stage.command('exit');self.stage.worker.wait(timeout=10);self.assertEqual(0,self.stage.worker.returncode)
        absent=self.stage.process.require_absent();self.stage.process.final_absence(absent)
        # Only the baseline was peer-sampled here. The independently bounded
        # original24-group seven-action proof is a separate explicit selector.
        self.assertEqual(3,len(self.graph.actor_samples))


class LifecycleActorStorage3DispatchCounters(unittest.TestCase):
    setUp=LifecycleActorStorage3Tests.setUp
    baseline=LifecycleActorStorage3Tests.baseline
    fields=LifecycleActorStorage3Tests.fields
    act=LifecycleActorStorage3Tests.act

    def boundary(self,fault):
        self.baseline()
        for index in range(6):self.act(index)
        adapter=self.stage.editor.adapter;factory=adapter._lifecycle_background_owner;checks=[];delayed=[]
        def factory_with_counter(*args,**kwargs):
            owner=factory(*args,**kwargs);run=owner.run_owned
            def original_run():
                reader=owner.runtime[1];fence=owner.phase_fence;check=fence.check
                def checked():
                    result=check();checks.append(True)
                    if len(checks)==2 and fault=='foreign-phase-part':
                        writer=fence.owner;index=len(writer.history.identities)
                        child=writer.history.store(index-1).read();child=deepcopy(child);child['index']=index
                        PrivateFeatureState(writer.history.store(index).path).write(child,None)
                    return result
                with ExitStack() as active:
                    active.enter_context(patch.object(fence,'check',checked))
                    if fault=='dispatch':
                        active.enter_context(patch.object(reader,'dispatch',lambda _request:self.fail('Replaced SDK dispatch must not execute')))
                    elif fault=='callback':active.enter_context(patch.object(reader,'before_io',lambda *_args:None))
                    elif fault=='late-five-seconds':
                        # Explicit adverse clock boundary for this new ARM
                        # acquisition: frozen native epoch, actual host clock.
                        # Earlier historical receipts keep their old clocks.
                        active.enter_context(patch.object(reader,'monotonic',time.monotonic))
                        active.enter_context(patch.object(reader,'clock_ms',lambda:self.stage.native.epoch()))
                        admission=LifecycleNamespaceBill.__call__
                        def actual_bill(namespace):
                            result=admission(namespace)
                            if namespace is owner.raw_namespace and len(checks)>=2 and not delayed:
                                delayed.append(True);time.sleep(5.05)
                            return result
                        active.enter_context(patch.object(LifecycleNamespaceBill,'__call__',actual_bill))
                    return run()
            owner.run_owned=original_run;return owner
        adapter._lifecycle_background_owner=factory_with_counter
        with self.assertRaises(NativeUIError):self.act(6)
        self.assertEqual([], [row for row in self.stage.editor.background.history.commands if row['operation']=='arm'])
        self.assertEqual([],self.stage.editor.background.inputs)
        if fault in ('foreign-phase-part','late-five-seconds'):self.assertEqual(2,len(checks))
        if fault=='late-five-seconds':self.assertEqual([True],delayed)

    def test_actual_second_fence_writes_then_slow_full_bill_cannot_reach_sdk_dispatch(self):self.boundary('late-five-seconds')
    def test_unowned_plausible_phase_part_is_not_adopted_before_actual_sdk(self):self.boundary('foreign-phase-part')
    def test_replaced_actual_dispatch_is_refused_before_sdk(self):self.boundary('dispatch')
    def test_replaced_actual_callback_is_refused_before_sdk(self):self.boundary('callback')


class LifecycleActorStorage3StrictEntryCounters(unittest.TestCase):
    setUp=LifecycleActorStorage3Tests.setUp
    baseline=LifecycleActorStorage3Tests.baseline
    fields=LifecycleActorStorage3Tests.fields
    act=LifecycleActorStorage3Tests.act

    def test_missing_original_chat_write_gate_keeps_composition_closed(self):
        self.baseline()
        for index in range(6):self.act(index)
        adapter=self.stage.editor.adapter;factory=adapter._lifecycle_background_owner
        def missing_chat_receipt(*args,**kwargs):
            owner=factory(*args,**kwargs);install=owner.originals.install_writer
            def install_existing(writer,role):
                if role=='chat':return None
                return install(writer,role)
            owner.originals.install_writer=install_existing;return owner
        adapter._lifecycle_background_owner=missing_chat_receipt
        with self.assertRaises(NativeUIError):self.act(6)
        self.assertIsNotNone(self.background);self.assertIsNone(self.background.state)
        self.assertEqual(0,self.background.originals.archive.bill()['receipts'])
        self.assertEqual([],self.stage.editor.background.inputs)
        self.assertEqual([],self.stage.editor.background.history.commands)
        self.stage.command('exit');self.stage.worker.wait(timeout=10);self.assertEqual(0,self.stage.worker.returncode)
        absent=self.stage.process.require_absent();self.stage.process.final_absence(absent)


if __name__=='__main__':unittest.main()
