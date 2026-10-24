"""Genuine original multi-cut/publication joins with declared native models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from feature_journeys.witness import Client
from ios.adapters.emote_rooted_archive import capture
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_rooted_publications import select
from ios.self_tests.emote_rooted_whole_fixture import paired


class RootedWindowTests(unittest.TestCase):
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
                        first[flow.role]=live.record(live.state['records'][-1])['measurement']
            if index<2:f.target.domain.sleep(1.6)
        descriptor=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='emotes',runId=primary.run,ticket=first['primary']['ticket'],
            roles={role:dict(binding=binding_from_context(flow.state['binding']),heldResources=[{k:r[k] for k in
                ('resource','kind','originalSha256')} for r in first[role]['held']],originalSha256=digest(first[role]))
                for role,flow in (('primary',primary),('actor',actor))})
        terminal.description(descriptor);terminal.window(samples,descriptor)
        print('Three genuine pairs satisfy the common terminal window codec',flush=True)
        for flow in (primary,actor):
            with flow.held(30):
                flow.load();parts=flow.components();owner=flow.retirement_owner(parts);live=IOSEmoteRootedLive(owner)
                values=[pair['primary'] for pair in samples] if flow.role=='primary' else []
                if values:self.assertEqual(3,len(live.selected_many(values)))
                else:
                    snapshot=capture(owner,flow.state['cleanup'][-1])
                    store=PrivateFeatureState(flow.store.path.with_name('phase-publication-emotes-'+flow.run+'-actor.json'))
                    value=store.read();entries=[pair['actor'] for pair in samples]
                    history=len(f.actor.target.domain.history)
                    selected=select(snapshot,value,store=store,entries=entries,lock=flow.lock,primary_lock=flow.primary_lock)
                    self.assertEqual(entries,[row['entry'] for row in selected]);self.assertEqual(history,len(f.actor.target.domain.history))
                    wrong=deepcopy(entries);wrong[0]['receivedEpochMs']+=1
                    with self.assertRaises(NativeUIError):select(snapshot,value,store=store,entries=wrong,lock=flow.lock,primary_lock=flow.primary_lock)


if __name__=='__main__':unittest.main()
