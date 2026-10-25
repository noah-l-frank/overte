"""Existing-owner cleanup cannot infer an end from a name or empty SDK slot."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_existing import finalize_existing,retire_existing


class AvatarExistingTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        def forbidden(*_args,**_kwargs):raise AssertionError('No SDK or target acquisition for unowned or malformed end')
        self.runtime=IOSAvatarRuntime(SimpleNamespace(state_path=lambda _:self.root/'session.json',
            _candidate_guard=forbidden,_binding=forbidden,_target=forbidden,_retired_candidate_scope=forbidden))

    def test_no_owned_original_keeps_generic_cleanup_available_without_any_sdk_probe(self):
        self.assertFalse(finalize_existing(self.runtime,'existing',None,None))
        self.assertIsNone(retire_existing(self.runtime,'existing',None,None))

    def test_orphan_carrier_keeps_responsibility_and_cannot_skip_generic_sdk_retirement(self):
        store=PrivateFeatureState(self.root/'avatar-unknown-original.json');store.write(dict(unknown=True),None)
        with self.assertRaises(NativeUIError):finalize_existing(self.runtime,'existing',None,None)
        self.assertEqual(dict(unknown=True),store.read())

    def test_malformed_named_feature_is_never_a_completed_end(self):
        store=PrivateFeatureState(self.root/'ios-avatar-primary-feature.json');store.write(dict(unknown=True),None)
        with self.assertRaises(NativeUIError):retire_existing(self.runtime,'existing',None,None)
        self.assertEqual(dict(unknown=True),store.read())


if __name__=='__main__':unittest.main()
