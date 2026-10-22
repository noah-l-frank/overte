"""Closed private Create configuration, without app/SDK operations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.create_configuration import settings


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.value=dict(artifactRoot=str(self.root),imagePolicy=dict(source='world-render-target',marker=[0,0,128,64],subject=[128,64,640,400]),
            actorTarget='owned-peer',rezAuthority=dict(controlUrl='http://127.0.0.1:43210/v1/create-rez',token='t'*64,
                domainId='00000000-0000-4000-8000-000000000001'))
    def test_role_specific_private_policy_and_domain_authority_are_preserved(self):
        self.assertEqual(self.value,settings(self.value,target='owned-primary'))
        actor={key:value for key,value in self.value.items() if key not in ('actorTarget','rezAuthority')};actor['primaryTarget']='owned-primary'
        self.assertEqual(actor,settings(actor,role='actor',target='owned-peer'))
        copied=settings(self.value);copied['rezAuthority']['token']='foreign';self.assertEqual('t'*64,self.value['rezAuthority']['token'])
    def test_foreign_authority_requested_effect_unknown_fields_and_self_peer_are_rejected(self):
        for fault in ('self','url','missing','effect','source','role'):
            value=deepcopy(self.value)
            if fault=='self':value['actorTarget']='owned-primary'
            elif fault=='url':value['rezAuthority']['controlUrl']='https://remote.invalid/v1/create-rez'
            elif fault=='missing':value.pop('rezAuthority')
            elif fault=='effect':value['objects']=[]
            elif fault=='source':value['imagePolicy']['source']='native-screen'
            else:value['primaryTarget']='another'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):settings(value,target='owned-primary')
    def test_artifact_alias_shared_directory_and_boolean_roi_are_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(NativeUIError):settings(dict(self.value,artifactRoot=str(alias)))
        value=deepcopy(self.value);value['imagePolicy']['subject'][0]=True
        with self.assertRaises((NativeUIError,ValueError)):settings(value)
        self.root.chmod(0o755)
        with self.assertRaises(NativeUIError):settings(self.value)


if __name__=='__main__':unittest.main()
