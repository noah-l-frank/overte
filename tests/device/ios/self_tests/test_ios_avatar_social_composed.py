"""Actual Node two-party consent, OAuth HTTPS and whole normal action owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.contract import VERSION
from ios.self_tests.avatar_social_domain import SocialDomain,RUN
from ios.self_tests.test_ios_avatar_active_composed import AvatarActiveComposedTests
from ios.adapters import avatar_social
from ios.adapters.avatar_code import pins
from self_tests import test_account_provider as tls


class AvatarSocialComposedTests(unittest.TestCase):
    domain_type=SocialDomain
    prepare=AvatarActiveComposedTests.prepare
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    def test_normal_request_cancel_decline_accept_and_delete_preserve_two_actual_protocols_and_https(self):
        d=self.prepare();p,a=d.owners['primary'],d.owners['actor'];ticket=16
        def action(verb):
            nonlocal ticket
            ticket+=1;identity=f'{ticket:032x}';inputs=dict(peer='owned-peer') if verb in ('connection-request','connection-remove') else {};d.client.activate(identity,verb,inputs)
            call=dict(contractVersion=VERSION,runId=RUN,ticket=identity,fixtureUrl=p.phase.fixture_url,verb=verb,inputs=inputs)
            if verb in ('peer-accept','peer-reject'):
                a.consent(a.phase.read())
            self.assertEqual({'performed':True},p.act(call));return identity
        def actor_surface():
            from adapters.normal_feature_state import PrivateFeatureState
            from adapters.normal_ui import NativeUI
            from ios.adapters.avatar_surface import IOSAvatarSurface
            with a.held():
                source=a.own_source();actual=a.runtime._sources(a.selector)
                sdk=NativeUI(actual['client'],actual['session'],actual['check'],monotonic=lambda:d.clock[0],sleep=d.sleep)
                owner=IOSAvatarSurface(PrivateFeatureState(source.store.path.with_name('ios-avatar-actor-actor-surface.json')),
                    source,sdk,observer_role='actor',subject_role='actor')
                return owner.prepare(a.phase.read()['ticket'])
        action('connection-request');actor_surface();action('connection-cancel');actor_surface()
        self.assertEqual('idle',d.views['actor']['phase'])
        action('connection-request');action('peer-reject')
        self.assertFalse(d.social.snapshot(RUN)['connected'])
        action('connection-request');action('peer-accept')
        self.assertTrue(d.social.snapshot(RUN)['connected']);self.assertTrue(d.tables['primary']);self.assertTrue(d.tables['actor'])
        action('connection-remove');d.directory('actor')
        self.assertFalse(d.social.snapshot(RUN)['connected']);self.assertEqual([],d.tables['primary']);self.assertEqual([],d.tables['actor'])
        for role in ('primary','actor'):
            self.assertTrue(d.timer_events[role]);self.assertTrue(d.http_events[role]);self.assertEqual('idle',d.views[role]['phase'])
            self.assertEqual(1,d.natives[role].input_log.count('login.submit'))


if __name__=='__main__':unittest.main()
