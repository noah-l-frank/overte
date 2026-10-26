"""Real locks/inventories guard a modeled Final envelope, never an end proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pure_original_validation import returning_input,inherited_scope,scope as pure_scope,PROFILE as EMOTE,AVATAR_PROFILE as SCENE
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_ended_archive import FilesOnlyClient
from ios.adapters.avatar_final_pure_round import scope,PROFILE
from ios.adapters.avatar_held_final import IOSAvatarHeldFinal
from ios.self_tests.test_ios_avatar_input_owner import BINDING,RUN


class AvatarFinalPureRoundTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.calls=[]
        owner=object.__new__(IOSAvatarHeldFinal);owner.root=self.root/'originals';owner.root.mkdir(mode=0o700)
        owner.run,owner.role,owner.historical=RUN,'primary',True;owner.inputs={};owner.bindings={};owner.locks={}
        client=FilesOnlyClient('https://controlled.invalid/feature-fixture/v1','historical-final-test-'+'a'*32)
        owner.authority=AvatarAuthorityReader(client,RUN)
        for role in ('primary','actor'):
            directory=self.root/role;directory.mkdir(mode=0o700)
            owner.locks[role]=ScriptSourceLock(directory/'script-feature-sources.lock');self.enterContext(owner.locks[role].held())
            root=owner.root/role;root.mkdir(mode=0o700);child=('b' if role=='primary' else 'c')*32
            owner.bindings[role]=deepcopy(BINDING)
            owner.inputs[role]=dict(root=str(root),childRunId=child,ticket='d'*32,fixtureUrl=client.url+'/runs/'+child+'/',
                markerFixtureUrl=client.url+'/runs/'+RUN+'/',baseline=dict(state={},scripts={},http={}),logoutBefore={},
                paths={kind:str(directory/('ios-avatar-primary-'+suffix+'.json')) for kind,suffix in
                    dict(post=role+'-postlogout',tail=role+'-postlogout-tail',pointers='pointers',web='marker-web').items()})
        owner.store=PrivateFeatureState(owner.locks['primary'].path.with_name('ios-avatar-primary-final.json'))
        owner.state=dict(rows=[],pending=None);owner.previous=owner.envelope(owner.state);owner.store.write(owner.previous,None)
        self.owner=owner;self.argument={'modeledOriginal':True};self.original=PrivateFeatureState(owner.root/'avatar-original.json')
        self.original.write({'original':[1,2,3]},None)
    def validate(self,value):self.calls.append(value);return value
    def test_same_exact_scope_shares_only_literal_successes_and_discards_them_on_exit(self):
        value={'original':1}
        with scope(self.owner,self.argument):
            returning_input(self.validate,value)
            with scope(self.owner,deepcopy(self.argument)):returning_input(self.validate,deepcopy(value))
            self.assertEqual(1,len(self.calls))
        returning_input(self.validate,value);self.assertEqual(2,len(self.calls))
    def test_same_inode_rewrite_or_new_dangling_original_refuses_exit(self):
        for fault in ('rewrite','dangling'):
            path=self.owner.root/'avatar-new-original.json'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                with scope(self.owner,self.argument):
                    returning_input(self.validate,{'original':1})
                    if fault=='rewrite':self.original.path.write_bytes(self.original.path.read_bytes())
                    else:path.symlink_to('missing-original')
            path.unlink(missing_ok=True)
    def test_mutated_owner_argument_or_binding_is_not_a_new_scope_baseline(self):
        for fault in ('owner','argument','binding'):
            state=deepcopy(self.owner.state);binding=deepcopy(self.owner.bindings);argument=deepcopy(self.argument)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                with scope(self.owner,self.argument):
                    if fault=='owner':self.owner.state['unexpected']=True
                    elif fault=='argument':self.argument['unexpected']=True
                    else:self.owner.bindings['primary']['generation']+=1
            self.owner.state=state;self.owner.bindings=binding;self.argument=argument
    def test_unheld_replacement_lock_and_foreign_owner_cannot_enable_reuse(self):
        original=self.owner.locks['actor'];self.owner.locks['actor']=ScriptSourceLock(original.path)
        with self.assertRaises(NativeUIError):
            with scope(self.owner,self.argument):self.fail('Unheld lock admitted')
        self.owner.locks['actor']=original
        with self.assertRaises(NativeUIError):
            with scope(object(),self.argument):self.fail('Foreign owner admitted')
    def test_profile_cannot_inherit_from_scene_or_emote_and_exception_does_not_leak(self):
        for foreign in (SCENE,EMOTE):
            with self.subTest(profile=foreign),pure_scope(foreign,lambda:True),self.assertRaises(NativeUIError):
                with scope(self.owner,self.argument):self.fail('Foreign validation inherited')
            with scope(self.owner,self.argument),self.assertRaises(NativeUIError):
                with inherited_scope(foreign,lambda:True):self.fail('Final validation leaked')
        with self.assertRaisesRegex(ValueError,'original failure'):
            with scope(self.owner,self.argument):
                returning_input(self.validate,{'original':1});raise ValueError('original failure')
        returning_input(self.validate,{'original':1});self.assertEqual(2,len(self.calls))


if __name__=='__main__':unittest.main()
