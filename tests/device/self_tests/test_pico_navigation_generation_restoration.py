"""Actual fifteen-action Python/TLS owners and normal G1 restoration inputs.

Qt, Settings QMetaType/serialization, OS, Session consumption and GPU are
explicit native models. No compiler, physical target or external service runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import shutil
import unittest
from unittest.mock import patch
import uuid

from adapters.native_feature_observation import need
from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_generation_restoration import NavigationGenerationRestoration
from adapters.pico4.navigation_originals import read_original
from adapters.script_journey.history import unpack
from adapters.token_places_ui import sha
from self_tests import test_pico_navigation_generation_prefix as generation
from self_tests import test_navigation_origin as original_origin


class Model(generation.Model):
    def __init__(self,root):
        super().__init__(root);self.restoration_qml=[];self.lose_restore_return=False;self.ignore_restore_entry=False

    def raw(self):
        value=super().raw();value['loginControlsVersion']=2
        if self.shown and not self.login and not self.page:
            value['controls'].append(dict(id='login.entry',token=str(uuid.uuid5(uuid.NAMESPACE_URL,self.bridge+'/'+self.generation+'/login.entry')),
                enabled=True,focused=False,inputReady=True))
        return value

    def send(self,command):
        if command=={}:
            # The real native hook ignores the identity-less private-file
            # clearing packet. It issues no input and retains its last status.
            return deepcopy(self.owner_test.ui_status),self.epoch()
        restoration=PrivateFeatureState(self.root/'navigation-prefix-generation-1-restoration.json').read() if self.g1 else None
        if restoration is None:return super().send(command)
        state=unpack(restoration['payload'])[0]
        need(state['phase'] in ('entry','origin') and state['qml'] and state['qml'][-1]['command']==command)
        self.restoration_qml.append(deepcopy(command))
        if command['controlId']=='login.entry':
            need(state['phase']=='entry' and self.shown and not self.login and not self.page)
            self.sequence+=1
            if not self.ignore_restore_entry:
                self.login=True;self.focus='';self.draft=self.selected;self.generation=str(uuid.uuid4())
            return dict(schemaVersion=1,bridgeId=self.bridge,commandId=command['commandId'],sequence=command['sequence'],
                performed=True,error='',processId=32,updatedEpochMs=self.epoch()),self.epoch()
        need(state['phase']=='origin' and self.login and command['controlId']=='login.server')
        # Reuse the existing ordinary handler AND its actual modeled persisted
        # startup file. No target/expected setting is injected into persistence.
        result,epoch=generation.original.Model.send(self,command);result['processId']=32
        if command['action']=='submit' and self.lose_restore_return:raise NativeUIError('Synthetic lost applied QString Return')
        return result,epoch


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationGenerationRestorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):generation.NavigationGenerationPrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):generation.NavigationGenerationPrefixTests.tearDownClass()

    def setUp(self):
        self.f=generation.NavigationGenerationPrefixTests();self.f.model_type=Model;self.f.setUp()
        # Prefix setup already registered the original bound Model.close before
        # transit replaced that attribute. Preserve its original directory too.
        world=self.f.world;world.temporary.cleanup=lambda:None
        def finish():
            self.f.doCleanups();self.assertTrue(world.root.is_dir())
        self.addCleanup(finish)
        producer=patch.object(generation,'Model',Model);producer.start();self.addCleanup(producer.stop)

    def prepare(self):
        f=self.f;f.prepare_generation()
        for index in range(12,15):f.flow.act(f.next_call(index));f.flow.observe();f.actor.observe()
        # The actual canonical factory constructs a NEW reader per owner. Keep
        # the producer's native sequence/birth; never reuse another host writer.
        f.adapter._navigation_environment=lambda _target:NativeNavigationEnvironment(f.model.source_send,
            lambda:json.dumps(f.model.packet),f.model.epoch,f.model.guard,32,monotonic=lambda:f.model.clock,sleep=f.model.sleep)
        self.old=f.original_parent.origin.state['original'];self.sdk=deepcopy(f.sdk_calls)
        self.g0=[deepcopy(row) for row in f.flow.generation_owner.restart.state['files']]
        self.g1=[read_original(f.root/('navigation-prefix-generation-1-'+name+'.json')) for name in ('parent','close-join','tablet-close')]
        self.before_controllers=deepcopy(f.model.controller_calls)
        ticket=uuid.uuid4().hex;f.server.journal.activate(generation.prefix.RUN,ticket,'cleanup',{});f.model.provider.activate(generation.prefix.RUN,ticket)
        with f.lock.held():self.owner=NavigationGenerationRestoration(f.flow.generation_owner,f.adapter,'owned-model')
        self.call=dict(contractVersion=generation.CONTRACT_VERSION,runId=generation.prefix.RUN)

    def preserved(self):
        self.assertEqual(self.sdk,self.f.sdk_calls)
        for row in self.g0+self.g1:self.assertEqual(row,read_original(row['path']))

    def test_fifteen_original_actions_then_normal_g1_login_return_home_close_restore_exact_original(self):
        self.prepare();f=self.f
        self.assertEqual(dict(performed=True),f.flow.restore(self.call));self.owner=f.flow.generation_owner.restoration_owner
        self.assertEqual(self.old['selectedServer'],f.model.selected);self.assertEqual(self.old['selectedServer'],f.model.effective)
        self.assertFalse(f.model.login);self.assertFalse(f.model.shown)
        self.assertEqual([('login.entry','activate'),('login.server','activate'),('login.server','replace'),('login.server','submit')],
            [(row['controlId'],row['action']) for row in f.model.restoration_qml])
        self.assertEqual(['tablet.open','input.primary','tablet.close'],
            [row['commands'][0]['operation'] for row in f.model.controller_calls[len(self.before_controllers):]])
        origin=self.owner.origin
        self.assertEqual(3,origin.state['navigationOriginVersion']);self.assertEqual(f.url,origin.state['original']['selectedServer'])
        self.assertEqual(32,origin.state['original']['processId']);self.assertEqual(31,self.old['processId'])
        self.assertEqual(self.old['settings']['rawSettingsSha256'],self.owner.state['quiet'][-1]['environment']['settings']['rawSettingsSha256'])
        self.assertEqual('complete',self.owner.state['phase']);self.preserved()
        commands=deepcopy(f.model.restoration_qml);controllers=deepcopy(f.model.controller_calls)
        self.assertEqual(dict(performed=True),f.flow.restore(self.call))
        self.assertEqual(commands,f.model.restoration_qml);self.assertEqual(controllers,f.model.controller_calls);self.preserved()

    def test_applied_lost_return_cold_finishes_same_original_without_second_qt_or_controller_input(self):
        self.prepare();f=self.f;f.model.lose_restore_return=True
        with self.assertRaises(NativeUIError):f.flow.restore(self.call)
        owner=f.flow.generation_owner.restoration_owner
        self.assertEqual('origin',owner.state['phase']);self.assertEqual(2,owner.origin.state['operation']['stage'])
        self.assertEqual(self.old['selectedServer'],f.model.selected)
        self.assertEqual(self.old['selectedServer'],PrivateFeatureState(f.root/'synthetic-product-navigation-startup.json').read()['selected'])
        before=len(f.model.restoration_qml);f.model.lose_restore_return=False
        self.assertEqual(dict(performed=True),f.cold_generation().restore(self.call))
        self.assertEqual(before,len(f.model.restoration_qml));self.assertEqual(1,sum(row['action']=='submit' for row in f.model.restoration_qml))
        self.assertEqual(3,len(f.model.controller_calls)-len(self.before_controllers));self.preserved()

    def test_original_qurl_setting_is_refused_before_any_normal_mutation(self):
        f=self.f;f.model.selected_type='url';original=f.model.selected
        with self.assertRaises(NativeUIError):f.flow.prepare()
        self.assertEqual(original,f.model.selected);self.assertEqual([],f.model.calls);self.assertEqual([],f.model.controller_calls)
        self.assertIsNone(f.flow.origin.state)

    def test_original_absent_setting_is_refused_before_any_normal_mutation(self):
        f=self.f;f.model.present=False;original=f.model.selected
        with self.assertRaises(NativeUIError):f.flow.prepare()
        self.assertEqual(original,f.model.selected);self.assertEqual([],f.model.calls);self.assertEqual([],f.model.controller_calls)
        self.assertIsNone(f.flow.origin.state)

    def test_actual_old_pid_presence_blocks_handoff_before_new_open_or_qt_input(self):
        self.prepare();f=self.f;f.kernel.presence='present'
        with self.assertRaises(NativeUIError):f.flow.restore(self.call)
        owner=f.flow.generation_owner.restoration_owner
        self.assertEqual('admission',owner.state['phase']);self.assertIsNone(owner.state['reference'])
        self.assertEqual([],f.model.restoration_qml);self.assertEqual(self.before_controllers,f.model.controller_calls)
        self.assertIsNone(owner.authority.store.read());self.preserved()

    def test_phase_changes_after_real_entry_command_cas_send_zero_entry_and_cold_never_repeats(self):
        self.prepare();f=self.f;write=PrivateFeatureState.write;changed=[]
        def landed(store,value,previous):
            answer=write(store,value,previous)
            if store.path==self.owner.store.path and not changed and value.get('navigationGenerationRestorationVersion')==1:
                state=unpack(value['payload'])[0]
                if state['qml'] and state['qml'][-1]['command']['controlId']=='login.entry':
                    ticket=uuid.uuid4().hex;f.server.journal.activate(generation.prefix.RUN,ticket,'cleanup',{});f.model.provider.activate(generation.prefix.RUN,ticket)
                    changed.append(True)
            return answer
        with patch.object(PrivateFeatureState,'write',landed),self.assertRaises(NativeUIError):f.flow.restore(self.call)
        owner=f.flow.generation_owner.restoration_owner;original=read_original(owner.store.path)
        self.assertTrue(changed);self.assertEqual([],f.model.restoration_qml);self.assertEqual(1,len(owner.state['qml']))
        controllers=deepcopy(f.model.controller_calls)
        with self.assertRaises(NativeUIError):f.cold_generation().restore(self.call)
        self.assertEqual([],f.model.restoration_qml);self.assertEqual(controllers,f.model.controller_calls)
        self.assertEqual(original,read_original(owner.store.path));self.preserved()

    def test_foreign_settings_original_is_archived_before_refusal_and_reading_acquisition_cannot_be_adopted(self):
        self.prepare();f=self.f;write=PrivateFeatureState.write;changed=[]
        def landed(store,value,previous):
            answer=write(store,value,previous)
            if store.path==self.owner.store.path and not changed and value.get('navigationGenerationRestorationVersion')==1:
                state=unpack(value['payload'])[0]
                if state['phase']=='quiet':f.model.other='f'*64;changed.append(True)
            return answer
        with patch.object(PrivateFeatureState,'write',landed),self.assertRaises(NativeUIError):f.flow.restore(self.call)
        owner=f.flow.generation_owner.restoration_owner
        self.assertTrue(changed);self.assertEqual('reading',owner.state['acquisitions'][-1]['phase'])
        packet=owner.state['acquisitions'][-1]['packets']['environment']
        self.assertEqual('f'*64,packet['otherSettingsSha256'])
        self.assertEqual(packet,json.loads(owner.state['nativeOriginals'][-1]['raw']))
        original=read_original(owner.store.path);counts=f.source_counts();commands=deepcopy(f.model.restoration_qml);controllers=deepcopy(f.model.controller_calls)
        with self.assertRaises(NativeUIError):f.cold_generation().restore(self.call)
        self.assertEqual(counts,f.source_counts());self.assertEqual(commands,f.model.restoration_qml);self.assertEqual(controllers,f.model.controller_calls)
        self.assertEqual(original,read_original(owner.store.path));self.preserved()

    def test_reused_reader_keeps_original_writer_and_cannot_bypass_single_owner_on_retry(self):
        self.prepare();f=self.f;reader=f.adapter._navigation_environment('owned-model')
        f.adapter._navigation_environment=lambda _target:reader
        with f.lock.held():
            first=NavigationGenerationRestoration(f.flow.generation_owner,f.adapter,'owned-model');first.live()
            callback=reader.original
            second=NavigationGenerationRestoration(f.flow.generation_owner,f.adapter,'owned-model')
            for _attempt in range(2):
                with self.assertRaises(NativeUIError):second.live()
                self.assertIsNone(second.runtime);self.assertIs(callback,reader.original)
                self.assertIs(first,reader._pico_navigation_restoration_owner)
        self.assertEqual([],f.model.restoration_qml);self.assertEqual(self.before_controllers,f.model.controller_calls);self.preserved()

if __name__=='__main__':unittest.main()
