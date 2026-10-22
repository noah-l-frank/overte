"""Closed observer-version admission and independent Snapshot actor dispatch.

The entry-point boundary is synthetic; these tests do not measure a Phone,
rendered image, OS sheet or product effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_feature_state import PrivateFeatureState
import script_observer as observer

BASE=['scripts','authentication','graphics']
V3=BASE+['emotes','world-web','tablet-web','world-navigation','audio']
V4=V3+['create','avatar-people']
V5=V4+['assets']
V6=V5+['chat']
V7=V6+['lifecycle-input']
V8=V7+['snapshots']
AREAS={2:BASE,3:V3,4:V4,5:V5,6:V6,7:V7,8:V8}


class SnapshotsObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='phone-observer-v8-');self.addCleanup(self.temp.cleanup)
        self.store=PrivateFeatureState(Path(self.temp.name)/'observer.json')
        self.base=dict(featureObserverVersion=8,area='snapshots',target='owned-phone',candidateArguments=[],
            fixtureUrl='http://controlled.invalid/feature-fixture/v1',actorToken='a'*64,durationSeconds=30)
        self.now=0.
    def config(self,value):
        self.store.write(value,self.store.read());return observer.configuration(self.store.path)
    def value(self,version,area):
        value=self.base|dict(featureObserverVersion=version,area=area)
        if area=='authentication':value['fixtureUrl']='https://owned.invalid/feature-fixture/v1'
        if area=='emotes':value['imagePolicy']=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595])
        if area=='avatar-people':
            value['fixtureUrl']='https://owned.invalid/feature-fixture/v1';value['peerTarget']='separate-peer'
            value['peerImagePolicy']=dict(imageExtent=[1000,750],markerRoi=[20,20,180,60],
                imagePolicy=dict(source='world-render-target',marker=[24,24,152,56],subject=[280,155,720,595]))
        return value
    def test_closed_historical_grammars_and_v8_keep_all_fourteen_areas(self):
        self.assertEqual(8,observer.VERSION)
        for version,areas in AREAS.items():
            for area in V8:
                value=self.value(version,area)
                with self.subTest(version=version,area=area):
                    if area in areas:self.assertEqual(value,self.config(value))
                    else:
                        with self.assertRaises((ValueError,RuntimeError)):self.config(value)
    def test_snapshot_config_rejects_expected_facts_primary_credentials_and_extra_controls(self):
        for change in (dict(expectedState={}),dict(imagePolicy={}),dict(peerTarget='foreign'),dict(adapterToken='b'*64),
                       dict(readerToken='r'*64),dict(actorToken='short'),dict(featureObserverVersion=True),dict(durationSeconds=29)):
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):
                self.config(self.base|change)
    def adapter(self,steps,metadata=None):
        self.run='b'*32
        if metadata is None:metadata=dict(runId=self.run,fixtureUrl=self.base['fixtureUrl']+'/runs/'+self.run+'/')
        store=SimpleNamespace(read=Mock(return_value=metadata));actor=SimpleNamespace(step=Mock(side_effect=steps))
        adapter=SimpleNamespace(snapshots_feature_store=Mock(return_value=store),_snapshots_actor=Mock(return_value=actor),
            invoke=Mock(side_effect=AssertionError('Actor must not invoke primary operations')),
            _snapshots_feature=Mock(side_effect=AssertionError('Actor must not acquire primary facade')))
        return adapter,actor,store
    def sleep(self,value):self.now+=value
    def run_actor(self,adapter):return observer.run(adapter,self.base,monotonic=lambda:self.now,sleep=self.sleep)
    def test_actual_dispatch_uses_separate_client_and_only_actor_step_until_retirement(self):
        adapter,actor,store=self.adapter([False,observer.PhoneScriptSourceBusy(),True])
        self.assertEqual(0,self.run_actor(adapter));self.assertEqual(3,actor.step.call_count)
        args=adapter._snapshots_actor.call_args
        self.assertEqual(('owned-phone',self.run),args.args)
        client=args.kwargs['client'];self.assertEqual(self.base['fixtureUrl'],client.url)
        adapter.invoke.assert_not_called();adapter._snapshots_feature.assert_not_called()
    def test_non_boolean_completion_cannot_stand_in_for_actor_retirement(self):
        for result in (None,1,dict(retired=True),'complete'):
            adapter,_,_=self.adapter([result])
            with self.subTest(result=result),self.assertRaises((ValueError,RuntimeError)):self.run_actor(adapter)
    def test_foreign_run_source_cannot_construct_actor(self):
        adapter,_,_=self.adapter([True],dict(runId='b'*32,fixtureUrl='http://foreign.invalid/runs/'+'b'*32+'/'))
        with self.assertRaises((ValueError,RuntimeError)):self.run_actor(adapter)
        adapter._snapshots_actor.assert_not_called()
    def test_missing_owner_never_becomes_a_successful_observer(self):
        adapter,_,store=self.adapter([True]);store.read.return_value=None
        with self.assertRaises((ValueError,RuntimeError)):self.run_actor(adapter)
        adapter._snapshots_actor.assert_not_called()
    def test_failed_or_slow_actor_cannot_hide_missing_retirement(self):
        for result in (ValueError('Incomplete original retirement'),lambda:self.advance_and_finish()):
            adapter,actor,_=self.adapter([False])
            actor.step.side_effect=result
            self.now=0.
            with self.subTest(result=type(result).__name__),self.assertRaises((ValueError,RuntimeError)):self.run_actor(adapter)
    def advance_and_finish(self):self.now=30.;return True
    def test_clock_regression_after_step_never_qualifies_a_finished_actor(self):
        adapter,actor,_=self.adapter([True]);self.now=1.
        def regressed():self.now=.5;return True
        actor.step.side_effect=regressed
        with self.assertRaises((ValueError,RuntimeError)):self.run_actor(adapter)
    def test_bootstrap_disables_every_primary_feature_and_forbids_reader_token(self):
        fields=('record','artifact','expected_inputs','expected_source_sha','expected_version_code','minimum_version_code','channel',*observer.EVIDENCE_KEYS)
        args=SimpleNamespace(**{key:'synthetic' for key in fields},action='describe',target='owned-phone',operation=None,arguments='{}',build_evidence=None,expected_artifact_sha256=None)
        flags=['OVERTE_PHONE_FEATURE_'+area.replace('-','_').upper() for area in V8]
        captured={}
        def run(*args):captured.update({key:os.environ.get(key) for key in flags});return 0
        self.config(self.base)
        with patch.dict(os.environ,{key:'1' for key in flags},clear=True),patch.object(observer,'parse_args',return_value=args),patch.object(observer,'VerifiedCandidate'),patch.object(observer,'PhoneAppiumAdapter'),patch.object(observer,'run',side_effect=run):
            self.assertEqual(0,observer.main(['--config',str(self.store.path)]))
            self.assertEqual({key:'0' for key in flags},captured)
        with patch.dict(os.environ,{'OVERTE_E2E_FEATURE_READER_TOKEN':'r'*64},clear=True),patch.object(observer,'VerifiedCandidate') as candidate:
            self.assertEqual(2,observer.main(['--config',str(self.store.path)]));candidate.assert_not_called()


if __name__=='__main__':unittest.main()
