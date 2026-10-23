"""Durable Assets Cancel/File/Home through original Qt and the existing session.

OpenXR transport/status and standard-controller delivery are explicit host
endpoints. Page, loader, context and component lifetimes are actual Qt objects.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import test_assets_page_home as page_module
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_home_owner import OwnedAssetsHome
from adapters.script_journey.history import unpack,same
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from openxr_input.adapter_session import PicoOpenXrAdapterSession,AdapterSessionError


class OriginalChannelTransport:
    def __init__(self,test):self.test=test;self.envelopes=[];self.neutral=None;self.lose=False;self.ignore=False
    def stage(self,envelope,profile,*,before_publish=None):
        test=self.test;state=test.home_store.read()
        test.assertEqual(envelope,state['envelope']);test.assertEqual('issued',state['phase'])
        test.assertEqual(test.cancel_before,test.store.read());test.assertEqual(test.files_before,test.file_store.read())
        before_publish(deepcopy(envelope));self.envelopes.append(deepcopy(envelope))
        if not self.ignore:
            receipt=json.loads(test.host.request(dict(action='host-normal-pico-x')));test.assertEqual(2,receipt['edges'])
        self.neutral=dict(enabled=True,acceptedSequence=envelope['sequence'],acceptedNonce='[redacted]',state='neutral',
            activeCommandId='',updatedEpochMs=test.host.epoch_milliseconds())
        return dict(sequence=envelope['sequence'])
    def read_status(self,*,expected_nonce=None,expected_sequence=None):
        if expected_sequence is not None and self.lose:raise AdapterSessionError('Explicit lost host ACK after original delivery')
        return deepcopy(self.neutral)


class AssetsHomeOwnerTests(unittest.TestCase):
    setUpClass=classmethod(page_module.AssetsPageHomeTests.setUpClass.__func__)
    tearDownClass=classmethod(page_module.AssetsPageHomeTests.tearDownClass.__func__)
    def setUp(self):
        page_module.AssetsPageHomeTests.setUp(self);self.addCleanup(self.preserve_home)
    make=page_module.AssetsPageHomeTests.make
    cancel_phase=page_module.AssetsPageHomeTests.cancel_phase
    def preserve_home(self):
        destination=os.environ.get('OVERTE_ASSETS_PAGE_EVIDENCE')
        if destination is None or not hasattr(self,'home'):return
        page_module.AssetsPageHomeTests.preserve(self,self.home.pages)
        directory=Path(destination).resolve(strict=True)
        state=self.home_store.read()
        if state is not None:PrivateFeatureState(directory/(self._testMethodName+'-home.json')).write(state,None)
    pointers=page_module.AssetsPageHomeTests.pointers
    def prepare(self):
        self.owner.open();self.cancel_phase();self.assertTrue(self.owner.cancel()['filesRetired'])
        self.cancel_before=deepcopy(self.store.read());self.files_before=deepcopy(self.file_store.read())
        self.journal.activate(self.run,'3'*32,'close',{})
        self.home_store=PrivateFeatureState(self.path/'normal-assets-home-stage1-host.json');self.lock=ScriptSourceLock(self.path/'script-sources.lock')
        self.transport=OriginalChannelTransport(self);self.session=PicoOpenXrAdapterSession(self.transport,'explicit-assets-home-channel',self.path)
        self.session.begin(self.binding['processIdentity']);self.home_owner()
    def home_owner(self):
        factory=self.host.factory
        def locked(target,source_lock):
            self.assertEqual(target,self.host.target);self.assertIs(source_lock,self.lock);self.lock.assert_held();return self.lock
        factory._script_journey=lambda:SimpleNamespace(_lock=locked)
        # These declared endpoints provide the already tested original child
        # owner and actual Qt source; execute the complete production factory.
        factory._assets_cancel_owner=lambda *_args,**_kwargs:self.owner
        factory._assets_cancel_store=lambda *_args:PrivateFeatureState(self.path/'normal-assets-cancel-stage1-host.json')
        factory._assets_pages=lambda *_args,**_kwargs:self.host.pages()
        factory.pico_input_session=lambda _target:self.session
        with self.lock.held():self.home=factory._assets_home_owner(self.host.target,self.run,self.url,
            PhaseFixtureReader(self.client,self.run,'assets'),source_lock=self.lock)
        self.assertIsInstance(self.home,OwnedAssetsHome);self.assertEqual(self.home_store.path,self.home.store.path)
    def original_children(self):
        self.assertEqual(self.cancel_before,self.store.read());self.assertEqual(self.files_before,self.file_store.read())
    def test_normal_home_durably_joins_original_cancel_file_and_page_owners(self):
        self.prepare();result=self.home.close_page();self.assertTrue(result['homeObserved'] and result['pageRetired'])
        self.assertFalse(result['contextRetired']);self.assertTrue(result['retained']);self.assertEqual('home-retained',self.home_store.read()['phase'])
        self.assertTrue(result['page']['contextAlive']);self.assertFalse(result['page']['contextValid'])
        self.assertTrue(result['page']['loaderAlive'] and result['page']['windowAlive']);self.original_children()
        history=deepcopy(unpack(self.home_store.read()['pages']));count=len(self.transport.envelopes);self.home_owner()
        self.assertTrue(same(history,self.home.pages.history));cold=self.home.reconcile();self.assertTrue(cold['homeObserved']);self.original_children()
        self.assertEqual(count,len(self.transport.envelopes));self.assertEqual(1,count)
        with self.assertRaises(NativeUIError):self.home.close_page()
        self.assertEqual(count,len(self.transport.envelopes));self.assertTrue(self.home_store.read()['quiet'] is not None)
    def test_lost_home_reply_cold_observes_original_page_without_repeating_x_or_release(self):
        self.prepare();self.transport.lose=True
        with self.assertRaises(NativeUIError):self.home.close_page()
        original=deepcopy(self.home_store.read());self.assertEqual('issued',original['phase']);self.assertIsNotNone(original['envelope'])
        self.transport.lose=False;operations=deepcopy(self.host.operations);self.home_owner();result=self.home.reconcile()
        self.assertTrue(result['homeObserved']);self.assertTrue(result['retained']);self.original_children()
        self.assertEqual(original['envelope'],self.home_store.read()['envelope']);self.assertEqual(1,len(self.transport.envelopes))
        self.assertTrue(all(command.get('operation')=='observe' for command in self.host.operations[len(operations):] if 'operation' in command))
    def test_changed_original_file_journal_refuses_before_normal_home_input(self):
        self.prepare();original=deepcopy(self.files_before);changed=deepcopy(original);changed['stage']=True
        self.file_store.write(changed,original)
        with self.assertRaises(NativeUIError):self.home.close_page()
        self.assertEqual([],self.transport.envelopes);self.assertIsNone(self.home_store.read())
        self.assertTrue(json.loads(self.host.request(dict(action='host-original-assets-pointers')))['pageAlive'])
        self.assertEqual(self.cancel_before,self.store.read());self.assertEqual(changed,self.file_store.read())


if __name__=='__main__':unittest.main()
