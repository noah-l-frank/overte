"""Genuine original multi-cut/publication joins with declared native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from feature_journeys.witness import Client
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal
from ios.adapters.emote_terminal import IOSEmoteTerminal
from ios.adapters.emote_rooted_inventory import IOSEmoteRootedInventory
from ios.adapters.emote_rooted_state import metadata_paths
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_observer import EmoteObservationPending
from ios.self_tests.emote_rooted_whole_fixture import paired


class RootedWindowTests(unittest.TestCase):
    def assert_original_window(self,lives,references,samples,store):
        """Shared assertions also support file-only retained-original replay."""
        window=IOSEmoteTerminalWindow(lives['primary'],lives['actor'])
        description=window.describe(references)
        proof=window.qualify(description,samples,references,publisher_store=store)
        self.assertEqual(digest(proof['original']),proof['seal']['liveOriginalSha256'])
        self.assertEqual(3,len(proof['original']['primary']))
        self.assertEqual([pair['actor'] for pair in samples],[row['entry'] for row in proof['original']['actor']])
        for fault in ('descriptor-process','missing-primary-original','changed-HTTP-receipt'):
            with self.subTest(fault=fault):
                desc,changed=deepcopy(description),deepcopy(samples)
                if fault=='descriptor-process':desc['roles']['actor']['binding']['processIdentity']='99'
                elif fault=='missing-primary-original':changed[-1]['primary']['sequence']+=100
                else:changed[0]['actor']['receivedEpochMs']+=1
                with self.assertRaises((NativeUIError,ValueError)):
                    window.qualify(desc,changed,references,publisher_store=store)
        actor=lives['actor'];original_lock=actor.primary_lock
        try:
            actor.primary_lock=actor.lock
            with self.assertRaises(NativeUIError):window.guard()
        finally:actor.primary_lock=original_lock
        original_phase=actor.phase_instance
        try:
            actor.phase_instance='1'*32
            with self.assertRaises(NativeUIError):window.guard()
        finally:actor.phase_instance=original_phase
        window.guard()
        return proof

    def test_three_genuine_paired_cuts_reopen_earlier_graphs_and_exact_actor_http_originals(self):
        f=paired(self,retain_originals=True);primary,actor=f.flow,f.actor.flow
        witness=Client(f.target.client.url,'r'*64)
        call=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        primary.observe(call);actor.observe(call);primary.act(f.call('play',name='Waving'));f.target.native.sleep(.25)
        primary.observe(call);actor.observe(call);f.call('cleanup')
        cleanup=dict(contractVersion=16,runId=primary.run)
        def waiting(seconds):
            if primary.lock._owner is None and primary.primary_lock._owner is None:
                self.assertIsNone(actor.lock._owner);actor.cleanup(cleanup)
            f.target.domain.sleep(seconds)
        primary.sleep=waiting
        self.assertEqual(dict(performed=True),primary.cleanup(cleanup))
        self.assertEqual('primary-scene-ordered',primary.state['retirement']['kind'])
        print('Normal Primary cleanup joined the once-only Actor scene3 publication',flush=True)
        samples=[];first={}
        for index in range(3):
            print('Acquiring original window pair '+str(index+1)+'/3',flush=True)
            p=primary.observe(call);print('Primary original pair '+str(index+1)+'/3 returned',flush=True)
            a=actor.observe(call);print('Actor original pair '+str(index+1)+'/3 returned',flush=True)
            self.assertEqual([],f.target.client.request('/runs/'+primary.run)['entries'])
            journal=witness.request('/runs/'+primary.run)
            matches=[entry for entry in journal['entries'] if entry['actorSequence']==a['sequence']]
            self.assertEqual(1,len(matches));samples.append(dict(primary=p,actor=matches[0]))
            if index==0:
                for flow in (primary,actor):
                    with flow.held(30):
                        flow.load();parts=flow.components();owner=flow.retirement_owner(parts);live=IOSEmoteRootedLive(owner)
                        first[flow.role]=deepcopy(live.state['records'][-1])
            if index<2:f.target.domain.sleep(1.6)
        # Actor.held acquires its actual lock and then the shared Primary lock.
        # Keep both live owners inside that same real ownership interval.
        with actor.held(30),read_scope(fresh=True) as reads:
            lives={};current=object.__new__(IOSEmoteTerminal);current.responsibilities=[]
            for flow in (primary,actor):
                flow.load();lives[flow.role]=current.local_window(flow)
            store=PrivateFeatureState(actor.store.path.with_name('phase-publication-emotes-'+primary.run+'-actor.json'))
            history=len(f.actor.target.domain.history)
            proof=self.assert_original_window(lives,first,samples,store)
            self.assertEqual(history,len(f.actor.target.domain.history))
            window=IOSEmoteTerminalWindow(lives['primary'],lives['actor']);journal=IOSEmoteTerminalJournal(window)
            journal.inspect(first)
            self.assertEqual(proof['seal'],journal.seal(proof['original']['description'],samples,publisher_store=store)['seal'])
            saved=journal.originals.read(journal.originals.expand(journal.state['record']));journal.proof(saved,journal.state)
            self.assertEqual(proof,saved)
            IOSEmoteRootedInventory(journal,reads).guard()
            paths=metadata_paths(window,current.responsibilities)+[journal.store]
            copies={str(path.path):path.read() for path in paths}
            print('Normal cleanup, all three pairs, persisted live seal and current paired inventory joined',flush=True)

            # This is the actual local fixture's DELETE and independent phase
            # response. Shutdown/finally is never substituted for retirement.
            witness.request('/runs/'+primary.run,method='DELETE')
            phase=primary.phase.status();actor_phase=actor.phase.status()
            self.assertFalse(phase['active']);self.assertFalse(actor_phase['active'])
            self.assertEqual(phase['instance'],actor_phase['instance'])
            self.assertEqual(proof['original']['description']['ticket'],phase['activations'][-1]['ticket'])
            archive_store=PrivateFeatureState(primary.store.path.with_name('ios-emote-primary-'+primary.run+'-rooted-finalization.json'))
            archive=None;leases=[]
            def unchanged():
                primary.lock.assert_held();actor.lock.assert_held()
                for lease in leases:lease.guard()
                self.assertEqual(copies,{str(path.path):path.read() for path in paths});return True
            actual_read=PrivateFeatureState.read
            def original_only(path):
                if str(path.path) in copies:raise AssertionError('Current metadata read during frozen ownership replay')
                return actual_read(path)
            def validate(actual):
                self.assertEqual(copies,actual)
                with patch.object(PrivateFeatureState,'read',original_only):
                    measured=IOSEmoteRootedOwnership(actual,run=primary.run,lock=primary.lock,actor_lock=actor.lock).read()
                self.assertEqual(proof,measured)
            archive=IOSEmoteRootedFinalArchive(archive_store,primary.root,primary.state['binding'],primary.run,'primary',
                primary.lock,primary.lock,paths,unchanged,validate)
            self.assertIsNone(archive.state)
            mutable=[archive_store.path]+[archive.record_store(index).path for index in range(1,len(paths)+1)]
            leases=[EmoteOriginalLease(root,mutable) for root in {primary.root,actor.root,primary.store.path.parent,actor.store.path.parent}]
            archive.begin(phase);archive.freeze();self.assertEqual('validated',archive.state['phase'])
            with self.assertRaises(EmoteObservationPending):archive.retire()
            self.assertTrue(all(path.read() is not None or copies[str(path.path)] is None for path in paths))
            self.retained_ownership_checkpoint=dict(archive=str(archive_store.path),metadataPaths=len(paths),
                seal=deepcopy(proof['seal']),phaseOriginal=deepcopy(phase),actorPhaseOriginal=deepcopy(actor_phase))
        print('Three genuine pairs satisfy the original terminal live seal and counterexamples',flush=True)
        print('Actual retired phase and frozen whole-role/seal checkpoint retained; process/SDK end remains separate',flush=True)


if __name__=='__main__':unittest.main()
