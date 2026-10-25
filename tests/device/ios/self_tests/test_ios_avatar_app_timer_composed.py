"""One actual whole-owner wearable recipe under the source2 timer grammar.

OAuth HTTPS, normal inputs, original JS, peer/source owners and PNGs execute;
native/Qt/renderer boundaries remain explicit models. This is not terminal end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.contract import VERSION
from ios.self_tests import test_ios_avatar_active_composed as active
from ios.self_tests.avatar_strong_app_domain import StrongAvatarAppDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from self_tests import test_account_provider as tls


class AvatarAppTimerComposedTests(unittest.TestCase):
    domain_type=StrongAvatarAppDomain
    prepare=active.AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def test_actual_wearable_recipe_and_both_original_observers_accept_avatar_app_timer(self):
        d=self.prepare();p=d.owners['primary'];call=dict(contractVersion=VERSION,runId=RUN)
        for owner in d.owners.values():owner.observe(dict(call,afterSequence=0))
        ticket='e'*32;inputs=dict(resource='gltf-bundle/main.gltf');d.client.activate(ticket,'wearable-add',inputs)
        action=dict(call,ticket=ticket,fixtureUrl=p.phase.fixture_url,verb='wearable-add',inputs=inputs)
        self.assertEqual(dict(performed=True),p.act(action))
        for owner in d.owners.values():
            value=owner.observe(dict(call,afterSequence=0));self.assertTrue(value['state']['wearable'])
        actual=d.scenes['primary'].f.sources['scripts-last'];worker=actual['source']['workers'][0]
        self.assertTrue(worker['avatar']['events']);self.assertTrue(worker['uiWork']['timers'])
        self.assertTrue(any(any(row['url'].endswith('/system/avatarapp.js') for row in caller['callerModules'])
            for caller in worker['avatar']['callerStacks']))


if __name__=='__main__':unittest.main()
