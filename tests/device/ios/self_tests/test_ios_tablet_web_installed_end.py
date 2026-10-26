"""Real canonical cleanup rejects unresolved Tablet files before SDK fallback.

Candidate/device/SDK producers use the existing explicit InstalledAdapter host
fixture. No complete Tablet archive or native retirement is modeled as success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys import terminal
from feature_journeys.witness import Client
from ios.adapters.tablet_web_canonical_end import verify
from ios.adapters.tablet_web_feature import IOSTabletWebFeature
from ios.adapters.tablet_web_runtime import IOSTabletWebRuntime
from ios.self_tests import test_ios_installed_adapter as installed_fixture
from ios.self_tests.test_ios_tablet_web_packets import BINDING
from self_tests.test_feature_terminal import Boundary


class TabletInstalledEndTests(unittest.TestCase):
    def setUp(self):
        self.f=installed_fixture.InstalledAdapterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_unresolved_tablet_original_blocks_actual_canonical_sdk_fallback(self):
        path=self.f.root/'tabletweb-actual-unresolved.json'
        PrivateFeatureState(path).write(dict(unresolvedInputResponsibility=True),None)
        raw=path.read_bytes();inode=path.stat().st_ino;session=deepcopy(self.f.adapter.read_session('test-only'))
        with self.assertRaises(NativeUIError):self.f.adapter.cleanup('test-only')
        self.assertEqual(raw,path.read_bytes());self.assertEqual(inode,path.stat().st_ino)
        self.assertEqual(session,self.f.adapter.read_session('test-only'))
        self.assertEqual(0,self.f.sessions);self.assertEqual(0,self.f.launches);self.assertEqual([],self.f.commands)

    def test_unresolved_tablet_directory_is_not_absence_or_permission_to_delete_sdk(self):
        path=self.f.root/'tabletweb-unresolved-originals';path.mkdir(mode=0o700)
        session=deepcopy(self.f.adapter.read_session('test-only'))
        with self.assertRaises(NativeUIError):self.f.adapter.cleanup('test-only')
        self.assertTrue(path.is_dir());self.assertEqual([],list(path.iterdir()))
        self.assertEqual(session,self.f.adapter.read_session('test-only'));self.assertEqual([],self.f.commands)

    def test_forged_tablet_archive_never_replaces_real_original_end(self):
        path=self.f.root/('tabletweb-final-archive-'+'a'*32+'.json')
        PrivateFeatureState(path).write(dict(complete=True),None)
        raw=path.read_bytes();inode=path.stat().st_ino
        with self.assertRaises(NativeUIError):self.f.adapter.cleanup('test-only')
        self.assertEqual(raw,path.read_bytes());self.assertEqual(inode,path.stat().st_ino)
        self.assertIsNotNone(self.f.adapter.read_session('test-only'))
        self.assertEqual(0,self.f.sessions);self.assertEqual([],self.f.commands)

    def test_missing_tablet_journal_preserves_existing_other_feature_cleanup(self):
        self.f.adapter.describe('test-only')
        self.assertEqual({'cleaned':True},self.f.adapter.cleanup('test-only'))
        self.assertIsNone(self.f.adapter.read_session('test-only'))
        self.assertIsNone(self.f.adapter._binding_store('test-only').read())
        self.assertEqual([],list(self.f.root.glob('tabletweb-*')))

    def test_valid_public_end_cannot_replace_missing_or_forged_private_originals(self):
        # The shared synthetic protocol model produces only public DTOs. Its
        # typed Tablet shape deliberately has no actual Tablet/OS/SDK archive.
        model=Boundary();model.journey().execute()
        end=deepcopy(model.reports[-1]['terminalRetirement']['end']);end['seal']['description']['area']='tablet-web'
        result=dict(stage='finish',end=end);terminal.result('tablet-web',result)
        call=dict(contractVersion=1,runId=model.run,stage='finish',seal=deepcopy(end['seal']))
        client=Client('http://127.0.0.1:9/feature-fixture/v1','a'*64)
        flow=IOSTabletWebFeature(IOSTabletWebRuntime(self.f.adapter),'test-only',client,model.run,'primary',BINDING,
            dict(explicitUnadmittedSetup=True),dict(primary='http://127.0.0.1:9',foreign='http://127.0.0.1:10'),monotonic=lambda:0.)
        with self.assertRaises(NativeUIError):verify(flow,call,result)
        path=self.f.root/('tabletweb-final-archive-'+model.run+'.json');self.assertFalse(path.exists())
        PrivateFeatureState(path).write(dict(complete=True),None);original=path.read_bytes();inode=path.stat().st_ino
        with self.assertRaises(NativeUIError):verify(flow,call,result)
        self.assertEqual(original,path.read_bytes());self.assertEqual(inode,path.stat().st_ino)
        self.assertEqual(0,self.f.sessions);self.assertEqual(0,self.f.launches);self.assertEqual([],self.f.commands)


if __name__=='__main__':unittest.main()
