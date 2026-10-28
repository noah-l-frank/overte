"""Actual publisher file/HTTP ordering; original product observations modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.original_file_reads import scope as original_reads
from ios.adapters.emote_original_lease import EmoteOriginalLease
from self_tests import test_phase_witness_publisher as fixture
from self_tests.test_completed_frame_lease import BINDING


class WitnessDecodeContextTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.PhaseWitnessPublisherTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.source=PrivateFeatureState(self.f.root/'declared-immutable-source.json');self.source.write(dict(declaredCodecInput=True),None)
        self.active=0;self.entered=self.exited=0;self.fail_exit=False
    @contextmanager
    def pure_round(self):
        self.assertEqual(0,self.active);before=EmoteOriginalLease.signature(self.source.path.lstat())
        body=self.source.read();self.entered+=1;self.active+=1
        try:yield
        finally:
            try:
                need(self.source.read()==body and EmoteOriginalLease.signature(self.source.path.lstat())==before)
                if self.fail_exit:raise NativeUIError('Actual decoder round exit refused')
            finally:self.active-=1;self.exited+=1
    def owner(self):
        f=self.f
        return PhaseWitnessPublisher(PrivateFeatureState(f.root/('phase-publication-'+f.area+'-'+f.run+'-actor.json')),
            BINDING,f.phase,f.lock,lambda:f.okay,f.validate_original,decode_context=self.pure_round)
    def test_constructor_and_all_pending_wal_writes_and_actual_posts_follow_round_exit(self):
        f=self.f;write=PrivateFeatureState.write;request=f.actor.request;writes=[];posts=[]
        def writing(store,value,previous):
            if store.path.name.startswith('phase-publication-'):
                self.assertEqual(0,self.active);writes.append(store.path.name)
            return write(store,value,previous)
        def requesting(path,value=None,*args,**kwargs):
            if path.endswith('/samples') and value is not None:self.assertEqual(0,self.active);posts.append(deepcopy(value))
            return request(path,value,*args,**kwargs)
        with f.lock.held(),patch.object(PrivateFeatureState,'write',writing),patch.object(f.actor,'request',side_effect=requesting):
            owner=self.owner();self.assertTrue(writes)  # The constructor really saved its empty WAL.
            owner.publish(f.original(1));owner.publish(f.original(2))
            self.assertEqual(2,len(posts));self.assertEqual(2,len(owner.state['records']));self.assertGreater(self.entered,2)
            self.assertEqual(self.entered,self.exited);self.assertEqual(0,self.active)
    def test_round_exit_refusal_preserves_actual_previous_wal_and_prevents_next_post(self):
        f=self.f
        with f.lock.held():
            owner=self.owner();owner.publish(f.original(1));raw=owner.store.path.read_bytes();inode=owner.store.path.stat().st_ino
            self.fail_exit=True;posts,request=f.posts('normal')
            with patch.object(f.actor,'request',side_effect=request),self.assertRaises(NativeUIError):owner.publish(f.original(2))
            self.assertEqual([],posts);self.assertEqual(raw,owner.store.path.read_bytes());self.assertEqual(inode,owner.store.path.stat().st_ino)
            self.assertEqual(0,self.active);self.assertEqual(self.entered,self.exited)
    def test_legacy_default_and_archive_never_acquire_a_context_or_retime_originals(self):
        f=self.f
        with f.lock.held():
            legacy=f.owner();legacy.publish(f.original());value=deepcopy(legacy.previous);state=deepcopy(legacy.state)
            class LiteralArchive(PhaseWitnessPublisher):
                decode_context=staticmethod(lambda:(_ for _ in ()).throw(AssertionError('Historical archive acquired a context')))
            archived=LiteralArchive.archive(value,store=legacy.store,binding=BINDING,run=f.run,area=f.area,
                fixture_url=f.url,phase_instance=legacy.instance,validate_original=f.validate_original)
            self.assertEqual(state,archived);self.assertEqual(value,legacy.previous);self.assertEqual(0,self.entered)
            self.assertIsNone(legacy.decode_context)
    def test_fresh_membership_scopes_execute_the_real_context_reader_in_each_decode(self):
        f=self.f
        with f.lock.held():
            owner=self.owner();owner.publish(f.original());before=self.entered
            with original_reads(fresh=True) as first:owner.decode(owner.previous)
            with original_reads(fresh=True) as second:owner.decode(owner.previous)
            self.assertIn(self.source.path,first);self.assertIn(self.source.path,second)
            self.assertEqual(before+2,self.entered);self.assertEqual(self.entered,self.exited)
    def test_source_same_bytes_new_inode_or_same_inode_change_refuses_at_round_exit(self):
        f=self.f
        with f.lock.held():
            owner=self.owner();owner.publish(f.original());validate=owner.validate_original
            for mode in ('new-inode','same-inode'):
                altered=[]
                def changed(value):
                    result=validate(value)
                    if self.active and not altered:
                        altered.append(True);raw=self.source.path.read_bytes()
                        if mode=='new-inode':
                            other=self.source.path.with_suffix('.replacement');other.write_bytes(raw);other.chmod(0o600);other.replace(self.source.path)
                        else:self.source.path.write_bytes(raw+b'\n')
                    return result
                with self.subTest(mode=mode),patch.object(owner,'validate_original',side_effect=changed),self.assertRaises(NativeUIError):owner.decode(owner.previous)
                self.assertTrue(altered);self.assertEqual(0,self.active)


if __name__=='__main__':unittest.main()
