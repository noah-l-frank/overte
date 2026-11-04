"""Warm pure PNG decoding with fresh original storage/clock checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.graphics_journey import originals
from adapters.normal_ui import NativeUIError
from self_tests import test_graphics_originals as source_fixture
from self_tests.test_pico_browser_stereo import Model,TICKET


class BrowserPngMemoTests(unittest.TestCase):
    def fixture(self):
        helper=source_fixture.GraphicsOriginalTests('runTest');helper.setUp();self.addCleanup(helper.doCleanups)
        image=helper.image()
        return helper,image

    def reader(self,helper,*,memo=None):
        return originals.GraphicsOriginals(helper.root,helper.body['binding'],helper.body['runId'],'primary',0,
            lambda:helper.okay,lambda _:False,monotonic=lambda:helper.clock,pixel_memo=memo)

    def test_explicit_memo_decodes_once_while_default_still_decodes_every_read(self):
        helper,image=self.fixture();memo=originals.GraphicsOriginalPixels();reader=self.reader(helper,memo=memo)
        with patch.object(originals,'original_pixels',wraps=originals.original_pixels) as decode:
            self.assertEqual(helper.raw,reader.read(image));self.assertEqual(helper.raw,reader.read(image))
            self.assertEqual(1,decode.call_count)
            self.assertEqual(helper.raw,helper.writer.read(image));self.assertEqual(helper.raw,helper.writer.read(image))
            self.assertEqual(3,decode.call_count)
        self.assertIs(type(memo.key),bytes);self.assertIs(memo.key,memo._key);self.assertLess(len(memo.key),1024)

    def test_changed_raw_or_pixel_header_cannot_reuse_a_successful_decode(self):
        helper,image=self.fixture();memo=originals.GraphicsOriginalPixels();reader=self.reader(helper,memo=memo)
        reader.read(image);known=memo.key;path=helper.root/image['name'];raw=path.read_bytes()
        path.write_bytes(raw[:-1])
        with self.assertRaises(NativeUIError):reader.read(image)
        path.write_bytes(raw)
        changed=deepcopy(image);changed['capture']['source']['image']['pixelSha256']='0'*64
        with patch.object(originals,'original_pixels',wraps=originals.original_pixels) as decode:
            with self.assertRaises(NativeUIError):reader.read(changed)
            self.assertEqual(1,decode.call_count)
        self.assertIs(known,memo.key)

    def test_warm_decode_keeps_guard_budget_mode_inode_and_all_actual_bytes_required(self):
        helper,image=self.fixture();reader=self.reader(helper,memo=originals.GraphicsOriginalPixels());reader.read(image)
        helper.okay=False
        with self.assertRaises(NativeUIError):reader.read(image)
        helper.okay=True
        def late():helper.clock+=6;return True
        reader.guard=late
        with self.assertRaises(NativeUIError):reader.read(image)
        reader.guard=lambda:True;path=helper.root/image['name'];path.chmod(0o644)
        with self.assertRaises(NativeUIError):reader.read(image)
        path.chmod(0o600);old=helper.root/'preserved.png';path.rename(old);path.write_bytes(helper.raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):reader.read(image)
        self.assertEqual(helper.raw,old.read_bytes());self.assertEqual(helper.raw,path.read_bytes())

    def test_failed_first_decode_does_not_create_a_success_key_or_permit_foreign_memo(self):
        helper,image=self.fixture();memo=originals.GraphicsOriginalPixels();reader=self.reader(helper,memo=memo)
        with patch.object(originals,'original_pixels',side_effect=NativeUIError('Original pixel decode refused')):
            with self.assertRaises(NativeUIError):reader.read(image)
        self.assertIsNone(memo.key);self.assertEqual(helper.raw,reader.read(image))
        reader.pixel_memo=originals.GraphicsOriginalPixels()
        with self.assertRaises(NativeUIError):reader.read(image)
        with self.assertRaises(NativeUIError):self.reader(helper,memo=True)

    def test_memo_key_mutation_refuses_and_metadata_uses_full_original_validator(self):
        helper,image=self.fixture();memo=originals.GraphicsOriginalPixels();reader=self.reader(helper,memo=memo);reader.read(image)
        memo.key=b'foreign'
        with self.assertRaises(NativeUIError):reader.read(image)
        metadata=helper.metadata();reader=self.reader(helper,memo=originals.GraphicsOriginalPixels())
        self.assertEqual((helper.root/metadata['name']).read_bytes(),reader.read(metadata))
        wrong=deepcopy(metadata);wrong['sha256']='0'*64
        with self.assertRaises(NativeUIError):reader.read(wrong)

    def test_actual_pico_stereo_shares_one_key_across_writer_and_passive_retirement_reads(self):
        model=Model();self.addCleanup(model.close);owner=model.browser_stereo()
        with patch.object(originals,'original_pixels',wraps=originals.original_pixels) as decode:
            state=owner.acquire(TICKET);self.assertEqual('complete',state['phase']);self.assertEqual(1,decode.call_count)
            raw=owner.image_bytes();self.assertEqual(raw,owner.image_bytes());self.assertEqual(1,decode.call_count)
        self.assertIs(owner.images.pixel_memo,owner.archival_images.pixel_memo)
        self.assertIs(owner.pixel_memo,owner.images.pixel_memo)
        self.assertEqual([],list(model.native_root.iterdir()))
        self.assertIsNone(model.owner_store('primary').read())

    def test_actual_warm_stereo_rejects_identical_bytes_on_a_foreign_inode_without_new_capture(self):
        model=Model();self.addCleanup(model.close);owner=model.browser_stereo();state=owner.acquire(TICKET)
        path=owner.images.root/state['image']['name'];raw=path.read_bytes();old=path.with_suffix('.preserved')
        path.rename(old);path.write_bytes(raw);path.chmod(0o600);commands=len(model.gpu.commands)
        with self.assertRaises(NativeUIError):owner.image_bytes()
        self.assertEqual(commands,len(model.gpu.commands));self.assertEqual(raw,old.read_bytes());self.assertEqual(raw,path.read_bytes())


if __name__=='__main__':unittest.main()
