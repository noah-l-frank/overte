"""Private original JSON bytes, identities and manifests; no native/device run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.normal_ui import NativeUIError
from overte_phone_emote_originals import PhoneEmoteOriginals,BLOCK,MAX_FRAMES,LIMIT
from test_graphics_images import BINDING

RUN='d'*32


class EmoteOriginalsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-originals-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.clock=0.;self.okay=True;self.intents=[];self.fail=None
        self.store=self.owner()
    def owner(self,*,role='primary',binding=None,kind='sources'):
        return PhoneEmoteOriginals(self.root,BINDING if binding is None else binding,RUN,role,lambda:self.okay,
            self.intent,kind=kind,monotonic=lambda:self.clock)
    def intent(self,kind,value):
        self.intents.append((kind,deepcopy(value)))
        if self.fail==(kind,value['phase']):raise NativeUIError('Synthetic durable evidence intent failure')
    def test_original_bytes_identity_and_manifest_survive_reconstruction_without_retiming(self):
        value=dict(originalEpochMs=20000,sourceSequence=9,opaque='Original ä Ω 東京')
        descriptor=self.store.write(1,value);references=self.store.append([],descriptor)
        self.assertEqual([value],self.owner().restore(references,1));self.assertEqual(5,len(self.intents))
        self.assertEqual(['planned','opened','saved','planned','saved'],[row['phase'] for _kind,row in self.intents])
        value['originalEpochMs']=30000
        self.assertEqual(20000,self.store.restore(references,1)[0]['originalEpochMs'])
    def test_large_original_does_not_expand_the_existing_private_metadata_size_limit(self):
        frame=dict(originalEpochMs=20000,opaque='a'*200000)
        descriptor=self.store.write(1,frame);references=self.store.append([],descriptor)
        self.assertGreater(descriptor['bytes'],65536);self.assertEqual([frame],self.owner().restore(references,1))
        self.assertLess(self.store.manifest_path(references[0]).stat().st_size,65536)
    def test_manifest_boundary_retains_all_originals_and_keeps_prior_indexes_immutable(self):
        references=[];earlier=None
        for index in range(1,BLOCK+2):
            references=self.store.append(references,self.store.write(index,dict(originalSequence=index)))
            if index==1:earlier=deepcopy(references)
        self.assertEqual(2,len(references));self.assertEqual(BLOCK,references[0]['count']);self.assertEqual(1,references[1]['count'])
        self.assertEqual([dict(originalSequence=1)],self.owner().restore(earlier,1))
        self.assertEqual([dict(originalSequence=index) for index in range(1,BLOCK+2)],self.owner().restore(references,BLOCK+1))
    def test_same_bytes_in_a_replacement_inode_are_not_the_original_file(self):
        descriptor=self.store.write(1,dict(originalEpochMs=20000));value=self.store.expand(descriptor);path=self.store.path(value)
        replacement=self.root/'replacement';replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        with self.assertRaises(NativeUIError):self.store.read(value)
    def test_missing_truncated_or_changed_original_bytes_are_unavailable(self):
        for fault in ('missing','truncated','changed'):
            with self.subTest(fault=fault):
                descriptor=self.store.write(len(self.intents)+1,dict(originalEpochMs=20000));value=self.store.expand(descriptor);path=self.store.path(value)
                if fault=='missing':path.unlink()
                elif fault=='truncated':path.write_bytes(b'{}')
                else:path.write_bytes(path.read_bytes().replace(b'20000',b'20001'))
                with self.assertRaises((OSError,NativeUIError)):self.store.read(value)
    def test_foreign_role_candidate_or_file_type_cannot_supply_originals(self):
        descriptor=self.store.write(1,dict(originalEpochMs=20000));value=self.store.expand(descriptor)
        for binding,role in ((BINDING,'actor'),(BINDING|dict(artifactSha256='f'*64),'primary')):
            with self.subTest(role=role,binding=binding['artifactSha256']),self.assertRaises(NativeUIError):self.owner(role=role,binding=binding).read(value)
        path=self.store.path(value);target=self.root/'foreign';path.rename(target);path.symlink_to(target)
        with self.assertRaises((OSError,NativeUIError)):self.store.read(value)
    def test_hardlink_and_public_permissions_cannot_supply_originals(self):
        descriptor=self.store.write(1,dict(originalEpochMs=20000));value=self.store.expand(descriptor);path=self.store.path(value)
        link=self.root/'other-link';os.link(path,link)
        with self.assertRaises(NativeUIError):self.store.read(value)
        link.unlink();path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.store.read(value)
    def test_existing_files_are_never_overwritten_even_with_identical_payloads(self):
        frame=dict(originalEpochMs=20000);descriptor=self.store.write(1,frame);references=self.store.append([],descriptor)
        with self.assertRaises(FileExistsError):self.store.write(1,frame)
        with self.assertRaises(NativeUIError):self.store.append([],descriptor)
        self.assertEqual([frame],self.store.restore(references,1))
    def test_manifest_corruption_wrong_count_or_foreign_reference_is_rejected(self):
        descriptor=self.store.write(1,dict(originalEpochMs=20000));references=self.store.append([],descriptor)
        for changed in (references[0]|dict(count=2),references[0]|dict(bytes=1),references[0]|dict(block=True)):
            with self.subTest(changed=changed),self.assertRaises((OSError,NativeUIError)):self.store.restore([changed],1)
        path=self.store.manifest_path(references[0]);path.write_text('{}\n')
        with self.assertRaises(NativeUIError):self.store.restore(references,1)
    def test_missing_original_cannot_be_registered_by_a_new_manifest(self):
        descriptor=self.store.write(1,dict(originalEpochMs=20000));self.store.path(self.store.expand(descriptor)).unlink()
        with self.assertRaises((OSError,NativeUIError)):self.store.append([],descriptor)
        self.assertEqual([],list(self.root.glob('emote-index-*')))
    def test_durable_opened_intent_precedes_bytes_and_is_preserved_on_write_failure(self):
        self.fail=('original','opened')
        with self.assertRaises(NativeUIError):self.store.write(1,dict(originalEpochMs=20000))
        kind,value=self.intents[-1];self.assertEqual('original',kind);self.assertEqual('opened',value['phase'])
        self.assertEqual(0,self.store.path(value).stat().st_size)
    def test_failed_plan_creates_no_file_and_failed_manifest_preserves_original_bytes(self):
        self.fail=('original','planned')
        with self.assertRaises(NativeUIError):self.store.write(1,dict(originalEpochMs=20000))
        self.assertEqual([],list(self.root.iterdir()));self.fail=None
        descriptor=self.store.write(1,dict(originalEpochMs=20000));self.fail=('manifest','planned')
        with self.assertRaises(NativeUIError):self.store.append([],descriptor)
        self.assertEqual(dict(originalEpochMs=20000),self.store.read(self.store.expand(descriptor)))
    def test_size_bounds_and_whole_io_deadline_apply_before_success(self):
        with self.assertRaises(NativeUIError):self.store.write(1,dict(opaque='x'*LIMIT))
        self.assertEqual([],self.intents)
        for index in (True,0,MAX_FRAMES+1):
            with self.subTest(index=index),self.assertRaises(NativeUIError):self.store.write(index,{})
        original=self.intent
        def late(kind,value):original(kind,value);self.clock+=6
        self.store.intent=late
        with self.assertRaises(NativeUIError):self.store.write(1,dict(originalEpochMs=20000))
        self.assertEqual([],list(self.root.iterdir()))
    def test_all_1024_originals_fit_bounded_metadata_without_dropping_history(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from overte_phone_script_history import pack
        references=[]
        for index in range(1,MAX_FRAMES+1):
            references=self.store.append(references,self.store.write(index,dict(originalSequence=index)))
        self.assertEqual(8,len(references));self.assertTrue(all(ref['count']==BLOCK for ref in references))
        metadata=PrivateFeatureState(self.root/'bounded-owner.json')
        metadata.write(dict(payload=pack([dict(revision=MAX_FRAMES,manifests=references)])),None)
        self.assertLess(metadata.path.stat().st_size,65536)
        restored=self.owner().restore(references,MAX_FRAMES)
        self.assertEqual(list(range(1,MAX_FRAMES+1)),[row['originalSequence'] for row in restored])
    def test_input_history_cannot_be_substituted_for_original_native_source_frames(self):
        descriptor=self.store.write(1,dict(originalEpochMs=20000));original=self.store.expand(descriptor)
        with self.assertRaises(NativeUIError):self.owner(kind='inputs').read(original)


if __name__=='__main__':unittest.main()
