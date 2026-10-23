"""Public terminal codecs cannot replace the actual private Worlds end graph."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys import terminal
from feature_journeys.witness import Client
from ios.adapters.navigation_canonical_end import verify
from ios.adapters.navigation_feature import IOSNavigationFeature
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from self_tests.test_feature_terminal import Boundary


class NavigationCanonicalEndTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        test=self
        class InertRuntime(IOSNavigationRuntime):
            def __init__(self):pass
            def state_path(self,_selector):return test.root/'sdk-session.json'
            def _sources(self,*_args,**_kwargs):test.fail('Canonical post-end guard attempted native/session acquisition')
        # Explicitly synthetic public End, accepted by the real common codec.
        # It carries no private native/PNG/OS/SDK originals for this owner.
        model=Boundary();model.journey().execute();self.end=deepcopy(model.reports[-1]['terminalRetirement']['end'])
        self.client=Client('http://127.0.0.1:9/feature-fixture/v1','a'*64)
        self.flow=IOSNavigationFeature(InertRuntime(),'owned',self.client,model.run,self.root)
        self.whole=NavigationWholeFeature(self.flow)
        self.call=dict(contractVersion=terminal.VERSION,runId=model.run,stage='finish',seal=deepcopy(self.end['seal']))
        self.result=dict(stage='finish',end=self.end);terminal.arguments('world-navigation',self.call);terminal.result('world-navigation',self.result)

    def test_valid_public_end_cannot_create_or_complete_missing_private_owners(self):
        before=set(self.root.iterdir())
        with patch.object(self.client,'request',side_effect=AssertionError('No fixture request')):
            with self.assertRaises(NativeUIError):verify(self.whole,self.call,self.result)
        # The actual source lock may be created; no end or SDK owner may be.
        self.assertEqual(before|{self.flow.lock.path},set(self.root.iterdir()))
        self.assertIsNone(PrivateFeatureState(self.root/'ios-navigation-final-archive.json').read())

    def test_forged_archive_markers_and_nonfinish_calls_cannot_skip_the_original_decoder(self):
        for name in ('ios-navigation-final-archive.json','ios-navigation-process-end.json','ios-navigation-session-end.json'):
            PrivateFeatureState(self.root/name).write(dict(forged=True),None)
        originals={path:path.read_bytes() for path in self.root.iterdir()}
        with patch.object(self.client,'request',side_effect=AssertionError('No fixture request')):
            with self.assertRaises(NativeUIError):verify(self.whole,self.call,self.result)
            with self.assertRaises(NativeUIError):verify(self.whole,dict(contractVersion=terminal.VERSION,runId=self.flow.run,stage='inspect'),self.result)
        self.assertEqual(originals,{path:path.read_bytes() for path in originals})


if __name__=='__main__':unittest.main()
