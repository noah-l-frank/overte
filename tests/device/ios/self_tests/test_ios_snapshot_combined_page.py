"""Explicit normal Combined Page/Capture/cleanup/launcher component."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters.snapshot_page_return_owner import _ReturnPage
from ios.adapters.snapshot_page_return_owner import SnapshotPageReturnOwner
from ios.adapters.snapshot_journey_files import IOSSnapshotJourneyFilesOwner
from ios.adapters.snapshot_share_archive_end_owner import SnapshotShareArchiveEndOwner
from ios.adapters import snapshot_combined_work,snapshot_work
from ios.self_tests.snapshot_combined_page_domain import CombinedPageDomain,RUN


class SnapshotCombinedPageTests(unittest.TestCase):
    def pins(self,d):
        return {path.name:(path.stat().st_ino,path.read_bytes()) for path in d.ctx.root.iterdir()
            if path.name.startswith('ios-snapshot-combined-page-frame-')}

    def test_normal_open_capture_file_cleanup_launcher_restore_and_read_only_archive(self):
        d=CombinedPageDomain(self)
        with d.owner() as owner:
            result=owner.capture('f'*32);self.assertEqual(2,result['capture']['iosSnapshotDecodedCaptureVersion'])
            self.assertEqual(2,owner.previous['iosSnapshotPageOwnerVersion'])
            first=owner.record(1);self.assertEqual(2,first['iosSnapshotPageObservationVersion'])
            self.assertEqual('qrc:/scripts/defaultScripts.js',first['originals']['work']['source']['workers'][0]['manager']['url'])
            child=owner.runtime.capture_child(owner);self.assertTrue(child.combined)
            host=child.history('artifact',child.state['artifact']).path();self.assertEqual(d.f.bytes,host.read_bytes())
            self.assertTrue(child.cleanup()['hostOriginalRetained']);self.assertFalse(d.f.f.h.path.exists())
            restored=owner.restore();self.assertTrue(restored['launcherSelectionRestored']);self.assertTrue(restored['wholeFeatureRequired'])
            self.assertFalse(d.shown);self.assertEqual(2,d.index);self.assertEqual(d.f.bytes,host.read_bytes())
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        self.assertEqual(1,d.capture.capture_count);self.assertEqual(1,d.clicks.count('snapshot.entry'));self.assertEqual(1,d.clicks.count('tablet.close'))
        self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.capture.commands))
        pins=self.pins(d);commands=deepcopy(d.capture.commands);requests=deepcopy(d.requests);native=d.ctx.native.sequence
        self.assertTrue(pins)
        with lock.held(),patch.object(type(store),'write',side_effect=AssertionError('Historical write')):
            archive=IOSSnapshotPageOwner.archive(store,lock,binding,RUN,url,combined=True);self.assertEqual(restored,archive.restoration())
            with self.assertRaises(NativeUIError):IOSSnapshotPageOwner.archive(store,lock,binding,RUN,url)
        self.assertEqual(pins,self.pins(d));self.assertEqual(commands,d.capture.commands);self.assertEqual(requests,d.requests);self.assertEqual(native,d.ctx.native.sequence)

    def test_lost_entry_and_close_returns_reconstruct_original_route_without_resend(self):
        d=CombinedPageDomain(self,count=1,index=0,snapshot_page=0);d.lose.add('snapshot.entry')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        d.lose.clear();pins=self.pins(d)
        with d.owner() as owner:self.assertTrue(owner.open('f'*32)['unknownInputReturns'])
        d.lose.add('tablet.close')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        d.lose.clear()
        with d.owner() as owner:self.assertTrue(owner.restore()['inputDeliveryUnknown'])
        self.assertEqual(1,d.clicks.count('snapshot.entry'));self.assertEqual(1,d.clicks.count('tablet.close'))
        self.assertEqual(pins,{name:self.pins(d)[name] for name in pins})

    def test_explicit_profile_refuses_saved_other_owner_before_query_or_input(self):
        d=CombinedPageDomain(self,count=1,index=0,snapshot_page=0)
        with d.owner() as owner:owner.open('f'*32)
        commands=deepcopy(d.capture.commands);requests=deepcopy(d.requests)
        with self.assertRaises(NativeUIError),d.owner(combined=False):pass
        self.assertEqual(commands,d.capture.commands);self.assertEqual(requests,d.requests)

    def test_ignored_page_input_stays_owned_without_second_delivery(self):
        d=CombinedPageDomain(self);d.ignore.add('tablet.page.1')
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        self.assertEqual(['hud.tablet','tablet.page.1'],d.clicks);self.assertEqual(2,d.index)

    def test_orphan_combined_original_blocks_both_explicit_profiles_without_adoption(self):
        d=CombinedPageDomain(self,count=1,index=0,snapshot_page=0)
        path=d.ctx.root/'ios-snapshot-combined-page-frame-unowned.json';path.write_bytes(b'unchanged orphan bytes');path.chmod(0o600)
        original=(path.stat().st_ino,path.read_bytes());commands=deepcopy(d.capture.commands)
        for combined in (False,True):
            with self.subTest(combined=combined),self.assertRaises(NativeUIError),d.owner(combined=combined):pass
        self.assertEqual(original,(path.stat().st_ino,path.read_bytes()));self.assertEqual(commands,d.capture.commands);self.assertFalse(d.clicks)

    def test_lost_home_and_selected_page_returns_restore_actual_original_index_once(self):
        d=CombinedPageDomain(self)
        with d.owner() as owner:owner.open('f'*32)
        for control in ('tablet.home','tablet.page.3'):
            d.lose.add(control)
            with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
            d.lose.remove(control)
        with d.owner() as owner:self.assertTrue(owner.restore()['launcherSelectionRestored'])
        self.assertEqual(2,d.index);self.assertFalse(d.shown)
        for control in ('tablet.home','tablet.page.3','tablet.close'):self.assertEqual(1,d.clicks.count(control))

    def test_combined_query_is_fixed_while_legacy_static_and_return_defaults_stay_literal(self):
        command=dict(schemaVersion=1,commandId='ios-'+'b'*32,action=snapshot_work.ACTION,runId=RUN)
        IOSSnapshotPageOwner.query(command);_ReturnPage.query(command)
        with self.assertRaises(NativeUIError):IOSSnapshotPageOwner.query(command,combined=True)
        command['action']=snapshot_combined_work.ACTION;IOSSnapshotPageOwner.query(command,combined=True)
        with self.assertRaises(NativeUIError):IOSSnapshotPageOwner.query(command)
        legacy=object.__new__(_ReturnPage);self.assertFalse(legacy.combined_profile())
        self.assertEqual('ios-snapshot-return-page',legacy.frame_namespace())

    def test_literal_return1_rejects_combined_page_before_binding_any_child(self):
        # The first typed/profile guard must fail before reading any main,
        # child or SDK field; Page2 is not a claimed Share-return2 archive.
        page=object.__new__(IOSSnapshotPageOwner);page.historical=True;page.combined=True
        files=object.__new__(IOSSnapshotJourneyFilesOwner);files.historical=True
        end=object.__new__(SnapshotShareArchiveEndOwner);end.historical=True
        owner=object.__new__(SnapshotPageReturnOwner)
        with self.assertRaises(NativeUIError):owner.initialize(page,files,end,historical=True)

    def test_retained_actual_timer_dispatch_blocks_restore_despite_idle_script(self):
        d=CombinedPageDomain(self,count=1,index=0,snapshot_page=0)
        with d.owner() as owner:owner.open('f'*32)
        d.held_work=True;clicks=deepcopy(d.clicks)
        value=d.work_packet(dict(commandId='ios-'+'7'*32))
        snapshot_combined_work.admit(value,'qrc:/scripts/')
        with self.assertRaises(NativeUIError):snapshot_combined_work.admit(value,'qrc:/scripts/',quiet=True)
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        self.assertEqual(clicks,d.clicks);self.assertTrue(d.shown)

    def test_foreign_actual_compiled_module_blocks_before_first_navigation(self):
        d=CombinedPageDomain(self,count=1,index=0,snapshot_page=0)
        def foreign(value):value['source']['workers'][0]['codeSources']['evaluations'][0]['sha256']='0'*64
        d.fault=foreign
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        self.assertFalse(d.clicks)

    def test_saved_original_before_parent_CAS_recovers_unchanged_inode_without_query(self):
        d=CombinedPageDomain(self,count=1,index=0,snapshot_page=0)
        with d.owner() as owner:
            save=owner.save
            def lost():
                if owner.state['records']:raise OSError('Declared original saved before parent CAS')
                return save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.open('f'*32)
        pins=self.pins(d);commands=deepcopy(d.capture.commands);native=d.ctx.native.sequence;self.assertTrue(pins)
        with d.owner() as owner:owner.recover_observation()
        self.assertEqual(pins,self.pins(d));self.assertEqual(commands,d.capture.commands);self.assertEqual(native,d.ctx.native.sequence);self.assertFalse(d.clicks)


if __name__=='__main__':unittest.main()
