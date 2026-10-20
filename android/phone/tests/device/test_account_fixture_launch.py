"""Existing Phone cold-launch path, synthetic SDK/ADB only; no device calls."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import shlex
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
import test_feature_adapters as bound
from overte_phone_account_fixture import origin,launch_command,EXTRA

FIXTURE='https://owned.invalid:10443/feature-fixture/v1'


class AccountFixtureLaunchTests(unittest.TestCase):
    def setUp(self):
        self.f=bound.FeatureAdapterTests('test_existing_input_scope_admits_normal_file_input_without_parent_session_repair')
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.target.update(selector=bound.SELECTOR,scene={'kind':'android-debug-e2e'},
            clientControl={'kind':'android-run-as-command','relativePath':self.f.adapter.ANDROID_CLIENT_COMMAND})
        self.f.target['capabilities']['appium:autoLaunch']=False
        self.f.adapter.read_session(bound.SELECTOR)['targetFingerprint']=self.f.adapter.snapshot_fingerprint(self.f.target)
        self.f.read_only_boundaries(forbid_normal_session=False)
        self.sent=[]
        def execute(arguments,*,target,timeout):
            self.assertEqual('test-only-native-target',target);self.assertEqual(5,timeout)
            self.sent.append(deepcopy(arguments));return 'synthetic shell input receipt only'
        for boundary in (patch.dict(os.environ,{'OVERTE_PHONE_ACCOUNT_FIXTURE':'1','OVERTE_E2E_FEATURE_FIXTURE_URL':FIXTURE}),
                         patch.object(self.f.fixture.adb,'execute',side_effect=execute,create=True)):
            boundary.start();self.addCleanup(boundary.stop)

    def launch(self):return self.f.adapter.start_android_e2e(self.f.native,'native-session',self.f.target)

    def test_exact_owned_https_origin_is_the_only_extra_in_one_existing_session_launch(self):
        self.f.native.running=False
        self.assertIsNone(self.launch());self.assertEqual(1,len(self.sent))
        self.assertEqual(['shell'],self.sent[0][:1])
        self.assertEqual(['am','start','-S','-n',bound.PACKAGE+'/org.overte.phone.E2eLauncherActivity',
            '--es',EXTRA,'https://owned.invalid:10443'],shlex.split(self.sent[0][1]))
        self.assertEqual([],self.f.native.lifecycle_inputs)
        # A launch receipt cannot establish process startup or an actual auth
        # endpoint. The later Authentication owner must measure both freshly.
        self.assertFalse(self.f.native.running)

    def test_default_off_keeps_the_existing_sdk_launcher_without_an_origin_extra(self):
        self.f.native.running=False
        self.f.native.on_launch=lambda:None
        with patch.dict(os.environ,{'OVERTE_PHONE_ACCOUNT_FIXTURE':'0'}):self.launch()
        self.assertEqual([],self.sent);self.assertEqual(['launch'],self.f.native.lifecycle_inputs)

    def test_existing_app_launch_operation_uses_this_same_hook_for_a_cold_process(self):
        self.f.native.running=False
        self.assertEqual({'launched':True},self.f.adapter.invoke(bound.SELECTOR,'app.launch',{}))
        self.assertEqual(1,len(self.sent));self.assertFalse(self.f.native.running)

    def test_unbound_non_debug_and_auto_launching_candidates_fail_before_shell_input(self):
        mutations=[lambda:self.f.target['capabilities'].update({'appium:autoLaunch':True}),
                   lambda:self.f.target.update(scene={'kind':'other'}),
                   lambda:setattr(self.f.adapter,'candidate',None)]
        target=deepcopy(self.f.target);candidate=self.f.adapter.candidate
        for mutate in mutations:
            self.f.target.clear();self.f.target.update(deepcopy(target));self.f.adapter.candidate=candidate;mutate()
            with self.subTest(mutation=mutate),self.assertRaises((RuntimeError,ValueError)):self.launch()
        self.assertEqual([],self.sent)

    def test_wrong_sdk_session_or_changed_installed_bytes_cannot_launch_another_target(self):
        with self.assertRaises((RuntimeError,ValueError)):
            self.f.adapter.start_android_e2e(self.f.native,'foreign-session',self.f.target)
        self.f.fixture.adb.digest='f'*64
        with self.assertRaises((RuntimeError,ValueError)):self.launch()
        self.assertEqual([],self.sent)

    def test_lost_launch_return_is_not_retried_by_the_hook(self):
        def lost(arguments,**_options):self.sent.append(arguments);raise RuntimeError('synthetic lost shell return')
        with patch.object(self.f.fixture.adb,'execute',side_effect=lost):
            with self.assertRaises(RuntimeError):self.launch()
        self.assertEqual(1,len(self.sent));self.assertEqual([],self.f.native.lifecycle_inputs)

    def test_changed_candidate_after_delivery_rejects_the_receipt(self):
        def replaced(arguments,**_options):self.sent.append(arguments);self.f.fixture.adb.digest='f'*64;return ''
        with patch.object(self.f.fixture.adb,'execute',side_effect=replaced):
            with self.assertRaises((ValueError,RuntimeError)):self.launch()
        self.assertEqual(1,len(self.sent))

    def test_plain_http_credentials_paths_query_fragment_bad_ports_and_shell_sources_are_rejected(self):
        for value in ('http://owned.invalid/feature-fixture/v1','https://u:p@owned.invalid/feature-fixture/v1',
            FIXTURE+'/',FIXTURE+'?secret=x',FIXTURE+'#x',FIXTURE+'?',
            'https://owned.invalid:0/feature-fixture/v1','https://owned.invalid:65536/feature-fixture/v1',
            'https://owned.invalid:/feature-fixture/v1','https://OWNED.invalid/feature-fixture/v1',
            'https://owned.invalid;echo-x/feature-fixture/v1','https://$(echo-x)/feature-fixture/v1',
            'https://%65vil.invalid/feature-fixture/v1','https://-bad.invalid/feature-fixture/v1',
            'https://333.1.2.3/feature-fixture/v1',FIXTURE+'\n'):
            with self.subTest(value=value),self.assertRaises((RuntimeError,ValueError)):origin(value)
        self.assertEqual([],self.sent)

    def test_ipv4_ipv6_and_dns_origins_remain_exact_canonical_shell_arguments(self):
        for value in ('https://127.0.0.1:10443','https://[::1]:10443','https://owned.invalid'):
            fixture=value+'/feature-fixture/v1'
            self.assertEqual(value,origin(fixture));self.assertEqual(value,shlex.split(launch_command(bound.PACKAGE,fixture))[-1])

    def test_invalid_opt_in_is_rejected_even_before_an_existing_process_is_activated(self):
        with patch.dict(os.environ,{'OVERTE_PHONE_ACCOUNT_FIXTURE':'yes'}):
            with self.assertRaises((RuntimeError,ValueError)):self.f.adapter.invoke(bound.SELECTOR,'app.launch',{})
        self.assertEqual([],self.sent);self.assertEqual([],self.f.native.lifecycle_inputs)


if __name__=='__main__':unittest.main()
