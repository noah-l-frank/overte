"""Original host UI validation/transport; Qt, AFC and process ports modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters import navigation_ui as inventory,normal_input
from ios.self_tests.test_ios_normal_input import Boundary


def root(*,shown=True,visible=True,window=True):
    return dict(rootId=str(uuid.uuid4()),qmlSource='qrc:/qml/+android_phoneInterface/AddressBarDialog.qml',
        shown=shown,visible=visible,windowPresent=window,field=dict(text='original address',visible=visible,focused=False))


def observed(*roots,complete=True):
    value=Boundary().observed();value['controls']=[]
    value['navigationInventory']=dict(iosNavigationUiInventoryVersion=1,complete=complete,roots=list(roots))
    return value


class NavigationUiTests(unittest.TestCase):
    def test_hidden_input_target_does_not_mean_actual_dialog_closed(self):
        value=observed(root());before=deepcopy(value)
        self.assertTrue(inventory.project(value)['addressDialog']);self.assertEqual(before,value)
        self.assertEqual([],value['controls'])

    def test_hidden_retained_object_and_actual_destruction_keep_distinct_originals(self):
        value=observed(root(shown=False,visible=False))
        self.assertFalse(inventory.project(value)['addressDialog']);self.assertEqual(1,len(inventory.project(value)['roots']))
        self.assertEqual([],inventory.project(observed())['roots'])
        self.assertFalse(inventory.project(observed())['addressDialog'])

    def test_incomplete_empty_survey_cannot_establish_closed_dialog(self):
        with self.assertRaises(NativeUIError):inventory.project(observed(complete=False))
        with self.assertRaises(NativeUIError):inventory.project(Boundary().observed())
        with self.assertRaises(NativeUIError):inventory.project(observed(root(),complete=False))

    def test_shown_detached_or_multiple_visible_originals_are_uncertain(self):
        for rows in ([root(window=False)],[root(),root()]):
            with self.subTest(rows=rows),self.assertRaises(NativeUIError):inventory.project(observed(*rows))

    def test_unselected_component_forged_identity_and_extra_fields_are_rejected(self):
        for fault in ('component','traversal','identity','duplicate','boolean','version','field','extra','visible'):
            value=observed(root());item=value['navigationInventory']['roots'][0]
            if fault=='component':item['qmlSource']='qrc:/qml/AddressBarDialog.qml'
            elif fault=='traversal':item['qmlSource']='qrc:/qml/../+android_phoneInterface/AddressBarDialog.qml'
            elif fault=='identity':item['rootId']='not-original'
            elif fault=='duplicate':value['navigationInventory']['roots'].append(deepcopy(item))
            elif fault=='boolean':item['shown']=1
            elif fault=='version':value['navigationInventory']['iosNavigationUiInventoryVersion']=True
            elif fault=='field':item['field']['text']=None
            elif fault=='visible':item['shown']=False
            else:value['navigationInventory']['closed']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):inventory.project(value)

    def test_original_input_transport_retains_inventory_without_creating_input(self):
        boundary=Boundary();original=boundary.observed
        def read():
            value=original();value['controls']=[];value['navigationInventory']=observed(root())['navigationInventory'];return value
        boundary.observed=read
        with patch.object(normal_input,'urlopen',boundary.post):
            value=boundary.input().capture();self.assertTrue(inventory.project(value)['addressDialog'])
        self.assertEqual(['observe'],[query['operation'] for query in boundary.requests])
        self.assertNotIn('input',boundary.requests[0])

    def test_extension_cannot_make_a_stale_or_foreign_native_envelope_fresh(self):
        for fault in ('stale','cross-process'):
            boundary=Boundary();original=boundary.observed
            def read():
                value=original();value['navigationInventory']=observed()['navigationInventory']
                if fault=='stale':value['sampleEpochMs']-=10000
                else:value['processId']=43
                return value
            boundary.observed=read
            with self.subTest(fault=fault),patch.object(normal_input,'urlopen',boundary.post),self.assertRaises(NativeUIError):
                boundary.input().capture()
            self.assertEqual(1,len(boundary.requests))

    def test_historical_projection_never_retimes_the_original_snapshot(self):
        value=observed(root());value['sampleEpochMs']=1000
        before=json.dumps(value,sort_keys=True);self.assertTrue(inventory.project(value)['addressDialog'])
        self.assertEqual(before,json.dumps(value,sort_keys=True))
        with self.assertRaises(NativeUIError):normal_input.observation(value,42,10000)
