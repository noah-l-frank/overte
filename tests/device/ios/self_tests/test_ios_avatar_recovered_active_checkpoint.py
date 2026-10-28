"""Recovered original preparation continues into actual active/checkpoint owners.

Native Qt/OS/SDK/renderer producers remain StrongDomain's declared models. Real
HTTPS, ordinary repository JS/input, immutable PNG/private files and original
Avatar decoders execute. This is not the complete cleanup/end or installed API.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from feature_journeys.contract import VERSION
from feature_journeys.scenarios import SCENARIOS
from ios.adapters.avatar_feature import AvatarFeaturePending
from ios.adapters import avatar_operation_clock
from ios.self_tests.avatar_strong_domain import StrongDomain,RUN
from ios.self_tests import test_ios_avatar_prepare_composed as preparation


class AvatarRecoveredActiveCheckpointTests(unittest.TestCase):
    retain_originals=True
    domain_type=StrongDomain
    domain=preparation.AvatarPrepareComposedTests.domain
    issued_original_pin=preparation.AvatarPrepareComposedTests.issued_original_pin
    recovered_public_preparation=preparation.AvatarPrepareComposedTests.recovered_public_preparation

    @classmethod
    def setUpClass(cls):preparation.AvatarPrepareComposedTests.setUpClass()
    @classmethod
    def tearDownClass(cls):preparation.AvatarPrepareComposedTests.tearDownClass()

    def preparation_unchanged(self,d,kept,initial):
        for role,owner in d.owners.items():
            with owner.held(paired=True):
                owner.load();saved=kept[role];event=owner.state['preparationClose']
                self.assertEqual(saved['event']['before'],event['before'])
                self.assertEqual(saved['event']['issuedIntent'],event['issuedIntent'])
                self.assertTrue(saved['issued']==owner.preparation_issued_original(),'Issued Close original changed')
                self.assertTrue(saved['before']==owner.preparation_source(event['before']),'Before-Close original changed')
                for path,pin in saved['pins'].values():
                    self.assertTrue(pin==self.issued_original_pin(path),'Immutable Close carrier changed')
                self.assertTrue(saved['loginPin']==self.issued_original_pin(saved['loginPath']),'Protected account original changed')
                self.assertTrue(initial[role]==owner.initial_original(),'Untouched initial frame/PNG original changed')
            self.assertEqual(1,d.natives[role].input_log.count('login.submit'))
            self.assertTrue(d.natives[role].account['loggedIn'])

    def observed_image(self,owner,public):
        with owner.held(paired=True):
            owner.load();observer=owner.components(owner.source_parts())['observer']
            row=observer.state['rows'][-1];record=observer.read_record(row)
            original=observer.validate_original(row)
            self.assertTrue(public==original['public'],'Public facts do not match their original decoder')
            sample=record['facts']['image'];frame,raw,measurement=observer.samples.archive(sample)
            self.assertIsNotNone(measurement);self.assertTrue(raw.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertEqual(sample['requestId'][4:],measurement['frameId'])
            self.assertEqual(owner.role=='actor',measurement['remote'])
            self.assertEqual(owner.state['sessions']['input']['sessions']['primary'],measurement['sessionId'])
            self.assertTrue(any(item['kind']=='image' and item['name']==observer.samples.read_record(sample)['owner']['name']
                for item in public['artifacts']))
            return dict(reference=deepcopy(row),image=deepcopy(sample),frameId=measurement['frameId'],
                pngSha256=hashlib.sha256(raw).hexdigest(),hostAfter=frame['clockJoin']['hostAfterMonotonic'])

    def test_both_lost_close_recoveries_continue_normal_scale_independent_images_publication_and_cleanup_checkpoint(self):
        d,kept=self.recovered_public_preparation();p,a=d.owners['primary'],d.owners['actor']
        initial={}
        for role,owner in d.owners.items():
            with owner.held(paired=True):owner.load();initial[role]=deepcopy(owner.initial_original())
        call=dict(contractVersion=VERSION,runId=RUN);baseline={};before_images={}
        for role,owner in d.owners.items():
            baseline[role]=owner.observe(dict(call,afterSequence=0))
            before_images[role]=self.observed_image(owner,baseline[role])
        self.assertEqual(baseline['primary']['state'],baseline['actor']['state'])
        self.preparation_unchanged(d,kept,initial)

        ticket='7'*32;inputs=dict(value=1.5);d.client.activate(ticket,'avatar-scale',inputs)
        journal_before=deepcopy(d.client.observe()['entries'])
        actor_inputs=list(d.widgets['actor'].requests)
        actor_observer=a.store.path.with_name('ios-avatar-actor-observer.json')
        observer_pin=self.issued_original_pin(actor_observer)
        with self.assertRaisesRegex(AvatarFeaturePending,'Primary input has not returned'):
            a.observe(dict(call,afterSequence=baseline['actor']['sequence']))
        self.assertEqual(journal_before,d.client.observe()['entries'])
        self.assertEqual(actor_inputs,d.widgets['actor'].requests)
        self.assertTrue(observer_pin==self.issued_original_pin(actor_observer),'Early Actor acquisition retained an outcome')

        action=dict(call,ticket=ticket,fixtureUrl=p.phase.fixture_url,verb='avatar-scale',inputs=inputs)
        self.assertEqual({'performed':True},p.act(action));self.assertEqual(1.5,d.widgets['primary'].scale)
        self.assertEqual(1.,d.widgets['actor'].scale)
        returned_inputs=len(d.widgets['primary'].requests)
        self.assertEqual({'performed':True},p.act(action))
        self.assertEqual(returned_inputs,len(d.widgets['primary'].requests))
        current={};images={}
        for role,owner in d.owners.items():
            current[role]=owner.observe(dict(call,afterSequence=baseline[role]['sequence']))
            images[role]=self.observed_image(owner,current[role])
            self.assertEqual(1.5,current[role]['state']['scale'])
            self.assertNotEqual(before_images[role]['frameId'],images[role]['frameId'])
            self.assertNotEqual(before_images[role]['pngSha256'],images[role]['pngSha256'])
            self.assertGreater(current[role]['sequence'],baseline[role]['sequence'])
        self.assertEqual(current['primary']['state'],current['actor']['state'])
        with a.held(paired=True):
            a.load();observer=a.components(a.source_parts())['observer'];publisher=observer.publisher()
            receipt=publisher.load(publisher.state['records'][-1])
            self.assertEqual('published',receipt['mode'])
            self.assertTrue(images['actor']['reference']==receipt['intent']['original'],'Actor published a substituted observation')
            self.assertEqual(ticket,receipt['entry']['ticket'])
            self.assertEqual(current['actor']['state'],receipt['entry']['facts'])
        self.preparation_unchanged(d,kept,initial)

        cleanup_ticket='8'*32;d.client.activate(cleanup_ticket,'cleanup',{})
        for owner in (p,a):
            owner.requested_cleanup_clock=avatar_operation_clock.begin(d.host(),d.clock[0])
            self.assertTrue(owner.restore_inputs(call,deepcopy(owner.requested_cleanup_clock)))
        self.assertEqual(1.,d.widgets['primary'].scale)
        for owner in (p,a):owner.cleanup_checkpoint()
        p.wait_actor_checkpoint()
        for owner in (p,a):owner.wait_peer_checkpoint()
        for owner in (p,a):
            with owner.held(paired=True):
                owner.load();self.assertEqual('cleaning',owner.state['phase'])
                event=next(row for row in owner.state['cleanup'] if row['kind']=='checkpoint')
                observer=owner.components(owner.source_parts())['observer']
                original=observer.validate_original(event['reference'])
                self.assertEqual(SCENARIOS['avatar-people']['baseline'],original['public']['state'])
                self.assertTrue(original['public']['resources'])
                self.assertTrue(any(row['kind']=='checkpoint-barrier' for row in owner.state['cleanup']))
                self.assertEqual(owner.role=='actor',event['published'])
                self.assertFalse(any(row['kind'] in ('scene','final','final-ready','ended') for row in owner.state['cleanup']))
        self.preparation_unchanged(d,kept,initial)
        # Both accounts/SDKs and all later Scene/Final/process retirement stay
        # owned. No complete capability or native execution follows.


if __name__=='__main__':unittest.main()
