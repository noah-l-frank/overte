"""Actual terminal carrier/phase linkage and runtime bypass refusals.

Paired role/window and process setup are explicit host models. These cases do
not qualify native Stop, the whole rooted graph or a physical end transition.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_rooted_fence_cut import IOSEmoteRootedFenceCut
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.self_tests import test_ios_emote_terminal_journal as journal_fixture
from ios.self_tests import test_ios_emote_rooted_process_end as process_fixture


class RootedStopAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.f=process_fixture.RootedProcessEndStorageTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def test_callable_dictionary_and_foreign_cut_cannot_authorize_canonical_stop(self):
        owner=self.f.owner
        foreign=object.__new__(IOSEmoteRootedFenceCut);foreign.end=object()
        unarmed=object.__new__(IOSEmoteRootedFenceCut);unarmed.end=owner
        for cut in (lambda:True,dict(end=owner),SimpleNamespace(end=owner),foreign,unarmed):
            with self.subTest(kind=type(cut).__name__),patch('ios.adapters.installed_process_runtime.admitted_source') as source:
                with self.assertRaises(NativeUIError):IOSEmoteRuntime._emote_rooted_stop(owner.runtime,owner,cut)
                source.assert_not_called()
        self.assertEqual([],self.f.os.queries);self.assertEqual([],self.f.stops)
    def test_requested_peer_dictionary_cannot_supply_actor_end_authority(self):
        owner=self.f.owner;owner.role='primary';owner.peer=dict(phase='complete',overrides={})
        with self.assertRaises(NativeUIError):owner.peer_identity()
        self.assertEqual([],self.f.os.queries);self.assertEqual([],self.f.stops)


class RootedFenceCutLinkTests(unittest.TestCase):
    def setUp(self):
        fixture=journal_fixture.TerminalJournalTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        journal=fixture.owner();fixture.inspect(journal);fixture.seal(journal)
        self.proof=journal.originals.read(journal.originals.expand(journal.state['record']))
        run=fixture.description['runId'];ticket=fixture.description['ticket'];binding=fixture.roles['primary'].binding
        retired=dict(fixturePhaseVersion=1,instance='3'*32,sequence=10,requestId='4'*32,runId=run,area='emotes',
            capturedEpochMs=100000,active=False,createdEpochMs=89000,retiredEpochMs=99900,
            activations=[dict(sequence=1,ticket=ticket,activatedEpochMs=90000,stimulus=dict(verb='cleanup',inputs={}))])
        before=dict(deepcopy(retired),sequence=11,requestId='5'*32,capturedEpochMs=100100)
        after=dict(deepcopy(retired),sequence=12,requestId='6'*32,capturedEpochMs=100200)
        copied=PrivateFeatureState(fixture.roles['primary'].lock.path.with_name('explicit-copy-model.json'))
        copied.write(dict(pairedScopeModel=True),None);copies={str(copied.path):copied.read()}
        archive=IOSEmoteRootedFinalArchive(PrivateFeatureState(fixture.roles['primary'].lock.path.with_name('ios-emote-rooted-final.json')),
            fixture.artifacts,binding,run,'primary',fixture.roles['primary'].lock,fixture.roles['primary'].lock,[copied],
            lambda:True,lambda actual:actual==copies)
        archive.begin(retired);archive.freeze()
        end=SimpleNamespace(run=run,role='primary',binding=binding,seal=deepcopy(self.proof['seal']),archive=archive)
        self.cut=object.__new__(IOSEmoteRootedFenceCut);self.cut.end=end;self.cut.proof=deepcopy(self.proof)
        self.cut.floor=99000;self.cut.instance=retired['instance']
        # This value models only phase/header operands. The actual Scope/key/
        # pointer/four-clock originals are required by the separate local decoder.
        self.value=dict(runId=run,role='primary',binding=deepcopy(binding),phaseBefore=before,phaseAfter=after,held=[],
            archiveSha256=digest(end.archive.previous),sealSha256=digest(end.seal),
            acquisitions=[dict(hostBeforeEpochMs=100110),dict(hostAfterEpochMs=100190)])
    def test_actual_stored_terminal_seal_context_accepts_only_its_retired_phase_prefix(self):
        self.cut.check_authority(self.value)
        for mode in ('foreign-instance','changed-prefix','active','wrong-archive','held'):
            value=deepcopy(self.value)
            if mode=='foreign-instance':value['phaseBefore']['instance']='f'*32
            elif mode=='changed-prefix':value['phaseAfter']['activations'][0]['activatedEpochMs']+=1
            elif mode=='active':value['phaseBefore'].update(active=True,retiredEpochMs=None)
            elif mode=='wrong-archive':value['archiveSha256']='e'*64
            else:value['held']=[dict(resource='panel:foreign',kind='qt-root',originalSha256='e'*64)]
            with self.subTest(mode=mode),self.assertRaises((NativeUIError,ValueError)):self.cut.check_authority(value)
    def test_changed_seal_cannot_be_blessed_by_changing_the_requested_digest(self):
        self.cut.end.seal['liveOriginalSha256']='e'*64
        value=deepcopy(self.value);value['sealSha256']=digest(self.cut.end.seal)
        with self.assertRaises((NativeUIError,ValueError)):self.cut.check_authority(value)
    def test_original_retirement_floor_cannot_be_replaced_by_an_earlier_requested_time(self):
        self.cut.floor=99901
        with self.assertRaises((NativeUIError,ValueError)):self.cut.check_authority(self.value)
    def test_unvalidated_phase_or_uncommitted_archive_state_cannot_supply_cut_authority(self):
        archive=self.cut.end.archive;saved=deepcopy(archive.state)
        archive.state['phase']='freezing'
        with self.assertRaises(NativeUIError):self.cut.check_authority(self.value)
        archive.state=deepcopy(saved);archive.state['phaseOriginal']['requestId']='e'*32
        with self.assertRaises(NativeUIError):self.cut.check_authority(self.value)
        archive.state=saved;self.cut.check_authority(self.value)
    def test_changed_actual_archive_file_cannot_inherit_validated_memory(self):
        archive=self.cut.end.archive;old=archive.store.read()
        changed=deepcopy(old);changed['runId']='f'*32;archive.store.write(changed,old)
        with self.assertRaises(NativeUIError):self.cut.check_authority(self.value)


if __name__=='__main__':unittest.main()
