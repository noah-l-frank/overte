"""Actual prepared metadata namespace and auth separation in the host fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture,ADAPTER
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletFixtureOwnershipTests(unittest.TestCase):
    def test_prepared_binding_has_existing_sdk_parent_before_any_observation(self):
        f=PairedTabletFixture(self);b=f.boundary;path=Path(f.metadata['installedPath'])
        self.assertEqual(b.root,path.parent);self.assertNotEqual(b.context_test.admission.fixture.store.path,path)
        self.assertEqual(b.context_test.admission.fixture.store.read(),PrivateFeatureState(path).read())
        self.assertEqual(0o600,path.stat().st_mode&0o777)
    def test_actual_adapter_baseline_uses_restricted_token_and_cannot_read_actor_effect_facts(self):
        f=PairedTabletFixture(self);self.assertEqual(ADAPTER,f.primary.client.token)
        result=f.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));self.assertEqual([],result['resources'])
        restricted=f.primary.client.request('/runs/'+RUN);self.assertEqual([],restricted['entries'])
        before=f.fixture.journal.snapshot(RUN)
        with self.assertRaises(ValueError) as refused:f.primary.client.request('/runs/'+RUN+'/active',dict(ticket='e'*32,verb='cleanup',inputs={}))
        self.assertEqual(403,getattr(refused.exception.__cause__,'code',None))
        self.assertEqual(before,f.fixture.journal.snapshot(RUN))
        snapshot=f.controller.request('/runs/'+RUN);self.assertEqual('tablet-web',snapshot['area'])
        self.assertEqual([],f.sdk.errors)


if __name__=='__main__':unittest.main()
