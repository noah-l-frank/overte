"""Snapshot Actor scheduling policy only; no target, input or effect producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import ast
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_snapshots_actor import PhoneSnapshotsActor
from overte_phone_script_lock import PhoneScriptSourceBusy


class SnapshotActorPollingTests(unittest.TestCase):
    def actor(self):
        actor=PhoneSnapshotsActor.__new__(PhoneSnapshotsActor)
        actor._cleanup_reader=None;actor._cleanup_anchor=None;actor._cleanup_failed=False;actor._ordinary_failed=False;actor.state=None
        actor.feature=Mock(spec=(),side_effect=AssertionError('Polling grants no source authority'))
        return actor
    def test_no_initialized_or_retained_reader_uses_the_normal_cadence(self):
        actor=self.actor();self.assertEqual(.25,actor.poll_delay())
        actor.state=dict(phase='watching',quiet=dict(complete=True),pending=None);self.assertEqual(.25,actor.poll_delay())
        actor.feature.assert_not_called()
    def test_retained_reader_without_a_completed_current_sample_is_not_accelerated(self):
        actor=self.actor();actor._cleanup_reader=object();actor._cleanup_anchor=object();actor.state=dict(phase='watching',quiet=None,pending=None)
        self.assertEqual(.25,actor.poll_delay());actor.feature.assert_not_called()
    def test_actual_cleanup_continuity_keeps_two_source_lock_contender_opportunities(self):
        actor=self.actor();actor._cleanup_reader=object();actor._cleanup_anchor=object();actor.state=dict(phase='watching',quiet=dict(complete=False),pending=None)
        self.assertEqual(.05,actor.poll_delay());self.assertGreaterEqual(actor.poll_delay(),2*.025)
        actor.state['quiet']['complete']=True;self.assertEqual(.05,actor.poll_delay())
        actor.state['pending']=dict(issued=True);self.assertEqual(.25,actor.poll_delay())
        actor.state['pending']=None;actor._cleanup_anchor=None;self.assertEqual(.25,actor.poll_delay())
        actor.feature.assert_not_called()
    def test_closed_or_failed_flow_cannot_keep_the_short_cleanup_yield(self):
        actor=self.actor();actor._cleanup_reader=object();actor._cleanup_anchor=object();actor.state=dict(phase='retired',quiet=dict(complete=True),pending=None)
        self.assertEqual(.25,actor.poll_delay());actor.state['phase']='watching'
        actor._cleanup_failed=True;self.assertEqual(.25,actor.poll_delay())
        actor._cleanup_failed=False;actor._ordinary_failed=True;self.assertEqual(.25,actor.poll_delay())
        actor.feature.assert_not_called()
    def test_actual_host_actor_loop_uses_the_same_policy_and_busy_cadence(self):
        import test_snapshots_feature_journey as journey
        tree=ast.parse(journey.ACTOR)
        loop=next(node for node in tree.body if isinstance(node,ast.While))
        flow=SimpleNamespace(step=Mock(side_effect=[False,PhoneScriptSourceBusy(),True]),poll_delay=Mock(return_value=.05))
        adapter=SimpleNamespace(actor=Mock(return_value=flow));clock=[0.];delays=[]
        def sleep(value):delays.append(value);clock[0]+=value
        namespace=dict(time=SimpleNamespace(monotonic=lambda:clock[0],sleep=sleep),started=0.,flow=None,
            adapter=adapter,RUN='b'*32,client=object(),sys=sys,PhoneScriptSourceBusy=PhoneScriptSourceBusy)
        with self.assertRaises(SystemExit) as closed:
            exec(compile(ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[])),'<original-host-actor-loop>','exec'),namespace)
        self.assertEqual(0,closed.exception.code);self.assertEqual([.05,.25],delays)
        self.assertEqual(3,flow.step.call_count);flow.poll_delay.assert_called_once_with()
        adapter.actor.assert_called_once()


if __name__=='__main__':unittest.main()
