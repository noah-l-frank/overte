"""Actual normal JS/input/private originals with explicit modeled UI/GPU sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_held_marker_scope import IOSEmoteHeldMarkerScope
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_observation import IOSEmoteRootedObserver
from ios.adapters.emote_held_observation import IOSEmoteHeldObservationDecoder
from ios.adapters.emote_marker_files import OwnedEmoteMarkerFiles
from ios.adapters.emote_originals import IOSEmoteOriginals
from ios.adapters.web_closures import drained_owned_resources
from ios.self_tests import test_ios_emote_marker_scope as old
from ios.self_tests.emote_rooted_marker_fixture import RootedMarkerDomain
from ios.self_tests.world_web_ui_roots_fixture import Root

legacy_owner=old.MarkerScopeTests.owner


def rooted(model,*args,**kwargs):
    owner=object.__new__(IOSEmoteRootedMarkerScope);owner.__dict__.update(legacy_owner(model,*args,**kwargs).__dict__)
    assert owner.previous is None,'Select the original version before its first write'
    owner.files=OwnedEmoteMarkerFiles(None,owner.files.store,owner.binding)
    owner.originals=IOSEmoteOriginals(owner.root,owner.binding,owner.run,owner.role,owner.guard,owner.storage_intent,kind='inputs')
    return owner


class EmoteRootedMarkerTests(unittest.TestCase):
    def setUp(self):
        self.f=old.MarkerScopeTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.scope=rooted(self.f);self.domain=RootedMarkerDomain(self.scope)

    def prepare(self):self.scope.prepare();self.domain.paint();self.scope.admit_rendered()

    def archive(self,value=None):
        s=self.scope
        return IOSEmoteRootedMarkerScope.archive(s.previous if value is None else value,
            root=s.root,binding=s.binding,run=s.run,role=s.role,lock=s.lock)

    def test_normal_cleanup_preserves_cached_allocations_and_detached_live_roots_then_reopens_without_transport(self):
        self.prepare();self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertEqual(3,self.scope.previous['iosEmoteMarkerScopeVersion'])
        rows=self.scope.held_originals();self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<={r['kind'] for r in rows})
        last=self.scope.frames[self.scope.state['quiet'][-1]-1]
        self.assertEqual([],last['widgets']['scriptInventory']['rootMembership']['managers'])
        self.assertTrue(any(r['original'].get('rootKind')=='manager' for r in rows))
        self.assertTrue(any('iosEmoteMarkerProcessHolderVersion' in r['original'] for r in rows))
        admitted=self.scope.frames[self.scope.state['webAdmission']-1]
        with self.assertRaises(NativeUIError):drained_owned_resources(last['web'],admitted['web'])
        files={p:(p.stat().st_ino,p.read_bytes()) for p in self.scope.root.rglob('*') if p.is_file()}
        actions=list(self.domain.io.actions);before=dict(self.domain.sequences)
        self.assertEqual(rows,self.archive().held_originals());self.assertEqual({'performed':True},self.scope.cleanup())
        self.assertEqual(actions,self.domain.io.actions);self.assertEqual(before,self.domain.sequences)
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in self.scope.root.rglob('*') if p.is_file()})
        for reader in (IOSEmoteMarkerScope,IOSEmoteHeldMarkerScope):
            with self.subTest(reader=reader.__name__),self.assertRaises(NativeUIError):
                reader.archive(self.scope.previous,root=self.scope.root,binding=self.scope.binding,
                    run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
        for version in (1,2,4):
            wrong=deepcopy(self.scope.previous);wrong['iosEmoteMarkerScopeVersion']=version
            with self.subTest(version=version),self.assertRaises(NativeUIError):self.archive(wrong)

    def test_new_actual_root_during_quiet_restarts_selected_window_without_erasing_the_holder(self):
        widgets=self.domain.widgets;events=[]
        def new_root():
            if self.scope.state['phase']=='quiet' and len(self.scope.state['quiet'])==1 and not events:
                root=Root('manager');self.domain.actual_roots['new-detached']=root
                self.domain.roots.observe(root);events.append(len(self.scope.frames)+1)
            return widgets()
        self.scope.live['native'].capture=new_root
        self.prepare();self.scope.cleanup();self.assertEqual(1,len(events))
        self.assertTrue(all(index>events[0] for index in self.scope.state['quiet']))
        row=next(r for r in self.scope.held_originals() if r['original'].get('rootKind')=='manager')
        self.assertEqual(2,len(row['original']['roots']));self.assertEqual(self.scope.held_originals(),self.archive().held_originals())

    def test_legacy_missing_unready_foreign_and_outside_acquisition_root_originals_are_refused(self):
        self.scope.capture('initial-original');frame=self.scope.frames[-1]
        for fault in ('legacy','unready','foreign','before-acquisition'):
            wrong=deepcopy(frame);inventory=wrong['widgets']['scriptInventory']
            if fault=='legacy':
                inventory.pop('rootOwnership');inventory.pop('rootMembership');inventory['inventoryVersion']=1
            elif fault=='unready':inventory['rootOwnership']['wholeTreeReady']=False
            elif fault=='foreign':inventory['rootOwnership']['processId']=52
            else:inventory['rootOwnership']['capturedEpochMs']=wrong['clockJoin']['nativeBefore']['capturedEpochMs']-1
            # A self-consistent adversarial bracket cannot supply missing roots.
            wrong['clockJoin']['originalsSha256']=digest({k:wrong[k] for k in ('world','terminal','dialogs','web','widgets','work')})
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.scope.validate_frame(wrong)


class EmoteRootedObservationTests(unittest.TestCase):
    def test_actual_playback_and_png_originals_select_scope_three_before_historical_decode(self):
        from ios.self_tests import emote_active_observer_fixture as active
        with (patch.object(old.MarkerScopeTests,'owner',rooted),
              patch.object(active.native_fixture,'RunningDomain',RootedMarkerDomain),
              patch.object(active,'IOSEmoteObserver',IOSEmoteRootedObserver)):
            f=active.ActiveObserverFixture(self,defer_setup=True)
        f.scope.prepare();f.domain.paint();f.scope.admit_rendered()
        first=f.observer.observe(0);self.assertEqual('idle',first['state']['animation'])
        self.assertEqual(3,f.scope.previous['iosEmoteMarkerScopeVersion'])
        f.actions.act(f.activate('open'));opened=f.observer.observe(first['sequence'])
        self.assertTrue(opened['state']['panel'])
        f.actions.act(f.activate('play',name='Waving'));before=f.actions.state['current']['before'];f.native.sleep(.25)
        played=f.observer.observe(opened['sequence'],input_barrier=dict(index=before['revision'],sha256=before['sha256']))
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(played['state']['override'])
        self.assertGreater(played['state']['poseProgress'],0.);self.assertEqual(1,len(played['artifacts']))
        original=f.observer.original(f.observer.state['records'][-1]);old_observer=f.observer
        files={p:(p.stat().st_ino,p.read_bytes()) for p in f.root.rglob('*') if p.is_file()}
        counts={k:len(v.commands) for k,v in f.f.gpus.items()}
        rebuilt=IOSEmoteRootedObserver(old_observer.store,old_observer.sources,old_observer.binding,old_observer.role,
            old_observer.root,old_observer.policy,old_observer.phase,old_observer.lock,old_observer.guard,
            samples=old_observer.samples,monotonic=old_observer.monotonic,epoch_ms=old_observer.epoch_ms)
        self.assertEqual(played,rebuilt.decoder.derive(original)['public'])
        legacy=IOSEmoteHeldObservationDecoder(old_observer.sources,old_observer.binding,old_observer.role,
            old_observer.root,old_observer.policy,old_observer.lock,phase_instance=old_observer.phase.previous['instance'])
        with self.assertRaises(NativeUIError):legacy.derive(original)
        self.assertEqual(counts,{k:len(v.commands) for k,v in f.f.gpus.items()})
        self.assertEqual(files,{p:(p.stat().st_ino,p.read_bytes()) for p in f.root.rglob('*') if p.is_file()})


if __name__=='__main__':unittest.main()
