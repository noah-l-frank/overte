"""Read-only fixture attachment with actual HTTP/phase journals, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
import unittest

from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_fixture import NavigationFixtureReader,NavigationPhasePending,NavigationRunRetired
from self_tests import test_navigation_scene as scene_tests

TICKET=scene_tests.TICKET


class NavigationFixtureTests(unittest.TestCase):
    def setUp(self):
        self.harness=scene_tests.NavigationSceneTests();self.harness.setUp();self.addCleanup(self.harness.doCleanups)
        self.run=self.harness.open();self.token=secrets.token_hex(32);self.harness.server.adapter_token=self.token
        self.client=AdapterFixtureClient(self.harness.client.url,self.token)
    def reader(self):
        value=NavigationFixtureReader(self.client,self.run);value.attach();return value

    def test_actual_readonly_role_attaches_existing_run_without_runner_token_or_peer_facts(self):
        reader=self.reader();sample=reader.read();self.assertTrue(self.client._adapter_admitted)
        self.assertEqual(self.run,sample['runId']);self.assertEqual(TICKET,sample['ticket']);self.assertEqual('baseline',sample['verb'])
        self.assertEqual(digest(sample['originals']),sample['originalsSha256'])
        self.assertEqual({'phaseBefore','phaseAfter','navigation','scene'},set(sample['originals']))
        self.assertNotIn('entries',sample);self.assertNotIn('passed',sample);self.assertNotIn('processId',sample)
        self.assertIsNone(getattr(self.client,'run',None));self.assertEqual(1,len(self.harness.server.journal.runs))
        with self.assertRaises(NativeUIError):self.client.request('/runs/'+self.run+'/active',
            dict(ticket='c'*32,verb='open',inputs={}))
        self.assertEqual([TICKET],[row['ticket'] for row in self.harness.server.journal.phase(self.run,'f'*32)['activations']])

    def test_original_scene_receipts_continue_immutably_across_fresh_passive_reads(self):
        reader=self.reader();self.harness.get('/navigation/scene.json');first=reader.read();again=reader.read()
        self.assertEqual(first['originals']['scene']['responses'],again['originals']['scene']['responses'])
        self.assertNotEqual(first['originals']['phaseBefore']['requestId'],again['originals']['phaseBefore']['requestId'])
        self.assertGreater(again['originals']['phaseBefore']['sequence'],first['originals']['phaseAfter']['sequence'])
        self.assertEqual(first['originals']['scene']['responses'][0],again['originals']['scene']['responses'][0])

    def test_integer_provider_quantization_preserves_distinct_original_fractional_phase_clock(self):
        reader=self.reader();original=self.client.request;floor=[None]
        # Model the documented integer/fractional precision boundary while
        # keeping actual HTTP phase nonces/histories and separate source clocks.
        def request(path,*args,**kwargs):
            value=deepcopy(original(path,*args,**kwargs))
            if path.endswith('/phase') and floor[0] is None:
                floor[0]=int(value['capturedEpochMs']);value['capturedEpochMs']=floor[0]+.9
            elif path.endswith('/navigation') or path.endswith('/navigation-scene'):value['capturedEpochMs']=floor[0]
            return value
        self.client.request=request;sample=reader.read();originals=sample['originals']
        self.assertGreater(originals['phaseBefore']['capturedEpochMs'],originals['navigation']['capturedEpochMs'])
        self.assertEqual(floor[0],originals['navigation']['capturedEpochMs'])
        self.assertEqual(floor[0]+.9,originals['phaseBefore']['capturedEpochMs'])

    def test_phase_crossing_retains_originals_and_never_resends_a_product_input(self):
        reader=self.reader();first=reader.read();original=self.client.request;calls=[];crossed=False
        def request(path,*args,**kwargs):
            nonlocal crossed
            value=original(path,*args,**kwargs);calls.append(path)
            if path.endswith('/navigation') and not crossed:
                crossed=True;self.harness.client.activate('c'*32,'open',{})
            return value
        self.client.request=request
        with self.assertRaises(NavigationPhasePending):reader.read()
        self.assertEqual(first,reader.last)
        self.assertTrue(all(path.startswith('/runs/') for path in calls));self.assertEqual(4,len(calls))
        current=reader.read();self.assertEqual('c'*32,current['ticket']);self.assertEqual('open',current['verb'])
        self.assertEqual(2,len(current['originals']['phaseAfter']['activations']))

    def test_original_run_retirement_is_distinct_from_an_empty_successful_phase(self):
        reader=self.reader();reader.read();self.harness.client.close()
        with self.assertRaises(NavigationRunRetired) as caught:reader.read()
        self.assertFalse(caught.exception.status['active']);self.assertIsNotNone(caught.exception.status['retiredEpochMs'])
        self.assertFalse(reader.status()['active']);self.assertFalse(reader.scene()['active'])
        with self.assertRaises(NavigationRunRetired):reader.read()

    def test_foreign_run_area_and_changed_origin_fail_before_transport(self):
        for field,new in [('run','f'*32),('area','graphics'),('url','http://foreign.invalid/feature-fixture/v1')]:
            client=AdapterFixtureClient(self.harness.client.url,self.token);reader=NavigationFixtureReader(client,self.run)
            calls=[];client.request=lambda *args,**kwargs:calls.append(args);setattr(client,field,new)
            with self.subTest(field=field),self.assertRaises(NativeUIError):reader.attach()
            self.assertEqual([],calls)

    def test_disabled_marker_profile_is_unavailable_instead_of_advertised_as_complete(self):
        reader=self.reader();self.harness.provider.scene_profile=None
        with self.assertRaises(ValueError):reader.read()
        self.assertIsNone(reader.last)

    def test_changed_source_birth_configuration_or_original_history_is_not_reassigned(self):
        for fault in ('instance','inputs','receipt'):
            reader=self.reader();self.harness.get('/navigation/scene.json');first=reader.read();original=self.client.request
            def request(path,*args,**kwargs):
                value=deepcopy(original(path,*args,**kwargs))
                if path.endswith('/navigation'):
                    if fault=='instance':value['instance']='f'*32
                    elif fault=='inputs':value['inputs']['sourceRevision']='f'*40
                if path.endswith('/navigation-scene') and fault=='receipt':value['responses'][0]['sha256']='f'*64
                return value
            self.client.request=request
            with self.subTest(fault=fault),self.assertRaises(ValueError):reader.read()
            self.assertEqual(first,reader.last);self.client.request=original

    def test_runner_or_actor_credentials_cannot_be_misrepresented_as_adapter_only_access(self):
        wrong=AdapterFixtureClient(self.harness.client.url,self.harness.client.token)
        with self.assertRaises(ValueError):NavigationFixtureReader(wrong,self.run).attach()
        self.assertFalse(wrong._adapter_admitted)


if __name__=='__main__':unittest.main()
