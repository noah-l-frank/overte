"""Normal JS/W3C/rooted observer with real host callbacks and fresh PNGs.

Native/SDK/GPU producers are models, never device/native/whole qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from inspect import unwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from feature_journeys.contract import result
from ios.adapters.emote_callback_observation import IOSEmoteCallbackRootedObserver,RESOURCE
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_sample_recovery import IOSEmoteSampleRecovery,validate_abandonment
from ios.self_tests.emote_callback_observer_fixture import normal_observer
from ios.adapters.emote_callback_feature import IOSEmoteCallbackFeature
from ios.adapters.emote_callback_samples import IOSEmoteCallbackSamples,EmoteCallbacksPending
from ios.adapters.emote_observation_operation import ObservationPending
from ios.self_tests.emote_completed_frame_context_fixture import FrameCallbackWorld


class CallbackObserverTests(unittest.TestCase):
    def prepared(self):return SimpleNamespace(target=normal_observer(self))
    def observe(self,f,after=0,barrier=None):return f.target.observer.observe(after,input_barrier=barrier)
    def action(self,f,verb,**inputs):
        target=f.target;target.actions.act(target.activate(verb,**inputs));ref=target.actions.state['current']['before']
        if verb in ('play','sit','override'):target.native.sleep(.25)
        return dict(index=ref['revision'],sha256=ref['sha256'])
    def commands(self,target):
        return [deepcopy(query) for slot in target.callback_context.worlds.values() for query in slot.commands]
    def cold(self,target):
        owner=target.observer
        return IOSEmoteCallbackRootedObserver(owner.store,owner.sources,owner.binding,owner.role,owner.root,owner.policy,owner.phase,owner.lock,
            lambda:True,samples=target.samples,epoch_ms=target.scope.epoch_ms,monotonic=target.scope.monotonic)

    def test_actual_pending_token_is_public_until_fresh_inspect_and_new_png_then_history_stays_pending(self):
        f=self.prepared();target=f.target
        with target.trace_consumer.held():
            public=self.observe(f);self.assertIn(RESOURCE,public['resources'])
            self.assertEqual(public,result('feature.emotes.observe',public));self.assertTrue(public['artifacts'])
            owner=target.observer;reference=deepcopy(owner.state['records'][-1]);original=owner.original(reference)
            first=original['image'];self.assertEqual(3,first['iosEmoteSampleVersion'])
            self.assertFalse(target.callback_context.all_drained())
        self.assertTrue(target.callback_context.all_drained())
        before=self.commands(target)
        self.assertIn(RESOURCE,owner.validate_original(dict(iosEmoteObservationReferenceVersion=1,**reference))['public']['resources'])
        self.assertEqual(before,self.commands(target))
        current=self.observe(f,public['sequence']);self.assertNotIn(RESOURCE,current['resources'])
        last=owner.original(owner.state['records'][-1])['image']
        self.assertNotEqual(first['requestId'],last['requestId'])
        self.assertNotEqual(unpack(first['payload'])[0]['capture']['source']['renderTrace']['frameId'],
            unpack(last['payload'])[0]['capture']['source']['renderTrace']['frameId'])
        self.assertTrue(target.callback_context.all_drained())
        prior_slot=target.callback_context.world(first['requestId']);self.assertEqual('inspect',prior_slot.commands[-1]['operation'])
        self.assertEqual(1,sum(q['operation']=='release' for q in prior_slot.commands))
        self.assertEqual(3,owner.previous['iosEmoteObserverVersion'])

    def test_normal_play_cancel_uses_new_image3_pixels_and_original_restore_with_actual_drain(self):
        f=self.prepared();target=f.target
        with target.trace_consumer.held():first=self.observe(f)
        self.assertIn(RESOURCE,first['resources'])
        barrier=self.action(f,'play',name='Crying')
        playing=self.observe(f,first['sequence'],barrier);self.assertTrue(playing['state']['override'])
        active=target.observer.original(target.observer.state['records'][-1]);self.assertEqual('playback',active['proof']['kind'])
        barrier=self.action(f,'cancel');quiet=self.observe(f,playing['sequence'],barrier)
        restored=target.observer.original(target.observer.state['records'][-1])
        self.assertFalse(quiet['state']['override']);self.assertNotIn(RESOURCE,quiet['resources'])
        self.assertEqual('restoration',restored['proof']['kind']);self.assertTrue(quiet['artifacts'])
        self.assertNotEqual(active['image']['requestId'],restored['image']['requestId'])
        self.assertTrue(target.callback_context.all_drained())
        proofs=target.samples.drain();self.assertTrue(all(p['source']['callbacks']==0 and not p['source']['gpuPending'] for p in proofs))
        self.assertEqual(quiet,target.observer.decoder.derive(restored)['public'])

    def test_actual_lost_read_recovers_outer_sample3_abandonment_without_capture_replay_or_legacy_adoption(self):
        f=self.prepared();target=f.target;real=FrameCallbackWorld.original;dropped=[]
        def lost_read(slot):
            if slot.commands and slot.commands[-1]['operation']=='read':
                dropped.append(slot.request_id);raise OSError('Declared lost native frame carrier')
            return real(slot)
        with patch.object(FrameCallbackWorld,'original',lost_read),self.assertRaises(NativeUIError):target.samples.capture(target.ticket)
        row=deepcopy(target.samples.state['rows'][-1]);slot=target.callback_context.world(row['requestId'])
        self.assertEqual([row['requestId']],dropped);self.assertEqual(1,sum(q['operation']=='read' for q in slot.commands))
        recovery=target.observer.sample_recovery;self.assertTrue(recovery.recover())
        self.assertEqual(2,recovery.previous['iosEmoteSampleRecoveryVersion'])
        record=target.samples.record(target.samples.state['rows'][-1]);self.assertEqual(3,record['iosEmoteSampleVersion'])
        self.assertEqual('abandoned',record['phase']);self.assertTrue(target.callback_context.all_drained())
        with self.assertRaises(NativeUIError):validate_abandonment(record,root=target.root,binding=target.samples.binding,
            run=target.samples.run,role=target.samples.role,lock=target.lock)
        with self.assertRaises(NativeUIError):IOSEmoteSampleRecovery(target.samples)
        self.assertEqual(1,sum(q['operation']=='read' for q in slot.commands))
        public=self.observe(f);self.assertTrue(public['artifacts']);self.assertNotIn(RESOURCE,public['resources'])
        self.assertEqual(1,sum(q['operation']=='read' for q in slot.commands))

    def test_rewriting_callback_receipt_cannot_create_empty_resources_from_a_pending_original(self):
        f=self.prepared();target=f.target
        with target.trace_consumer.held():public=self.observe(f)
        owner=target.observer;original=owner.original(owner.state['records'][-1]);before=self.commands(target)
        self.assertIn(RESOURCE,public['resources'])
        for fault in ('callbacks','metadata','gpu','frame-id'):
            changed=deepcopy(original);sample=changed['image'];frame=unpack(sample['payload'])[0]
            if fault=='callbacks':frame['retirement']['source']['callbacks']=0
            elif fault=='metadata':frame['retirement']['source']['metadataBytes']=1
            elif fault=='gpu':frame['retirement']['source']['gpuPending']=True
            else:frame['capture']['source']['renderTrace']['frameId']='f'*32
            sample['payload']=pack([frame])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.decoder.derive(changed)
        self.assertEqual(before,self.commands(target))

    def test_cold_owner3_replays_callback_resource_without_live_query_and_default_owner_refuses_it(self):
        f=self.prepared();target=f.target
        with target.trace_consumer.held():public=self.observe(f)
        before=self.commands(target);fresh=self.cold(target)
        self.assertEqual(3,fresh.previous['iosEmoteObserverVersion']);self.assertEqual(2,fresh.sample_recovery.FormatVersion)
        value=fresh.validate_original(dict(iosEmoteObservationReferenceVersion=1,**fresh.state['records'][-1]))['public']
        self.assertEqual(public,value);self.assertIn(RESOURCE,value['resources'])
        with self.assertRaises(NativeUIError):IOSEmoteRootedObserver(fresh.store,fresh.sources,fresh.binding,fresh.role,fresh.root,fresh.policy,
            fresh.phase,fresh.lock,lambda:True,samples=target.samples,epoch_ms=target.scope.epoch_ms,monotonic=target.scope.monotonic)
        self.assertEqual(before,self.commands(target))

    def test_no_image_original_has_no_callback_absence_authority_in_this_profile(self):
        f=self.prepared();target=f.target;public=self.observe(f);owner=target.observer
        original=owner.original(owner.state['records'][-1]);changed=deepcopy(original);changed['image']=None
        # Directly exercise this exact closed boundary; no unrelated earlier
        # source/pose/phase exception can mask missing absence authority.
        with self.assertRaises(NativeUIError):owner.decoder.image_resources(changed)
        self.assertNotIn(RESOURCE,public['resources']);self.assertTrue(target.callback_context.all_drained())


    def feature_pending_boundary(self,stage):
        # Negative dispatch boundary only: no model product outcome is ever
        # returned. Genuine observer/sample/phase owners supply the endpoints;
        # the lease model proves the private retry signal crosses its finally.
        f=self.prepared();target=f.target;events=[];held=[False]
        class Flow:
            run=target.samples.run;role='primary';phase=target.phase
            Samples=IOSEmoteCallbackSamples;Observer=IOSEmoteCallbackRootedObserver
            state=dict(phase='ready',inputBarrier=None,lastCall=None)
            @contextmanager
            def held(self,seconds):
                events.append('enter');held[0]=True
                try:yield
                finally:held[0]=False;events.append('exit')
            def prepare(self):
                if stage=='prepare':raise EmoteCallbacksPending('Actual typed readiness at construction boundary')
                return dict(observer=target.observer,samples=target.samples)
        body=unwrap(IOSEmoteCallbackFeature.observe);flow=Flow()
        def pending_abandon():raise EmoteCallbacksPending('Actual typed readiness at abandonment boundary')
        with patch.object(target.observer,'abandon_read',pending_abandon),self.assertRaises(ObservationPending) as raised:
            body(flow,dict(contractVersion=16,runId=flow.run,afterSequence=0))
        self.assertEqual(target.ticket,raised.exception.ticket);self.assertEqual(['enter','exit'],events);self.assertFalse(held[0])

    def test_prepare_pending_is_translated_before_owner_fact_or_success_can_escape(self):self.feature_pending_boundary('prepare')

    def test_abandon_pending_is_translated_before_owner_fact_or_success_can_escape(self):self.feature_pending_boundary('abandon')


if __name__=='__main__':unittest.main()
