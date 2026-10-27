"""Actual original Model decoder dataflow with hostile parent/hook boundaries.

QML/backend/native preparation retains the existing declared host models.
Each assertion afterward is pure; no query, write, new clocks or retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_creation_round import ModelCreationRound,eligible
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters import assets_model_origin as origin
from ios.self_tests.assets_parsed_fixture import Fixture


class AssetsModelCreationRoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory();cls.addClassCleanup(temporary.cleanup)
        cls.path=Path(temporary.name);cls.path.chmod(0o700);cls.f=Fixture(cls.path);cls.addClassCleanup(cls.f.close)
        patched=patch('adapters.asset_backend_client.build_opener',return_value=cls.f);patched.start();cls.addClassCleanup(patched.stop)
        cls.model,cls.baking=cls.f.prepared();cls.parsed=cls.f.parsed(cls.model,cls.baking);cls.parsed.reserve();cls.parsed.observe()
        cls.source=cls.parsed.sources;cls.source.capture(cls.source.epoch_ms())

    def setUp(self):
        self.native=deepcopy(self.f.boundary.native_clock.commands);self.inputs=deepcopy(self.f.boundary.inputs);self.requests=deepcopy(self.f.requests)

    def tearDown(self):
        self.assertEqual(self.native,self.f.boundary.native_clock.commands);self.assertEqual(self.inputs,self.f.boundary.inputs);self.assertEqual(self.requests,self.f.requests)

    def test_full_model_is_decoded_once_inside_one_decoder_but_public_frames_stay_full(self):
        self.assertTrue(eligible(self.source));calls=[];code=OwnedAssetsModel.decode.__code__
        def profile(frame,event,arg):
            if event=='call' and frame.f_code is code and frame.f_locals.get('self') is self.model:calls.append(1)
        previous=sys.getprofile();sys.setprofile(profile)
        try:
            with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure decoder write')):
                state=self.source.decode(self.source.previous)
        finally:sys.setprofile(previous)
        self.assertEqual(self.source.state,state);self.assertEqual(1,len(calls))
        frame=self.source._cached[0]
        with patch.object(self.model,'decode',wraps=self.model.decode) as decode:
            self.source.frame(frame);decode.assert_called_once()

    def test_changed_parent_file_and_wal_cannot_reuse_or_exit_a_live_round(self):
        paths=[self.model.sources.originals.path(self.model.sources.originals.expand(self.model.sources.state['frames'][0])),self.model.store.path]
        for path in paths:
            round_=ModelCreationRound(self.source);raw=path.read_bytes();inode=path.stat().st_ino
            try:
                path.write_bytes(b'{}')
                with self.subTest(path=path.name),self.assertRaises(NativeUIError):round_.check()
            finally:
                path.write_bytes(raw)
                with self.assertRaises(NativeUIError):round_.close()
            self.assertEqual(inode,path.stat().st_ino);self.assertFalse(round_.active)

    def test_changed_parent_memory_and_parser_or_frame_hook_cannot_reuse_a_live_round(self):
        round_=ModelCreationRound(self.source);original=deepcopy(self.model.state)
        try:
            self.model.state['phase']='reserved'
            with self.assertRaises(NativeUIError):round_.check()
        finally:self.model.state=original;round_.close()
        for target,name in ((origin,'validate'),(self.source,'frame')):
            round_=ModelCreationRound(self.source)
            with patch.object(target,name,wraps=getattr(target,name)),self.assertRaises(NativeUIError):round_.check()
            round_.close()

    def test_private_and_public_frame_overrides_use_the_existing_full_decoder(self):
        for name in ('frame','_origin_frame'):
            with (patch.object(self.source,name,wraps=getattr(self.source,name)) as hook,
                    patch.object(self.model,'decode',wraps=self.model.decode) as model):
                self.source.decode(self.source.previous)
                self.assertEqual(len(self.source.state['frames']),hook.call_count);self.assertEqual(len(self.source.state['frames']),model.call_count)

    def test_current_guard_and_closed_round_are_never_reused(self):
        round_=ModelCreationRound(self.source);self.f.boundary.live=False
        try:
            with self.assertRaises(NativeUIError):round_.check()
        finally:self.f.boundary.live=True;round_.close()
        self.assertIsNone(round_.creation)
        with self.assertRaises(NativeUIError):round_.check()

    def test_historical_missing_context_and_dirty_parent_are_literal_fallbacks(self):
        previous=self.model.sources.previous;state=deepcopy(self.model.usage.source.state)
        try:
            del self.model.sources.previous;self.assertFalse(eligible(self.source))
            self.model.sources.previous=previous;self.model.usage.source.state['aborted']=not state['aborted']
            self.assertFalse(eligible(self.source))
        finally:self.model.sources.previous=previous;self.model.usage.source.state=state
