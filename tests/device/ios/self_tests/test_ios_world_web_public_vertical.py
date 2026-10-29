"""Full source composition; original native/Qt/GPU/OS producers remain models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import json
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import SCENARIOS
from ios.adapters import feature_configuration
from ios import world_web_observer
from ios.self_tests.world_web_public_vertical_fixture import PublicWorldVertical


class WorldWebPublicVerticalTests(unittest.TestCase):
    def test_public_all19_shared_evidence_repeat_cleanup_terminal_and_actual_actor_worker_exit(self):
        vertical=PublicWorldVertical(self);original=deepcopy(vertical.configuration)
        store=PrivateFeatureState(vertical.configuration_path)
        # Real prospective capabilities, no capabilities patch/Flow spy.
        for version in (5,6):
            old=deepcopy(original);old['iosFeatureAdapterVersion']=version;old.pop('worldWebCoordinatorVersion')
            if version==5:old.pop('emoteCoordinatorVersion')
            feature_configuration.validate(old);store.write(old,store.read())
            before=(len(vertical.calls),len(vertical.factories),len(vertical.native_operations))
            with self.assertRaises(NativeUIError):feature_configuration.capabilities(vertical.targets['primary'])
            self.assertEqual(before,(len(vertical.calls),len(vertical.factories),len(vertical.native_operations)))
        for coordinator in (True,0,2,None):
            bad=deepcopy(original);bad['worldWebCoordinatorVersion']=coordinator
            store.write(bad,store.read())
            with self.assertRaises(NativeUIError):feature_configuration.capabilities(vertical.targets['primary'])
        store.write(original,store.read())
        self.assertEqual(4,len(feature_configuration.capabilities(vertical.targets['primary'])))
        journey=vertical.journey();phases=journey.execute()
        self.assertEqual(21,len(phases));self.assertEqual('owned-clean-baseline',phases[0]['phase'])
        self.assertEqual('cleanup-restored-baseline',phases[-1]['phase'])
        self.assertEqual(1,len(vertical.reports));report=vertical.reports[0]
        self.assertTrue(report['sequenceCompleted']);self.assertTrue(report['cleanupSucceeded'])
        self.assertTrue(report['cleanupEnabled']);self.assertFalse(report['deviceAcceptance'])
        self.assertEqual(19,len(SCENARIOS['world-web']['steps']))
        actions=[values for name,values in vertical.calls if name=='feature.world-web.act']
        self.assertEqual([step['verb'] for step in SCENARIOS['world-web']['steps']],[value['verb'] for value in actions])
        self.assertEqual(2,sum(name=='feature.world-web.cleanup' for name,_value in vertical.calls))
        first_inspect=next(index for index,(name,value) in enumerate(vertical.calls)
            if name=='feature.world-web.terminal' and value['stage']=='inspect')
        self.assertEqual(2,sum(name=='feature.world-web.cleanup' for name,_value in vertical.calls[:first_inspect]))
        self.assertEqual(['inspect','seal','finish'],[value['stage'] for name,value in vertical.calls if name=='feature.world-web.terminal'])
        self.assertGreaterEqual(len(vertical.factories),len(vertical.calls))
        expected=sum(bool(set(step['evidence'])&{'image','changed'}) for step in SCENARIOS['world-web']['steps'])
        images=[evidence for phase in phases for evidence in phase['evidence'] if evidence['kind'] in ('image','changed')]
        self.assertEqual(expected,len(images));self.assertTrue(all(row['observed']['sha256'] for row in images))
        self.assertTrue(all(sample['witness'] is not None for sample in report['samples']))
        self.assertEqual(0,vertical.worker.result);self.assertFalse(vertical.worker.thread.is_alive())
        worker_events=json.loads((vertical.root/'actual-actor-worker-events.json').read_text())
        self.assertEqual(vertical.worker_events,worker_events)
        self.assertEqual(dict(event='actual-worker-return',returnCode=0,uncaughtExceptionType=None),worker_events[-1])
        self.assertFalse(world_web_observer.failure(vertical.f.secondary))
        self.assertIsNotNone(report['terminalRetirement']['end'])
        # Public canonical generic cleanup must use retained complete originals
        # and never issue another Stop/DELETE/query after both SDKs are gone.
        before=(deepcopy(vertical.f.requests),deepcopy(vertical.f.own),deepcopy(vertical.native_operations),
            {role:model.native_calls for role,model in vertical.f.models.items()})
        for selector in ('primary','actor'):
            self.assertEqual(dict(cleaned=True),vertical.adapter.cleanup(selector))
            self.assertEqual(dict(cleaned=True),vertical.adapter.cleanup(selector))
        self.assertEqual(before,(vertical.f.requests,vertical.f.own,vertical.native_operations,
            {role:model.native_calls for role,model in vertical.f.models.items()}))
        for role in ('primary','actor'):
            self.assertFalse(vertical.f.models[role].running);self.assertFalse(vertical.f.models[role].sdk_live)
            self.assertEqual(1,sum(value==(role,'app.stop') for value in vertical.f.own))
            self.assertEqual(1,sum(selector==role and method=='DELETE' and path=='/session/'+vertical.f.sdks[role].binding['sessionId']
                for selector,method,path,_body in vertical.f.requests))


if __name__=='__main__':unittest.main()
