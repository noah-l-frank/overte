"""Worker control routing only; native/UI/publication sources are not modeled as proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
import threading
from adapters.normal_ui import NativeUIError
from adapters.native_clock_join import digest
from adapters.script_feature.history import pack
from adapters.script_feature.lock import ScriptSourceLock,ScriptSourceBusy
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from ios import world_web_observer
from ios.adapters.world_web_terminal import WorldWebTerminal
from ios.adapters.world_web_canonical_end import verify as canonical_end
from ios.self_tests.test_ios_world_web_runtime import WorldWebRuntimeTests
from ios.self_tests.test_ios_peer_admission import PeerAdmissionTests


class EndOneIteration(BaseException):pass


class WorldWebWorkerRouteTests(unittest.TestCase):
    def modeled_admitted_roles(self):
        case=WorldWebRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        admission=PeerAdmissionTests();admission.setUp();self.addCleanup(admission.doCleanups)
        proof=admission.admit();actor=case.coordinator()
        with actor.held():
            actor.load();actor.state['binding']=deepcopy(proof['binding']);actor.state['primaryBinding']=deepcopy(admission.primary);actor.save()
            terminal=WorldWebTerminal.from_actor(actor);primary=terminal.flow
            primary.state=dict(actor.state,phase='baseline',binding=deepcopy(admission.primary),primaryBinding=deepcopy(admission.primary),actorAdmission=proof)
            primary.save()
        return actor,terminal

    def test_canonical_post_end_rejects_missing_owner_and_nonfinish_before_any_live_query(self):
        actor,owner=self.modeled_admitted_roles();calls=[]
        def forbidden(*_args,**_kwargs):calls.append('live');raise AssertionError('Canonical post-end attempted a live query')
        actor.runtime._existing=forbidden;actor.phase.status=owner.flow.phase.status=forbidden
        description=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='world-web',runId=actor.run,ticket='c'*32,
            roles={flow.role:dict(binding=binding_from_context(flow.state['binding']),heldResources=[],originalSha256=digest(flow.previous))
                for flow in (owner.flow,actor)})
        seal=dict(featureTerminalSealVersion=1,description=description,windowSha256=digest(['unobserved-window']),liveOriginalSha256=digest(['unobserved-live']))
        for flow,call,result in (
                (actor,dict(contractVersion=terminal.VERSION,runId=actor.run,stage='inspect'),dict(stage='inspect',description={})),
                (owner.flow,dict(contractVersion=terminal.VERSION,runId=actor.run,stage='inspect'),dict(stage='inspect',description={})),
                (owner.flow,dict(contractVersion=terminal.VERSION,runId=actor.run,stage='finish',seal=seal),dict(stage='finish',end={}))):
            with self.subTest(role=flow.role,stage=call['stage']),self.assertRaises(NativeUIError):canonical_end(flow,call,result)
        self.assertEqual([],calls)

    def test_active_cleanup_keeps_the_real_actor_publication_entry_selected(self):
        case=WorldWebRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        flow=case.coordinator();calls=[]
        # These are explicit control-loop seams, never source/effect receipts.
        flow.phase.status=lambda:dict(active=True,activations=[dict(stimulus=dict(verb='cleanup',inputs={}))])
        def publish():
            flow.lock.assert_held();flow.primary_lock.assert_held();blocked=[]
            def other_writer():
                try:
                    with ScriptSourceLock(flow.primary_lock.path,timeout=.05).held():blocked.append(False)
                except ScriptSourceBusy:blocked.append(True)
            thread=threading.Thread(target=other_writer);thread.start();thread.join(2)
            self.assertFalse(thread.is_alive());self.assertEqual([True],blocked);calls.append('publish')
        flow.publish=publish
        def forbidden(_call):raise AssertionError('Worker selected receipt-only cleanup instead of publication')
        flow.cleanup=forbidden
        def end(_delay):raise EndOneIteration()
        with self.assertRaises(EndOneIteration):
            world_web_observer.run_flow(flow,dict(durationSeconds=30),monotonic=lambda:1.,sleep=end)
        self.assertEqual(['publish'],calls)
        self.assertFalse(world_web_observer.failure(flow));self.assertEqual([],case.checked)

    def test_sealing_intent_pauses_without_sources_but_fake_completion_cannot_exit(self):
        actor,owner=self.modeled_admitted_roles();calls=[]
        def forbidden():calls.append('source');raise AssertionError('Post-seal native/fixture/publication query')
        actor.phase.status=actor.publish=forbidden
        with owner.held():
            # This is deliberately an intent-only journal, not qualified live
            # evidence. It may pause a worker but cannot prove a final result.
            roles={flow.role:dict(binding=binding_from_context(flow.state['binding']),heldResources=[],originalSha256=digest(flow.previous))
                for flow in (owner.flow,actor)}
            description=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='world-web',runId=actor.run,ticket='c'*32,roles=roles)
            owner.state=dict(phase='sealing',description=description,seal=None,end=None,records=[],pending=None);owner.save()
        self.assertEqual('sealed',world_web_observer.step(actor));self.assertEqual([],calls)
        before=owner.store.read();bad=deepcopy(before)
        state=deepcopy(owner.state);state['phase']='complete';bad['payload']=pack([state]);owner.store.write(bad,before)
        with self.assertRaises(NativeUIError):world_web_observer.step(actor)
        self.assertEqual([],calls)
        # Even a syntactically valid end envelope cannot stand in for the
        # missing private roles/window/OS/SDK/archive carriers. All numbers
        # below are explicitly adversarial metadata, not observed clocks.
        seal=dict(featureTerminalSealVersion=1,description=description,windowSha256=digest(['forged-window']),liveOriginalSha256=digest(['forged-live']))
        forged_roles={}
        for role,prior in roles.items():
            quiet=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance=digest([role,'instance'])[:32],
                processId=int(prior['binding']['processIdentity']),samples=3,originalSha256=digest([role,'forged-os']),
                hostAfterFirstEpochMs=100000,hostBeforeLastEpochMs=103500,hostAfterFirstMonotonic=10.,hostBeforeLastMonotonic=13.5,
                osAfterFirstEpochMs=100000,osBeforeLastEpochMs=103500,osAfterFirstMonotonicMs=10000,osBeforeLastMonotonicMs=13500)
            forged_roles[role]=dict(binding=prior['binding'],heldOriginalSha256=prior['originalSha256'],stopOriginalSha256=digest([role,'forged-stop']),
                osAbsence=quiet,sdkDeletionOriginalSha256=digest([role,'forged-sdk']),archiveSha256=digest([role,'forged-archive']))
        end=dict(featureTerminalEndVersion=1,seal=seal,roles=forged_roles);terminal.ended(end,seal)
        state.update(seal=seal,end=end);forged=deepcopy(bad);forged['payload']=pack([state]);owner.store.write(forged,bad)
        with self.assertRaises(NativeUIError):world_web_observer.step(actor)
        with self.assertRaises(NativeUIError):canonical_end(owner.flow,dict(contractVersion=terminal.VERSION,runId=actor.run,stage='finish',seal=seal),dict(stage='finish',end=end))
        self.assertEqual([],calls)

    def test_inactive_fixture_alone_never_stops_or_completes_the_actor(self):
        case=WorldWebRuntimeTests();case.setUp();self.addCleanup(case.doCleanups)
        flow=case.coordinator();calls=[];flow.phase.status=lambda:dict(active=False)
        def forbidden(*_args):calls.append('effect');raise AssertionError('Fixture inactivity is not a terminal source')
        flow.publish=flow.cleanup=flow.finalize=forbidden
        def end(_delay):raise EndOneIteration()
        with self.assertRaises(EndOneIteration):
            world_web_observer.run_flow(flow,dict(durationSeconds=30),monotonic=lambda:1.,sleep=end)
        self.assertEqual([],calls);self.assertTrue(world_web_observer.failure(flow));self.assertEqual([],case.checked)


if __name__=='__main__':unittest.main()
