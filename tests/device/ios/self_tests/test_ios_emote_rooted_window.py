"""Genuine original multi-cut/publication joins with declared native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
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
        with primary.held(30):
            primary.load();primary.phase.read();primary.clean_local(primary.components())
        actor.cleanup(dict(contractVersion=16,runId=primary.run))
        print('Initial Actor scene3 publication committed',flush=True)
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
        with actor.held(30):
            lives={}
            for flow in (primary,actor):
                flow.load();parts=flow.components();owner=flow.retirement_owner(parts);live=IOSEmoteRootedLive(owner)
                lives[flow.role]=live
            store=PrivateFeatureState(actor.store.path.with_name('phase-publication-emotes-'+primary.run+'-actor.json'))
            history=len(f.actor.target.domain.history)
            self.assert_original_window(lives,first,samples,store)
            self.assertEqual(history,len(f.actor.target.domain.history))
        print('Three genuine pairs satisfy the original terminal live seal and counterexamples',flush=True)


if __name__=='__main__':unittest.main()
