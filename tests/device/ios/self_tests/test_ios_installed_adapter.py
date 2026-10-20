"""Physical canonical mixin/gate/HTTP/AFC paths, synthetic OS/native byte sources.

The original candidate verifier and native launch/device boundaries are injected.
These are host logic checks, never installed-code or physical-client acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.ios import binding
from ios.adapters.installed_adapter import ArtifactLease
from ios.adapters.installed_code import SDK
from ios.adapters.adapter import IOSNativeMixin
from ios.adapters import appium_adapter as ios_backend
from ios.self_tests.test_ios_bundle_observation import Boundary
from self_tests.test_native_feature_observation import Boundary as ClockBoundary
from fixture.serve import FixtureState


class InstalledAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root = Path(self.temp.name)
        self.artifacts = self.root/'artifacts';self.artifacts.mkdir();self.artifact = self.artifacts/'Overte.ipa'
        self.artifact.write_bytes(b'Synthetic artifact boundary; not an installable build')
        self.native = Boundary();self.clock = ClockBoundary();self.clock.mutate = lambda v:v.update(processId=42)
        self.process = dict(bundleId=self.native.bundle['bundleId'],pid=42,foreground=True)
        self.source = dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance='d'*32,
                           available=True,cleanupPending=False,sdk=dict(SDK))
        self.summary = dict(physicalHandoffVersion=1,bundleIdentity=deepcopy(self.native.bundle),
                            artifactIdentity=dict(sourceRevision='a'*40,artifactSha256='e'*64))
        self.args = argparse.Namespace(platform='ios',action='describe',physical_candidate_metadata='test-only',
                                       artifact_root=str(self.artifacts),candidate_manifest=None)
        self.preflights = self.sessions = self.launches = 0
        self.ignored_stop = self.cleanup_failure = self.cleanup_ignored = False
        self.commands = [];self.after_operation = None
        self.target = dict(platform='ios',physical=True,appId=self.native.bundle['bundleId'],
            artifactMode='personal-team-preinstalled',_artifactMode='personal-team-preinstalled',
            probe={'kind':'ios-documents'},testBuild=dict(resultsDirectory='owned-results',
                fixtureOrigin='http://controlled.invalid:49121',scenePath='/scene.json'),capabilities={})
        fixture = FixtureState();echo = [b''];test = self
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*_):return False
            def read(self,_limit):return echo[0]
        def post(request,timeout):
            self.assertEqual(5,timeout);value=json.loads(request.data);fixture.set_client_command(value)
            echo[0]=json.dumps(value).encode()
            if value['action']=='ios-bundle-observe':self.native.send(value)
            elif value['action']=='feature-native-observe':self.clock.send(value)
            else:raise AssertionError('unexpected native input')
            return Response()
        class Client:
            def execute(self,session,operation,values):
                test.assertEqual('test-only',session);test.commands.append((operation,deepcopy(values)))
                if operation=='mobile: overteProcessSourceInfo':return deepcopy(test.source)
                if operation=='mobile: overteProcessInfo':return deepcopy(test.process)
                if operation in ('mobile: terminateApp','mobile: overteAbortApp'):
                    if not test.ignored_stop:test.process=None
                    return True
                if operation=='mobile: backgroundApp':test.process['foreground']=False;return True
                if operation=='mobile: pullFile':
                    path=values['remotePath']
                    if path=='@org.example.overte:documents/owned-results/ios-installed-bundle-observation.json':raw=test.native.original()
                    elif path=='@org.example.overte:documents/owned-results/feature-native-observation.json':raw=json.dumps(test.clock.sample)
                    else:raise AssertionError('foreign private file')
                    return base64.b64encode(raw.encode()).decode()
                raise AssertionError('unexpected OS operation: '+operation)
        class Base:
            def __init__(self,platform):
                self.platform=platform;self.adapter_id='appium-ios';self.client=Client()
                self._state=dict(sessionId='test-only',generation=1,targetFingerprint=self.fingerprint())
            @staticmethod
            def advertised_capabilities(target):return ['app.launch','app.foreground','app.process','app.install','app.upgrade']
            def fingerprint(self):return hashlib.sha256(json.dumps(test.target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            def target(self,selector):return test.target
            def state_path(self,selector):return test.root/'session.json'
            def read_session(self,selector):return deepcopy(self._state)
            def save_session(self,selector,state):self._state=deepcopy(state)
            def ensure_session(self,selector):
                test.sessions+=1;return self.client,'test-only',deepcopy(self._state)
            def describe(self,selector):return {'adapter':self.adapter_id,'executionIdentity':{'untrusted':True}}
            def launch_ios_test_build(self,selector,client,session,state,target,scene_url=None,*,reactivate=False):
                if state.get('iosE2ELaunchCompleted') is not True:
                    test.assertEqual('preparing',self._binding_store(selector).read()['phase'])
                    test.launches+=1
                    test.process=dict(bundleId=test.native.bundle['bundleId'],pid=42,foreground=True)
                    if test.launches>1:
                        earlier=test.native.mutate
                        def renewed(v):
                            if earlier:earlier(v)
                            v.update(instance='e'*32)
                        test.native.mutate=renewed
                elif reactivate:test.process['foreground']=True
                self.assert_ios_process_identity(selector,client,session,state,target)
                state.update(iosE2ELaunchCompleted=True,iosE2ESceneUrl='test-only');self.save_session(selector,state)
            def invoke(self,selector,operation,values):
                client,session,state=self.ensure_session(selector)
                if operation=='app.launch':
                    self.launch_ios_test_build(selector,client,session,state,test.target,reactivate=True);result={'launched':True}
                elif operation=='app.foreground':result={'foreground':test.process is not None and test.process['foreground']}
                else:result={'performed':True}
                if test.after_operation:test.after_operation()
                return result
            def cleanup(self,selector):
                if test.cleanup_failure:raise RuntimeError('synthetic failed native teardown')
                if not test.cleanup_ignored:test.process=None;self._state=None
                return {'cleaned':True}
        self.Base=Base
        def preflight(_args):self.preflights+=1;return deepcopy(self.summary)
        for boundary in (patch.object(binding,'candidate_preflight',side_effect=preflight),
            patch('ios.adapters.feature_observation.post_request',side_effect=post),
            patch.object(IOSNativeMixin,'wait_first_ios_probe',return_value=None)):
            boundary.start();self.addCleanup(boundary.stop)
        self.adapter=binding.create_adapter(self.args,Base)

    def test_canonical_subclass_emits_identity_only_after_measured_bytes_and_clean_sources(self):
        self.assertIsInstance(self.adapter,self.Base)
        result=self.adapter.describe('test-only')
        self.assertEqual('e'*64,result['executionIdentity']['artifactSha256'])
        self.assertTrue(result['executionIdentity']['installedCandidateVerified'])
        self.assertEqual(1,self.launches);self.assertGreaterEqual(self.preflights,3)
        self.assertEqual('bound',self.adapter._binding_store('test-only').read()['phase'])
        actions=[c['action'] for c in self.native.commands]
        self.assertEqual(['ios-bundle-observe','ios-bundle-observe'],actions)
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))
        self.assertNotIn('app.install',self.adapter.advertised_capabilities(self.target))

    def test_native_reply_factory_retains_actual_installed_candidate_gate_without_scripts_profile(self):
        self.adapter.describe('test-only');self.assertNotIn('normalScripts',self.target)
        reader=self.adapter._navigation_replies('test-only')
        before=len(self.commands)
        self.artifact.write_bytes(b'changed original artifact boundary')
        with self.assertRaises(RuntimeError):reader.read('a'*32)
        self.assertEqual(before,len(self.commands))

    def test_restart_factories_preserve_candidate_gate_before_any_session_or_private_owner_io(self):
        self.artifact.write_bytes(b'changed original artifact boundary')
        for method in ('_script_missing_manager', '_script_restart_prepare', '_script_restart_adopt', '_script_restart_handoff',
                       '_script_restart_inputs', '_script_restart_source', '_script_restart', '_script_restart_stopped'):
            with self.subTest(method=method), self.assertRaises(ValueError):
                getattr(self.adapter, method)('test-only')
        self.assertEqual(0, self.sessions); self.assertEqual([], self.commands)
        self.assertFalse((self.root / 'normal-script-restart.json').exists())

    def restart_input_origin(self):
        self.target['serverUrl'] = 'http://controlled.invalid:4723'
        self.adapter._state['targetFingerprint'] = self.adapter.fingerprint()
        self.adapter.describe('test-only')
        origin = dict(scope='NATIVE_UI_COMPONENT_ONLY', processIdentity='42', sessionId='component-scope',
            generation=self.adapter._state['generation'], targetFingerprint=self.adapter.fingerprint())
        native = self.adapter._native_source_scope('test-only').native_observer()
        self.adapter._script_restart_inputs('test-only').capture(origin, native)

    def test_restart_stopped_query_requires_original_retired_source_and_never_creates_or_launches_a_session(self):
        self.restart_input_origin(); self.adapter.invoke('test-only', 'app.stop', {})
        before = self.sessions; launches = self.launches
        with patch.object(ios_backend, 'WebDriver', return_value=self.adapter.client):
            self.assertEqual({'running': False, 'identity': None}, self.adapter._script_restart_stopped('test-only'))
            for changed in ({'available': False}, {'cleanupPending': True}, {'instance': 'e' * 32}):
                original = deepcopy(self.source); self.source.update(changed)
                with self.subTest(changed=changed), self.assertRaises((ValueError, RuntimeError)):
                    self.adapter._script_restart_stopped('test-only')
                self.source = original
        self.assertEqual(before, self.sessions); self.assertEqual(launches, self.launches)
        self.assertEqual('retired', self.adapter._binding_store('test-only').read()['phase'])

    def test_restart_stopped_query_can_finish_uncertain_retirement_only_after_current_source_proves_absence(self):
        self.restart_input_origin(); self.ignored_stop = True
        with self.assertRaises(RuntimeError): self.adapter.invoke('test-only', 'app.stop', {})
        self.assertEqual('retiring', self.adapter._binding_store('test-only').read()['phase'])
        stops = sum(operation == 'mobile: terminateApp' for operation, _values in self.commands)
        with patch.object(ios_backend, 'WebDriver', return_value=self.adapter.client):
            with self.assertRaises(ValueError): self.adapter._script_restart_stopped('test-only')
            self.assertEqual('retiring', self.adapter._binding_store('test-only').read()['phase'])
            self.process = None  # Original synthetic OS observation finally changes.
            self.assertEqual({'running': False, 'identity': None}, self.adapter._script_restart_stopped('test-only'))
        self.assertEqual('retired', self.adapter._binding_store('test-only').read()['phase'])
        self.assertEqual(stops, sum(operation == 'mobile: terminateApp' for operation, _values in self.commands))
        self.assertEqual(1, self.launches)

    def test_full_candidate_recheck_after_original_operation_blocks_changed_evidence(self):
        self.adapter.describe('test-only')
        self.after_operation=lambda:self.summary.update(changedEvidence=True)
        with self.assertRaises(ValueError):self.adapter.invoke('test-only','app.foreground',{})

    def test_artifact_replacement_addition_or_restoration_is_detected_before_ui(self):
        original=self.artifact.read_bytes()
        self.artifact.write_bytes(b'changed');self.artifact.write_bytes(original)
        with self.assertRaises(ValueError):self.adapter.describe('test-only')
        self.assertEqual(0,self.sessions)
        lease=ArtifactLease(self.artifacts);(self.artifacts/'extra').write_text('new')
        with self.assertRaises(ValueError):lease.guard()

    def test_missing_plugin_or_foreign_installed_bytes_never_emits_identity(self):
        for fault in ('plugin','bytes'):
            if fault=='plugin':self.source['available']=False
            else:self.source['available']=True;self.native.mutate=lambda v:v.update(bundle=dict(v['bundle'],bundleSha256='f'*64))
            with self.assertRaises((ValueError,RuntimeError)):self.adapter.describe('test-only')
            owned=self.adapter._binding_store('test-only').read()
            if fault=='plugin':self.assertIsNone(owned)
            else:self.assertEqual('preparing',owned['phase'])
            self.adapter.cleanup('test-only')
            # A fresh private session fixture after independent teardown.
            self.adapter=binding.create_adapter(self.args,self.Base)

    def test_profile_that_could_install_is_rejected_before_session_or_launch(self):
        self.target.update(artifactMode='signed-ipa',_artifactMode='signed-ipa')
        with self.assertRaises(ValueError):self.adapter.describe('test-only')
        self.assertEqual((0,0),(self.sessions,self.launches))
        for operation in ('app.install','app.upgrade'):
            with self.assertRaises(ValueError):self.adapter.invoke('test-only',operation,{})
        self.assertEqual(0,self.sessions)

    def test_background_query_resume_and_stopped_process_are_independently_observed(self):
        self.adapter.describe('test-only')
        self.assertEqual({'backgrounded':True},self.adapter.invoke('test-only','lifecycle.background',{}))
        self.assertEqual({'foreground':False},self.adapter.invoke('test-only','app.foreground',{}))
        self.assertEqual({'launched':True},self.adapter.invoke('test-only','app.launch',{}))
        self.assertEqual(1,self.launches)
        self.assertEqual({'stopped':True},self.adapter.invoke('test-only','app.stop',{}))
        self.assertEqual('retired',self.adapter._binding_store('test-only').read()['phase'])
        self.assertEqual({'running':False,'identity':None},self.adapter.invoke('test-only','app.process',{}))
        self.assertEqual({'launched':True},self.adapter.invoke('test-only','app.launch',{}))
        self.assertEqual(2,self.launches)

    def test_stop_ack_without_absence_retains_retiring_intent_and_refuses_relaunch(self):
        self.adapter.describe('test-only');self.ignored_stop=True
        with self.assertRaises(RuntimeError):self.adapter.invoke('test-only','app.stop',{})
        self.assertEqual('retiring',self.adapter._binding_store('test-only').read()['phase'])
        with self.assertRaises(ValueError):self.adapter.invoke('test-only','app.launch',{})
        self.assertEqual(1,self.launches)

    def test_native_crash_retires_actual_pid_before_restart(self):
        self.adapter.describe('test-only')
        self.assertEqual({'crashed':True},self.adapter.invoke('test-only','app.crash',{'mode':'abort'}))
        self.assertEqual('retired',self.adapter._binding_store('test-only').read()['phase'])
        self.assertIsNone(self.process)

    def test_session_or_pid_replacement_never_silently_adopts_a_foreign_process(self):
        self.adapter.describe('test-only');self.process['pid']=43
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.describe('test-only')
        self.process['pid']=42;self.adapter._state['generation']+=1
        with self.assertRaises(ValueError):self.adapter.describe('test-only')
        self.assertEqual(1,self.launches)
        self.adapter._state=None;before=self.sessions
        with self.assertRaises(ValueError):self.adapter.describe('test-only')
        self.assertEqual(before,self.sessions)

    def test_cleanup_uses_original_teardown_after_candidate_loss_and_retains_failed_ownership(self):
        self.adapter.describe('test-only');self.artifact.unlink();self.args.action='cleanup'
        cleanup=binding.create_adapter(self.args,self.Base)
        self.cleanup_failure=True
        with self.assertRaises(RuntimeError):cleanup.cleanup('test-only')
        self.assertIsNotNone(cleanup._binding_store('test-only').read())
        self.cleanup_failure=False;self.cleanup_ignored=True
        with self.assertRaises(ValueError):cleanup.cleanup('test-only')
        self.assertIsNotNone(cleanup._binding_store('test-only').read())
        self.cleanup_ignored=False
        self.assertEqual({'cleaned':True},cleanup.cleanup('test-only'))
        self.assertIsNone(cleanup._binding_store('test-only').read())

    def test_lease_rejects_symlink_nonordinary_or_nonabsolute_input(self):
        linked=self.artifacts/'link';linked.symlink_to(self.artifact)
        with self.assertRaises(ValueError):ArtifactLease(self.artifacts)
        with self.assertRaises(ValueError):ArtifactLease(Path('relative'))


if __name__=='__main__':unittest.main()
