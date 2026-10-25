"""Real normal Node marker recipe and weak objects; native/GPU are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_held_marker_scope import IOSAvatarHeldMarkerScope
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_marker_files import OwnedAvatarMarkerFiles
from ios.adapters.avatar_originals import IOSAvatarOriginals
from ios.adapters.web_closures import drained_owned_resources
from ios.self_tests import test_ios_avatar_marker_scope as old
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus


class HeldDomain(old.AvatarDomain):
    def __init__(self,scope):
        super().__init__(scope);outer=self
        class ActualEpochCensus(RootCensus):
            def tick(_self):_self.elapsed+=1;return outer.epoch()
        self.roots=ActualEpochCensus();self.actual_roots={};self.root_ids={}
    def widgets(self):
        value=super().widgets();inventory=value['scriptInventory'];members=dict(managers=[],pickers=[])
        self.roots.elapsed=round(self.time*1000)
        for group,kind in (('managers','manager'),('pickers','picker')):
            for row in inventory[group]:
                if kind not in self.actual_roots:
                    self.actual_roots[kind]=Root(kind);self.root_ids[kind]=self.roots.observe(self.actual_roots[kind])
                members[group].append(self.root_ids[kind])
        # This is the modeled producer's v2 constructor, before raw capture.
        return value|{'scriptInventory':dict(inventoryVersion=2,complete=True,managers=inventory['managers'],pickers=inventory['pickers'],
            tabletPresent=inventory['tabletPresent'],tabletShown=inventory['tabletShown'],rootOwnership=self.roots.source(),rootMembership=members)}
    def web(self,run,url):
        value=super().web(run,url)
        if self.context is not None:
            value['contexts'][0]['updatedEpochMs']=self.context['updatedEpochMs']
            if not self.running:
                for name,counter in value['contexts'][0]['resources'].items():
                    if name!='policy-grant':counter.update(retired=0,pending=counter['created'])
        return value


class AvatarHeldMarkerScopeTests(unittest.TestCase):
    def setUp(self):
        self.f=old.AvatarMarkerScopeTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.skeleton=self.f.scope.__dict__.copy();self.scope=self.owner();self.domain=HeldDomain(self.scope)
    def owner(self):
        owner=object.__new__(IOSAvatarHeldMarkerScope);owner.__dict__.update(self.skeleton)
        owner.state=deepcopy(self.skeleton['state']);owner.frames=[];owner.previous=owner.store.read()
        owner.files=OwnedAvatarMarkerFiles(None,PrivateFeatureState(owner.root/'ios-avatar-primary-marker-files.json'),owner.binding)
        owner.originals=IOSAvatarOriginals(owner.root,owner.binding,owner.run,owner.role,owner.guard,owner.storage_intent,kind='inputs')
        if owner.previous is not None:owner.state=owner.decode(owner.previous)
        return owner
    def archive(self):
        return IOSAvatarHeldMarkerScope.archive(self.scope.previous,root=self.scope.root,binding=self.scope.binding,
            run=self.scope.run,role=self.scope.role,lock=self.scope.lock)

    def test_literal_two_preserves_once_delivery_and_refuses_legacy_reinterpretation(self):
        calls=[];self.scope.once('open-marker-manager',lambda:calls.append('input'))
        before=self.scope.store.path.read_bytes();self.assertEqual(2,self.scope.previous['iosAvatarMarkerScopeVersion'])
        self.owner().once('open-marker-manager',lambda:calls.append('replayed'));self.assertEqual(['input'],calls)
        self.assertEqual(before,self.scope.store.path.read_bytes());self.assertEqual(self.scope.state,self.archive().state)
        with self.assertRaises(NativeUIError):IOSAvatarMarkerScope.archive(self.scope.previous,root=self.scope.root,
            binding=self.scope.binding,run=self.scope.run,role=self.scope.role,lock=self.scope.lock)
    def test_real_marker_cleanup_keeps_cached_resources_and_detached_root_originals_until_process_end(self):
        owned=self.scope.prepare();self.domain.paint();self.scope.admit_rendered();self.assertEqual('local',self.domain.vm['added'][0]['host'])
        self.assertEqual(owned['marker']['id'],self.domain.vm['added'][0]['id'])
        self.assertEqual({'performed':True},self.scope.cleanup());self.assertEqual('released',self.scope.state['phase'])
        last=self.scope.frames[self.scope.state['quiet'][-1]-1];admitted=self.scope.frames[self.scope.state['webAdmission']-1]
        with self.assertRaises(NativeUIError):drained_owned_resources(last['web'],admitted['web'])
        actual=self.scope.held_originals();kinds={row['kind'] for row in actual}
        self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<=kinds)
        self.assertFalse(last['widgets']['scriptInventory']['rootMembership']['managers'])
        self.assertTrue(any(row['original'].get('rootKind')=='manager' for row in actual))
        self.assertEqual(actual,self.archive().held_originals());before=list(self.domain.io.actions)
        self.scope.cleanup();self.assertEqual(before,self.domain.io.actions)
    def test_unknown_input_keeps_issued_responsibility_and_never_resends(self):
        calls=[]
        def lost():calls.append('input');raise OSError('Actual normal return unavailable')
        with self.assertRaises(OSError):self.scope.once('load-marker-script',lost)
        with self.assertRaises(NativeUIError):self.owner().once('load-marker-script',lambda:calls.append('replay'))
        self.assertEqual(['input'],calls);self.assertEqual('issued',self.owner().state['operations'][0]['phase'])
    def test_legacy_inventory_missing_actual_roots_and_short_host_epoch_cannot_qualify_two(self):
        self.scope.capture('actual-baseline');frame=deepcopy(self.scope.frames[-1]);inventory=frame['widgets']['scriptInventory']
        for fault in ('legacy','missing','host'):
            wrong=deepcopy(frame)
            if fault=='legacy':
                wrong['widgets']['scriptInventory']={k:v for k,v in inventory.items() if k not in ('rootOwnership','rootMembership')}
                wrong['widgets']['scriptInventory']['inventoryVersion']=1
                # Recompute the bracket only as an adversarial original carrier.
                from adapters.native_clock_join import digest
                wrong['clockJoin']['originalsSha256']=digest({k:wrong[k] for k in ('world','terminal','dialogs','web','widgets','work')})
                with self.assertRaises(NativeUIError):self.scope.validate_frame(wrong)
            elif fault=='missing':
                wrong['widgets']['scriptInventory']['rootOwnership']['wholeTreeReady']=False
                with self.assertRaises(NativeUIError):self.scope.ui_absent(wrong)
            else:
                first=deepcopy(frame);last=deepcopy(frame)
                for row in (first,last):
                    row['clockJoin']['hostBeforeMonotonic']=0;row['clockJoin']['hostAfterMonotonic']=.1
                last['clockJoin'].update(hostBeforeMonotonic=3.1,hostAfterMonotonic=3.2)
                last['world']['clockBefore']['monotonicMs']+=3100;last['world']['clockAfter']['monotonicMs']+=3100
                last['world']['clockBefore']['epochMs']+=3100;last['world']['clockAfter']['epochMs']+=3100
                self.assertFalse(IOSAvatarHeldMarkerScope.quiet_interval(first,last))


if __name__=='__main__':unittest.main()
