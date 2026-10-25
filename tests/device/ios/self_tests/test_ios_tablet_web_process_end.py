"""Actual role/child WAL and OS reader composition; prior live seal is modeled.

OS producer, prior Tablet seal and installed state are explicit host models.
The real original OS codec, private files, immutable receipt ledger, parent CAS
and prefix recovery run unchanged. This is not a native or paired-device result.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.tablet_web_process_end import TabletWebProcessEnd
from ios.self_tests import test_ios_retired_process as native_fixture
from self_tests.test_completed_frame_lease import BINDING,RUN


class TabletProcessEndWALTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');held=self.lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.native=native_fixture.Boundary();self.binding=dict(BINDING,processIdentity='42');scope={k:v for k,v in self.binding.items() if k!='processIdentity'}
        self.sdk=PrivateFeatureState(self.root/'sdk.json');sdk=dict(sessionId=self.binding['sessionId']);self.sdk.write(sdk,None)
        installed=PrivateFeatureState(self.root/'installed.json');installed.write({'testOnlyPriorInstalled':True},None)
        base=SimpleNamespace(_candidate_guard=lambda **_args:None,read_session=lambda _selector:self.sdk.read(),_target=lambda _selector:{},
            _scope=lambda *_args:deepcopy(scope),_binding_store=lambda _selector:installed)
        self.runtime=SimpleNamespace(adapter=base,state_path=lambda _selector:self.sdk.path)
        self.terminal_store=PrivateFeatureState(self.root/'terminal.json');self.terminal_previous={'testOnlyPriorPairedTabletSeal':True};self.terminal_store.write(self.terminal_previous,None)
        self.transport=patch('ios.adapters.tablet_web_process_end.IOSGraphicsRuntime._retired_process_observer',side_effect=lambda *_args:self.native.reader())
        self.transport.start();self.addCleanup(self.transport.stop)
    def make(self,role='primary'):
        owner=object.__new__(TabletWebProcessEnd);owner.binding=deepcopy(self.binding);owner.run=RUN;owner.lock=self.lock
        owner.feature=SimpleNamespace(root=self.root,runtime=self.runtime,selector='existing-only',role=role,screen=None,clock=lambda:True,
            epoch_ms=self.native.epoch,monotonic=lambda:self.native.clock,binding=self.binding,run=RUN)
        owner.terminal=SimpleNamespace(store=self.terminal_store,previous=self.terminal_previous,replay=lambda:self.terminal_previous)
        owner.store=PrivateFeatureState(self.root/('tabletweb-process-end-'+RUN+'.json'));owner.previous=owner.store.read()
        owner.authority=lambda _value:None  # Explicit model of the earlier fully decoded paired seal/fixture retirement.
        if owner.previous is None:
            owner.state=dict(phase='stop-issued',source=deepcopy(native_fixture.SOURCE),bundleId=native_fixture.BUNDLE,
                terminalSha256=digest(self.terminal_previous),retirement={'testOnlyPriorRetirement':True,'acquisition':{'hostAfterEpochMs':self.native.epoch()}},started=dict(epochMs=self.native.epoch(),monotonic=self.native.clock),
                stopReturned=False,roles=dict(primary=None,actor=None),inventories=owner.inventories());owner.save()
        else:owner.state=owner.decode(owner.previous)
        return owner
    def test_lost_parent_update_preserves_actual_child_and_original_host_then_new_CLI_reads_fresh(self):
        owner=self.make();write=owner.store.write;lost=[False]
        def lose(value,previous):
            role=owner.state['roles']['primary']
            if role is not None and role['pending'] is None and role['issuers'] and not lost[0]:
                lost[0]=True;raise OSError('Actual child saved, parent update return lost')
            return write(value,previous)
        owner.store.write=lose
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=100001),self.assertRaises(OSError):owner.advance('primary')
        self.assertEqual(1,len(self.native.queries));reconstructed=self.make()
        self.assertIsNotNone(reconstructed.state['roles']['primary']['pending'])
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=200002):self.assertFalse(reconstructed.advance('primary'))
        role=reconstructed.state['roles']['primary'];self.assertIsNone(role['pending'])
        self.assertEqual([100001,200002],[item['hostProcessId'] for item in role['issuers']]);self.assertEqual(2,len(self.native.queries))
        self.assertEqual(2,len(reconstructed.os_archive('primary',role['original'])['records']))
    def test_same_actual_issuer_cannot_qualify_both_roles_or_send_an_actor_OS_query(self):
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=100001):self.make().advance('primary')
        count=len(self.native.queries)
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=100001),self.assertRaises((NativeUIError,ValueError)):self.make('actor').advance('actor')
        self.assertEqual(count,len(self.native.queries));self.assertIsNone(self.make().state['roles']['actor'])
    def test_original_native_counter_floor_survives_failed_later_query_and_reconstruction(self):
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=100001):self.make().advance('primary')
        self.native.sequence=1
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=200002),self.assertRaises(NativeUIError):self.make().advance('primary')
        actual=self.make();self.assertIsNotNone(actual.state['roles']['primary']['pending'])
        with patch('ios.adapters.tablet_web_process_end.issuer_host',return_value=300003),self.assertRaises(NativeUIError):actual.advance('primary')
        role=self.make().state['roles']['primary'];self.assertIsNotNone(role['pending'])
        rows=self.make().os_rows('primary',self.make().os_archive('primary',role['original']))
        self.assertEqual(['observed','abandoned'],[row['mode'] for row in rows]);self.assertGreater(rows[0]['original']['sequence'],100)
    def test_unknown_same_namespace_inventory_carrier_is_not_mutable_or_permission_for_an_OS_query(self):
        self.make()
        path=self.root/('tabletweb-process-inventory-frame-sources-'+RUN+'-primary-0099-'+'f'*64+'.json')
        path.touch(mode=0o600)
        with self.assertRaises(NativeUIError):self.make().advance('primary')
        self.assertEqual([],self.native.queries);self.assertTrue(path.exists())


if __name__=='__main__':unittest.main()
