"""Explicit source admission, private paths and role configuration; no SDK IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.feature_configuration import configuration,capabilities,OPERATIONS
from ios.script_observer import configuration as observer_configuration
from ios.authentication_observer import configuration as authentication_observer_configuration
from ios.adapters.normal_scripts import PROFILE


class IOSScriptConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.store=PrivateFeatureState(self.root/'feature.json')
        self.value=dict(iosFeatureAdapterVersion=1,areas=['scripts'],fixtureConfig=str(self.root/'reader.json'))
        self.target=dict(physical=True,normalScripts=dict(contractVersion=1,profile=PROFILE),
            nativeUiObservation=dict(kind='uikit-documents',version=1),probe=dict(kind='ios-documents'),testBuild={'configured':True})

    def test_default_configuration_advertises_no_unbound_feature_capability(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertIsNone(configuration());self.assertEqual([],capabilities(self.target))

    def test_exact_source_profile_and_private_explicit_config_admit_only_scripts(self):
        self.store.write(self.value,None)
        with patch.dict(os.environ,{'OVERTE_IOS_FEATURE_ADAPTER_CONFIG':str(self.store.path)},clear=True):
            self.assertEqual(self.value,configuration());self.assertEqual(self.value,configuration(self.store.path))
            self.assertEqual(sorted(op for op in OPERATIONS if op.startswith('feature.scripts.')),capabilities(self.target))
            for change in (dict(physical=False),dict(probe={}),dict(normalScripts=None)):
                with self.assertRaises(NativeUIError):capabilities(self.target|change)

    def test_unknown_areas_boolean_versions_extra_fields_and_relative_private_paths_fail(self):
        for fields in (dict(areas=['graphics']),dict(areas=['scripts','scripts']),dict(iosFeatureAdapterVersion=True),
                       dict(fixtureConfig='reader.json'),dict(extra=True)):
            self.store.write(self.value|fields,self.store.read())
            with self.assertRaises(NativeUIError):configuration(str(self.store.path))

    def test_public_config_permissions_cannot_admit_feature_ownership(self):
        self.store.write(self.value,None);self.store.path.chmod(0o644)
        with self.assertRaises(NativeUIError):configuration(str(self.store.path))

    def test_authentication_requires_canonical_explicit_https_process_origin(self):
        self.store.write(self.value|dict(areas=['authentication','scripts']),None)
        with patch.dict(os.environ,{'OVERTE_IOS_FEATURE_ADAPTER_CONFIG':str(self.store.path)},clear=True):
            with self.assertRaises(NativeUIError):capabilities(self.target)
            target=self.target|dict(testBuild={'launchEnvironment':{'HIFI_METAVERSE_URL':'https://owned.invalid'}})
            self.assertEqual(sorted(OPERATIONS),capabilities(target))
            self.store.write(self.value|dict(areas=['authentication']),self.store.read())
            self.assertEqual(sorted(op for op in OPERATIONS if '.authentication.' in op),capabilities(target))

    def test_actor_config_has_its_own_credential_and_requires_closed_source_fields(self):
        value=dict(iosScriptObserverVersion=1,target='owned-target',candidateArguments=['--artifact-root','/private/artifacts'],
            fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1',actorToken='a'*64,durationSeconds=600)
        self.store.write(value,None);self.assertEqual(value,observer_configuration(self.store.path))
        for fields in (dict(iosScriptObserverVersion=True),dict(durationSeconds=0),dict(readerToken='b'*64),dict(candidateArguments=[])):
            self.store.write(value|fields,self.store.read())
            with self.assertRaises((RuntimeError,ValueError)):observer_configuration(self.store.path)

    def test_authentication_actor_has_separate_closed_private_https_configuration(self):
        value=dict(iosAuthenticationObserverVersion=1,target='owned-target',candidateArguments=['--artifact-root','/private/artifacts'],
            fixtureUrl='https://owned.invalid/feature-fixture/v1',actorToken='a'*64,durationSeconds=600)
        self.store.write(value,None);self.assertEqual(value,authentication_observer_configuration(self.store.path))
        for fields in (dict(iosAuthenticationObserverVersion=True),dict(fixtureUrl='http://owned.invalid/feature-fixture/v1'),
                       dict(durationSeconds=0),dict(readerToken='b'*64),dict(candidateArguments=[])):
            self.store.write(value|fields,self.store.read())
            with self.assertRaises((RuntimeError,ValueError)):authentication_observer_configuration(self.store.path)


if __name__=='__main__':unittest.main()
