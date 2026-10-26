"""Actual original manifest/file continuity; native source producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager,nullcontext
import time
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope
from ios.adapters.avatar_observation import _AppearanceFrames,frame
from ios.self_tests.test_ios_avatar_sources import AvatarSourcesTests


@contextmanager
def actual_reads(sources):
    """Observe real reads without enabling original membership collection."""
    paths=set();private=PrivateFeatureState.read;original=sources.originals.read
    def metadata(store):
        value=private(store);paths.add(store.path);return value
    def frame_read(reference):
        value=original(reference);paths.add(sources.originals.path(reference));return value
    with patch.object(PrivateFeatureState,'read',metadata),patch.object(sources.originals,'read',side_effect=frame_read):yield paths


def coherent_native_producer(fixture):
    # Configure new native-boundary producers before their first acquisition.
    # The generic source fixture deliberately does not promise cross-channel
    # appearance coherence or a fresh repeated Rig evaluation.
    state=fixture.prototypes['state']['source']
    row=next(row for row in fixture.prototypes['renderers']['source']['avatars'] if row['self'])
    for key in ('requestedUrl','resourceUrl','geometryLoaded','rigReady','shouldRender','targetScale','modelScale'):row[key]=deepcopy(state[key])
    def observed(name,value):
        if name=='renderers':
            for row in value['source']['avatars']:
                pose=row['rigPose'] if row['self'] else row['externalPose']
                pose['capturedEpochMs']=value['clockBefore']['epochMs']
                pose['evaluationSequence']=100+value['sequence']
    fixture.mutate=observed


class AvatarManifestFrameTests(unittest.TestCase):
    collector=True
    def setUp(self):
        self.f=AvatarSourcesTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        coherent_native_producer(self.f.fixture)
        self.enterContext(self.f.lock.held());self.live=self.f.owner()
        for _ in range(4):self.live.read()
        self.sources=self.f.owner(historical=True)
        if self.collector:self.enterContext(scope(fresh=True))
        self.reader=_AppearanceFrames(self.sources)
    def manifests(self):return sorted(self.sources.root.glob('avatar-index-sources-*.json'))
    def test_reuse_keeps_exact_manifest_membership_and_reopens_each_original_frame(self):
        calls=[];original=self.sources.originals.manifest;count=dict(self.f.fixture.sources)
        def read(ref):calls.append(deepcopy(ref));return original(ref)
        with patch.object(self.sources.originals,'manifest',side_effect=read):
            with scope(fresh=True) as first:a=self.reader(1)
            with scope(fresh=True) as last:b=self.reader(4)
            self.reader.verify()
        self.assertEqual(2,len(calls));self.assertEqual(self.sources.frames[0],a);self.assertEqual(self.sources.frames[-1],b)
        self.assertTrue(set(self.manifests())<=first and set(self.manifests())<=last)
        first_path=self.sources.originals.path(self.sources.originals.expand(self.sources.originals.manifest(self.sources.state['manifests'][0])[0]))
        self.assertIn(first_path,first);self.assertNotIn(first_path,last)
        self.assertEqual(count,self.f.fixture.sources)
        a['originals']['state']['source']['geometryLoaded']=False
        self.assertEqual(self.sources.frames[0],self.reader(1))
    def test_same_inode_same_bytes_manifest_rewrite_is_not_a_cached_original(self):
        self.reader(1);path=self.sources.originals.manifest_path(self.sources.state['manifests'][0]);before=path.stat();raw=path.read_bytes();path.write_bytes(raw)
        self.assertEqual(before.st_ino,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.reader(4)
    def test_original_frame_tampering_is_rechecked_even_with_warm_manifest(self):
        self.reader(1);ref=self.sources.originals.manifest(self.sources.state['manifests'][0])[-1]
        path=self.sources.originals.path(self.sources.originals.expand(ref));raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaises(NativeUIError):self.reader(4)
    def test_missing_legacy_prefix_cannot_become_an_unchecked_dangling_link(self):
        path=self.manifests()[0];path.unlink();self.reader(1)
        path.symlink_to(self.sources.root/'missing-private-original')
        self.assertFalse(path.exists())
        with self.assertRaises(NativeUIError):self.reader(4)
    def test_actual_bound_role_and_binding_cannot_be_rebound_during_the_scope(self):
        self.reader(1);original=self.sources.binding
        self.sources.binding=dict(original,artifactSha256='f'*64)
        with self.assertRaises(NativeUIError):self.reader(4)
        self.sources.binding=original;self.sources.role='actor'
        with self.assertRaises(NativeUIError):self.reader(4)
    def test_in_memory_source_mutation_and_final_manifest_mutation_both_refuse(self):
        self.reader(1);self.sources.frames[-1]['originals']['state']['source']['geometryLoaded']=False
        with self.assertRaises(NativeUIError):self.reader(4)
        path=self.sources.originals.manifest_path(self.sources.state['manifests'][0]);path.write_bytes(path.read_bytes())
        with self.assertRaises(NativeUIError):self.reader.verify()
    def test_slow_index_reuse_preserves_the_existing_five_second_file_budget(self):
        store=self.sources.originals;now=[0.];store.clock=None;store.monotonic=lambda:now[0]
        self.reader(1);original=self.reader.cache.signatures
        def slow(paths):now[0]=5.;return original(paths)
        with patch.object(self.reader.cache,'signatures',side_effect=slow),self.assertRaises(NativeUIError):self.reader(4)


class AvatarPlainManifestFrameTests(AvatarManifestFrameTests):
    collector=False
    def test_reuse_keeps_exact_manifest_membership_and_reopens_each_original_frame(self):
        from adapters.original_file_reads import active
        self.assertFalse(active());calls=[];original=self.sources.originals.manifest;count=dict(self.f.fixture.sources)
        def read(ref):calls.append(deepcopy(ref));return original(ref)
        with patch.object(self.sources.originals,'manifest',side_effect=read):
            a=self.reader(1);b=self.reader(4);self.reader.verify()
        self.assertFalse(active());self.assertEqual(2,len(calls));self.assertEqual(self.sources.frames[0],a)
        self.assertEqual(self.sources.frames[-1],b);self.assertEqual(count,self.f.fixture.sources)
    def test_missing_legacy_prefix_cannot_become_an_unchecked_dangling_link(self):
        # Plain OriginalFrameStore.manifest never reads older prefixes. This
        # memo preserves that exact read set; full collectors still reject it.
        path=self.manifests()[0];path.unlink();self.reader(1)
        path.symlink_to(self.sources.root/'missing-private-original')
        self.assertEqual(self.sources.frames[-1],self.reader(4));self.reader.verify()
    def test_immutable_store_path_and_actual_parent_identity_cannot_be_rebound(self):
        self.reader(1);old=self.sources.store.path;self.sources.store.path=old.with_name('foreign-source.json')
        with self.assertRaises(NativeUIError):self.reader(4)
        self.sources.store.path=old;root=self.sources.root;moved=root.with_name(root.name+'-moved')
        root.rename(moved);root.mkdir(mode=0o700)
        for path in moved.iterdir():path.rename(root/path.name)
        with self.assertRaises(NativeUIError):self.reader(4)
    def test_traversal_cannot_switch_collector_mode_after_its_first_actual_read(self):
        self.reader(1)
        with scope(fresh=True),self.assertRaises(NativeUIError):self.reader(4)


class AvatarManifestFrameBenchmarkTests(unittest.TestCase):
    def test_fresh_thirtytwo_and_sixtyfour_frame_graphs_keep_native_queries_and_original_files_unchanged(self):
        f=AvatarSourcesTests();f.setUp();self.addCleanup(f.doCleanups)
        coherent_native_producer(f.fixture)
        with f.lock.held():
            live=f.owner()
            for count in (32,64):
                while len(live.frames)<count:live.read()
                sources=f.owner(historical=True);paths=list(sources.root.iterdir())
                original_files={path:(path.stat().st_ino,digest(path.read_bytes().hex())) for path in paths if path.is_file()}
                query_count=dict(f.fixture.sources)
                for collected in (False,True):
                    measurements={};expected=None
                    for label,read in (('plain',lambda index:frame(sources,index)),('scoped',_AppearanceFrames(sources))):
                        started=time.perf_counter()
                        with actual_reads(sources) as reads:
                            with scope(fresh=True) if collected else nullcontext(set()) as membership:
                                actual=[digest(read(index)) for index in range(1,count+1)]
                                if label=='scoped':read.verify()
                        measurements[label]=time.perf_counter()-started
                        if expected is None:expected=actual;expected_members=set(membership);expected_reads=set(reads)
                        else:
                            self.assertEqual(expected,actual);self.assertEqual(expected_members,membership);self.assertEqual(expected_reads,reads)
                    self.assertEqual(original_files,{path:(path.stat().st_ino,digest(path.read_bytes().hex())) for path in paths if path.is_file()})
                    self.assertEqual(query_count,f.fixture.sources)
                    print('Avatar raw manifest replay collector='+str(collected)+' frames='+str(count)+' files='+str(len(original_files))
                        +' plain='+format(measurements['plain'],'.6f')+' scoped='+format(measurements['scoped'],'.6f')
                        +' nativeQueries=0 originalFilesUnchanged=true readSetsIdentical=true',flush=True)


class AvatarAppearanceCollectorTests(unittest.TestCase):
    def test_normal_avatar_effect_is_identical_in_plain_and_complete_original_membership_traversals(self):
        from ios.self_tests.test_ios_avatar_observation import AvatarObservationTests
        f=AvatarObservationTests();f.setUp();self.addCleanup(f.doCleanups)
        plain=f.act('avatar-url',dict(resource='avatar-a.fst'),1)
        before=deepcopy(f.fixture.fixture.sources)
        with scope(fresh=True) as originals:collected=f.measure()
        self.assertEqual(plain,collected);self.assertEqual('A',collected['state']['avatar'])
        self.assertEqual(before,f.fixture.fixture.sources)
        self.assertTrue(any(path.name.startswith('avatar-frame-sources-') for path in originals))
        self.assertTrue(any(path.name.startswith('avatar-index-sources-') for path in originals))
