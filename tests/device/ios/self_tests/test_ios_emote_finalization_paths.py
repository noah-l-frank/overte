"""A saved archive cannot introduce extra or reordered metadata delete paths."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_feature import IOSEmoteFeature
from ios.adapters.emote_finalization import IOSEmoteFinalization
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class FinalizationPathTests(unittest.TestCase):
    def test_foreign_extra_or_reordered_copies_are_refused_before_any_native_proof_or_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);root.chmod(0o700)
            flow=object.__new__(IOSEmoteFeature);flow.role='primary';flow.run=RUN;flow.root=root
            flow.selector=flow.primary_selector='primary';flow.policy={'source':'world-render-target'}
            flow.phase=SimpleNamespace(fixture_url='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/')
            flow.runtime=SimpleNamespace(state_path=lambda _:root/'session.json');flow.state={'binding':BINDING}
            flow.store=PrivateFeatureState(root/'ios-emote-primary-feature.json')
            final=IOSEmoteFinalization(flow);paths=final.paths(lambda _:None)
            copies={str(path.path):None for path in paths}
            copies[str(flow.store.path)]=flow.envelope(dict(phase='cleaned',retirement={'original':{}},cleanup=[{}]))
            foreign=root/'unrelated.json';foreign.write_bytes(b'{"mustRemain":true}');foreign.chmod(0o600)
            extra=dict(copies);extra[str(foreign)]={'mustRemain':True}
            reordered=dict(reversed(list(copies.items())))
            for altered in (extra,reordered):
                with self.subTest(kind='extra' if altered is extra else 'reordered'):
                    with patch.object(final,'owner',side_effect=AssertionError('Unqualified paths reached the native decoder')) as decoder:
                        with self.assertRaises(NativeUIError):final.decode(altered)
                        decoder.assert_not_called()
                    self.assertEqual(b'{"mustRemain":true}',foreign.read_bytes())
