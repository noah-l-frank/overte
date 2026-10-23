"""World-script VM/code/QObject originals, with explicit V8/SDK producer seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.pico4.browser_vm import PicoBrowserVm,reviewed
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_pico_browser_vm as original


class WorldBrowserVmTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        # Change only the independent test producer's literal script/HTTP bytes.
        # Production validation still resolves its actual fixed resource pins.
        with patch.object(original,'reviewed',side_effect=lambda:reviewed('world')):
            self.b=original.Boundary(self.root)
    def owner(self,*,surface='world',role='primary'):
        b=self.b;scripts=b.script.reader();scripts.clock_ms=lambda:b.objects.epoch;scripts.monotonic=lambda:b.objects.host
        path=b.store if role=='primary' else PrivateFeatureState(self.root/'actor-vm.json')
        with b.lock.held():return PicoBrowserVm(original.RUN,original.URL,original.SCRIPT,role,original.BINDING,
            scripts,b.objects.reader(),path,b.lock,lambda:deepcopy(b.http),surface=surface)
    def capture(self,owner):
        with self.b.lock.held():return owner.capture()
    def test_actual_world_resource_pin_is_distinct_and_old_tablet_default_stays_frozen(self):
        tablet,tablet_bytes=reviewed();world,world_bytes=reviewed('world')
        self.assertNotEqual(tablet['sha256'],world['sha256']);self.assertNotEqual(tablet_bytes,world_bytes)
        vm=self.owner();self.assertEqual({'retired':False,'running':True},self.capture(vm))
        self.assertEqual(world['sha256'],vm.origin['code']['sha256'])
        self.assertEqual('world',vm.surface());self.assertNotIn('picoBrowserVmVersion',vm.scope)
        self.assertEqual(1,vm.scope['picoWorldBrowserVmVersion'])
    def test_tablet_compiler_body_or_http_receipt_cannot_qualify_the_world_script(self):
        for fault in ('code','http'):
            self.setUp();vm=self.owner()
            if fault=='code':
                wrong=reviewed()[0]
                self.b.edit=lambda value:value['source']['engines'][0]['compiled']['compilations'][0].update(wrong)
            else:self.b.http['responses'][0]['sha256']=reviewed()[0]['sha256']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.capture(vm)
            self.assertEqual('reading',vm.store.read()['phase'])
            count=self.b.count()
            with self.assertRaises(NativeUIError):self.owner()
            self.assertEqual(count,self.b.count())
    def test_original_world_and_tablet_scope_cannot_be_cold_adopted_as_each_other(self):
        vm=self.owner();self.capture(vm);count=self.b.count()
        with self.assertRaises(NativeUIError):self.owner(surface='tablet')
        self.assertEqual(count,self.b.count());self.assertEqual(1,len(self.owner().frames))
        # A distinct actor may acquire its own originals, never the primary's.
        actor=self.owner(role='actor');self.capture(actor)
        self.assertNotEqual(actor.store.path,vm.store.path)
        self.assertNotEqual(actor.frame(0)['scripts']['requestId'],vm.frame(0)['scripts']['requestId'])
    def test_service_absence_does_not_retire_actual_qobjects_and_full_quiet_keeps_all_three_clocks(self):
        vm=self.owner();self.capture(vm);self.b.stopped=True
        self.assertFalse(self.capture(vm)['retired'])
        for kind in ('manager','engine','worker'):
            self.b.objects.row[kind+'Alive']=False;self.b.objects.row[kind+'DestroyedEpochMs']=19999
        with self.b.lock.held():
            for index in range(1,33):
                self.b.objects.host=index*.1;self.b.objects.epoch=20000+100*index
                vm.capture()
                if vm.quiet(20001):break
            self.assertEqual(1,len(vm.windows));window=deepcopy(vm.windows[0]);count=self.b.count()
        cold=self.owner();self.assertEqual(count,self.b.count())
        with self.b.lock.held():self.assertTrue(cold.quiet(20001))
        self.assertEqual([window],cold.windows)
    def test_scope_alias_or_replaced_literal_chunk_cannot_become_new_world_ownership(self):
        vm=self.owner();self.capture(vm);count=self.b.count()
        vm.scope['picoWorldBrowserVmVersion']=True
        with self.assertRaises(NativeUIError):self.capture(vm)
        self.assertEqual(count,self.b.count())
        self.setUp();vm=self.owner();self.capture(vm);child=vm.chunks.store(0);raw=child.path.read_bytes()
        replacement=self.root/'replacement';replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(child.path)
        count=self.b.count()
        with self.assertRaises(NativeUIError):self.capture(vm)
        self.assertEqual(count,self.b.count())


    def test_native_jump_during_final_memo_cannot_return_a_fresh_world_vm_sample(self):
        vm=self.owner();append=vm._append_cache
        def late(raw,sha):
            append(raw,sha);self.b.objects.epoch+=1501
        with patch.object(vm,'_append_cache',side_effect=late),self.assertRaises(NativeUIError):self.capture(vm)
        self.assertTrue(vm.failed);self.assertEqual('ready',vm.store.read()['phase'])
        count=self.b.count()
        with self.assertRaises(NativeUIError):self.capture(vm)
        self.assertEqual(count,self.b.count())

    def test_generic_cleanup_retains_rootless_world_vm_originals_without_reconstructing_owner(self):
        import sys
        root=Path(__file__).resolve().parents[3];sys.path.insert(0,str(root/'android/vr/pico/tests/device'))
        import test_native_execution_binding as native
        from adapters.pico4.script_journey import PicoScriptJourney
        h=native.NativeExecutionBindingTest();h.setUp();self.addCleanup(h.doCleanups)
        h.navigation_setup();adapter=h.instance();target=h.fake.target
        self.assertFalse(adapter._world_web_retained(target))
        journey=PicoScriptJourney(adapter);journey.state_area='world-web';folder=journey.state_path(target).parent
        original=folder/'pico-world-web-primary-vm.chunk-000000.json';original.write_bytes(b'actual unresolved world VM original');original.chmod(0o600)
        self.assertTrue(adapter._world_web_retained(target))
        with self.assertRaises((ValueError,RuntimeError)):adapter.cleanup(target)
        self.assertFalse(h.fake.running);self.assertEqual(b'actual unresolved world VM original',original.read_bytes())


if __name__=='__main__':unittest.main()
