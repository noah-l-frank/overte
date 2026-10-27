"""Passive owned-domain identity/policy source; no service or policy mutation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from self_tests.snapshot_domain_fixture import PolicyFixture,RUN,DOMAIN


class SnapshotDomainPolicyTests(unittest.TestCase):
    def test_passive_opt_in_does_not_enable_permission_control_or_other_sources(self):
        from fixture.domain import parse_args
        for extra,enabled in (([],False),(['--feature-snapshot-domain-policy'],True)):
            with patch('sys.argv',['domain.py','--check']+extra):args=parse_args()
            self.assertEqual(enabled,args.feature_snapshot_domain_policy);self.assertFalse(args.feature_create_rez);self.assertFalse(args.feature_assets_backend);self.assertFalse(args.feature_chat_receiver)
    def test_actual_guarded_id_and_settings_derive_open_hifi_acl_without_private_settings(self):
        f=PolicyFixture(self);reader=f.client()
        for anonymous,logged_in,expected in ((True,True,'open'),(False,True,'hifi'),(False,False,'acl')):
            f.policy(anonymous,logged_in);record=reader.read(RUN,uuid.uuid4().hex);packet=record['packet'];self.assertEqual(expected,packet['restriction']);self.assertEqual(DOMAIN,packet['domainId'])
            self.assertTrue(packet['controlledFixtureProjectionOnly']);self.assertTrue(packet['externalRegistrationRequired']);self.assertNotIn('NEVER-RETAIN',json.dumps(packet));self.assertNotIn(f.config['token'],json.dumps(record['configuration']))
        self.assertEqual(['/id','/settings.json']*3,f.calls)
    def test_wrong_actual_process_after_id_or_settings_blocks_before_any_policy_packet(self):
        for path in ('/id','/settings.json'):
            with self.subTest(path=path):
                f=PolicyFixture(self);f.drift=path
                with self.assertRaises(NativeUIError):f.reader.read(RUN,uuid.uuid4().hex)
                self.assertEqual({},f.reader.queries)
    def test_original_nonce_keeps_original_policy_and_late_cached_source_is_not_fresh(self):
        f=PolicyFixture(self);reader=f.client();nonce=uuid.uuid4().hex;old=reader.read(RUN,nonce)['packet'];f.policy(False,False)
        self.assertEqual(old,f.reader.read(RUN,nonce));self.assertEqual(2,len(f.calls));f.epoch+=1601;f.mono+=1.601
        with self.assertRaises(NativeUIError):reader.read(RUN,nonce)
        self.assertEqual(old,f.reader.read(RUN,nonce));self.assertEqual('acl',reader.read(RUN,uuid.uuid4().hex)['packet']['restriction'])
    def test_missing_or_duplicate_effective_standard_row_is_unavailable_not_false_policy(self):
        for fault in ('missing','duplicate','not-bool'):
            f=PolicyFixture(self);rows=f.settings['values']['security']['standard_permissions']
            if fault=='missing':rows.pop()
            elif fault=='duplicate':rows[-1]=deepcopy(rows[0])
            else:rows[0]['id_can_connect']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):f.reader.read(RUN,uuid.uuid4().hex)
    def test_passive_wrong_credential_cannot_query_domain_or_use_control_authority(self):
        f=PolicyFixture(self);config=deepcopy(f.config);config['token']='x'*43
        from feature_journeys.snapshot_domain_client import SnapshotDomainClient
        reader=SnapshotDomainClient(config,epoch_ms=lambda:f.epoch,monotonic=lambda:f.mono)
        with self.assertRaises(NativeUIError):reader.read(RUN,uuid.uuid4().hex)
        self.assertEqual([],f.calls)


if __name__=='__main__':unittest.main()
