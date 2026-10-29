"""Real private configuration/canonical binding; no complete Avatar admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION
from ios.adapters import feature_configuration
from ios.self_tests.avatar_canonical_frontdoor_fixture import AvatarCanonicalFrontdoor
from ios.self_tests.avatar_prepare_fixture import RUN
from self_tests import test_account_provider as tls


class AvatarCanonicalFrontdoorBirthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()

    def test_actual_canonical_target_scope_and_Installed_binding_use_declared_before_birth_mode(self):
        f=AvatarCanonicalFrontdoor(self);d=f.domain
        for role in ('primary','actor'):
            native=d.natives[role];original=d.installed[role].store.read()
            self.assertEqual('personal-team-preinstalled',native.target['artifactMode'])
            self.assertEqual(native.fingerprint(),native.state['targetFingerprint'])
            self.assertEqual(native.fingerprint(),original['scope']['targetFingerprint'])
            target=f.adapter._target(role);state=f.adapter.read_session(role)
            scope=f.adapter._scope(role,state['sessionId'],state,target);self.assertEqual(original['scope'],scope)
            actual=f.adapter._binding(role,native,state['sessionId'],state,target)
            self.assertEqual(original,actual.record());claim=actual.verify()
            self.assertEqual(dict(schemaVersion=1,sourceRevision=scope['sourceRevision'],artifactSha256=scope['artifactSha256'],installedCandidateVerified=True),claim)
            updated=d.installed[role].store.read()
            self.assertEqual({k:v for k,v in original.items() if k!='observation'},{k:v for k,v in updated.items() if k!='observation'})
            self.assertGreater(updated['observation']['sequence'],original['observation']['sequence'])
            self.assertNotEqual(updated['observation']['commandId'],original['observation']['commandId'])
        self.assertTrue(any(operation=='mobile: overteProcessSourceInfo' for _role,operation,_values in f.operations))
        self.assertTrue(all(not n.input_log and not n.lifecycle_inputs for n in d.natives.values()))
        self.assertTrue(all(owner.store.read() is None for owner in d.owners.values()))

    def test_real_private_configs1_to8_remain_closed_before_any_Avatar_flow_or_new_native_query(self):
        f=AvatarCanonicalFrontdoor(self);d=f.domain;before=f.snapshot_effects()
        monitor=sys.monitoring;tool=next(i for i in range(6) if monitor.get_tool(i) is None)
        monitor.use_tool_id(tool,'avatar-real-closed-admission');seen=[];code=feature_configuration.capabilities.__code__
        def call(actual,_offset):seen.append(actual)
        monitor.register_callback(tool,monitor.events.PY_START,call);monitor.set_local_events(tool,code,monitor.events.PY_START)
        try:
            for version in range(1,9):
                with self.subTest(version=version):
                    value=f.configuration(version);f.set_configuration(value);seen.clear()
                    with self.assertRaises(NativeUIError):f.adapter.invoke('primary','feature.avatar-people.observe',dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
                    self.assertEqual([code] if version>=5 else [],seen)
                    self.assertEqual(before,f.snapshot_effects())
                    self.assertTrue(all(owner.store.read() is None for owner in d.owners.values()))
                    self.assertEqual(value,PrivateFeatureState(f.config_store.path).read())
        finally:
            monitor.set_local_events(tool,code,0);monitor.register_callback(tool,monitor.events.PY_START,None);monitor.free_tool_id(tool)
