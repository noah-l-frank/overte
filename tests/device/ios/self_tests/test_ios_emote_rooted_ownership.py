"""Real proof/CAS originals; role graphs and paired measurements are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.self_tests import test_ios_emote_terminal_journal as journal_fixture


class RootedOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.f=journal_fixture.TerminalJournalTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f
        for owner in f.roles.values():owner.previous={}
        f.proof['original']['journals']={role:deepcopy(live.previous) for role,live in f.roles.items()}
        f.proof['seal']['liveOriginalSha256']=digest(f.proof['original'])
        self.journal=f.owner();f.inspect(self.journal);f.seal(self.journal)
        self.publisher=f.roles['actor'].lock.path.with_name('phase-publication-emotes-'+f.description['runId']+'-actor.json')
        self.copies={str(self.journal.store.path):self.journal.previous,str(self.publisher):{}}
        for role,live in f.roles.items():
            self.copies[str(live.lock.path.with_name('ios-emote-'+role+'-feature.json'))]=dict(artifactRoot=str(live.root))

    def owner(self,copies=None):
        f=self.f;copies=deepcopy(self.copies if copies is None else copies)
        # The existing complete role parser is independently tested on actual
        # retained graphs. This seam supplies no production/native fact.
        values={path:value for path,value in copies.items() if path!=str(self.journal.store.path)}
        def store(path):need(str(path) in values);return Frozen(Path(path),values[str(path)])
        roles=SimpleNamespace(copies=values,run=f.description['runId'],locks={role:live.lock for role,live in f.roles.items()},
            read=lambda:f.window,store=store)
        with patch('ios.adapters.emote_rooted_ownership.IOSEmoteRootedState',return_value=roles):
            return IOSEmoteRootedOwnership(copies,run=roles.run,lock=roles.locks['primary'],actor_lock=roles.locks['actor'])

    def test_exact_frozen_metadata_and_actual_proof_join_without_current_sdk_reads(self):
        owner=self.owner();actual=PrivateFeatureState.read
        def no_current(store):
            if str(store.path) in self.copies:raise AssertionError('Current metadata forbidden')
            return actual(store)
        with patch.object(PrivateFeatureState,'read',no_current):self.assertEqual(self.f.proof,owner.read())
        self.assertEqual('sealed',self.journal.state['phase'])

    def test_optional_completion_projection_keeps_default_proof_and_one_guarded_role_read(self):
        owner=self.owner();role_read=owner.roles.read
        # Paired measurements stay explicitly modeled here; the real persisted
        # terminal proof and file guards remain the existing journal fixture.
        with (patch.object(owner.roles,'read',wraps=role_read) as reads,
                patch.object(self.f.window,'qualify_with_retirement_floor',return_value=(self.f.proof,104000)) as projected):
            proof,floor=owner.read_with_retirement_floor()
            self.assertEqual(self.f.proof,proof);self.assertEqual(104000,floor)
            reads.assert_called_once();projected.assert_called_once()
            self.assertEqual(self.f.proof,owner.read())
            self.assertEqual(1,projected.call_count)

    def test_later_live_journal_cannot_borrow_an_older_terminal_seal(self):
        owner=self.owner();self.f.roles['actor'].previous=dict(laterJournal=True)
        with self.assertRaises(NativeUIError):owner.read()

    def test_changed_publisher_copy_cannot_borrow_the_original_publication_proof(self):
        copies=deepcopy(self.copies);copies[str(self.publisher)]=dict(laterPublication=True)
        with self.assertRaises(NativeUIError):self.owner(copies).read()

    def test_missing_publisher_copy_never_falls_back_to_an_existing_sdk_file(self):
        copies=deepcopy(self.copies);del copies[str(self.publisher)]
        actual=PrivateFeatureState(self.publisher);actual.write({},None)
        with self.assertRaises(NativeUIError):self.owner(copies).read()
        self.assertEqual({},actual.read())

    def test_missing_or_replaced_proof_file_remains_unavailable(self):
        owner=self.owner();path=self.f.identity(self.journal)[0];value=PrivateFeatureState(path).read()
        PrivateFeatureState(path).write(value,value)
        with self.assertRaises(NativeUIError):owner.read()
        path.unlink()
        with self.assertRaises((NativeUIError,OSError)):owner.read()

    def test_missing_terminal_metadata_cannot_start_a_role_or_sdk_reader(self):
        copies=deepcopy(self.copies);del copies[str(self.journal.store.path)]
        with self.assertRaises(NativeUIError):self.owner(copies)


if __name__=='__main__':unittest.main()
