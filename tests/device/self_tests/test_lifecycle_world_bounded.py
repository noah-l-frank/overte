"""Opt-in early Base64 refusal retains the actual existing World2 bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_world_codec as codec
from adapters.script_journey import history
from self_tests import test_pico_lifecycle_world as world_fixture


class LifecycleWorldBoundedCodecTests(unittest.TestCase):
    def test_actual_normal_world_history_and_unicode_keep_identical_default_payload_bytes(self):
        fixture=world_fixture.LifecycleWorldTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        owner=fixture.started();owner.world_input();owner.release()
        corpus=[[deepcopy(owner.state)],[dict(text='Grüße Ω 東京 🐧',values=[None,True,1,1.5])]]
        for frames in corpus:
            for version in (1,2):
                with self.subTest(version=version,frames=len(frames)):
                    old=codec.pack(frames,version);bounded=codec.pack(frames,version,bounded=True)
                    self.assertEqual(old,bounded);self.assertEqual(history.canonical(old),history.canonical(bounded))
                    self.assertEqual(frames,codec.unpack(bounded,version))

    def test_real_incompressible_xz_refuses_before_base64_only_in_explicit_mode(self):
        frames=[''.join(hashlib.sha256(str(index).encode()).hexdigest() for index in range(2000))]
        compress=codec.lzma.compress;encode=codec.base64.b64encode
        actual=compress(history.canonical(frames),format=codec.lzma.FORMAT_XZ,preset=3)
        self.assertGreater(4*((len(actual)+2)//3),history.MAX_PACKED)
        with patch.object(codec.lzma,'compress',wraps=compress) as compressed,\
                patch.object(codec.base64,'b64encode',wraps=encode) as encoded,self.assertRaises(NativeUIError):
            codec.pack(frames,2,bounded=True)
        self.assertEqual(1,compressed.call_count);encoded.assert_not_called()
        with patch.object(codec.base64,'b64encode',wraps=encode) as encoded,self.assertRaises(NativeUIError):
            codec.pack(frames,2)
        self.assertEqual(1,encoded.call_count)

    def test_bounded_mode_aliases_refuse_before_compression_or_base64(self):
        for alias in (None,0,1,'true',[],{}):
            with self.subTest(alias=repr(alias)),patch.object(codec.lzma,'compress') as compressed,\
                    patch.object(codec.base64,'b64encode') as encoded,self.assertRaises(NativeUIError):
                codec.pack([dict(value='actual')],2,bounded=alias)
            compressed.assert_not_called();encoded.assert_not_called()


if __name__=='__main__':unittest.main()
