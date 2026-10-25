"""Composed preparation and Avatar actions; explicit native/Qt model seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from feature_journeys.contract import VERSION
from ios.self_tests.avatar_active_fixture import ActiveDomain,RUN,TICKET
from self_tests import test_account_provider as tls


class AvatarActiveComposedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()
    domain_type=ActiveDomain
    def prepare(self):
        d=self.domain_type(self);primary,actor=d.owners['primary'],d.owners['actor']
        with actor.held():actor.initialize();actor.login()
        sleep=primary.sleep;started=[]
        def schedule(seconds):
            if not started and primary.state is not None and primary.state['initial'] is not None:started.append(True);actor.prepare()
            sleep(seconds)
        primary.sleep=schedule;primary.prepare();primary.sleep=sleep;return d
    def test_actual_url_scale_favorite_and_recovery_use_same_whole_source_originals(self):
        d=self.prepare();owner=d.owners['primary'];name='e2e-'+RUN
        cases=[('avatar-url',dict(resource='avatar-a.fst')),('avatar-bookmark-save',dict(name=name)),('avatar-scale',dict(value=1.5)),
            ('wearable-add',dict(resource='gltf-bundle/main.gltf')),('avatar-url',dict(resource='missing.fst')),('avatar-bookmark-choose',dict(name=name)),('avatar-restore',{}),('avatar-bookmark-delete',dict(name=name))]
        for index,(verb,inputs) in enumerate(cases,1):
            ticket=f'{index:032x}';d.client.activate(ticket,verb,inputs)
            call=dict(contractVersion=VERSION,runId=RUN,ticket=ticket,fixtureUrl=owner.phase.fixture_url,verb=verb,inputs=inputs)
            self.assertEqual({'performed':True},owner.act(call));before=len(d.widgets['primary'].requests)
            self.assertEqual({'performed':True},owner.act(call));self.assertEqual(before,len(d.widgets['primary'].requests))
        self.assertEqual('',d.widgets['primary'].name);self.assertEqual(1.,d.widgets['primary'].scale)
        self.assertTrue(d.input_packets['primary']['events']);self.assertEqual(1,d.natives['primary'].input_log.count('login.submit'))


if __name__=='__main__':unittest.main()
