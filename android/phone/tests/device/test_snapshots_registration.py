"""Independent public Snapshot gates and owner-factory lifetime counterprobes.

SDK/process boundaries are synthetic. Factory spies prove routing/configuration
only, never product effects, immutable-retirement validity or cleanup success.
The full public journey supplies those independent original-source proofs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import test_account_fixture_launch
import test_feature_adapters as bound
from test_feature_dispatch import Boundary as PhaseBoundary
from adapters.normal_feature_state import PrivateFeatureState
from adapters.shared_appium.adapter import AppiumAdapter
from feature_journeys.scenarios import VERSION
from overte_phone_script_history import pack
from self_tests.test_phone_navigation import NativePhone

RUN='a'*32


class SnapshotsRegistrationTests(unittest.TestCase):
    def setUp(self):
        setup=test_account_fixture_launch.AccountFixtureLaunchTests();setup.setUp();self.addCleanup(setup.doCleanups)
        self.f=setup.f;self.adapter=self.f.adapter
        self.f.target['controls']={'normalNavigation':deepcopy(NativePhone().profile)}
        self.adapter.read_session(bound.SELECTOR)['targetFingerprint']=self.adapter.snapshot_fingerprint(self.f.target)
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-registration-audit-');self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.settings=self.root/'configuration.json';self.access=self.root/'adapter-access.json'
        self.config=dict(snapshotsFeatureVersion=1,artifactRoot=str(self.root),imageExtent=[1000,750],markerRoi=[20,20,180,60],
            imagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595]),
            fileImagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595]),
            domainId='12345678-1234-4234-8234-123456789abc',receiverApkSha256='e'*64)
        self.url='https://owned.invalid:10443/feature-fixture/v1'
        PrivateFeatureState(self.settings).write(self.config,None)
        PrivateFeatureState(self.access).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=self.url,adapterToken='d'*64),None)
        environment=dict(OVERTE_PHONE_FEATURE_SNAPSHOTS='1',OVERTE_PHONE_SNAPSHOTS_CONFIGURATION=str(self.settings),
            OVERTE_PHONE_NORMAL_SNAPSHOT='1',OVERTE_PHONE_ACCOUNT_FIXTURE='1',
            OVERTE_E2E_FEATURE_FIXTURE_URL=self.url,OVERTE_PHONE_FEATURE_FIXTURE_CONFIG=str(self.access))
        env=patch.dict(os.environ,environment);env.start();self.addCleanup(env.stop)

    def call(self):return dict(contractVersion=VERSION,runId=RUN)

    def owner(self):
        return dict(snapshotsFeatureVersion=1,runId=RUN,fixtureUrl=self.url+'/runs/'+RUN+'/',configuration=deepcopy(self.config),
            binding=self.adapter.normal_feature_runtime(bound.SELECTOR,read_only=True)[2],payload=pack([dict(originalSource='synthetic exact owner')]))

    def test_complete_public_triple_requires_explicit_bound_normal_account_and_tls_gates(self):
        capabilities=self.adapter.advertised_capabilities(self.f.target)
        self.assertEqual({'feature.snapshots.'+kind for kind in ('act','observe','cleanup')},
            {value for value in capabilities if value.startswith('feature.snapshots.')})
        for change in (dict(OVERTE_PHONE_NORMAL_SNAPSHOT='0'),dict(OVERTE_PHONE_ACCOUNT_FIXTURE='0'),
                dict(OVERTE_PHONE_SNAPSHOTS_CONFIGURATION=''),dict(OVERTE_PHONE_FEATURE_FIXTURE_CONFIG='')):
            with self.subTest(change=change),patch.dict(os.environ,change),self.assertRaises((ValueError,RuntimeError)):
                self.adapter.advertised_capabilities(self.f.target)
        with patch.object(self.adapter,'candidate',None),self.assertRaises((ValueError,RuntimeError)):
            self.adapter.advertised_capabilities(self.f.target)
        client=SimpleNamespace(url=self.url.replace('https:','http:'))
        with patch.object(self.adapter,'account_fixture_configuration',return_value={}),patch.object(self.adapter,'_feature_fixture_client',return_value=client),self.assertRaisesRegex(ValueError,'TLS'):
            self.adapter.advertised_capabilities(self.f.target)

    def test_default_off_invalid_enable_and_unknown_arguments_do_not_construct_owner(self):
        for flag in ('0','','true'):
            with self.subTest(flag=flag),patch.dict(os.environ,{'OVERTE_PHONE_FEATURE_SNAPSHOTS':flag}),patch.object(self.adapter,'_snapshots_feature') as factory:
                if flag=='0':
                    self.assertFalse(any(item.startswith('feature.snapshots.') for item in self.adapter.advertised_capabilities(self.f.target)))
                with self.assertRaises((ValueError,RuntimeError)):self.adapter.invoke(bound.SELECTOR,'feature.snapshots.cleanup',self.call())
                factory.assert_not_called()
        with patch.object(self.adapter,'_snapshots_feature') as factory:
            with self.assertRaises((ValueError,RuntimeError)):
                self.adapter.invoke(bound.SELECTOR,'feature.snapshots.cleanup',self.call()|dict(expectedRetired=True))
            factory.assert_not_called()

    def test_original_phase_precedes_owner_construction_and_selects_exact_finalizer(self):
        for active in (True,False):
            phase=PhaseBoundary('snapshots',active);phase.client.url=self.url;events=[];request=phase.client.request
            def read(path,**kwargs):events.append('original-phase');return request(path,**kwargs)
            phase.client.request=read
            def factory(_selector,run,*,retirement=False):
                self.assertEqual(RUN,run);self.assertEqual(['original-phase'],events)
                events.append(('owner',retirement))
                return SimpleNamespace(cleanup=lambda values:events.append('cleanup') or {'performed':True},
                    finalize=lambda:events.append('finalize') or {'performed':True})
            with self.subTest(active=active),patch.object(self.adapter,'_feature_fixture_client',return_value=phase.client),patch.object(self.adapter,'_snapshots_feature',side_effect=factory):
                self.assertEqual({'performed':True},self.adapter.invoke(bound.SELECTOR,'feature.snapshots.cleanup',self.call()))
            self.assertEqual(['original-phase',('owner',not active),'cleanup' if active else 'finalize'],events)

    def test_foreign_stale_or_missing_original_phase_never_constructs_owner(self):
        for fault in ('nonce','run','area','stale','closure','expected'):
            phase=PhaseBoundary('snapshots',False);phase.client.url=self.url
            def mutate(value):
                if fault=='nonce':value['requestId']='f'*32
                elif fault=='run':value['runId']='f'*32
                elif fault=='area':value['area']='chat'
                elif fault=='stale':value['capturedEpochMs']-=5000
                elif fault=='closure':value['retiredEpochMs']=None
                else:value['expectedRetired']=True
            phase.fault=mutate
            with self.subTest(fault=fault),patch.object(self.adapter,'_feature_fixture_client',return_value=phase.client),patch.object(self.adapter,'_snapshots_feature') as factory:
                with self.assertRaises((ValueError,RuntimeError)):self.adapter.invoke(bound.SELECTOR,'feature.snapshots.cleanup',self.call())
                factory.assert_not_called()

    def test_retirement_payload_preserves_exact_original_configuration_without_current_settings(self):
        owner=self.owner();parent=self.adapter.snapshots_retirement_store(bound.SELECTOR)
        parent.write(dict(snapshotsRetirementVersion=1,runId=RUN,binding=owner['binding'],payload=pack([dict(phase='retiring',owner=owner)])),None)
        settings=PrivateFeatureState(self.settings);settings.write(dict(expectedRetired=True),settings.read())
        with patch('overte_phone_snapshots_feature.PhoneSnapshotsFeature',side_effect=lambda *args,**kwargs:(args,kwargs)):
            args,kwargs=self.adapter._snapshots_feature(bound.SELECTOR,RUN,retirement=True)
            self.assertEqual(self.config,args[3]);self.assertEqual({},kwargs)
        with self.assertRaises((ValueError,RuntimeError)):self.adapter._snapshots_feature(bound.SELECTOR,RUN,retirement=False)
        foreign=deepcopy(owner);foreign['configuration']['receiverApkSha256']='f'*64
        self.adapter.snapshots_feature_store(bound.SELECTOR).write(foreign,None)
        with patch('overte_phone_snapshots_feature.PhoneSnapshotsFeature') as constructor:
            with self.assertRaises((ValueError,RuntimeError)):self.adapter._snapshots_feature(bound.SELECTOR,RUN,retirement=True)
            constructor.assert_not_called()

    def test_missing_active_controls_cannot_replace_completed_immutable_archive(self):
        with patch('overte_phone_snapshots_retirement.completed_archive',side_effect=ValueError('Original completed archive missing')) as original,patch('overte_phone_snapshots_feature.PhoneSnapshotsFeature') as constructor:
            with self.assertRaisesRegex(ValueError,'completed archive missing'):
                self.adapter._snapshots_feature(bound.SELECTOR,RUN,retirement=True)
            original.assert_called_once();constructor.assert_not_called()

    def test_second_cleanup_requires_fresh_actual_binding_and_exact_original_archive_policy(self):
        owner=self.owner();archive=dict(owner=owner)
        with patch('overte_phone_snapshots_retirement.completed_archive',return_value=archive) as original,patch('overte_phone_snapshots_feature.PhoneSnapshotsFeature',side_effect=lambda *args,**kwargs:args):
            args=self.adapter._snapshots_feature(bound.SELECTOR,RUN,retirement=True)
            self.assertEqual(owner['configuration'],args[3]);self.assertEqual(owner['binding'],original.call_args.args[1])
        for fault in ('binding','policy','run','fixture'):
            changed=deepcopy(archive)
            if fault=='binding':changed['owner']['binding']['sessionId']='foreign'
            elif fault=='policy':changed['owner']['configuration']['receiverApkSha256']='f'*64
            elif fault=='run':changed['owner']['runId']='f'*32
            else:changed['owner']['fixtureUrl']='https://foreign.invalid/feature-fixture/v1/runs/'+RUN+'/'
            with self.subTest(fault=fault),patch('overte_phone_snapshots_retirement.completed_archive',return_value=changed),patch('overte_phone_snapshots_feature.PhoneSnapshotsFeature') as constructor:
                with self.assertRaises((ValueError,RuntimeError)):self.adapter._snapshots_feature(bound.SELECTOR,RUN,retirement=True)
                constructor.assert_not_called()

    def test_global_cleanup_attempts_snapshot_first_with_flag_removed_and_keeps_unresolved_children_red(self):
        self.f.read_only_boundaries();store=self.adapter.snapshots_feature_store(bound.SELECTOR);owner=dict(runId=RUN);store.write(owner,None)
        self.settings.unlink() # Cleanup must not depend on today's private opt-in configuration.
        order=[]
        def factory(_selector,run,*,retirement=False):
            self.assertEqual(RUN,run);self.assertTrue(retirement);order.append('snapshot')
            return SimpleNamespace(finalize=lambda:(_ for _ in ()).throw(ValueError('Unresolved original child')))
        def base(_selector):order.append('base');return {'cleaned':True}
        with patch.dict(os.environ,{'OVERTE_PHONE_FEATURE_SNAPSHOTS':'0'}),patch.object(self.adapter,'_snapshots_feature',side_effect=factory),patch.object(AppiumAdapter,'cleanup',side_effect=base):
            with self.assertRaisesRegex(ValueError,'PHONE_SNAPSHOTS_FEATURE_CLEANUP_INCOMPLETE'):self.adapter.cleanup(bound.SELECTOR)
        self.assertEqual(['snapshot','base'],order);self.assertEqual(owner,store.read())
        store.discard(owner)
        child=PrivateFeatureState(self.adapter.state_path(bound.SELECTOR).with_name('phone-snapshots-actor-originals.json'));child.write(dict(original='unresolved'),None)
        with patch.dict(os.environ,{'OVERTE_PHONE_FEATURE_SNAPSHOTS':'0'}),patch.object(AppiumAdapter,'cleanup',side_effect=base):
            with self.assertRaisesRegex(ValueError,'PHONE_SNAPSHOTS_FEATURE_CLEANUP_INCOMPLETE'):self.adapter.cleanup(bound.SELECTOR)
        self.assertEqual(dict(original='unresolved'),child.read())


if __name__=='__main__':unittest.main()
