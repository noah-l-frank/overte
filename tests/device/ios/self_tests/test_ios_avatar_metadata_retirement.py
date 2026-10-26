"""Actual private metadata CAS with an explicitly injected end-admission seam.

The admission seam models only the output/read membership of a full decoder.
These cases qualify metadata refusal/resumption, never an Avatar end graph.
Actual InstalledCodeBinding decoding and original file/inode checks remain.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack
from ios.adapters.avatar_metadata_retirement import retire_existing
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_api_entry import scope as api_scope
from ios.adapters.avatar_session_cleanup import budget as cleanup_budget
from ios.adapters.installed_code import SDK,InstalledCodeBinding
from ios.self_tests.test_ios_bundle_observation import Boundary


class AvatarMetadataRetirementTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.paths={role:self.root/role/'session.json' for role in ('primary','actor')}
        self.artifacts={role:self.root/(role+'-artifacts') for role in self.paths}
        for path in list(self.artifacts.values())+[path.parent for path in self.paths.values()]:path.mkdir(mode=0o700)
        self.run='a'*32;self.binding=dict(sourceRevision='b'*40,artifactSha256='c'*64,sessionId='ended-primary',
            generation=1,targetFingerprint='d'*64,processIdentity='42')
        self.scope={key:value for key,value in self.binding.items() if key!='processIdentity'}
        self.provenance=dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance='e'*32,
            available=True,cleanupPending=False,sdk=dict(SDK))
        self.calls=[];boundary=Boundary();observation=boundary.reader().read()
        self.bundle=boundary.bundle['bundleId']
        for role in self.paths:
            owner=dict(iosAvatarFeatureVersion=1,runId=self.run,role=role,selectors=dict(primary='primary',actor='actor'),
                artifactRoot=str(self.artifacts[role]),payload=pack([dict(phase='terminal-ready',bindings={role:self.binding})]))
            self.store(role,'ios-avatar-'+role+'-feature.json').write(owner,None)
        self.process_name='ios-avatar-primary-'+self.run+'-terminal-process.json'
        process=dict(binding=self.binding,runId=self.run,role='primary',bundleId=self.bundle,source=self.provenance,payload=pack([dict(phase='ended')]))
        self.store('primary',self.process_name).write(process,None)
        self.sdk=dict(sessionId=self.binding['sessionId'],generation=1,targetFingerprint=self.binding['targetFingerprint'],physicalTargetAttested=True)
        self.installed=dict(bindingVersion=4,phase='retired',scope=self.scope,source=self.provenance,
            process=dict(bundleId=self.bundle,pid=42,foreground=True),observation=observation,previousInstance=None,recovery=None)
        self.store('primary','session.json').write(self.sdk,None)
        self.store('primary','installed-code-binding.json').write(self.installed,None)
        def candidate(selector,scope):
            self.assertEqual('primary',selector);self.assertEqual(self.scope,scope);self.calls.append('candidate')
            return {'appId':self.bundle}
        def forbidden(*_args,**_kwargs):raise AssertionError('No native/process/SDK calls are allowed during metadata CAS')
        def record(selector,scope,value):
            candidate(selector,scope)
            class Frozen:
                def read(self):return deepcopy(value)
            return InstalledCodeBinding(Frozen(),scope,boundary.bundle,forbidden,forbidden,forbidden).record()
        self.base=SimpleNamespace(state_path=lambda role:self.paths[role],read_session=lambda role:self.store(role,'session.json').read(),
            _binding_store=lambda role:self.store(role,'installed-code-binding.json'),_retired_candidate_scope=candidate,
            _avatar_retired_binding_record=record,
            _target=forbidden,ensure_session=forbidden,invoke=forbidden,_binding=forbidden,_candidate_guard=forbidden)
        self.runtime=IOSAvatarRuntime(self.base)
        self.admit=patch('ios.adapters.avatar_metadata_retirement.finalize_existing',side_effect=self.admitted)
        self.admit.start();self.addCleanup(self.admit.stop)
    def store(self,role,name):return PrivateFeatureState(self.paths[role].with_name(name))
    def admitted(self,_runtime,_selector,_config,_client,*,membership,check=lambda:None):
        check()
        for path in self.root.rglob('*.json'):
            if path.name not in ('session.json','installed-code-binding.json'):membership.add(path)
        self.calls.append('admission');return True
    def run_retirement(self):return retire_existing(self.runtime,'primary',None)
    def originals(self):
        return {path:(path.stat().st_ino,path.read_bytes()) for path in self.root.rglob('*.json')
            if path.name not in ('session.json','installed-code-binding.json')}
    def assert_metadata(self):
        self.assertIsNotNone(self.store('primary','session.json').read())
        self.assertIsNotNone(self.store('primary','installed-code-binding.json').read())
    def test_actual_retired_metadata_cas_and_repeat_preserve_all_original_bytes_and_inodes(self):
        before=self.originals();self.assertEqual({'cleaned':True},self.run_retirement())
        self.assertEqual({'cleaned':True},self.run_retirement());self.assertEqual(before,self.originals())
        self.assertIsNone(self.store('primary','session.json').read());self.assertIsNone(self.store('primary','installed-code-binding.json').read())
        self.assertEqual(2,self.calls.count('admission'))
    def test_foreign_sdk_scope_flags_or_component_metadata_are_retained(self):
        for change in ({'sessionId':'foreign'},{'generation':True},{'targetFingerprint':'f'*64},
                {'processIdentity':'42'},{'iosE2ELaunchCompleted':True},{'iosNormalSnapshot':{}},{'physicalTargetAttested':False}):
            store=self.store('primary','session.json');old=store.read();store.write(dict(self.sdk,**change),old)
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):self.run_retirement()
            self.assert_metadata()
    def test_installed_typed_record_scope_pid_source_phase_or_bundle_must_match(self):
        changes=[{'phase':'bound'},{'bindingVersion':True},{'unknown':True},{'scope':dict(self.scope,generation=2)},
            {'process':dict(self.installed['process'],pid=43)}, {'source':dict(self.provenance,instance='f'*32)},
            {'observation':dict(self.installed['observation'],status='pending')}]
        for change in changes:
            store=self.store('primary','installed-code-binding.json');old=store.read();store.write(dict(self.installed,**change),old)
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):self.run_retirement()
            self.assert_metadata()
    def test_unqualified_admission_cannot_retire_metadata(self):
        with patch('ios.adapters.avatar_metadata_retirement.finalize_existing',return_value=False):
            with self.assertRaises((ValueError,RuntimeError)):self.run_retirement()
        self.assert_metadata()
    def test_original_mutation_during_admission_is_not_a_new_qualifying_baseline(self):
        def mutate(*args,**kwargs):
            self.admitted(*args,**kwargs);path=self.store('primary',self.process_name);value=path.read()
            path.write(dict(value,unexpected=True),value);return True
        with patch('ios.adapters.avatar_metadata_retirement.finalize_existing',side_effect=mutate):
            with self.assertRaises((ValueError,RuntimeError)):self.run_retirement()
        self.assert_metadata()
    def test_actual_read_membership_must_cover_unknown_avatar_carriers(self):
        path=self.artifacts['primary']/'avatar-unknown.json';PrivateFeatureState(path).write(dict(unknown=True),None)
        def admit(*args,**kwargs):
            self.admitted(*args,**kwargs);kwargs['membership'].remove(path);return True
        with patch('ios.adapters.avatar_metadata_retirement.finalize_existing',side_effect=admit):
            with self.assertRaises((ValueError,RuntimeError)):self.run_retirement()
        self.assert_metadata()
    def test_metadata_change_during_full_admission_is_not_adopted_for_cas(self):
        def mutate(*args,**kwargs):
            self.admitted(*args,**kwargs);store=self.store('primary','session.json');value=store.read()
            store.write({key:item for key,item in value.items() if key!='physicalTargetAttested'},value);return True
        with patch('ios.adapters.avatar_metadata_retirement.finalize_existing',side_effect=mutate):
            with self.assertRaises((ValueError,RuntimeError)):self.run_retirement()
        self.assert_metadata()
    def test_lost_metadata_cas_return_resumes_without_reissuing_process_or_sdk_input(self):
        original=PrivateFeatureState.discard
        def interrupted(store,previous):
            if store.path.name=='installed-code-binding.json':raise RuntimeError('Synthetic lost second metadata CAS')
            return original(store,previous)
        before=self.originals()
        with patch.object(PrivateFeatureState,'discard',interrupted):
            with self.assertRaises(RuntimeError):self.run_retirement()
        self.assertIsNone(self.store('primary','session.json').read());self.assertIsNotNone(self.store('primary','installed-code-binding.json').read())
        self.assertEqual({'cleaned':True},self.run_retirement());self.assertEqual(before,self.originals())
    def test_failed_preparation_uses_its_actual_abort_provenance_without_success_scene(self):
        owner=self.store('primary','ios-avatar-primary-feature.json');value=owner.read()
        owner.write(dict(value,payload=pack([dict(phase='ready',bindings={'primary':self.binding})])),value)
        process=self.store('primary',self.process_name);value=process.read();process.discard(value)
        self.process_name='ios-avatar-primary-'+self.run+'-abort.json'
        self.store('primary',self.process_name).write(dict(value,payload=pack([dict(phase='aborted')])),None)
        self.assertEqual({'cleaned':True},self.run_retirement())
    def test_exhausted_original_api_or_cleanup_budget_cannot_retire_metadata(self):
        for kind,limit in (('api',25),('cleanup',60)):
            clock=[0.]
            def slow(*args,**kwargs):
                self.admitted(*args,**kwargs);clock[0]=limit;return True
            manager=api_scope(lambda:clock[0]) if kind=='api' else cleanup_budget(self.base,'primary',monotonic=lambda:clock[0])
            with self.subTest(kind=kind),self.assertRaises((ValueError,RuntimeError)):
                with manager,patch('ios.adapters.avatar_metadata_retirement.finalize_existing',side_effect=slow):self.run_retirement()
            self.assert_metadata()


if __name__=='__main__':unittest.main()
