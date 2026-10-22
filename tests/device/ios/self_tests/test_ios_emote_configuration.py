"""Private configuration grammar only: no session, target or device operations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_configuration import settings


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.value=dict(artifactRoot=str(self.root),imagePolicy=dict(source='world-render-target',marker=[0,0,256,64],subject=[0,64,640,400]),actorTarget='owned-peer')
    def test_explicit_peer_and_policy_are_preserved_and_never_auto_select_a_target(self):
        self.assertEqual(self.value,settings(self.value,target='owned-primary'))
        actor={key:value for key,value in self.value.items() if key!='actorTarget'};actor['primaryTarget']='owned-primary'
        self.assertEqual(actor,settings(actor,role='actor',target='owned-peer'))
        for value in (dict(self.value,actorTarget='owned-primary'),dict(self.value,actorTarget=''),dict(self.value,actorTarget='https://device.invalid')):
            with self.assertRaises(NativeUIError):settings(value,target='owned-primary')
    def test_request_desired_effects_unknown_keys_and_other_image_sources_are_refused(self):
        for fault in ('state','image','marker','optional-peer','role'):
            value=deepcopy(self.value)
            if fault=='state':value['animation']='Waving'
            elif fault=='image':value['imagePolicy']['source']='native-screen'
            elif fault=='marker':value['imagePolicy']['marker']=[0,0,0,64]
            elif fault=='optional-peer':value.pop('actorTarget')
            else:value['primaryTarget']='another'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):settings(value)
    def test_shared_or_aliased_artifact_directory_is_refused_before_any_native_read(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(NativeUIError):settings(dict(self.value,artifactRoot=str(alias)))
        self.root.chmod(0o755)
        with self.assertRaises(NativeUIError):settings(self.value)


if __name__=='__main__':unittest.main()
