"""Real immutable app ownership coordinates Stop; no Actor effect is copied."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_app_readiness import ready,retain,store_for
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.adapters.tablet_web_actions import TabletWebActions
from ios.self_tests.test_ios_tablet_web_app_origin import originals_boundary,EPOCH,BINDING,RUN,ROOT
from ios.self_tests.test_ios_retired_process import SOURCE


class TabletAppReadinessTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        values=originals_boundary();self.metadata=values[0];self.app=dict(owner=values[0],files=values[1],scripts=values[2],buttons=values[3],controls=values[4],afterEpochMs=EPOCH)
        self.calls=[]
        def source(role):return TabletWebSourceOwner(self.root,BINDING,RUN,role,ROOT,31,self.lock,lambda:True,monotonic=lambda:0.)
        def runtime(actual):return SimpleNamespace(observer=SimpleNamespace(source=actual),bootstrap=SimpleNamespace(original=lambda:dict(instance='d'*32)),
            admission=dict(installedAfter=dict(source=deepcopy(SOURCE))),read_auxiliary=lambda kind:self.calls.append(kind))
        self.actor=runtime(source('actor'));self.primary=runtime(source('primary'))
        self.reference=self.actor.observer.source.remember_app(self.app);primary_reference=self.primary.observer.source.remember_app(self.app)
        owner_file='tabletweb-app-files-'+RUN+'-1.json';PrivateFeatureState(self.root/owner_file).write(self.metadata,None)
        plan=dict(tabletWebAppOwnerVersion=1,binding=BINDING,runId=RUN,payload=pack([dict(operations=[],pending=None,generations=[dict(index=1,
            ticket=self.metadata['ticket'],ownerFile=owner_file,reserved=True,ownership=self.metadata,directory=self.app['files']['source']['directory'],
            admission=primary_reference,dialogBefore=None)])]))
        PrivateFeatureState(self.root/('tabletweb-app-owner-'+RUN+'.json')).write(plan,None)
    def test_actor_retains_its_exact_registered_original_then_primary_uses_only_private_readiness(self):
        self.assertFalse(ready(self.primary,[self.metadata]));value=retain(self.actor,self.metadata,self.reference)
        self.assertTrue(ready(self.primary,[self.metadata]));self.assertEqual(self.reference,value['admission']);self.assertNotIn('public',value)
        self.assertNotIn('capturedEpochMs',value);self.assertEqual([],self.calls)
    def test_missing_or_foreign_admission_cannot_query_VM_start_cleanup_input_or_Stop(self):
        feature=object.__new__(IOSTabletWebFeature);feature.role='primary';feature.state=dict(phase='cleaning',cleanupBefore={'testOnlyActualBeforeTail':True},cleanupStop=None)
        with (patch('ios.adapters.tablet_web_feature.TabletWebTail',side_effect=AssertionError('No fresh tail/VM query while Actor admission missing')),
                patch('ios.adapters.tablet_web_feature.TabletWebCleanupAppOwner',side_effect=AssertionError('No cleanup input/Stop'))):
            self.assertIsNone(feature.cleanup_live(self.primary));self.assertEqual([],self.calls)
            value=retain(self.actor,self.metadata,self.reference);store=store_for(self.actor.observer.source,self.metadata)
            foreign=deepcopy(value);foreign['runId']='f'*32;store.write(foreign,value)
            with self.assertRaises(NativeUIError):feature.cleanup_live(self.primary)
        self.assertIsNone(feature.state['cleanupStop']);self.assertEqual([],self.calls)
    def test_same_input_bytes_foreign_process_source_native_birth_or_unregistered_original_is_refused(self):
        value=retain(self.actor,self.metadata,self.reference);store=store_for(self.actor.observer.source,self.metadata)
        for fault in ('source','birth','binding','reference'):
            changed=deepcopy(value)
            if fault=='source':changed['processSource']['instance']='f'*32
            elif fault=='birth':changed['nativeInstance']='f'*32
            elif fault=='binding':changed['binding']['generation']+=1
            else:changed['admission']['index']+=1
            store.write(changed,store.read())
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,FileNotFoundError)):ready(self.primary,[self.metadata])
        self.assertEqual([],self.calls)
    def test_before_first_open_missing_actor_cue_leaves_prepared_input_waiting_without_a_click(self):
        action=object.__new__(TabletWebActions);action.runtime=self.primary
        action.apps=SimpleNamespace(ownership=lambda _generation:self.metadata);action.current_generation=lambda:dict(index=1)
        action.app_button=lambda _verb:self.calls.append('ordinary-app-click');row=dict(phase='waiting',call=dict(verb='open'))
        self.assertIsNone(action.open_ready(row,lambda:True));self.assertIsNone(action.open_ready(row,lambda:True))
        self.assertEqual('waiting',row['phase']);self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main()
