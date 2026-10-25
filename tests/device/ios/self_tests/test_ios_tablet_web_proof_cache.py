"""Real private inventory/read membership bounds historical proof reuse."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from ios.adapters.tablet_web_proof_cache import TabletPublicationProofCache


class TabletProofCacheTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,targetFingerprint='c'*64,
            sessionId='existing-only',generation=1,processIdentity='42')
        self.cache=TabletPublicationProofCache([self.root],self.binding,'d'*32,'actor')
        self.store=PrivateFeatureState(self.root/'actual-original.json');self.store.write(dict(actual=1),None)
        self.calls=0;self.seal=dict(actualBootstrap='e'*32);self.value=dict(original='f'*32)
    def decoder(self,value):
        self.calls+=1;actual=self.store.read();need(actual=={'actual':1})
        pending=PrivateFeatureState(self.root/'actual-failed-prefix.json').read();need(pending is None)
        return dict(original=deepcopy(value),actual=actual)
    def read(self):return self.cache.decode(self.value,self.seal,self.decoder)
    def test_successful_full_decoder_reused_only_with_actual_read_membership_and_unchanged_inventory(self):
        with scope() as first:answer=self.read()
        self.assertEqual({self.store.path},first)
        answer['actual']['actual']=9
        with scope() as second:again=self.read()
        self.assertEqual(first,second);self.assertEqual(1,self.calls);self.assertEqual(1,again['actual']['actual'])
    def test_new_failed_prefix_invalidates_previous_success_and_never_caches_failure(self):
        self.read();pending=PrivateFeatureState(self.root/'actual-failed-prefix.json');pending.write(dict(status='failed'),None)
        for _ in range(2):
            with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(3,self.calls)
    def test_publisher_cas_may_change_but_original_decoder_cannot_read_excluded_path(self):
        self.read();publisher=PrivateFeatureState(self.cache.publisher);publisher.write(dict(issued=True),None)
        self.read();self.assertEqual(1,self.calls)
        def forbidden(value):publisher.read();return dict(value)
        with self.assertRaises(NativeUIError):self.cache.decode(dict(other=1),self.seal,forbidden)
        publisher.discard(publisher.read());self.read();self.assertEqual(1,self.calls)
    def test_same_bytes_new_inode_and_mode_changes_force_actual_decoder_not_old_success(self):
        self.read();raw=self.store.path.read_bytes();old=self.root/'old-inode';self.store.path.rename(old)
        self.store.path.write_bytes(raw);self.store.path.chmod(0o600);old.unlink();self.read();self.assertEqual(2,self.calls)
        self.store.path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(3,self.calls)
    def test_hardlink_is_refused_before_any_cached_result_can_return(self):
        self.read();os.link(self.store.path,self.root/'alias')
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,self.calls)
    def test_external_read_has_no_reuse_without_independent_actual_root_lease(self):
        external=tempfile.TemporaryDirectory();self.addCleanup(external.cleanup);root=Path(external.name);root.chmod(0o700)
        store=PrivateFeatureState(root/'actual-screen.json');store.write(dict(actual='png'),None)
        calls=[]
        def decode(value):calls.append(value);return store.read()
        self.cache.decode(self.value,self.seal,decode);self.cache.decode(self.value,self.seal,decode);self.assertEqual(2,len(calls))
        cache=TabletPublicationProofCache([self.root,root],self.binding,'d'*32,'actor')
        cache.decode(self.value,self.seal,decode);cache.decode(self.value,self.seal,decode);self.assertEqual(3,len(calls))
        old=store.read();store.write(dict(actual='different-png'),old)
        self.assertEqual({'actual':'different-png'},cache.decode(self.value,self.seal,decode));self.assertEqual(4,len(calls))
    def test_actual_context_mutation_invalidates_even_with_identical_original_files(self):
        self.read();self.seal['actualBootstrap']='1'*32;self.read();self.assertEqual(2,self.calls)
    def test_mutation_during_full_decode_never_mints_reusable_success(self):
        def changed(value):
            answer=self.decoder(value);PrivateFeatureState(self.root/'new-pending.json').write(dict(issued=True),None);return answer
        with self.assertRaises(NativeUIError):self.cache.decode(self.value,self.seal,changed)
        self.assertEqual({},self.cache.values)


if __name__=='__main__':unittest.main()
