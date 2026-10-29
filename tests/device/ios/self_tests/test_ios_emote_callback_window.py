"""Three genuine paired Callback cuts and exact Actor HTTP-original joins.

Models declare native/SDK/Qt/GPU before birth. JS/W3C/UDP/HTTP/PNG, ordinary
cleanup and typed saved originals are actual. No OS/SDK/whole end is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.emote_callback_live import IOSEmoteCallbackLive
from ios.adapters.emote_callback_window import IOSEmoteCallbackWindow
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters import emote_callback_archive as archive
from ios.adapters import emote_rooted_publications as legacy_publications
from ios.self_tests.emote_callback_paired_fixture import paired


class CallbackWindowTests(unittest.TestCase):
    def queries(self,f):
        return dict(primary=len(f.target.domain.history),actor=len(f.actor.target.domain.history),
            primaryInputs=deepcopy(f.target.domain.io.actions),actorInputs=deepcopy(f.actor.target.domain.io.actions),
            gpu={role:[deepcopy(q) for slot in target.callback_context.worlds.values() for q in slot.commands]
                for role,target in (('primary',f.target),('actor',f.actor.target))})

    def test_actual_three_cuts_original_actor_receipts_and_held_pair_keep_legacy_window_closed(self):
        f=paired(self);primary,actor=f.flow,f.actor.flow;witness=Client(f.target.client.url,'r'*64)
        call=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        primary.observe(call);actor.observe(call)
        primary.act(f.call('play',name='Crying'));f.target.native.sleep(.25)
        playing=actor.observe(call);self.assertTrue(playing['state']['override'])
        primary.act(f.call('cancel'));restored=actor.observe(call);self.assertFalse(restored['state']['override'])
        f.call('cleanup');cleanup=dict(contractVersion=16,runId=primary.run)
        def waiting(seconds):
            if primary.lock._owner is None and primary.primary_lock._owner is None:
                self.assertIsNone(actor.lock._owner);actor.cleanup(cleanup)
            f.target.domain.sleep(seconds)
        primary.sleep=waiting
        self.assertEqual(dict(performed=True),primary.cleanup(cleanup))
        self.assertEqual('primary-scene-ordered',primary.state['retirement']['kind'])
        pairs=[];first={}
        for index in range(3):
            p=primary.observe(call);a=actor.observe(call);journal=witness.request('/runs/'+primary.run)
            matches=[entry for entry in journal['entries'] if entry['actorSequence']==a['sequence']]
            self.assertEqual(1,len(matches));pairs.append(dict(primary=p,actor=matches[0]))
            if index==0:
                for flow in (primary,actor):
                    with flow.held(30):
                        flow.load();owner=flow.retirement_owner(flow.components());live=IOSEmoteCallbackLive(owner)
                        first[flow.role]=deepcopy(live.state['records'][-1])
            if index<2:f.target.domain.sleep(1.6)
        with actor.held(30):
            lives={}
            for flow in (primary,actor):
                flow.load();owner=flow.retirement_owner(flow.components());lives[flow.role]=IOSEmoteCallbackLive(owner)
            window=IOSEmoteCallbackWindow(lives['primary'],lives['actor']);description=window.describe(first)
            store=PrivateFeatureState(actor.store.path.with_name('phase-publication-emotes-'+primary.run+'-actor.json'))
            before=self.queries(f);proof=window.qualify(description,pairs,first,publisher_store=store)
            self.assertEqual(2,proof['original']['iosEmoteTerminalWindowVersion'])
            self.assertEqual(digest(proof['original']),proof['seal']['liveOriginalSha256'])
            self.assertEqual([row['actor'] for row in pairs],[row['entry'] for row in proof['original']['actor']])
            self.assertEqual(3,len(proof['original']['primary']));self.assertEqual(before,self.queries(f))
            self.assertNotIn('end',proof)
            for fault in ('process','missing-cut','changed-receipt','borrowed-last-entry'):
                chosen,samples=deepcopy(description),deepcopy(pairs)
                if fault=='process':
                    old=chosen['roles']['actor']['binding']['processIdentity'];chosen['roles']['actor']['binding']['processIdentity']='999' if old!='999' else '998'
                    self.assertNotEqual(old,chosen['roles']['actor']['binding']['processIdentity'])
                elif fault=='missing-cut':samples[-1]['primary']['sequence']+=100
                elif fault=='changed-receipt':samples[0]['actor']['receivedEpochMs']+=1
                else:samples[0]['actor']=deepcopy(samples[-1]['actor'])
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                    window.qualify(chosen,samples,first,publisher_store=store)
            with self.assertRaises(NativeUIError):IOSEmoteTerminalWindow(lives['primary'],lives['actor'])
            snapshot=archive.capture(lives['actor'].owner,lives['actor'].owner.state['records'][-1])
            with self.assertRaises(NativeUIError):legacy_publications.select(snapshot,store.read(),store=store,
                entries=[row['actor'] for row in pairs],lock=actor.lock,primary_lock=primary.lock)
            # Changing an actually bound role/phase cannot reuse a valid proof.
            phase=lives['actor'].phase_instance
            try:
                lives['actor'].phase_instance='f'*32 if phase!='f'*32 else 'e'*32
                with self.assertRaises(NativeUIError):window.guard()
            finally:lives['actor'].phase_instance=phase
            self.assertEqual(before,self.queries(f));window.guard()


if __name__=='__main__':unittest.main()
