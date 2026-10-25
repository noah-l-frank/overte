"""Actual missing Actor custody cannot progress an issued ordinary Open.

The actual four-file host bundle is explicitly prepared; full normal selection
is a separate case. No Actor/readiness source is invented, and native producers
remain models. Actual local SDK/files/JS and action ownership execute normally.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.tablet_web_actions import TabletWebActions
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletMissingActorGateTests(unittest.TestCase):
    def test_actual_absent_Actor_keeps_waiting_and_repeat_makes_no_VM_query_click_or_Stop(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary;primary=fixture.primary
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));ticket='b'*32
        fixture.fixture.journal.activate(RUN,ticket,'open',{})
        with primary.parts() as runtime:
            owner=TabletWebAppOwner(runtime);name='tabletweb-app-files-'+RUN+'-1.json'
            owned=OwnedTabletWebAppFiles(None,PrivateFeatureState(b.root/name),b.binding).reserve_app(RUN,b.source.fixture,ticket)
            runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(RUN,owned['fixtureUrl'],ticket,owned['nonce']))
            directory=b.directories[owned['runId']].as_uri();b.load(directory+'/script.js');b.ui.qt.opened=True
            admission=runtime.remember_app(owned)
            owner.state['generations'].append(dict(index=1,ticket=ticket,ownerFile=name,reserved=True,ownership=owned,directory=directory,admission=admission,dialogBefore=None));owner.save()
            call=dict(contractVersion=16,runId=RUN,ticket=ticket,fixtureUrl=b.source.fixture,verb='open',inputs={})
            actions=TabletWebActions(runtime);self.assertIsNone(actions.act(call));saved=deepcopy(actions.saved)
            self.assertEqual('waiting',actions.state['pending']['phase']);before=len(b.commands)
            self.assertIsNone(TabletWebActions(runtime).act(call));self.assertEqual(saved,actions.store.read())
            self.assertEqual(before,len(b.commands));self.assertEqual([],b.host_app.call('read')['navigations'])
            self.assertEqual([],b.ui.lifecycle_inputs);self.assertNotIn('scripts.stop.0',b.ui.qt.inputs)
            self.assertTrue(all(path.exists() for path in b.directories.values()))
            self.assertFalse(any(method=='DELETE' for method,_path in fixture.sdk.calls))


if __name__=='__main__':unittest.main()
