"""Kernel process proofs on owned synthetic stdin workers, never Overte services."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import ast
import textwrap
import threading
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from fixture.messages_mixer import MessagesMixerObservation
from self_tests import test_messages_mixer as fixture_seams


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux original fixture process source')
class MixerFixtureSourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_seams.MessagesMixerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.processes={role:self.fixture.spawn(role) for role in MessagesMixerObservation.ROLES}
        self.source=MessagesMixerObservation(self.fixture.mixer,self.processes,self.fixture.owner.matches,
            '11111111-2222-4333-8444-555555555555',1)

    def test_only_original_mixer_changes_while_all_eight_actual_kernel_processes_stay_pinned(self):
        first=self.source.state();self.assertTrue(first['mixer']['running']);self.assertEqual(8,len(first['processes']))
        self.fixture.mixer.transition('offline');absent=self.source.state()
        self.assertFalse(absent['mixer']['running']);self.assertIsNone(absent['mixerIdentity'])
        self.assertEqual(first['processes'],absent['processes']);self.assertEqual(first['instance'],absent['instance'])
        self.fixture.mixer.transition('online');fresh=self.source.state()
        self.assertTrue(fresh['mixer']['running']);self.assertNotEqual(first['mixerIdentity'],fresh['mixerIdentity'])
        self.assertEqual(first['processes'],fresh['processes']);self.assertEqual(first['domainId'],fresh['domainId'])
        self.assertEqual(3,fresh['sequence']);self.assertEqual(3,fresh['mixer']['generation'])
        self.assertNotIn(self.fixture.owner.owner,json.dumps(fresh))
        self.assertNotIn('processId',json.dumps(fresh));self.assertNotIn('startIdentity',json.dumps(fresh))

    def test_dead_non_mixer_and_lost_original_ownership_are_unavailable_not_unchanged(self):
        self.source.state();process=self.processes['assignment-1'];process.terminate();process.wait(timeout=3)
        with self.assertRaises(NativeUIError):self.source.state()
        self.assertIsNone(self.fixture.mixer.process.poll())
        source=MessagesMixerObservation(self.fixture.mixer,{**self.processes,'assignment-1':self.fixture.spawn('1')},
            self.fixture.owner.matches,'11111111-2222-4333-8444-555555555555',1)
        source.state();source.owned=lambda _pid:False
        with self.assertRaises(NativeUIError):source.state()
        self.assertIsNone(self.fixture.mixer.process.poll())

    def test_original_endpoint_wraps_actual_source_after_only_its_existing_transition(self):
        domain=(Path(__file__).resolve().parents[1]/'fixture/domain.py').read_text()
        function=next(node for node in ast.walk(ast.parse(domain)) if isinstance(node,ast.FunctionDef) and node.name=='mixer_control')
        namespace=dict(transition_lock=threading.Lock(),stack_state='online',mixer=self.fixture.mixer,
            mixer_observation=self.source,assignment_processes=self.fixture.processes,need=lambda value:self.assertTrue(value))
        exec(compile(textwrap.dedent(ast.get_source_segment(domain,function)),'original-domain-mixer-control','exec'),namespace)
        control=namespace['mixer_control'];original=self.fixture.mixer.process
        for stream in (original.stdin,original.stdout,original.stderr):self.addCleanup(stream.close)
        first=control(None);offline=control('offline');online=control('online')
        self.assertTrue(first['mixer']['running']);self.assertFalse(offline['mixer']['running']);self.assertTrue(online['mixer']['running'])
        self.assertIsNotNone(original.poll());self.assertNotIn(original,self.fixture.processes)
        self.assertEqual(first['processes'],online['processes']);self.assertEqual(first['domainId'],online['domainId'])
        self.assertNotEqual(first['mixerIdentity'],online['mixerIdentity'])



if __name__=='__main__':unittest.main()
