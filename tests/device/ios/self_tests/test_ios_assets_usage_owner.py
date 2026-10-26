"""Durable normal Usage inputs over real source files and original QML JS.

Existing-server publication, Qt/native clocks and APIs are declared models;
neither oven work nor actual entity/model/resource/rendering is established.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack,pack
from ios.adapters.assets_usage_owner import OwnedAssetsUsage
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_usage_fixture import Fixture,RUN


class AssetsUsageOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.b=self.f.boundary
        for attribute,kind in (('file_store','files'),('picker_store','picker'),('upload_store','upload'),('reply_store','replies')):
            getattr(self.f,attribute).path=self.path/('ios-assets-'+RUN+'-primary-'+kind+'.json')
        self.o=self.f.owned_existing_source();old=self.o.store.path;self.o.store.path=self.path/('ios-assets-'+RUN+'-primary-usage.json');old.rename(self.o.store.path);self.o.select()

    def restored(self):return OwnedAssetsUsage(self.f.owner(),self.o.store,lock=self.f.lock)

    def test_durable_checkbox_and_model_default_acceptance_are_only_ui_resolution(self):
        self.o.baking(True);self.o.open_model();self.o.accept_model()
        entries=self.o.state['inputs'];self.assertTrue(all(row['resolvedBy'] is not None for row in entries))
        self.assertEqual([True],[event['enabled'] for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='baking-started'])
        events=[event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='entity-returned'];self.assertEqual(1,len(events));self.assertEqual('simple-compound',events[0]['args'][3])
        self.assertEqual(0,self.b.host_state['uploads']);self.assertEqual('ready',self.o.source.state['phase']);self.assertIsNone(self.o.state['clientClosedBy'])
        before=deepcopy(self.b.inputs);requests=deepcopy(self.b.reads.requests);restored=self.restored();self.assertEqual(self.o.state,restored.state)
        self.assertEqual(before,self.b.inputs);self.assertEqual(requests,self.b.reads.requests)

    def test_lost_normal_toggle_recovers_exact_owned_command_without_resending(self):
        self.b.configure(lost='assets.baking')
        with self.assertRaises(NativeUIError):self.o.baking(True)
        entry=next(row for row in self.o.state['inputs'] if row['slot']=='usage-bake-on');self.assertIsNotNone(entry['command']);self.assertIsNone(entry['resolvedBy'])
        before=deepcopy(self.b.inputs);restored=self.restored();restored.resolve('usage-bake-on');self.assertEqual(before,self.b.inputs)
        self.assertEqual(1,len([event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='baking-started']))

    def test_ignored_toggle_stays_owned_and_cannot_be_reissued(self):
        self.b.configure(ignore='assets.baking')
        with self.assertRaises(NativeUIError):self.o.baking(True)
        before=deepcopy(self.b.inputs);restored=self.restored()
        with self.assertRaises(NativeUIError):restored.resolve('usage-bake-on')
        with self.assertRaises(NativeUIError):restored.baking(True)
        self.assertEqual(before,self.b.inputs);self.assertIsNone(next(row for row in restored.state['inputs'] if row['slot']=='usage-bake-on')['resolvedBy'])

    def test_fresh_effective_permission_and_foreign_model_url_block_acceptance(self):
        self.o.open_model();self.b.configure(canRez=False,canRezTmp=False);before=deepcopy(self.b.inputs)
        with self.assertRaises(NativeUIError):self.o.accept_model()
        self.assertEqual(before,self.b.inputs);self.b.configure(canRez=True,modelUrl='atp:/foreign/model.fbx')
        with self.assertRaises(NativeUIError):self.o.accept_model()
        self.assertEqual(before,self.b.inputs);self.assertFalse(any(event['kind']=='entity-returned' for event in self.b.host_state['bundleInfo']['serviceEvents']))

    def test_changed_independent_mapping_blocks_before_normal_baking_delivery(self):
        self.b.reads.data[self.o.path()]=b'Foreign current mapping body';before=deepcopy(self.b.inputs)
        with self.assertRaises(NativeUIError):self.o.baking(True)
        self.assertEqual(before,self.b.inputs);self.assertFalse(any(event['kind']=='baking-started' for event in self.b.host_state['bundleInfo']['serviceEvents']))

    def test_deferred_original_baking_callback_resolves_later_without_new_click(self):
        self.b.configure(deferBaking=True)
        with self.assertRaises(NativeUIError):self.o.baking(True)
        before=deepcopy(self.b.inputs);restored=self.restored();self.b.configure(completeBaking=True);restored.resolve('usage-bake-on')
        self.assertEqual(before,self.b.inputs);self.assertIsNone(restored.state['clientClosedBy'])

    def test_tampered_command_admission_and_effect_cannot_replay_a_success(self):
        self.o.baking(True);value=self.o.store.read()
        for mutate in (lambda state:state['inputs'][-1]['command'].update(fieldToken='00000000-0000-0000-0000-000000000001'),
                lambda state:state['inputs'][-1]['effect'].update(checked=False),lambda state:state['inputs'][-1].update(admission=None)):
            changed=deepcopy(value);state=unpack(changed['payload'])[0];mutate(state);changed['payload']=pack([state])
            with self.assertRaises(NativeUIError):self.o.decode(changed)
        before=deepcopy(self.b.inputs);self.assertEqual(self.o.state,self.restored().state);self.assertEqual(before,self.b.inputs)

    def test_lost_model_acceptance_reopens_original_ui_only_without_new_creation(self):
        self.o.open_model();self.b.configure(lost='assets.model.accept')
        with self.assertRaises(NativeUIError):self.o.accept_model()
        before=deepcopy(self.b.inputs);restored=self.restored();restored.resolve('usage-accept-model');self.assertEqual(before,self.b.inputs)
        events=[event for event in self.b.host_state['bundleInfo']['serviceEvents'] if event['kind']=='entity-returned'];self.assertEqual(1,len(events))
        self.assertIsNone(restored.state['clientClosedBy']);self.assertEqual('ready',restored.source.state['phase'])

    def test_original_page_retirement_keeps_possible_model_consumer_retirement_blocking(self):
        self.o.open_model();self.o.accept_model();self.o.close_clients();self.assertIsNotNone(self.o.state['clientClosedBy'])
        before=deepcopy(self.b.inputs);requests=deepcopy(self.b.requests);clock_requests=deepcopy(self.b.native_clock.commands)
        rows=inspect_directory(self.path);self.assertEqual(['server-retirement','usage-model-retirement'],rows[0]['responsibilities'])
        self.assertEqual('primary-chosen',self.f.picker.state['phase']);self.assertFalse(self.b.root.exists());self.assertEqual(before,self.b.inputs)
        self.assertEqual(requests,self.b.requests);self.assertEqual(clock_requests,self.b.native_clock.commands)


if __name__=='__main__':unittest.main()
