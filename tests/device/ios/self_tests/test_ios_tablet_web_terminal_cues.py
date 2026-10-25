"""Original parent intents only defer Actor work; they never grant retirement.

The earlier sealed-terminal presence is explicitly modeled. Real private files
and source locking run unchanged; no native/source/OS success is modeled here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.tablet_web_terminal_finish import actor_step
from self_tests.test_completed_frame_lease import BINDING,RUN


class TabletTerminalCueTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        self.binding=dict(BINDING,processIdentity='42')
        self.feature=SimpleNamespace(root=self.root,run=RUN,role='actor',binding=deepcopy(self.binding),locked=lambda lock:lock.held())
        self.store=PrivateFeatureState(self.root/('tabletweb-process-end-'+RUN+'.json'))
        self.terminal=patch('ios.adapters.tablet_web_terminal_finish.TabletWebTerminal',return_value=SimpleNamespace(state={'seal':'modeled prior presence only'}))
        self.terminal.start();self.addCleanup(self.terminal.stop)
        self.proof=patch('ios.adapters.tablet_web_terminal_finish.checked',side_effect=AssertionError('No full proof/OS/input may start from a missing/unissued parent cue'))
        self.checked=self.proof.start();self.addCleanup(self.proof.stop)
    def cue(self,**changes):
        value=dict(tabletWebProcessEndVersion=1,runId=RUN,binding=self.binding,payload=pack([dict(phase='prepared')]))
        value.update(changes);self.store.write(value,self.store.read())
    def test_missing_parent_and_actual_prepared_intent_wait_without_any_new_proof_OS_or_input(self):
        self.assertIs(False,actor_step(self.feature));self.assertIsNone(self.store.read())
        self.cue();raw=self.store.path.read_bytes();self.assertIs(False,actor_step(self.feature))
        self.assertEqual(raw,self.store.path.read_bytes());self.checked.assert_not_called()
    def test_foreign_run_binding_or_boolean_version_cannot_be_an_admitted_waiting_parent(self):
        for fields in (dict(runId='f'*32),dict(binding=dict(self.binding,processIdentity='43')),dict(tabletWebProcessEndVersion=True)):
            with self.subTest(fields=fields):
                self.cue(**fields);raw=self.store.path.read_bytes()
                with self.assertRaises(NativeUIError):actor_step(self.feature)
                self.assertEqual(raw,self.store.path.read_bytes());self.checked.assert_not_called()
    def test_unknown_phase_remains_owned_and_cannot_be_reclassified_as_no_stop(self):
        self.cue(payload=pack([dict(phase='unknown-stop-return')]))
        raw=self.store.path.read_bytes()
        with self.assertRaises(NativeUIError):actor_step(self.feature)
        self.assertEqual(raw,self.store.path.read_bytes());self.checked.assert_not_called()


if __name__=='__main__':unittest.main()
