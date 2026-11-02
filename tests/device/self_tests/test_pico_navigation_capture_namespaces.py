"""Real capture guards and retained originals at explicit native/GPU models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from adapters.pico4.navigation_originals import read_original
from adapters.owned_world_render import WorldRenderOwner
from self_tests import test_pico_browser_stereo as browser
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
import uuid


class NavigationRetiredCaptureNamespacesTests(unittest.TestCase):
    def test_every_canonical_capture_factory_refuses_each_existing_navigation_namespace_before_send(self):
        from self_tests import test_pico_emote_sources as emote
        fixture=emote.SourcesTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as canonical
        native_fixture=canonical.NativeExecutionBindingTest();native_fixture.setUp();self.addCleanup(native_fixture.doCleanups)
        adapter=native_fixture.instance();adapter.pico_configuration=('modeled-namespace',fixture.root)
        sends=[]
        def send(command):sends.append(command);raise NativeUIError('Unexpected native send at blocked namespace')
        native=SimpleNamespace(pid=31,guard=fixture.guard,clock_ms=lambda:20000,monotonic=lambda:0.,sleep=lambda _seconds:None,send=send)
        adapter._native_feature_observer=lambda _target:native
        adapter._scripts=lambda _target:SimpleNamespace(binding=emote.BINDING)
        adapter._script_runtime=lambda _target:(None,None,emote.BINDING)
        adapter._script_paths=lambda _target:(fixture.root/'normal-script-state-namespace.json',fixture.root/'normal-script-ui-namespace.json')
        adapter._emote_source_store=lambda _target,role:PrivateFeatureState(fixture.root/('emote-'+role+'.json'))
        def lock(_target,provided):self.assertIs(fixture.lock,provided);return provided
        adapter._script_journey=lambda:SimpleNamespace(state_path=lambda _target:fixture.root/'state.json',_lock=lock)
        graphics_lock=PicoGraphicsBinding(adapter)._lock('owned')
        stores=adapter._navigation_world_render_stores('owned')
        self.assertEqual(['navigation-prefix-world-render-primary.json','navigation-prefix-world-render-actor.json',
            'navigation-prefix-generation-1-world-render-primary.json','navigation-prefix-generation-1-world-render-actor.json'],
            [store.path.name for store in stores])
        with fixture.lock.held():source=fixture.owner()
        factories=(('generic',graphics_lock,lambda:adapter._world_render_capture('owned',source_lock=graphics_lock)),
            ('emote',fixture.lock,lambda:adapter._emote_world_render_capture('owned',source)),
            ('browser',fixture.lock,lambda:adapter._browser_world_render_capture('owned',role='primary',source_lock=fixture.lock)),
            ('navigation',fixture.lock,lambda:adapter._navigation_world_render_capture('owned',role='primary',source_lock=fixture.lock)))
        for store in stores:
            with fixture.lock.held():
                role='primary' if 'primary' in store.path.name else 'actor'
                owner=WorldRenderOwner(store,emote.BINDING,fixture.guard,role=role)
                owner.intent(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-world-render-observe'))
                retained=read_original(store.path)
            for name,held,factory in factories:
                with self.subTest(namespace=store.path.name,factory=name),held.held():
                    capture=factory()
                    with self.assertRaises(NativeUIError):capture.read(0)
                self.assertEqual([],sends);self.assertEqual(retained,read_original(store.path))
            store.discard(store.read())  # Only this modeled counter's lease.

    def test_g0_and_g1_both_roles_block_browser_and_graphics_retirement_inspection_even_after_admission(self):
        fixture=browser.PicoBrowserStereoTests();self.addCleanup(fixture.doCleanups)
        model=fixture.model();proof=model.browser_stereo().acquire(browser.TICKET)['proof']
        binding,_stores=fixture.retired_binding(model)
        navigation=tuple(PrivateFeatureState(model.root/('navigation-'+str(generation)+'-'+role+'.json'))
            for generation in (0,1) for role in ('primary','actor'))
        binding.original._navigation_world_render_stores=lambda target:navigation
        graphics=PicoGraphicsBinding(binding.original)
        # This fixture's existing source lock owns the actual retained proof.
        graphics._lock=binding.original.source_lock
        factories=(binding._tablet_web_retired_capture_observer,graphics._graphics_retired_capture_observer)
        originals=[read_original(path) for path in model.artifacts.iterdir()]
        gpu=len(model.gpu.commands);storage=len(model.storage.commands)
        for store in navigation:
            for factory in factories:
                with self.subTest(path=store.path.name,factory=factory.__name__),model.lock.held():
                    reader=factory('owned',proof,model.lock);reader.request('inspect')
                    before=len(model.inventory.commands);foreign=dict(retainedOriginal=True)
                    store.write(foreign,None)
                    with self.assertRaises(NativeUIError):reader.request('inspect')
                    with self.assertRaises(NativeUIError):factory('owned',proof,model.lock)
                    self.assertEqual(before,len(model.inventory.commands))
                    self.assertEqual(foreign,store.read())
                    store.discard(foreign)  # Only this counter's synthetic file.
        self.assertEqual((gpu,storage),(len(model.gpu.commands),len(model.storage.commands)))
        self.assertEqual(originals,[read_original(row['path']) for row in originals])

if __name__=='__main__':unittest.main()
