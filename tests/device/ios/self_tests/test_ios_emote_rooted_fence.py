"""Real scope/input/proof files; native and fixture phase are explicit models.

These component cases do not qualify the frozen whole paired graph or any
Stop/OS/SDK integration. The public acquire entry still requires the actual
typed RootedOwnership and durable frozen archive, without a modeled fallback.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_rooted_fence import _local,_seal,_current_metadata,acquire,current,inactive
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_terminal_window import _retirement_floor
from ios.self_tests.test_ios_emote_rooted_quiet import EmoteRootedQuietTests
from ios.self_tests import test_ios_emote_terminal_journal as journal_fixture
from ios.self_tests.test_ios_emote_sources import BINDING,RUN,phase as phase_packet


class RootedFenceLocalTests(unittest.TestCase):
    def setUp(self):
        self.f=EmoteRootedQuietTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.refresh();self.scope,self.domain=self.f.scope,self.f.domain
        self.instance='3'*32;self.ticket='a'*32;self.calls=0;self.mode=None;self.callback=None
        self.retired=self.scope.epoch_ms();self.after=self.retired-1
        client=object.__new__(Client);client.url=self.scope.fixture_url.split('/runs/')[0];client.request=self.phase_request
        self.phase=PhaseFixtureReader(client,self.scope.run,'emotes',epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)

    def phase_request(self,path,*,phase_nonce):
        self.assertEqual('/runs/'+self.scope.run+'/phase',path);self.calls+=1
        if self.mode=='missing':return None
        if self.callback is not None:self.callback(self.calls)
        captured=self.scope.epoch_ms()-(2000 if self.mode=='stale' else 0)
        return dict(fixturePhaseVersion=1,instance='4'*32 if self.mode=='foreign-instance' else self.instance,
            sequence=self.calls,requestId=phase_nonce,runId=self.scope.run,area='emotes',capturedEpochMs=captured,
            active=self.mode=='active',createdEpochMs=self.retired-4000,
            retiredEpochMs=None if self.mode=='active' else self.retired,
            activations=[dict(sequence=1,ticket='b'*32 if self.mode=='foreign-ticket' else self.ticket,
                activatedEpochMs=self.retired-3000,stimulus=dict(verb='cleanup',inputs={}))])

    def local(self):
        return _local(self.scope,self.f.pointers,self.f.keys,self.phase,
            instance=self.instance,ticket=self.ticket,after=self.after)

    def test_real_scope_keys_pointer_originals_keep_held_roots_and_both_clock_domains(self):
        actions=list(self.domain.io.actions);held=self.scope.held_originals()
        value=self.local()
        self.assertEqual(held,value['held']);self.assertEqual(actions,self.domain.io.actions)
        self.assertFalse(value['phaseBefore']['active']);self.assertFalse(value['phaseAfter']['active'])
        self.assertEqual(self.scope.snapshot(),value['scope']);self.assertEqual(5,len(value['acquisitions']))
        self.assertGreater(abs(value['acquisitions'][0]['hostBeforeEpochMs']-value['nativeClock']['before']['epochMs']),1500)
        self.assertTrue(current(value['acquisitions'],value['nativeClock'],epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic))
        bad=deepcopy(value['nativeClock']);bad['after']['monotonicMs']-=2000
        with self.assertRaises(NativeUIError):current(value['acquisitions'],bad,epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)
        self.domain.sleep(1.5)
        with self.assertRaises(NativeUIError):current(value['acquisitions'],value['nativeClock'],epoch_ms=self.scope.epoch_ms,monotonic=self.scope.monotonic)
        self.assertEqual(actions,self.domain.io.actions)

    def test_missing_active_foreign_and_stale_phase_refuse_before_any_new_native_read(self):
        before=(len(self.scope.frames),len(self.f.keys.state['records']),len(self.f.pointers.state['records']))
        commands=list(self.f.keys_model.commands);self.domain.sleep(2.1)
        for mode in ('missing','active','foreign-instance','foreign-ticket','stale'):
            self.mode=mode;self.phase.previous=None
            with self.subTest(mode=mode),self.assertRaises((NativeUIError,ValueError,TypeError)):
                self.local()
            self.assertEqual(before,(len(self.scope.frames),len(self.f.keys.state['records']),len(self.f.pointers.state['records'])))
            self.assertEqual(commands,self.f.keys_model.commands)

    def test_phase_after_cannot_rewrite_a_new_original_even_with_equal_bytes(self):
        paths=set(self.scope.root.iterdir())
        def rewrite(ordinal):
            if ordinal!=2:return
            fresh=[path for path in self.scope.root.iterdir() if path not in paths and path.name.startswith('emote-keys-') and path.is_file()]
            self.assertTrue(fresh);fresh[0].write_bytes(fresh[0].read_bytes())
        self.callback=rewrite;actions=list(self.domain.io.actions)
        with self.assertRaises(NativeUIError):self.local()
        self.assertEqual(actions,self.domain.io.actions)
        self.assertIsNone(self.scope.state['pending'])
        self.assertTrue(self.scope.held_originals())

    def test_lost_retired_phase_after_keeps_the_actual_extended_owners_without_input_replay(self):
        quiet=list(self.scope.state['quiet']);actions=list(self.domain.io.actions)
        def lost(ordinal):
            if ordinal==2:raise OSError('Controlled lost retired phase return')
        self.callback=lost
        with self.assertRaises(OSError):self.local()
        self.assertEqual(quiet,self.scope.state['quiet'][:-1]);self.assertEqual(actions,self.domain.io.actions)
        self.assertIsNotNone(self.f.keys.store.read());self.assertIsNotNone(self.f.pointers.store.read())

    def test_actual_quiet_storage_cannot_skip_frozen_paired_seal_and_archive_authority(self):
        before=len(self.scope.frames)
        with self.assertRaises(NativeUIError):
            acquire(None,None,None,self.scope,self.f.pointers,self.f.keys,self.phase)
        self.assertEqual(before,len(self.scope.frames));self.assertEqual(0,self.calls)


class RootedFenceSealTests(unittest.TestCase):
    def test_real_persisted_terminal_proof_rejects_missing_foreign_and_modified_seals(self):
        fixture=journal_fixture.TerminalJournalTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        owner=fixture.owner();fixture.inspect(owner);fixture.seal(owner)
        proof=owner.originals.read(owner.originals.expand(owner.state['record']));owner.proof(proof,owner.state)
        binding=fixture.roles['primary'].binding;run=fixture.description['runId'];seal=proof['seal']
        _seal(proof,seal,run=run,role='primary',binding=binding)
        for mode in ('missing','foreign-run','changed-original'):
            selected=deepcopy(seal)
            if mode=='missing':selected=None
            elif mode=='foreign-run':selected['description']['runId']='f'*32
            else:selected['liveOriginalSha256']='0'*64
            with self.subTest(mode=mode),self.assertRaises((NativeUIError,ValueError,TypeError)):
                _seal(proof,selected,run=run,role='primary',binding=binding)


class RootedFenceMetadataTests(unittest.TestCase):
    """Real private copies/WALs; incomplete role graphs never gain authority."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);root.chmod(0o700);actor=root/'actor';actor.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(root/'script-feature-sources.lock');actor_lock=ScriptSourceLock(actor/'script-feature-sources.lock')
        for lock in (actor_lock,self.lock):
            held=lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.marker=PrivateFeatureState(root/'ios-emote-primary-marker.json');self.marker.write(dict(marker='component-only'),None)
        self.foreign=PrivateFeatureState(actor/'ios-emote-actor-feature.json');self.foreign.write(dict(role='component-only'),None)
        self.absent=PrivateFeatureState(actor/'ios-emote-actor-source-recovery.json')
        terminal=PrivateFeatureState(root/('ios-emote-primary-'+RUN+'-terminal.json'));terminal.write({},None)
        pointers=PrivateFeatureState(root/'ios-emote-primary-pointers.json');keys=PrivateFeatureState(root/'ios-emote-primary-keys.json')
        paths=[self.marker,self.foreign,self.absent,terminal,pointers,keys]
        copies={str(store.path):store.read() for store in paths}
        status=phase_packet(3,95000);status.update(active=False,retiredEpochMs=94900)
        self.archive=IOSEmoteRootedFinalArchive(PrivateFeatureState(root/'ios-emote-rooted-final.json'),root,BINDING,RUN,'primary',
            self.lock,self.lock,paths,lambda:True,lambda actual:actual==copies)
        self.archive.begin(status);self.archive.freeze()
        # These object-only role/component boundaries intentionally lack a
        # complete graph. A negative metadata case must fail BEFORE asking
        # the real paired decoder or any local native acquisition to run.
        self.ownership=object.__new__(IOSEmoteRootedOwnership);self.ownership.path=terminal.path;self.ownership.terminal={}
        self.ownership.roles=SimpleNamespace(run=RUN,locks=dict(primary=self.lock,actor=actor_lock),
            copies={path:value for path,value in copies.items() if path!=str(terminal.path)})
        self.ownership.read_with_retirement_floor=lambda:(_ for _ in ()).throw(AssertionError('Incomplete pair must never be decoded'))
        self.scope=object.__new__(IOSEmoteRootedMarkerScope)
        self.scope.run,self.scope.role,self.scope.lock,self.scope.store=RUN,'primary',self.lock,self.marker
        self.pointers=object.__new__(IOSEmotePointers);self.pointers.store=pointers
        self.keys=object.__new__(IOSEmoteKeys);self.keys.store=keys

    def assert_metadata_denied(self):
        with (patch('ios.adapters.emote_rooted_fence._current_metadata',wraps=_current_metadata) as metadata,
                patch('ios.adapters.emote_rooted_fence._local') as native):
            with self.assertRaises(NativeUIError):
                acquire(self.ownership,self.archive,None,self.scope,self.pointers,self.keys,None)
            metadata.assert_called_once();native.assert_not_called()

    def test_changed_other_role_current_metadata_blocks_before_frozen_decoder_or_native_queries(self):
        self.foreign.write(dict(role='changed-current-other-role'),self.foreign.read())
        self.assert_metadata_denied()

    def test_formerly_absent_other_role_recovery_cannot_appear_after_freeze(self):
        self.absent.write(dict(pending='new-unresolved-owner'),None)
        self.assert_metadata_denied()


