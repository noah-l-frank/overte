"""Real HTTP/AFC codecs and durable Back intent; Qt/OS are declared models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,tablet_back_controls as source
from ios.self_tests.test_ios_normal_input import Boundary


class BackBoundary(Boundary):
    def __init__(self):
        super().__init__(field='tablet.back');self.change=None;self.lost=False;self.intent=None;self.ignored=False
    def observed(self):
        value=super().observed();value.update(tabletShown=True,tabletBackControlsVersion=1)
        value['controls'][0].update(tabletBackControlVersion=1,navigationRootId='22222222-2222-4222-8222-222222222222',
            navigationQmlSource='file:///installed/qml/hifi/tablet/WindowRoot.qml',
            screenIdSha256=hashlib.sha256(b'create').hexdigest(),sourceHistorySha256=hashlib.sha256(b'[]').hexdigest(),
            sourceHistoryLength=0,backTargetPending=False,inputReady=True)
        if self.change:self.change(value)
        return value
    def post(self,request,timeout):
        import json
        command=json.loads(request.data)
        if command['operation']=='edit':
            # An actual independently readable private owner exists BEFORE
            # transport, including ignored input and an uncertain return.
            assert self.intent.read()==command['input']
        returned=super().post(request,timeout)
        if command['operation']=='edit':
            if self.ignored:self.receipt['status']['performed']=False
            if self.lost:raise OSError('Declared lost normal Back return')
        return returned


class TabletBackControlsTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name);self.b=BackBoundary();self.b.intent=PrivateFeatureState(self.root/'back-intent.json')
        self.native=self.b.input();self.enterContext(patch.object(normal_input,'urlopen',self.b.post))
    def reference(self):return source.reference(self.native.capture())
    def intent(self,command):self.b.intent.write(command,None)
    def inputs(self):return [row for row in self.b.requests if row['operation']=='edit']

    def test_original_back_token_is_delivered_once_after_actual_durable_intent(self):
        reference=self.reference();result=self.native.tablet_back_input(reference=reference,before_send=self.intent)
        self.assertEqual({'performed':True},result);self.assertEqual(1,len(self.inputs()))
        original=self.b.intent.read();self.assertEqual(original,self.inputs()[0]['input'])
        self.assertEqual(reference['control']['token'],original['fieldToken']);self.assertEqual('activate',original['operation'])
        self.assertNotIn('text',original);self.assertEqual(reference['scope']['lastSequence']+1,original['sequence'])
        # Delivery supplies no navigation, editor, keyboard or cleanup verdict.
        self.assertEqual({'performed'},set(result))

    def test_replaced_page_or_history_refuses_input_before_creating_an_intent(self):
        reference=self.reference()
        for mutate in (
            lambda v:v['controls'][0].update(navigationRootId='33333333-3333-4333-8333-333333333333'),
            lambda v:v['controls'][0].update(screenIdSha256='f'*64),
            lambda v:v['controls'][0].update(sourceHistorySha256='f'*64),
            lambda v:v['controls'][0].update(sourceHistoryLength=1),
            lambda v:v['controls'][0].update(backTargetPending=True,inputReady=False),
            lambda v:v.update(tabletShown=False),
            lambda v:v['controls'][0].update(token='44444444-4444-4444-8444-444444444444')):
            self.b.change=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):
                self.native.tablet_back_input(reference=reference,before_send=self.intent)
            self.assertIsNone(self.b.intent.read());self.assertEqual([],self.inputs())

    def test_uncertain_input_return_keeps_exact_intent_and_does_not_resend(self):
        reference=self.reference();self.b.lost=True
        with self.assertRaises(OSError):self.native.tablet_back_input(reference=reference,before_send=self.intent)
        self.assertEqual(1,len(self.inputs()));original=self.b.intent.read();self.b.lost=False
        self.native.capture();self.assertEqual(original,self.b.intent.read());self.assertEqual(1,len(self.inputs()))

    def test_ignored_input_receipt_is_not_success_and_does_not_discard_ownership(self):
        reference=self.reference();self.b.ignored=True
        with self.assertRaises(NativeUIError):self.native.tablet_back_input(reference=reference,before_send=self.intent)
        self.assertEqual(1,len(self.inputs()));self.assertEqual(self.inputs()[0]['input'],self.b.intent.read())

    def test_missing_or_refused_durable_intent_never_sends_back(self):
        reference=self.reference()
        for callback in (None,lambda command:False):
            with self.subTest(callback=callback),self.assertRaises(NativeUIError):
                self.native.tablet_back_input(reference=reference,before_send=callback)
        self.assertEqual([],self.inputs());self.assertIsNone(self.b.intent.read())

    def test_closed_schema_rejects_legacy_or_foreign_back_sources(self):
        original=self.b.observed()
        mutations=(lambda v:v.pop('tabletBackControlsVersion'),lambda v:v.update(tabletBackControlsVersion=True),
            lambda v:v['controls'][0].update(tabletBackControlVersion=True),
            lambda v:v['controls'][0].update(navigationQmlSource='file:///foreign/WindowRoot.qml'),
            lambda v:v['controls'][0].update(sourceHistoryLength=True),
            lambda v:v['controls'][0].update(screenIdSha256='expected-create'),
            lambda v:v['controls'][0].update(backTargetPending=True),
            lambda v:v['controls'][0].update(editor='create'))
        for mutate in mutations:
            value=deepcopy(original);mutate(value)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):normal_input.observation(value,42)
        self.assertEqual([],self.inputs())


if __name__=='__main__':unittest.main()
