"""Real admission ownership over synthetic original source/probe/cache IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.normal_ui import NativeUIError
from adapters.emote_admission import catalog
from overte_phone_emote_admission import PhoneEmoteAdmission
from overte_phone_script_history import pack,unpack
from test_emote_background import Model as BackgroundModel
from self_tests.test_native_animation_inventory import InventoryBoundary
from self_tests.test_emote_admission import add_manager,probe,POLICY,PROBE
from test_emote_sources import RUN


class Model(BackgroundModel):
    def __init__(self,root):
        super().__init__(root);self.use_included_source();self.widgets.tablet=False
        self.inventory=InventoryBoundary(self.roots.root);self.probe_sequence=0;self.probe_value=None;self.admission_fault=None
        observe=self.code.mutate
        def scripts(value):
            observe(value);value['source']['engines'][0]['required'].update(sequence=0,modules=[])
            add_manager(value,PROBE,catalog()['probe'])
            if self.admission_fault=='foreign-code':value['source']['engines'][1]['code']['sha256']='f'*64
        self.code.mutate=scripts
    def _animation_inventory(self,_selector,*,read_only):
        assert read_only
        self.inventory.epoch=self.epoch;reader=self.inventory.reader();reader.clock_ms=lambda:self.epoch
        reader.monotonic=lambda:self.clock;reader.sleep=self.sleep;reader.guard=lambda:self.okay and self.foreground
        return reader
    def invoke(self,selector,operation,values):
        if operation!='probe.snapshot':return super().invoke(selector,operation,values)
        assert values=={} and self.foreground
        if self.admission_fault=='frozen-probe' and self.probe_value is not None:return deepcopy(self.probe_value)
        self.probe_sequence+=1;value=probe(self.probe_sequence,self.epoch)
        if self.admission_fault=='wrong-domain':value['domain']['hostname']='foreign.invalid'
        elif self.admission_fault=='old-probe':value['sampleEpochMs']-=1600
        elif self.admission_fault=='phase':self.journal.activate(RUN,'e'*32,'open',{})
        elif self.admission_fault=='count-before-fence':value['sampleEpochMs']-=150;value['scene']['entityCount']+=1
        self.probe_value=deepcopy(value);return value


class EmoteAdmissionOwnerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-admission-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name))

    def owner(self):return PhoneEmoteAdmission(self.model.source(),POLICY)

    def test_three_fresh_independent_world_cache_source_groups_admit_without_any_input_or_prefetch(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();header=owner.wait(sleep=m.sleep)
            self.assertEqual('admitted',owner.state['phase']);self.assertEqual([1,2,3],owner.state['window']['records'])
            self.assertEqual(3,len(owner.state['records']));self.assertEqual(header,owner.store.read())
            reconstructed=self.owner();self.assertEqual(owner.state,reconstructed.state)
            self.assertEqual([],m.controls.input_requests);self.assertEqual([],m.tablet_inputs);self.assertEqual([],m.normal_inputs)
            self.assertTrue(all(set(command)=={'schemaVersion','commandId','action'} for command in m.inventory.commands))
            self.assertLess(owner.store.path.stat().st_size,65536)

    def test_actual_missing_cache_resource_can_warm_up_but_cannot_fill_expected_results(self):
        m=self.model;resource=m.inventory.resources.pop();send=m.inventory.send
        def loaded(request):
            if len(m.inventory.commands)==1:m.inventory.resources.append(resource);m.inventory.resources.sort(key=lambda row:row['resourceInstance'])
            send(request)
        m.inventory.send=loaded
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep)
            self.assertEqual([2,3,4],owner.state['window']['records']);rows=owner.records(owner.state)
            self.assertEqual(11,len(rows[0]['inventory']['source']['resources']));self.assertEqual(12,len(rows[-1]['inventory']['source']['resources']))

    def test_permanently_empty_cache_never_admits_and_retains_all_bounded_originals(self):
        m=self.model;m.inventory.resources=[]
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.wait(sleep=m.sleep)
            self.assertEqual('ready',owner.state['phase']);self.assertEqual(32,len(owner.state['records']));self.assertIsNone(owner.state['window'])
            self.assertIsNotNone(owner.store.read());self.assertEqual([],m.normal_inputs)

    def test_foreign_world_source_old_probe_and_phase_change_are_not_warmup(self):
        for fault in ('foreign-code','wrong-domain','old-probe','phase'):
            temporary=tempfile.TemporaryDirectory(prefix='overte-emote-admission-denial-');self.addCleanup(temporary.cleanup)
            m=Model(Path(temporary.name));m.admission_fault=fault
            with self.subTest(fault=fault),m.lock.held():
                owner=PhoneEmoteAdmission(m.source(),POLICY)
                with self.assertRaises(NativeUIError):owner.wait(sleep=m.sleep)
                self.assertEqual([],owner.state['records']);self.assertEqual('reading',unpack(owner.store.read()['payload'])[0]['phase'])
                self.assertLessEqual(len(m.inventory.commands),1);self.assertEqual([],m.controls.input_requests)

    def test_wrong_loaded_model_is_an_error_even_while_a_different_resource_is_missing(self):
        m=self.model;m.inventory.resources.pop();m.inventory.resources[0]['model']['sha256']='f'*64
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.wait(sleep=m.sleep)
            self.assertEqual(1,len(m.inventory.commands));self.assertEqual('reading',owner.state['phase']);self.assertIsNotNone(owner.store.read())

    def test_frozen_original_probe_never_becomes_three_independent_samples(self):
        m=self.model;m.admission_fault='frozen-probe'
        with m.lock.held():
            owner=self.owner()
            with self.assertRaises(NativeUIError):owner.wait(sleep=m.sleep)
            self.assertIsNone(owner.state['window']);self.assertEqual(1,m.probe_sequence);self.assertIsNotNone(owner.store.read())

    def test_missing_saved_original_is_not_hidden_by_memory_or_admitted_header(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep);ref=owner.state['records'][0]
            owner.originals.path(owner.originals.expand(ref)).unlink();before=len(m.inventory.commands)
            with self.assertRaises(FileNotFoundError):self.owner()
            with self.assertRaises(FileNotFoundError):owner.read()
            self.assertEqual(before,len(m.inventory.commands));self.assertIsNotNone(owner.store.read())

    def test_ignored_intent_persistence_cannot_dispatch_even_a_read(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();before=deepcopy(m.calls)
            with patch.object(owner.store,'write',return_value=None),self.assertRaises(NativeUIError):owner.read()
            self.assertEqual(before,m.calls);self.assertEqual([],m.inventory.commands);self.assertTrue(owner.failed)

    def test_lost_file_commit_leaves_a_pending_original_and_never_acquires_another_group(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();intent=owner.originals.intent
            def lost(kind,value):
                intent(kind,value)
                if value['phase']=='saved':raise NativeUIError('Synthetic original commit return lost')
            owner.originals.intent=lost
            with self.assertRaises(NativeUIError):owner.read()
            reconstructed=self.owner();self.assertEqual('saved',reconstructed.state['pending']['original']['phase'])
            before=len(m.inventory.commands)
            with self.assertRaises(NativeUIError):reconstructed.read()
            self.assertEqual(before,len(m.inventory.commands));self.assertIsNotNone(reconstructed.store.read())

    def test_changed_policy_or_saved_fake_window_cannot_reconstruct_admission(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep)
            with self.assertRaises(NativeUIError):PhoneEmoteAdmission(m.source(),POLICY|dict(domainId='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'))
            value=owner.store.read();state=unpack(value['payload'])[0];state['window']['records']=[1,1,1]
            value['payload']=pack([state]);owner.store.write(value,owner.previous)
            with self.assertRaises(NativeUIError):self.owner()

    def test_complete_lost_original_is_recovered_historically_before_new_fresh_queries(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();intent=owner.originals.intent
            def lost(kind,value):
                intent(kind,value)
                if value['phase']=='saved':raise NativeUIError('Synthetic complete original return lost')
            owner.originals.intent=lost
            with self.assertRaises(NativeUIError):owner.read()
            original=deepcopy(owner.state['pending']['original']);before=len(m.inventory.commands)
            reconstructed=self.owner();reconstructed.recover_pending()
            self.assertEqual(before,len(m.inventory.commands));self.assertEqual('ready',reconstructed.state['phase'])
            self.assertEqual(original['sha256'],reconstructed.state['records'][0]['sha256'])
            reconstructed.wait(sleep=m.sleep);self.assertEqual('admitted',reconstructed.state['phase'])
            self.assertGreater(len(m.inventory.commands),before);self.assertEqual([],m.normal_inputs)

    def test_changed_entity_count_resets_stability_even_when_sample_precedes_its_new_fence(self):
        m=self.model
        with m.lock.held():
            owner=self.owner();owner.wait(sleep=m.sleep);m.admission_fault='count-before-fence'
            m.epoch+=1000;m.roots.epoch=m.epoch;m.clock+=1
            actual=owner.read();self.assertFalse(actual['eligible']);self.assertEqual('ready',owner.state['phase'])
            self.assertIsNone(owner.state['window']);self.assertEqual(6,actual['probe']['scene']['entityCount'])


if __name__=='__main__':unittest.main()
