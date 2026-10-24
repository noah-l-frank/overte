"""Normal launcher pagination/restore with actual typed source originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_page_owner import IOSSnapshotPageOwner
from ios.adapters import normal_input,tablet_launcher_controls
from ios.self_tests.snapshot_page_domain import SnapshotPageDomain,RUN


class SnapshotPageOwnerTests(unittest.TestCase):
    def pins(self,domain):
        result={}
        for path in domain.ctx.root.iterdir():
            if path.name.startswith('ios-snapshot-page-frame-'):
                stat=path.stat();result[path.name]=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result

    def test_real_W3C_pagination_opens_snapshot_and_restores_actual_original_index_and_closed_visibility(self):
        d=SnapshotPageDomain(self)
        with d.owner() as owner:
            result=owner.open('f'*32);self.assertTrue(result['snapshotPageOpen']);self.assertEqual(2,result['originalPage']['selection']['launcherCurrentIndex'])
            original_root=result['originalPage']['selection']['launcherRootId']
            restored=owner.restore();self.assertTrue(restored['tabletClosed']);self.assertTrue(restored['launcherSelectionRestored']);self.assertTrue(restored['wholeFeatureRequired'])
            close=next(action for action in owner.state['actions'] if action['label']=='restore-close')
            restored_root=owner.route(owner.record(close['before']))['selection']['launcherRootId'];self.assertNotEqual(original_root,restored_root)
            store,lock,binding,url=owner.store,owner.lock,owner.binding,owner.fixture_url
        self.assertFalse(d.shown);self.assertEqual(2,d.index);self.assertEqual(['hud.tablet','tablet.page.1','tablet.page.2','snapshot.entry','tablet.home','tablet.page.3','tablet.close'],d.clicks)
        before=self.pins(d);commands=deepcopy(d.capture.commands);inputs=deepcopy(d.requests)
        with lock.held():
            archive=IOSSnapshotPageOwner.archive(store,lock,binding,RUN,url);self.assertEqual(restored,archive.restoration())
        self.assertEqual(before,self.pins(d));self.assertEqual(commands,d.capture.commands);self.assertEqual(inputs,d.requests)

    def test_connected_normal_open_capture_actual_png_child_file_cleanup_and_original_launcher_restore(self):
        d=SnapshotPageDomain(self)
        with d.owner() as owner:
            result=owner.capture('f'*32);self.assertEqual('png',result['capture']['image']['format'])
            child=owner.runtime.capture_child(owner);artifact=child.history('artifact',child.state['artifact'])
            self.assertEqual(d.f.bytes,artifact.read());host_original=artifact.path();self.assertTrue(d.f.f.h.path.exists())
            cleanup=child.cleanup();self.assertTrue(cleanup['hostOriginalRetained']);self.assertTrue(cleanup['pairedCleanupRequired'])
            self.assertFalse(d.f.f.h.path.exists());self.assertEqual(d.f.bytes,host_original.read_bytes())
            restored=owner.restore();self.assertTrue(restored['launcherSelectionRestored']);self.assertFalse(d.shown);self.assertEqual(2,d.index)
            self.assertTrue(host_original.exists());self.assertEqual(1,d.capture.capture_count)
        self.assertEqual(1,d.clicks.count('snapshot.entry'));self.assertEqual(1,d.clicks.count('tablet.close'))
        self.assertEqual(1,sum(query['action']=='feature-ios-snapshot-file-remove' for query in d.capture.commands))

    def test_lost_normal_entry_return_reconstructs_from_independent_original_route_without_second_click(self):
        d=SnapshotPageDomain(self,count=1,index=0,snapshot_page=0);d.lose.add('snapshot.entry')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        d.lose.clear();before=self.pins(d)
        with d.owner() as owner:
            result=owner.open('f'*32);self.assertTrue(result['unknownInputReturns']);owner.restore()
        self.assertEqual(1,d.clicks.count('snapshot.entry'));self.assertEqual(before,{name:self.pins(d)[name] for name in before})

    def test_ignored_page_input_never_infers_selected_page_or_resends_on_reconstruction(self):
        d=SnapshotPageDomain(self);d.ignore.add('tablet.page.1')
        for _ in range(2):
            with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        self.assertEqual(['hud.tablet','tablet.page.1'],d.clicks);self.assertEqual(2,d.index);self.assertEqual('launcher',d.route)

    def test_lost_normal_close_return_reconstructs_without_reopening_or_second_close(self):
        d=SnapshotPageDomain(self,count=1,index=0,snapshot_page=0)
        with d.owner() as owner:owner.open('f'*32)
        d.lose.add('tablet.close')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        self.assertFalse(d.shown);d.lose.clear()
        with d.owner() as owner:self.assertTrue(owner.restore()['tabletClosed'])
        self.assertEqual(1,d.clicks.count('tablet.close'));self.assertEqual(1,d.clicks.count('hud.tablet'))

    def test_stale_actual_proxy_source_token_prevents_any_entry_click(self):
        d=SnapshotPageDomain(self,count=1,index=0,snapshot_page=0);d.swap_token='snapshot.entry'
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        self.assertEqual(['hud.tablet'],d.clicks);self.assertEqual('launcher',d.route)

    def test_replaced_actual_launcher_root_between_WDA_resolution_and_delivery_blocks_old_entry(self):
        d=SnapshotPageDomain(self,count=1,index=0,snapshot_page=0);initial=d.root;d.swap_root='snapshot.entry'
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        self.assertNotEqual(initial,d.root);self.assertEqual(['hud.tablet'],d.clicks);self.assertEqual('launcher',d.route)

    def test_lost_home_and_restore_page_returns_resolve_each_actual_recreated_root_without_resend(self):
        d=SnapshotPageDomain(self)
        with d.owner() as owner:owner.open('f'*32)
        original=d.root;d.lose.add('tablet.home')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        self.assertNotEqual(original,d.root);self.assertEqual('launcher',d.route);d.lose.clear();d.lose.add('tablet.page.3')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        self.assertEqual(2,d.index);d.lose.clear()
        with d.owner() as owner:self.assertTrue(owner.restore()['tabletClosed'])
        self.assertEqual(1,d.clicks.count('tablet.home'));self.assertEqual(1,d.clicks.count('tablet.page.3'));self.assertEqual(1,d.clicks.count('tablet.close'))

    def test_hidden_foreign_editor_is_never_replaced_by_home_and_can_only_restore_visibility(self):
        d=SnapshotPageDomain(self,route='foreign')
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.open('f'*32)
        with d.owner() as owner:self.assertTrue(owner.restore()['tabletClosed'])
        self.assertEqual(['hud.tablet','tablet.close'],d.clicks);self.assertEqual('foreign',d.route)

    def test_unchanged_actual_snapshot_route_preserves_it_when_closing_original_visibility(self):
        d=SnapshotPageDomain(self,route='snapshot')
        with d.owner() as owner:
            self.assertTrue(owner.open('f'*32)['snapshotPageOpen']);self.assertFalse(owner.restore()['launcherSelectionRestored'])
        self.assertEqual(['hud.tablet','tablet.close'],d.clicks);self.assertEqual('snapshot',d.route)

    def test_changed_actual_page_count_blocks_restoration_before_selecting_an_old_index_or_close(self):
        d=SnapshotPageDomain(self)
        with d.owner() as owner:owner.open('f'*32)
        d.count=2
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        self.assertTrue(d.shown);self.assertNotIn('tablet.close',d.clicks)

    def test_actual_retained_native_timer_dispatch_blocks_navigation_and_close_despite_idle_Script_state(self):
        d=SnapshotPageDomain(self,count=1,index=0,snapshot_page=0)
        with d.owner() as owner:owner.open('f'*32)
        d.held_work=True;inputs=deepcopy(d.clicks)
        with d.owner() as owner,self.assertRaises(NativeUIError):owner.restore()
        self.assertEqual(inputs,d.clicks);self.assertTrue(d.shown)

    def test_saved_observation_before_parent_CAS_recovers_original_inode_bytes_without_source_query(self):
        d=SnapshotPageDomain(self,count=1,index=0,snapshot_page=0)
        with d.owner() as owner:
            save=owner.save
            def lost():
                if owner.state['records']:raise OSError('Explicit observation saved before coordinator CAS')
                return save()
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.open('f'*32)
        pins=self.pins(d);self.assertTrue(pins);commands=deepcopy(d.capture.commands);native=d.ctx.native.sequence
        with d.owner() as owner:owner.recover_observation()
        self.assertEqual(pins,self.pins(d));self.assertEqual(commands,d.capture.commands);self.assertEqual(native,d.ctx.native.sequence);self.assertFalse(d.clicks)


class TabletLauncherControlTests(unittest.TestCase):
    def test_native_extension_requires_actual_complete_coherent_selection_and_exact_version(self):
        d=SnapshotPageDomain(self);d.shown=True;value=d.f.input_native.observed()
        self.assertEqual(2,tablet_launcher_controls.selection(value)['launcherCurrentIndex'])
        for fault in ('missing','root','selected','version','source','control'):
            bad=deepcopy(value);row=next(row for row in bad['controls'] if row['id'].startswith('tablet.page.'))
            if fault=='missing':bad['controls'].remove(row)
            elif fault=='root':row['launcherRootId']='11111111-2222-4333-8444-777777777777'
            elif fault=='selected':row['launcherCurrentIndex']=0
            elif fault=='version':row['tabletLauncherControlVersion']=True
            elif fault=='source':row['launcherQmlSource']='qrc:/foreign/TabletHome.qml'
            else:row['launcherControlIndex']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):tablet_launcher_controls.selection(bad)
        normal_input.observation(value,42,value['sampleEpochMs'])
        del value['tabletLauncherControlsVersion']
        with self.assertRaises(NativeUIError):normal_input.observation(value,42,value['sampleEpochMs'])

if __name__=='__main__':unittest.main()
