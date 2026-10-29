"""Complete public/common Emote source composition; native remains modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import SCENARIOS
from ios import emote_observer
from ios.adapters import feature_configuration
from ios.self_tests.emote_public_vertical_fixture import PublicEmoteVertical


class PublicEmoteVerticalTests(unittest.TestCase):
    def test_explicit_v8_admission_keeps_legacy_rooted_originals_closed_without_transport(self):
        import os
        from unittest.mock import patch
        from feature_journeys.witness import Client
        from ios.self_tests.test_ios_emote_admission import EmoteAdmissionTests
        original=EmoteAdmissionTests();original.setUp();self.addCleanup(original.doCleanups)
        primary=original.h.root/'primary-art';actor=original.h.root/'actor-art'
        primary.mkdir(mode=0o700);actor.mkdir(mode=0o700)
        chosen=deepcopy(original.value['emotes']);chosen['artifactRoot']=str(primary)
        value=dict(original.value,iosFeatureAdapterVersion=8,emotes=chosen,emoteCoordinatorVersion=2,worldWebCoordinatorVersion=None,
            emoteTargets=dict(primaryTarget='owned-primary',actorTarget='owned-peer',
                primaryArtifactRoot=str(primary),actorArtifactRoot=str(actor)),
            **{field:None for field,_module in feature_configuration.WHOLE_SETTINGS.values()})
        with patch.object(Client,'request',side_effect=AssertionError('Metadata admission attempted transport')),\
             patch.dict(os.environ,OVERTE_IOS_FEATURE_ADAPTER_CONFIG=str(original.store.path)):
            for version in (4,6,7,8):
                selected=deepcopy(value);selected['iosFeatureAdapterVersion']=version
                if version<8:selected.pop('emoteTargets')
                if version==4:
                    for field,_module in feature_configuration.WHOLE_SETTINGS.values():selected.pop(field)
                    selected.pop('emoteCoordinatorVersion');selected.pop('worldWebCoordinatorVersion')
                elif version==6:selected.pop('worldWebCoordinatorVersion')
                original.store.write(selected,original.store.read());before=original.store.path.read_bytes();inode=original.store.path.stat().st_ino
                self.assertEqual(selected,feature_configuration.configuration())
                if version<8:
                    with self.assertRaises(NativeUIError):feature_configuration.capabilities(original.target)
                else:
                    self.assertEqual({'feature.emotes.'+kind for kind in ('act','observe','cleanup','terminal')},set(feature_configuration.capabilities(original.target)))
                self.assertEqual(before,original.store.path.read_bytes());self.assertEqual(inode,original.store.path.stat().st_ino)
            for coordinator in (True,1,3,None):
                original.store.write(dict(value,emoteCoordinatorVersion=coordinator),original.store.read())
                with self.assertRaises(NativeUIError):feature_configuration.capabilities(original.target)

    def test_public_all28_common_actions_rooted_end_and_actual_actor_worker_return(self):
        f=PublicEmoteVertical(self);original=deepcopy(f.configuration);store=PrivateFeatureState(f.configuration_path)
        # Readability does not silently upgrade old rooted coordinator configs.
        for version in (6,7):
            value=deepcopy(original);value['iosFeatureAdapterVersion']=version;value.pop('emoteTargets')
            if version==6:value.pop('worldWebCoordinatorVersion')
            feature_configuration.validate(value);store.write(value,store.read())
            before=(len(f.calls),len(f.factories),len(f.end.calls),len(f.end.native_reads))
            with self.assertRaises(NativeUIError):feature_configuration.capabilities(f.end.targets['primary'])
            self.assertEqual(before,(len(f.calls),len(f.factories),len(f.end.calls),len(f.end.native_reads)))
        for coordinator in (True,1,3,None):
            value=deepcopy(original);value['emoteCoordinatorVersion']=coordinator;store.write(value,store.read())
            with self.assertRaises(NativeUIError):feature_configuration.capabilities(f.end.targets['primary'])
        store.write(original,store.read())
        self.assertEqual({'feature.emotes.'+kind for kind in ('act','observe','cleanup','terminal')},
            set(feature_configuration.capabilities(f.end.targets['primary'])))
        phases=f.journey.execute()
        self.assertEqual(28,len(SCENARIOS['emotes']['steps']));self.assertEqual({'Sit1','Sit2','Sit3'},f.journey.sit_variants)
        self.assertEqual(1,len(f.reports));report=f.reports[0]
        self.assertTrue(report['sequenceCompleted']);self.assertTrue(report['cleanupSucceeded']);self.assertFalse(report['deviceAcceptance'])
        self.assertEqual('owned-clean-baseline',phases[0]['phase']);self.assertEqual('cleanup-restored-baseline',phases[-1]['phase'])
        self.assertTrue(all(sample['witness'] is not None for sample in report['samples']))
        self.assertTrue(any(row['evidence'] for row in phases));self.assertIsNotNone(report['terminalRetirement']['end'])
        self.assertEqual(['lifecycle.background','app.launch'],f.end.lifecycle_inputs)
        self.assertEqual(2,sum(operation=='feature.emotes.cleanup' for operation,_value in f.calls))
        first_inspect=next(index for index,(operation,value) in enumerate(f.calls)
            if operation=='feature.emotes.terminal' and value['stage']=='inspect')
        self.assertEqual(2,sum(operation=='feature.emotes.cleanup' for operation,_value in f.calls[:first_inspect]))
        self.assertEqual(['inspect','seal','finish'],[value['stage'] for operation,value in f.calls if operation=='feature.emotes.terminal'])
        self.assertEqual(len(f.calls),len(f.factories));self.assertEqual(0,f.worker.result);self.assertFalse(f.worker.thread.is_alive())
        events=json.loads((f.root/'actual-emote-worker-events.json').read_text());self.assertEqual(f.worker_events,events)
        self.assertEqual(dict(event='actual-worker-return',returnCode=0,uncaughtExceptionType=None),events[-1])
        self.assertFalse(emote_observer.failure(f.actor,f.worker.configuration))
        self.assertEqual(['actor','primary'],f.end.stops);self.assertEqual({'actor','primary'},f.end.deleted)
        for role in ('primary','actor'):
            self.assertEqual(1,sum(row[0]==role and row[1]=='DELETE' for row in f.end.calls))
            self.assertFalse(f.end.alive[role]);self.assertIsNone(f.adapter.read_session(role));self.assertIsNone(f.adapter._binding_store(role).read())
        # Both originally selected targets must reach the same complete
        # original paired proof, with no new native/SDK/process work.
        before=(deepcopy(f.end.calls),deepcopy(f.end.native_reads),deepcopy(f.end.source_factories),deepcopy(f.end.stops))
        foreign=f.root/'foreign-actor-originals';foreign.mkdir(mode=0o700)
        for fault in ('missing-pair','foreign-actor-root'):
            bad=deepcopy(original)
            if fault=='missing-pair':bad.pop('emoteTargets')
            else:bad['emoteTargets']['actorArtifactRoot']=str(foreign)
            store.write(bad,store.read())
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):f.adapter.cleanup('actor')
            self.assertEqual(before,(f.end.calls,f.end.native_reads,f.end.source_factories,f.end.stops))
        store.write(original,store.read())
        for selector in ('actor','primary','actor','primary'):
            self.assertEqual(dict(cleaned=True),f.adapter.cleanup(selector))
        self.assertEqual(before,(f.end.calls,f.end.native_reads,f.end.source_factories,f.end.stops))


if __name__=='__main__':unittest.main()
