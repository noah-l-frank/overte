"""Same-image historical context, real original files and continuity negatives."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters.tablet_web_samples import TabletWebSamples
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_page_flow as page


class TabletImageContextTests(unittest.TestCase):
    def setUp(self):
        component=page.TabletPageFlowTests();self.addCleanup(component.doCleanups)
        self.b=component.opened();self.runtime=self.b.runtime
        self.original=self.runtime.observe()
        self.tail=dict(tabletWebTailSourceVersion=1,bootstrap=deepcopy(self.original['bootstrap']),
            primaryBootstrap=deepcopy(self.original['primaryBootstrap']),observation=deepcopy(self.original['observation']))
        self.runtime.proof_cache=None
        self.commands=len(self.b.commands)

    def samples(self,runtime,callback):
        return TabletWebSamples(runtime,self.b.root,dict(source='native-screen',marker={},subject={}),
            historical=True,tail_validator=callback)

    @contextmanager
    def owners(self):
        actual=TabletWebSourceOwner.__init__;captured=[]
        def constructed(owner,*args,**kwargs):
            actual(owner,*args,**kwargs);captured.append(owner)
        with patch.object(TabletWebSourceOwner,'__init__',constructed):yield captured

    def test_fresh_context_reuses_exact_owner_keeps_caller_isolation_and_expires(self):
        with self.owners() as owners:
            with self.runtime.image_observation_context(self.original,self.b.root) as (observed,tail):
                self.assertIs(tail,self.runtime._image_tail_validator(tail))
                first=tail(self.tail);self.assertEqual(1,len(owners))
                first['frame']['state']['iosTabletWebStateVersion']=0
                self.assertEqual(2,tail(self.tail)['frame']['state']['iosTabletWebStateVersion'])
                self.assertEqual(1,len(owners));self.assertEqual(observed['public']['state']['page'],'reference')
            with self.assertRaises(NativeUIError):tail(self.tail)
            with self.assertRaises(NativeUIError):self.samples(self.runtime,tail)
        self.assertEqual(self.commands,len(self.b.commands))

    def test_no_op_callback_is_refused_even_inside_the_actual_image_scope(self):
        path=self.b.root/('tabletweb-screen-samples-'+self.b.source.run+'-primary.json')
        self.assertFalse(path.exists())
        with self.runtime.image_observation_context(self.original,self.b.root):
            with self.assertRaises(NativeUIError):self.samples(self.runtime,lambda _value:None)
        self.assertFalse(path.exists());self.assertEqual(self.commands,len(self.b.commands))

    def test_another_runtime_cannot_accept_the_current_image_closure(self):
        foreign=object.__new__(type(self.runtime));foreign.observer=self.runtime.observer
        with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
            with self.assertRaises(NativeUIError):self.samples(foreign,tail)
            foreign._image_tail=self.runtime._image_tail
            with self.assertRaises(NativeUIError):self.samples(foreign,tail)
        self.assertEqual(self.commands,len(self.b.commands))

    def test_source_role_binding_or_lock_swap_during_original_decode_cannot_mint_context(self):
        actual=self.runtime._validate_original;source=self.runtime.observer.source
        binding=deepcopy(source.binding);binding['processIdentity']='43'
        for field,foreign in (('role','actor'),('binding',binding),('lock',object())):
            with self.subTest(field=field):
                previous=getattr(source,field);self.runtime.proof_cache=None
                def decoded(*args,**kwargs):
                    value=actual(*args,**kwargs);setattr(source,field,foreign);return value
                try:
                    with patch.object(self.runtime,'_validate_original',decoded):
                        with self.assertRaises(NativeUIError):
                            with self.runtime.image_observation_context(self.original,self.b.root):
                                self.fail('A swapped live source must not issue an image context')
                finally:setattr(source,field,previous)
        self.assertEqual(self.commands,len(self.b.commands))

    def test_observation_proof_cache_hit_has_no_context_and_uses_original_tail_path(self):
        self.runtime.validate_original(self.original)
        with self.owners() as owners:
            with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
                self.assertEqual(self.runtime.validate_tail_source,tail)
                tail(self.tail);self.assertEqual(1,len(owners))
        self.assertEqual(self.commands,len(self.b.commands))

    def test_foreign_role_and_frame_never_inherit_current_context(self):
        with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
            foreign=deepcopy(self.tail);foreign['observation']['role']='actor'
            with self.assertRaises(NativeUIError):tail(foreign)
            foreign=deepcopy(self.tail);foreign['observation']['reference']['sha256']='c'*64
            with self.assertRaises(NativeUIError):tail(foreign)
        self.assertEqual(self.commands,len(self.b.commands))

    def test_retained_owner_role_mutation_is_rejected_before_prefix_reuse(self):
        with self.assertRaises(NativeUIError):
            with self.owners() as owners:
                with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
                    self.assertEqual(1,len(owners));owners[0].role='actor';tail(self.tail)
        self.assertEqual(self.commands,len(self.b.commands))

    def test_owner_header_alias_swap_cannot_select_another_journal(self):
        with self.assertRaises(NativeUIError):
            with self.owners() as owners:
                with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
                    owner=owners[0];owner.store=PrivateFeatureState(self.b.root/('tabletweb-context-'+owner.run+'-'+owner.role+'.json'))
                    tail(self.tail)
        self.assertEqual(self.commands,len(self.b.commands))

    def test_same_bytes_child_inode_replacement_during_actual_read_invalidates_context(self):
        actual=OriginalFrameStore.read;changed=[]
        with self.assertRaises(NativeUIError):
            with self.owners() as owners:
                with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
                    child=owners[0].children['trace'];path=child.store.path;inode=path.stat().st_ino
                    def read(store,value):
                        result=actual(store,value)
                        if not changed:
                            saved=child.store.read();child.store.write(saved,saved);changed.append(path.stat().st_ino)
                        return result
                    with patch.object(OriginalFrameStore,'read',read):tail(self.tail)
        self.assertEqual(1,len(changed));self.assertNotEqual(inode,changed[0])
        self.assertEqual(self.commands,len(self.b.commands))


if __name__=='__main__':unittest.main()
