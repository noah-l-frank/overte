"""Real orphan cues and original canonical budget cannot start SDK cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.adapters.tablet_web_session_cleanup import retire_existing,session_entry


class TabletCanonicalCleanupTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name);self.root.chmod(0o700)
        def forbidden(*_args,**_kwargs):raise AssertionError('Unqualified ownership cannot query/create/Stop/delete SDK')
        self.adapter=SimpleNamespace(state_path=lambda _selector:self.root/'session.json',_candidate_guard=forbidden,_binding=forbidden,
            read_session=forbidden,_binding_store=forbidden,_retired_candidate_scope=forbidden)
        self.runtime=IOSTabletWebRuntime(self.adapter)
    def test_no_tablet_owner_leaves_original_other_feature_cleanup_untouched_without_sdk_admission(self):
        PrivateFeatureState(self.root/'actual-other-feature.json').write(dict(otherOwner=True),None)
        self.assertIsNone(retire_existing(self.runtime,'private-existing-selector',None))
    def test_unknown_prefix_or_empty_owned_directory_stays_owned_and_blocks_normal_stop(self):
        for directory in (False,True):
            with self.subTest(directory=directory):
                path=self.root/('tabletweb-orphan-directory' if directory else 'tabletweb-orphan-original.json')
                if directory:path.mkdir(mode=0o700)
                else:PrivateFeatureState(path).write(dict(actualUnknownOwner=True),None)
                with self.assertRaises(NativeUIError):retire_existing(self.runtime,'private-existing-selector',None)
                self.assertTrue(path.exists())
                if directory:path.rmdir()
                else:path.unlink()
    def test_malformed_archive_marker_is_not_a_native_end_and_no_file_is_discarded(self):
        path=self.root/('tabletweb-final-archive-'+'a'*32+'.json');PrivateFeatureState(path).write(dict(complete=True),None)
        before=path.stat(),path.read_bytes()
        with self.assertRaises(NativeUIError):retire_existing(self.runtime,'private-existing-selector',None)
        self.assertEqual(before,(path.stat(),path.read_bytes()))
    def test_slow_ownership_scan_uses_original_started_budget_before_any_cleanup_callback(self):
        PrivateFeatureState(self.root/'tabletweb-actual-pending.json').write(dict(issued=True),None)
        calls=[];times=iter((0.,61.))
        wrapped=session_entry(lambda *_args:calls.append('forbidden cleanup'),monotonic=lambda:next(times))
        with patch('ios.adapters.feature_configuration.configuration',return_value=None),self.assertRaises(NativeUIError):wrapped(self.adapter,'private-existing-selector')
        self.assertEqual([],calls)
    def test_no_owner_keeps_default_callback_behavior_and_does_not_create_ownership(self):
        wrapped=session_entry(lambda *_args:{'originalOtherCleanup':True},monotonic=lambda:0.)
        with patch('ios.adapters.feature_configuration.configuration',return_value=None):self.assertEqual({'originalOtherCleanup':True},wrapped(self.adapter,'private-existing-selector'))
        self.assertEqual([],list(self.root.iterdir()))


if __name__=='__main__':unittest.main()
