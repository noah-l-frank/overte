"""Fresh genuine normal input and paired originals through actual end owners.

Native/WDA/OS producers and candidate preflight are declared host seams. The
normal JS/W3C input, UDP, HTTP, PNGs, typed role/fence/end constructors, canonical
Stop, SDK DELETE/GET404 and metadata CAS retirement are actual. Producer clocks
are synthetic; real fence-to-dispatch elapsed time is reported separately and
does not become native/device or real CPU-deadline acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from feature_journeys.witness import Client
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters import emote_rooted_fence
from ios.self_tests.emote_rooted_whole_end_fixture import WholeRootedEndFixture


class RootedWholeEndJourneyTests(unittest.TestCase):
    def timed(self,label,function):
        started=time.monotonic()
        try:return function()
        finally:print(json.dumps(dict(emoteWholeStage=label,seconds=round(time.monotonic()-started,6))),flush=True)
    def test_fresh_normal_play_paired_cleanup_seal_inactive_and_actual_end_without_authorization_models(self):
        f=WholeRootedEndFixture(self,retain_originals=True);normal=f.normal;primary,actor=normal.flow,normal.actor.flow
        observe=dict(contractVersion=16,runId=primary.run,afterSequence=0)
        self.timed('primary-baseline',lambda:primary.observe(observe))
        self.timed('actor-baseline',lambda:actor.observe(observe))
        self.timed('normal-play',lambda:primary.act(normal.call('play',name='Waving')))
        normal.target.native.sleep(.25)
        played=self.timed('primary-playing',lambda:primary.observe(observe))
        peer=self.timed('actor-playing',lambda:actor.observe(observe))
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(peer['state']['override'])
        normal.call('cleanup');cleanup=dict(contractVersion=16,runId=primary.run)
        def waiting(seconds):
            if primary.lock._owner is None and primary.primary_lock._owner is None:
                self.assertIsNone(actor.lock._owner);actor.cleanup(cleanup)
            normal.target.domain.sleep(seconds)
        primary.sleep=waiting
        self.assertEqual(dict(performed=True),self.timed('normal-paired-cleanup',lambda:primary.cleanup(cleanup)))
        self.assertEqual('primary-scene-ordered',primary.state['retirement']['kind'])
        self.assertEqual('actor-published',actor.state['retirement']['kind'])
        witness=Client(normal.target.client.url,'r'*64);samples=[]
        for index in range(3):
            p=self.timed('primary-pair-'+str(index+1),lambda:primary.observe(observe))
            a=self.timed('actor-pair-'+str(index+1),lambda:actor.observe(observe))
            entries=witness.request('/runs/'+primary.run)['entries']
            matches=[row for row in entries if row['actorSequence']==a['sequence']]
            self.assertEqual(1,len(matches));samples.append(dict(primary=p,actor=matches[0]))
            if index<2:normal.target.domain.sleep(1.6)
        self.assertTrue(normal.actor.target.packet_bytes)
        def call(stage,**values):return dict(contractVersion=1,runId=primary.run,stage=stage,**values)
        inspected=self.timed('controller-inspect',lambda:f.terminal.invoke(call('inspect')))
        sealed=self.timed('controller-seal',lambda:f.terminal.invoke(call('seal',description=inspected['description'],samples=samples)))
        seal=deepcopy(sealed['seal']);ui_inputs=deepcopy(normal.target.vm.state['events'])
        # This actual controller DELETE retires the loopback input journal.
        # Only finish may acquire its inactive original; none is synthesized or
        # supplied from a retained corpus or an expected descriptor.
        witness.request('/runs/'+primary.run,method='DELETE')
        local=emote_rooted_fence._local
        def measured_local(scope,*args,**kwargs):
            f.fresh_roles.add(scope.role)
            try:return local(scope,*args,**kwargs)
            finally:f.fresh_roles.remove(scope.role)
        result=None
        with patch.object(emote_rooted_fence,'_local',side_effect=measured_local):
            for attempt in range(25):
                try:
                    result=self.timed('controller-finish-'+str(attempt+1),lambda:f.terminal.invoke(call('finish',seal=seal)));break
                except EmoteObservationPending:
                    self.assertIsNone(primary.lock._owner);self.assertIsNone(actor.lock._owner)
                    normal.target.domain.sleep(1.6)
        self.assertIsNotNone(result,'Bounded real end owners did not complete')
        self.assertEqual('finish',result['stage']);self.assertEqual(seal,result['end']['seal'])
        self.assertEqual(['actor','primary'],f.stops);self.assertEqual({'actor','primary'},f.deleted)
        for role in ('actor','primary'):
            deletes=[row for row in f.calls if row[0]==role and row[1]=='DELETE']
            self.assertEqual(1,len(deletes));self.assertIsNone(f.base.read_session(role));self.assertIsNone(f.base._binding_store(role).read())
        self.assertEqual(ui_inputs,normal.target.vm.state['events'])
        archive=PrivateFeatureState(primary.store.path.with_name('ios-emote-primary-'+primary.run+'-rooted-final.json')).read()
        phase=unpack(archive['payload'])[0]['phaseOriginal'];self.assertFalse(phase['active'])
        self.assertEqual(seal['description']['ticket'],phase['activations'][-1]['ticket'])
        self.assertTrue(all(PrivateFeatureState(path).read() is None for path in archive['paths']))
        calls,reads,factories=deepcopy(f.calls),deepcopy(f.native_reads),deepcopy(f.source_factories)
        # Reopen the actual terminal factory after feature metadata retirement.
        # No facade/process/fence/SDK/archive constructor or reader is mocked.
        historical=f.runtime._emote_rooted_terminal(f.facades['primary'])
        self.assertEqual(result,self.timed('pure-historical-finish',lambda:historical.invoke(call('finish',seal=seal))))
        self.assertEqual(calls,f.calls);self.assertEqual(reads,f.native_reads);self.assertEqual(factories,f.source_factories)
        print(json.dumps(dict(genuineWholeEmoteHostEnd=True,realFenceToStopSeconds=f.real_fence_to_stop,
            realCPULeaseQualified=all(value<1.5 for value in f.real_fence_to_stop.values()) and len(f.real_fence_to_stop)==2,
            declaredModels=['candidate-preflight','native','WDA','OS-producer-clocks'],deviceAcceptance=False)),flush=True)


if __name__=='__main__':unittest.main()
