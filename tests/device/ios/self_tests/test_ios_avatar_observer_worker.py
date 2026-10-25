"""Worker scheduling against an original phase journal, no product verdict.

Only the coordinator methods are inert scheduling doubles. Product cleanup and
original retirement qualification are covered separately, never inferred here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from pathlib import Path
import secrets
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Journal,Client
from ios.avatar_observer import run_flow,failure


class AvatarObserverWorkerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.time=1.;self.run='a'*32;self.journal=Journal(clock=self.epoch)
        with patch.object(secrets,'token_hex',return_value=self.run):self.journal.register('avatar-people')
        self.journal.activate(self.run,'b'*32,'cleanup');self.client=Client('https://controlled.invalid/feature-fixture/v1','r'*64)
        self.client.request=lambda path,phase_nonce:self.journal.phase(self.run,phase_nonce)
        self.events=[];self.polls=0;self.retire=True
        self.flow=SimpleNamespace(root=self.root,run=self.run,role='actor',policy=dict(source='world-render-target',marker=[0,0,1,1],subject=[2,2,1,1]),
            phase=PhaseFixtureReader(self.client,self.run,'avatar-people',epoch_ms=self.epoch,monotonic=lambda:self.time),state=dict(phase='ready'),
            held=lambda:nullcontext(),load=lambda:None,cleanup=self.cleanup,finalize=self.finalize,
            observe=lambda _call:(_ for _ in ()).throw(AssertionError('Cleanup must not reopen active facts')))
        self.config=dict(target='actor',primaryTarget='primary',durationSeconds=30)
    def epoch(self):return 1700000000000+self.time*1000
    def cleanup(self,_call):self.events.append('cleanup');self.flow.state['phase']='cleaned';return dict(performed=True)
    def finalize(self):
        self.assertNotIn(self.run,self.journal.runs);self.events.append('finalize');return dict(performed=True)
    def sleep(self,seconds):
        self.time+=seconds;self.polls+=1
        if self.retire and self.polls==3:self.journal.close(self.run)
    def test_complete_waits_for_actual_retired_phase_before_worker_finalization(self):
        self.assertEqual(0,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        self.assertEqual(['cleanup','finalize'],self.events);self.assertEqual(3,self.polls)
        self.assertIsNone(next(iter(self.root.glob('avatar-worker-failed-*')),None))
    def test_prior_failed_history_still_finalizes_but_does_not_turn_green(self):
        failure(self.flow,self.config,record=True)
        self.assertEqual(2,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        self.assertEqual(['cleanup','finalize'],self.events);self.assertTrue(failure(self.flow,self.config))
    def test_active_fixture_wait_has_original_duration_without_replaying_completed_cleanup(self):
        self.retire=False
        self.assertEqual(2,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        self.assertEqual(['cleanup'],self.events);self.assertTrue(failure(self.flow,self.config));self.assertGreaterEqual(self.time,31)

    def test_original_held_end_exits_before_closed_fixture_http_and_retains_prior_failure(self):
        self.flow.state['phase']='terminal-ready';self.flow.terminal_actor_ended=lambda:True
        self.flow.phase.status=lambda:(_ for _ in ()).throw(AssertionError('No HTTP after actual ended admission'))
        self.assertEqual(0,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        failure(self.flow,self.config,record=True);path=self.root/('avatar-worker-failed-'+self.run+'.json');raw=path.read_bytes()
        self.assertEqual(2,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        self.assertEqual(raw,path.read_bytes());self.assertEqual([],self.events);self.assertEqual(0,self.polls)

    def test_original_failed_preparation_end_exits_failed_without_http_or_success_finalizer(self):
        self.flow.state['phase']='preparing';self.flow.failed_preparation_ended=lambda:True
        self.flow.phase.status=lambda:(_ for _ in ()).throw(AssertionError('No HTTP after original failed end'))
        self.assertEqual(2,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        self.assertEqual([],self.events);self.assertEqual(0,self.polls)

    def test_incomplete_held_original_cannot_skip_actual_phase_polling_or_claim_exit_success(self):
        self.retire=False;self.flow.state['phase']='terminal-ready';self.flow.terminal_actor_ended=lambda:False
        observed=[];status=self.flow.phase.status
        def current():observed.append(True);return status()
        self.flow.phase.status=current;self.flow.observe=lambda _call:None
        self.assertEqual(2,run_flow(self.flow,self.config,monotonic=lambda:self.time,sleep=self.sleep))
        self.assertTrue(observed);self.assertEqual([],self.events);self.assertGreaterEqual(self.time,31)


if __name__=='__main__':unittest.main()
