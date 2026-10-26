"""Real inventory/lock guards with an explicitly modeled held-Scene envelope.

These cases test pure-validation scope admission and refusal, not Scene effects
or complete retirement. A separate retained original graph measures the actual
joined decoder, without a replacement decoder or native/SDK calls.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pure_original_validation import returning_input,scope as pure_scope,inherited_scope,PROFILE as EMOTE_PROFILE
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
from ios.adapters.avatar_scene_round import scope,PROFILE
from ios.self_tests.test_ios_avatar_input_owner import BINDING,RUN


class AvatarSceneRoundTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.original=PrivateFeatureState(self.root/'avatar-original.json');self.original.write({'original':[1,2,3]},None)
        scene=object.__new__(IOSAvatarHeldScene);scene.store=PrivateFeatureState(self.root/'ios-avatar-primary-scene.json')
        scene.root=self.root;scene.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');scene.binding=deepcopy(BINDING)
        scene.run,scene.role,scene.baseline,scene.clock,scene.paths,scene.state=RUN,'primary',{}, {}, {}, {'modeledEnvelope':True}
        self.scene=scene;self.enterContext(scene.lock.held());self.calls=[]
    def validate(self,value):self.calls.append(value);return value
    def test_literal_pure_success_reuses_only_inside_exact_original_scope(self):
        value={'original':[1,2,3]};before=(self.original.path.stat().st_ino,self.original.path.read_bytes())
        with scope(self.scene):
            self.assertIs(value,returning_input(self.validate,value))
            second=deepcopy(value);self.assertIs(second,returning_input(self.validate,second))
            self.assertEqual(1,len(self.calls))
        returning_input(self.validate,value);self.assertEqual(2,len(self.calls))
        self.assertEqual(before,(self.original.path.stat().st_ino,self.original.path.read_bytes()))
    def test_original_rewrite_replacement_hardlink_or_new_carrier_refuses_scope_exit(self):
        for fault in ('rewrite','replacement','hardlink','new-file'):
            path=self.original.path;raw=path.read_bytes();alias=self.root/'avatar-alias.json'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                with scope(self.scene):
                    returning_input(self.validate,{'original':1})
                    if fault=='rewrite':path.write_bytes(raw)
                    elif fault=='replacement':
                        displaced=path.with_name('avatar-displaced.json');path.rename(displaced)
                        PrivateFeatureState(path).write({'original':[1,2,3]},None)
                    elif fault=='hardlink':
                        import os
                        os.link(path,alias)
                    else:PrivateFeatureState(alias).write({'unknown':True},None)
            # New scopes have their own independently inventoried test inputs.
            alias.unlink(missing_ok=True)
    def test_mutated_scene_binding_or_in_memory_envelope_cannot_complete_guard(self):
        for fault in ('binding','state'):
            old_binding=deepcopy(self.scene.binding);old_state=deepcopy(self.scene.state)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                with scope(self.scene):
                    returning_input(self.validate,{'original':1})
                    if fault=='binding':self.scene.binding['generation']+=1
                    else:self.scene.state['mutated']=True
            self.scene.binding=old_binding;self.scene.state=old_state
    def test_unheld_or_foreign_type_cannot_enable_pure_reuse(self):
        with self.scene.lock.held():self.scene.lock.assert_held()
        wrong=object.__new__(IOSAvatarHeldScene);wrong.__dict__.update(self.scene.__dict__)
        wrong.lock=ScriptSourceLock(self.scene.lock.path)
        with self.assertRaises(NativeUIError):
            with scope(wrong):self.fail('Unheld source admitted')
        with self.assertRaises(NativeUIError):
            with scope(object()):self.fail('Foreign owner admitted')
    def test_exception_does_not_leak_successes_to_later_live_validator(self):
        with self.assertRaisesRegex(ValueError,'actual decoder failure'):
            with scope(self.scene):
                returning_input(self.validate,{'original':1});raise ValueError('actual decoder failure')
        returning_input(self.validate,{'original':1});self.assertEqual(2,len(self.calls))
    def test_avatar_scope_isolated_from_explicit_nested_emote_scope(self):
        with scope(self.scene):
            returning_input(self.validate,{'original':1})
            with pure_scope(EMOTE_PROFILE,lambda:True):returning_input(self.validate,{'original':1})
            self.assertEqual(2,len(self.calls));returning_input(self.validate,{'original':1});self.assertEqual(2,len(self.calls))
        self.assertNotEqual(PROFILE,EMOTE_PROFILE)
    def test_inherited_scope_cannot_borrow_pure_successes_across_profile_boundaries(self):
        for outer,inner in ((PROFILE,EMOTE_PROFILE),(EMOTE_PROFILE,PROFILE)):
            with self.subTest(outer=outer),pure_scope(outer,lambda:True):
                returning_input(self.validate,{'original':1})
                with self.assertRaises(NativeUIError):
                    with inherited_scope(inner,lambda:True):self.fail('Cross-area inherited cache admitted')
    def test_untyped_or_unknown_profiles_cannot_activate_a_scope(self):
        for profile in (None,[],{},True,'foreign-profile'):
            with self.subTest(profile=profile),self.assertRaises(NativeUIError):
                with pure_scope(profile,lambda:True):self.fail('Foreign profile admitted')


if __name__=='__main__':unittest.main()