class RootedFenceRetirementFloorTests(unittest.TestCase):
    """Pure original host-clock projections; no native/paired qualification."""
    @staticmethod
    def clock(start,end):
        return dict(hostBeforeEpochMs=100000+start,hostAfterEpochMs=100000+end,
            hostBeforeMonotonic=start/1000,hostAfterMonotonic=end/1000)

    def test_retirement_after_public_start_but_before_role_or_receipt_end_is_refused(self):
        for role_end,receipt_end in ((900,800),(800,900)):
            with self.subTest(roleEnd=role_end,receiptEnd=receipt_end):
                rows=[dict(measurement=dict(acquisition=self.clock(700,role_end)))]
                publications=[dict(acquisition=self.clock(650,750))];receipts=[self.clock(760,receipt_end)]
                operands=deepcopy((rows,publications,receipts));floor=_retirement_floor(rows,publications,receipts)
                self.assertEqual(100900,floor)
                # Both the public/native acquisition start and the server's
                # acceptance can precede completion of the actual role/HTTP
                # read. Only the original host-after ends delimit retirement.
                status=phase_packet(3,101000);status.update(active=False,retiredEpochMs=100850)
                status['activations'][-1].update(ticket='a'*32,stimulus=dict(verb='cleanup',inputs={}))
                with self.assertRaises(NativeUIError):
                    inactive(status,run=RUN,instance=status['instance'],ticket='a'*32,after=floor)
                status['retiredEpochMs']=floor
                self.assertIs(status,inactive(status,run=RUN,instance=status['instance'],ticket='a'*32,after=floor))
                self.assertEqual(operands,(rows,publications,receipts))

    def test_later_unselected_publication_receipt_still_delimits_retirement(self):
        rows=[dict(measurement=dict(acquisition=self.clock(850,950)))]
        selected=[dict(acquisition=self.clock(600,750))]
        # The later actual journal receipt was already fully decoded even
        # though its sample is outside the requested three-pair window.
        receipts=[self.clock(760,800),self.clock(1000,1200)]
        floor=_retirement_floor(rows,selected,receipts);self.assertEqual(101200,floor)
        status=phase_packet(3,102000);status.update(active=False,retiredEpochMs=101100)
        status['activations'][-1].update(ticket='a'*32,stimulus=dict(verb='cleanup',inputs={}))
        with self.assertRaises(NativeUIError):
            inactive(status,run=RUN,instance=status['instance'],ticket='a'*32,after=floor)


if __name__=='__main__':unittest.main()
