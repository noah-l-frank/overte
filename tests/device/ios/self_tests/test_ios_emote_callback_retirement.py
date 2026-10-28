"""Real JS/W3C/PNG callback source models through retired Observer4 originals.

Selected before first capture: one actual host Frame/Trace/Window context.
Native Qt/SDK/GPU/process-end execution and whole Emote remain unqualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from pathlib import Path
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import unpack
from ios.adapters.emote_callback_observation import IOSEmoteCallbackRootedObserver,RESOURCE
from ios.adapters.emote_callback_samples import EmoteCallbacksPending
from ios.adapters.emote_callback_retirement import IOSEmoteCallbackRetirementObserver,IOSEmoteCallbackNativeRetirement
from ios.adapters.emote_retirement import IOSEmoteRetirement
from ios.adapters.emote_rooted_retirement import IOSEmoteRootedNativeRetirement
from ios.adapters import emote_callback_drain_originals as drains
from ios.self_tests import emote_callback_observer_fixture as fixture


def normal_retirement_observer(test):
    # Exact same declared producer selection as the qualified Consumer8, with
    # only the explicit new observer profile selected BEFORE owner birth.
    frames=fixture.bundled_frames()
    with (patch.object(fixture.vm_fixture,'ActualEmoteVM',partial(fixture.vm_fixture.ActualEmoteVM,frame_counts=frames)),
          patch.object(fixture.active_fixture,'ActualVMRig',partial(fixture.active_fixture.ActualVMRig,pose_profile='requested-clip')),
          patch.object(fixture.marker_fixture.MarkerScopeTests,'owner',fixture.rooted),
          patch.object(fixture.active_fixture.native_fixture,'RunningDomain',fixture.RootedMarkerDomain),
          patch.object(fixture.active_fixture,'IOSEmoteSamples',fixture.IOSEmoteCallbackSamples),
          patch.object(fixture.active_fixture,'IOSEmoteObserver',IOSEmoteCallbackRetirementObserver)):
        target=fixture.CallbackActiveFixture(test)
    target.w3c,target.normal=fixture.normal_tablet(target);return target


class CallbackRetirementTests(unittest.TestCase):
    def commands(self,target):return [deepcopy(q) for slot in target.callback_context.worlds.values() for q in slot.commands]
    def observe(self,target,after=0,barrier=None,retired=False):return target.observer.observe(after,input_barrier=barrier,retired=retired)
    def action(self,target,verb,**values):
        target.actions.act(target.activate(verb,**values));ref=target.actions.state['current']['before']
        if verb in ('play','sit','override'):target.native.sleep(.25)
        return dict(index=ref['revision'],sha256=ref['sha256'])
    def clean(self,target):
        self.action(target,'close');target.activate('cleanup')
        target.samples.drain();target.scope.cleanup()
        self.assertTrue(target.callback_context.all_drained());self.assertEqual('released',target.scope.state['phase'])
    def idle_retired(self):
        target=normal_retirement_observer(self);first=self.observe(target);self.clean(target)
        final=self.observe(target,first['sequence'],retired=True)
        original=target.observer.original(target.observer.state['records'][-1]);return target,first,final,original
    def native_reader(self,target):
        s=target.samples
        return IOSEmoteCallbackNativeRetirement(PrivateFeatureState(target.root/'callback-native4-reader.json'),
            target.root,s.binding,s.binding,s.run,s.role,target.phase.fixture_url,target.phase.previous['instance'],target.lock,target.lock,target.policy,
            dict(sources=target.sources.store.path,peers=None,files=target.root/'native-files.json',entities=target.root/'entities.json',pointers=target.root/'pointers.json'),lambda:True)
    def cold(self,target):
        o=target.observer
        return IOSEmoteCallbackRetirementObserver(o.store,o.sources,o.binding,o.role,o.root,o.policy,o.phase,o.lock,lambda:True,
            samples=target.samples,epoch_ms=target.scope.epoch_ms,monotonic=target.scope.monotonic)

    def test_normal_play_cancel_real_drain_persists_retired4_and_native4_sample_owner_boundary(self):
        target=normal_retirement_observer(self)
        with target.trace_consumer.held():first=self.observe(target)
        first_original=target.observer.original(target.observer.state['records'][-1]);self.assertIn(RESOURCE,first['resources'])
        barrier=self.action(target,'play',name='Crying');playing=self.observe(target,first['sequence'],barrier)
        self.assertTrue(playing['state']['override'])
        barrier=self.action(target,'cancel');restored=self.observe(target,playing['sequence'],barrier)
        self.assertFalse(restored['state']['override']);self.clean(target)
        final=self.observe(target,restored['sequence'],retired=True);o=target.observer
        original=o.original(o.state['records'][-1]);self.assertEqual(4,original['iosEmoteObservationOriginalVersion'])
        self.assertEqual([],final['resources']);self.assertEqual([],final['artifacts']);self.assertTrue(target.callback_context.all_drained())
        self.assertIsNone(original['image']);projection=original['sampleOwners'];self.assertEqual(4,projection['iosEmoteCallbackSampleOwnersVersion'])
        self.assertEqual(3,projection['samples']['iosEmoteSamplesVersion']);self.assertTrue(projection['current'])
        before=self.commands(target);reader=self.native_reader(target);reader.samples(projection,target.scope)
        self.assertEqual(4,reader.FORMAT_VERSION);self.assertEqual(before,self.commands(target))
        # Native4 sampleOwners validation is tested, not full native/rendered/
        # keyed/scene/process end retain; those independent gates stay closed.
        self.assertIn(RESOURCE,o.decoder.derive(first_original)['public']['resources'])
        old=unpack(first_original['image']['payload'])[0];self.assertEqual(1,old['retirement']['source']['callbacks'])

    def test_real_held_callback_refuses_retired_observation_before_any_drain_carrier_or_empty_fact(self):
        target=normal_retirement_observer(self)
        with target.trace_consumer.held():
            first=self.observe(target);target.activate('cleanup');before=len(target.observer.state['records'])
            with self.assertRaises(EmoteCallbacksPending):self.observe(target,first['sequence'],retired=True)
            self.assertEqual(before,len(target.observer.state['records']));self.assertIsNone(target.observer.state['pending'])
            self.assertFalse(any(target.root.glob(drains.NAMESPACE+'-*')));self.assertFalse(target.callback_context.all_drained())
        self.assertTrue(target.callback_context.all_drained());self.assertIn(RESOURCE,first['resources'])

    def test_cold_owner4_and_repeated_retired_cut_keep_older_immutable_drains_after_owner_wal_advances(self):
        target,first,final,original=self.idle_retired();o=target.observer;before=self.commands(target)
        cold=self.cold(target);self.assertEqual(final,cold.decoder.derive(original)['public']);self.assertEqual(before,self.commands(target))
        old=[deepcopy(ref) for ref in original['sampleOwners']['current']]
        target.native.sleep(.05)  # A distinct later real modeled cut, no original retiming.
        later=self.observe(target,final['sequence'],retired=True);new=o.original(o.state['records'][-1])
        self.assertEqual([],later['resources']);self.assertNotEqual(old,new['sampleOwners']['current'])
        before=self.commands(target);self.assertEqual(final,o.decoder.derive(original)['public']);self.assertEqual(before,self.commands(target))
        self.assertGreater(len(new['sampleOwners']['drains']),len(original['sampleOwners']['drains']))
        moved=deepcopy(original);moved['sampleOwners']=deepcopy(new['sampleOwners'])
        with self.assertRaises(NativeUIError):o.decoder.derive(moved)

    def test_missing_current_owner_foreign_binding_and_wrong_scope_cannot_clear_resources(self):
        target,first,final,original=self.idle_retired();before=self.commands(target)
        for fault in ('missing-current','foreign-binding','owner-as-scope'):
            value=deepcopy(original);projection=value['sampleOwners']
            if fault=='missing-current':projection['current']=[]
            elif fault=='foreign-binding':
                binding=projection['samples']['binding'];original_pid=binding['processIdentity']
                binding['processIdentity']='999' if original_pid!='999' else '998'
                self.assertNotEqual(original_pid,binding['processIdentity'])
            else:projection['scope']=deepcopy(projection['current'][0])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):target.observer.decoder.derive(value)
        self.assertEqual(before,self.commands(target))

    def test_changed_real_carrier_bytes_refuse_historical_absence_without_live_query(self):
        target,first,final,original=self.idle_retired();projection=original['sampleOwners']
        source=drains.store(target.root,target.samples.binding,target.samples.run,target.samples.role,target.lock)
        path=source.path(source.expand(projection['current'][0]));identity=path.stat();raw=path.read_bytes();path.write_bytes(raw+b' ')
        self.assertEqual((identity.st_dev,identity.st_ino),(path.stat().st_dev,path.stat().st_ino));before=self.commands(target)
        with self.assertRaises(NativeUIError):target.observer.decoder.derive(original)
        self.assertEqual(before,self.commands(target))

    def test_actual_opened_carrier_failure_stays_in_existing_pending_without_adoption_or_input_replay(self):
        target=normal_retirement_observer(self);first=self.observe(target);self.clean(target);o=target.observer
        save=o.save;failures=[]
        def saved_then_lost():
            value=save();pending=o.state['pending'];extra=None if pending is None else pending['callbackDrains']
            if extra is not None and extra['original'] is not None and extra['original']['phase']=='opened' and not failures:
                failures.append(deepcopy(extra['original']));raise OSError('Declared lost callback carrier write before bytes')
            return value
        with patch.object(o,'save',saved_then_lost),self.assertRaises(OSError):self.observe(target,first['sequence'],retired=True)
        self.assertEqual(1,len(failures));saved=PrivateFeatureState(o.store.path).read();state=unpack(saved['payload'])[0]
        self.assertIsNotNone(state['pending']['callbackDrains']['original']);self.assertEqual('opened',state['pending']['callbackDrains']['original']['phase'])
        source=drains.store(target.root,target.samples.binding,target.samples.run,target.samples.role,target.lock)
        path=source.path(failures[0]);self.assertEqual(0,path.stat().st_size);before=self.commands(target)
        with self.assertRaises(NativeUIError):o.abandon_read()
        self.assertEqual(before,self.commands(target));self.assertEqual(1,len(o.state['records']))
        self.assertEqual(saved,PrivateFeatureState(o.store.path).read())
        with self.assertRaises(NativeUIError):self.cold(target)
        self.assertEqual(before,self.commands(target));self.assertEqual(saved,PrivateFeatureState(o.store.path).read())

    def test_owner_wal_same_body_mutation_during_real_carrier_write_refuses_current_fact(self):
        target=normal_retirement_observer(self);first=self.observe(target);self.clean(target)
        actual=OriginalFrameStore.write;changed=[]
        def written_then_changed(source,index,frame):
            ref=actual(source,index,frame)
            if source.namespace==drains.NAMESPACE and frame.get('kind')=='owner' and not changed:
                row=frame['row'];owner=target.samples.owner(row);path=owner.store.path;before=path.stat()
                path.write_bytes(path.read_bytes()+b' ');self.assertEqual((before.st_dev,before.st_ino),(path.stat().st_dev,path.stat().st_ino));changed.append(path)
            return ref
        with patch.object(OriginalFrameStore,'write',written_then_changed),self.assertRaises(NativeUIError):self.observe(target,first['sequence'],retired=True)
        self.assertEqual(1,len(changed));self.assertEqual(1,len(target.observer.state['records']))
        self.assertIsNotNone(target.observer.state['pending']);self.assertIsNone(target.observer.state['pending']['original'])

    def test_unknown_original_carrier_refuses_retired_admission_before_native_query(self):
        target=normal_retirement_observer(self);first=self.observe(target)
        path=target.root/(drains.NAMESPACE+'-foreign.json');path.write_bytes(b'{}');path.chmod(0o600)
        target.activate('cleanup');before=self.commands(target)
        with self.assertRaises(NativeUIError):self.observe(target,first['sequence'],retired=True)
        self.assertEqual(before,self.commands(target));self.assertEqual(1,len(target.observer.state['records']))
        self.assertIsNone(target.observer.state['pending']);self.assertEqual(b'{}',path.read_bytes())

    def test_literal_observer3_and_retirement1_2_refuse_new_projection_without_queries(self):
        target,first,final,original=self.idle_retired();o=target.observer;before=self.commands(target)
        with self.assertRaises(NativeUIError):IOSEmoteCallbackRootedObserver(o.store,o.sources,o.binding,o.role,o.root,o.policy,o.phase,o.lock,
            lambda:True,samples=target.samples,epoch_ms=target.scope.epoch_ms,monotonic=target.scope.monotonic)
        reader=self.native_reader(target)
        for kind in (IOSEmoteRetirement,IOSEmoteRootedNativeRetirement):
            old=object.__new__(kind)
            for key in ('root','binding','run','role','lock','policy'):setattr(old,key,getattr(reader,key))
            with self.subTest(kind=kind.__name__),self.assertRaises(NativeUIError):old.samples(original['sampleOwners'],target.scope)
        self.assertEqual(before,self.commands(target))


if __name__=='__main__':unittest.main()
