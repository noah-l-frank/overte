"""Private whole settings cannot advertise an incomplete feature or execute IO.

Native setup is an explicit host-produced packet, not device qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_configuration as config
from ios.adapters.normal_scripts import PROFILE
from feature_journeys.witness import Client
from self_tests.test_completed_frame_lease import BINDING
from self_tests.test_native_feature_observation import Boundary


class WholeConfigurationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700);self.store=PrivateFeatureState(self.root/'features.json')
        self.empty=dict(iosFeatureAdapterVersion=5,areas=['scripts'],fixtureConfig=str(self.root/'fixture.json'),
            graphics=None,create=None,emotes=None,**{field:None for field,_ in config.WHOLE_SETTINGS.values()})
        image=dict(artifactRoot=str(self.root),imagePolicy=dict(source='world-render-target',marker=[0,0,64,32],subject=[0,40,100,100]))
        native=Boundary();native.send(dict(commandId='ios-'+'1'*32))
        origins=dict(primary='https://controlled.invalid',foreign='https://foreign.invalid')
        self.settings={'world-navigation':dict(artifactRoot=str(self.root)),
            'avatar-people':dict(image,actorTarget='independent-actor'),
            'world-web':dict(image,origins=origins,actorTarget='independent-actor'),
            'tablet-web':dict(image,imagePolicy=dict(source='native-screen',marker=[0,0,64,32],subject=[0,40,100,100]),
                physicalBinding=dict(BINDING,processIdentity='123'),setupNative=deepcopy(native.sample),origins=origins)}
        self.target=dict(physical=True,normalScripts=dict(contractVersion=1,profile=PROFILE),
            nativeUiObservation=dict(kind='uikit-documents',version=1),probe=dict(kind='ios-documents'),testBuild={'configured':True})

    def test_all_existing_whole_settings_validate_without_transport_but_complete_admission_stays_closed(self):
        def forbidden(*_args,**_kwargs):self.fail('Configuration attempted fixture transport')
        with patch.object(Client,'request',side_effect=forbidden):
            for area,(field,_) in config.WHOLE_SETTINGS.items():
                value=dict(self.empty,areas=[area],**{field:self.settings[area]});before=deepcopy(value)
                self.store.write(value,self.store.read())
                with self.subTest(area=area),patch.dict(os.environ,{'OVERTE_IOS_FEATURE_ADAPTER_CONFIG':str(self.store.path)}):
                    self.assertEqual(value,config.configuration());self.assertEqual(before,value)
                    with self.assertRaises(NativeUIError):config.capabilities(self.target)

    def test_literal_legacy_versions_remain_readable_without_new_fields_or_byte_rewrite(self):
        for version in range(1,5):
            value={key:deepcopy(self.empty[key]) for key in ('areas','fixtureConfig')};value['iosFeatureAdapterVersion']=version
            for threshold,field in ((2,'graphics'),(3,'create'),(4,'emotes')):
                if version>=threshold:value[field]=None
            self.store.write(value,self.store.read());before=self.store.path.read_bytes();inode=self.store.path.stat().st_ino
            with self.subTest(version=version):
                self.assertEqual(value,config.configuration(self.store.path))
                self.assertEqual(before,self.store.path.read_bytes());self.assertEqual(inode,self.store.path.stat().st_ino)
                for area in config.WHOLE_SETTINGS:
                    with self.assertRaises(NativeUIError):config.validate(dict(value,areas=[area]))

    def test_unknown_effect_fields_missing_whole_fields_and_unselected_settings_are_refused(self):
        for fault in ('missing','extra','unselected','boolean','duplicate','future'):
            value=deepcopy(self.empty)
            if fault=='missing':value.pop('worldWeb')
            elif fault=='extra':value['expectedScene']='requested effect'
            elif fault=='unselected':value['worldWeb']=self.settings['world-web']
            elif fault=='boolean':value['iosFeatureAdapterVersion']=True
            elif fault=='duplicate':value['areas']=['scripts','scripts']
            else:value['iosFeatureAdapterVersion']=6
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):config.validate(value)

    def test_version_five_preserves_complete_legacy_script_operations_and_no_terminal(self):
        self.store.write(self.empty,None)
        with patch.dict(os.environ,{'OVERTE_IOS_FEATURE_ADAPTER_CONFIG':str(self.store.path)}):
            self.assertEqual(['feature.scripts.act','feature.scripts.cleanup','feature.scripts.observe'],config.capabilities(self.target))
        self.assertNotIn('feature.scripts.terminal',config.OPERATIONS)
        for area in config.WHOLE_SETTINGS:self.assertIn('feature.'+area+'.terminal',config.OPERATIONS)


if __name__=='__main__':unittest.main()
