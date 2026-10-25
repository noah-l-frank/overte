"""Missing independent app ownership cannot click, query another VM or Stop.

The fault interrupts an actual returned waiting boundary after normal load;
the original pending input plan remains durable and is never replayed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack
from ios.adapters.tablet_web_actions import TabletWebActions
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletActorUnavailableTests(unittest.TestCase):
    def test_actual_missing_Actor_retains_waiting_input_without_extra_VM_query_click_or_Stop(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary;feature=fixture.primary
        feature.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ticket='b'*32;fixture.fixture.journal.activate(RUN,ticket,'open',{})
        call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb='open',inputs={})
        store=PrivateFeatureState(b.root/('tabletweb-actions-'+RUN+'.json'));sleep=feature.sleep
        def interrupted(duration):
            saved=store.read()
            if saved is not None:
                row=unpack(saved['payload'])[0]
                if row['pending'] is not None and row['pending']['phase']=='waiting':
                    raise InterruptedError('Actual returned independent-ownership wait interrupted')
            sleep(duration)
        feature.sleep=interrupted
        with self.assertRaises(InterruptedError):feature.act(call)
        original=deepcopy(store.read());self.assertEqual('waiting',unpack(original['payload'])[0]['pending']['phase'])
        self.assertEqual(1,len(b.loaded));self.assertEqual([],b.host_app.call('read')['navigations'])
        before=len(b.commands)
        with feature.parts() as runtime:self.assertIsNone(TabletWebActions(runtime).act(call))
        self.assertEqual(before,len(b.commands));self.assertEqual(original,store.read())
        self.assertEqual([],b.host_app.call('read')['navigations']);self.assertEqual([],b.ui.lifecycle_inputs)
        self.assertNotIn('scripts.stop.0',b.ui.qt.inputs)
        self.assertTrue(all(path.exists() for path in b.directories.values()))


if __name__=='__main__':unittest.main()
