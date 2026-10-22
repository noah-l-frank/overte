"""Closed filenames preserve the original OS DTO, clocks and private records."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.process_retirement import IOSProcessRetirement
from ios.self_tests.test_ios_process_retirement import BINDING,RUN
from ios.self_tests.test_ios_retired_process import Boundary,SOURCE,BUNDLE


class ProcessRetirementProfileTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.os=Boundary()
    def owner(self,profile='graphics',*,name=None,role='primary',stage=0,default=False):
        prefix={'graphics':'graphics','emote':'emote','worldweb':'world-web'}.get(profile,profile)
        store=PrivateFeatureState(self.root/(name or 'ios-'+prefix+'-'+role+'-'+str(stage)+'-process-retirement.json'))
        arguments={} if default else dict(profile=profile)
        return IOSProcessRetirement(store,self.os.reader(),BINDING,RUN,role,stage,self.lock,**arguments)
    def test_default_graphics_and_explicit_graphics_keep_identical_original_schema(self):
        with self.lock.held():
            default=self.owner(default=True);default.advance();original=deepcopy(default.previous)
            explicit=self.owner();self.assertEqual(original,explicit.previous)
            self.assertEqual({'iosProcessRetirementVersion','binding','source','bundleId','runId','role','stage','payload'},set(original))
            record=explicit.record_store(1).read()
            self.assertEqual({'iosProcessRetirementRecordVersion','binding','source','bundleId','runId','role','stage','payload'},set(record))
    def test_each_new_owner_requires_own_acquisitions_and_four_original_clocks_without_DTO_relabel(self):
        with self.lock.held():
            for profile in ('emote','worldweb'):
                owner=self.owner(profile);start=len(self.os.queries);self.assertFalse(owner.advance())
                self.os.clock+=1.6;self.assertFalse(owner.advance());self.os.clock+=1.6;self.assertTrue(owner.advance())
                last=owner.current();self.assertEqual(self.os.original,last['original']);self.assertEqual(3,len(self.os.queries)-start)
                self.assertEqual(1,owner.previous['iosProcessRetirementVersion']);self.assertNotIn('profile',owner.previous)
                archived=IOSProcessRetirement.archive(owner.previous,path=owner.store.path,binding=BINDING,source=SOURCE,
                    bundle=BUNDLE,run=RUN,role='primary',stage=0,profile=profile)
                self.assertTrue(archived['windows'][-1]['complete'])
                with self.assertRaises(NativeUIError):IOSProcessRetirement.archive(owner.previous,path=owner.store.path,binding=BINDING,
                    source=SOURCE,bundle=BUNDLE,run=RUN,role='primary',stage=0)
    def test_unknown_profile_wrong_closed_path_role_or_stage_fail_before_any_OS_query(self):
        with self.lock.held():
            for profile,name,role,stage in (('foreign',None,'primary',0),('worldweb','ios-graphics-primary-0-process-retirement.json','primary',0),
                ('emote','ios-world-web-primary-0-process-retirement.json','primary',0),('graphics',None,'foreign',0),('emote',None,'primary',True)):
                with self.subTest(profile=profile,name=name,role=role,stage=stage),self.assertRaises(NativeUIError):self.owner(profile,name=name,role=role,stage=stage)
            self.assertEqual([],self.os.queries)
    def test_warm_profile_mutation_cannot_send_or_rebind_existing_filename(self):
        with self.lock.held():
            owner=self.owner('worldweb');owner.advance();prior=len(self.os.queries);owner.profile='emote'
            with self.assertRaises(NativeUIError):owner.advance()
            self.assertEqual(prior,len(self.os.queries))


if __name__=='__main__':unittest.main()
