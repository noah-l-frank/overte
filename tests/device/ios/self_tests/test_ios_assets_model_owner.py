"""Pre-accept original baseline and normal API-created UUID ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_model_fixture import Fixture,RUN


class AssetsModelOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary
        for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies')):getattr(self.f,attribute).path=self.path/('ios-assets-'+RUN+'-primary-'+kind+'.json')
        self.usage=self.f.owned_existing_source();old=self.usage.store.path;self.usage.store.path=self.path/('ios-assets-'+RUN+'-primary-usage.json');old.rename(self.usage.store.path);self.usage.select()
        self.sources=self.f.sources(self.usage,store=PrivateFeatureState(self.path/('ios-assets-'+RUN+'-primary-model-sources.json')))
        self.store=PrivateFeatureState(self.path/('ios-assets-'+RUN+'-primary-model.json'));self.o=OwnedAssetsModel(self.usage,self.sources,self.store,lock=self.f.lock);self.o.reserve()

    def restored(self):
        usage=OwnedAssetsUsage(self.f.owner(),self.usage.store,lock=self.f.lock);sources=self.f.sources(usage,store=self.sources.store);return OwnedAssetsModel(usage,sources,self.store,lock=self.f.lock)

    def test_pre_accept_baseline_adopts_actual_uuid_then_observes_geometry_without_resource_verdict(self):
        self.o.start();self.assertEqual('issued',self.o.state['phase']);self.assertIsNone(self.o.observe());self.assertEqual('adopted',self.o.state['phase'])
        entity_id=self.o.state['creation']['proof']['entityId'];event=next(event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='entity-returned');self.assertEqual(event['id'],entity_id)
        self.b.models[entity_id].loaded=True;self.b.models[entity_id].added=True;observed=self.o.observe();self.assertEqual(entity_id,observed['entityId']);self.assertEqual('geometry-observed',self.o.state['phase'])
        self.assertIn('assetModelGeometryObservationVersion',observed);self.assertNotIn('resourceHash',observed);self.assertEqual(0,self.b.host_state['uploads'])
        before=deepcopy(self.b.inputs);clocks=deepcopy(self.b.native_clock.commands);restored=self.restored();self.assertEqual(self.o.state,restored.state);self.assertEqual(before,self.b.inputs);self.assertEqual(clocks,self.b.native_clock.commands)
        rows=inspect_directory(self.path);self.assertIn('model-resource-origin',rows[0]['responsibilities']);self.assertIn('usage-model-retirement',rows[0]['responsibilities']);self.assertEqual(clocks,self.b.native_clock.commands)

    def test_lost_normal_acceptance_uses_saved_baseline_and_never_creates_twice(self):
        self.b.configure(lost='assets.model.accept')
        with self.assertRaises(NativeUIError):self.o.start()
        self.assertEqual('issued',self.o.state['phase']);before=deepcopy(self.b.inputs);restored=self.restored();restored.recover();self.assertIsNone(restored.observe())
        self.assertEqual('adopted',restored.state['phase']);self.assertEqual(before,self.b.inputs);self.assertEqual(1,len(self.b.entities))
        self.assertEqual(1,len([event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='entity-returned']))

    def test_ignored_acceptance_does_not_adopt_or_repeat_an_input(self):
        self.b.configure(ignore='assets.model.accept')
        with self.assertRaises(NativeUIError):self.o.start()
        self.assertFalse(self.b.entities);before=deepcopy(self.b.inputs);restored=self.restored()
        for invoke in (restored.recover,restored.start,restored.observe):
            with self.assertRaises(NativeUIError):invoke()
        self.assertEqual(before,self.b.inputs);self.assertIsNone(restored.state['creation'])

    def test_interrupted_readonly_baseline_can_restart_without_reopening_or_accepting_old_frame(self):
        send=self.sources.readers['work'].send
        def lost(query):send(query);raise NativeUIError('modeled lost readonly baseline')
        self.sources.readers['work'].send=lost
        with self.assertRaises(NativeUIError):self.o.start()
        self.assertFalse(self.b.entities);self.assertEqual('reserved',self.o.state['phase']);self.sources.freeze_interrupted();self.sources.readers['work'].send=send
        self.o.start();self.assertIsNone(self.o.observe());self.assertEqual('adopted',self.o.state['phase'])
        self.assertEqual(1,len(self.sources.state['interrupted']));self.assertEqual(1,len([entry for entry in self.usage.state['inputs'] if entry['slot']=='usage-open-model']))

    def test_current_guard_refusal_cannot_reuse_cached_adoption_as_new_geometry(self):
        self.o.start();self.o.observe();before=deepcopy(self.b.native_clock.commands);self.b.live=False
        with self.assertRaises(NativeUIError):self.o.observe()
        self.assertEqual(before,self.b.native_clock.commands);self.assertIsNone(self.o.state['geometryObserved'])

    def test_closed_runtime_factory_reuses_actual_readers_and_creates_no_observation(self):
        from unittest.mock import patch
        runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.b.monotonic)
        state,work=self.b.model_readers(self.usage.source.clock)
        observer=SimpleNamespace(create_state=lambda clock:state,create_work=lambda clock:work,epoch_ms=lambda:self.b.clock()+5000)
        parts=dict(upload=self.usage.source,usage=self.usage,observer=observer,check=self.usage.guard);before=deepcopy(self.b.native_clock.commands)
        with patch.object(runtime,'state_path',return_value=self.path/'session.json'):
            produced=runtime._assets_model_components('test-only',RUN,'primary',self.f.files.url,self.f.lock,parts=parts)
        self.assertIs(self.usage,produced['model'].usage);self.assertIs(self.usage.source.clock,produced['model_sources'].native);self.assertEqual(before,self.b.native_clock.commands)


if __name__=='__main__':unittest.main()
