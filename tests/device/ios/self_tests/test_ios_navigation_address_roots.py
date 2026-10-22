"""Pure retained-root provenance and absence; actual Qt/SDK is explicitly modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_ui import NativeUIError,W3C_ELEMENT
from ios.adapters import navigation_address_roots as roots
from ios.self_tests.test_ios_navigation_ui import observed,root
from self_tests.test_completed_frame_lease import BINDING

RUN='a'*32


def control(id_):
    return dict(id=id_,token=str(uuid.uuid4()),enabled=True,focused=False,
        frame=dict(x=10,y=20,width=120,height=60))


class NavigationAddressRootsTests(unittest.TestCase):
    def setUp(self):
        self.before=observed();self.before.update(navigationDialogControlsVersion=1,navigationDialogSourceSequence=1)
        self.before['controls']=[control('hud.goto')]
        self.opened=observed(root());self.opened.update(navigationDialogControlsVersion=1,navigationDialogSourceSequence=2)
        self.opened['controls']=[control('address.field')]
        self.intent=dict(method='POST',path='/element/actual-goto-element/click',body={},original=self.before)
        self.intent['lookup']=dict(using='accessibility id',value='OverteNavigation.hud.goto',
            elements=[{W3C_ELEMENT:'actual-goto-element'}])
    def admit(self):return roots.admit(BINDING,RUN,self.intent,self.opened)
    def retained(self):
        value=deepcopy(self.opened);value['navigationDialogSourceSequence']+=1;value['controls']=[]
        row=value['navigationInventory']['roots'][0];row.update(shown=False,visible=False)
        row['field'].update(visible=False,focused=False);return value

    def test_original_opening_and_selected_root_are_preserved_while_hidden_object_is_still_owned(self):
        original=deepcopy((self.before,self.opened));lease=self.admit();current=self.retained()
        actual=roots.current(lease,current,closed=True)
        self.assertEqual(original,(self.before,self.opened));self.assertEqual('retained',actual['status'])
        self.assertFalse(actual['drained']);self.assertEqual(current,actual['original'])
        self.assertEqual(lease,roots.validate(lease));self.assertNotIn('performed',actual)

    def test_independent_complete_inventory_absence_is_distinct_from_retained_or_incomplete_roots(self):
        lease=self.admit();current=self.retained();current['navigationInventory']['roots']=[]
        actual=roots.current(lease,current,closed=True);self.assertTrue(actual['drained']);self.assertEqual('absent',actual['status'])
        current['navigationInventory']['complete']=False
        with self.assertRaises(NativeUIError):roots.current(lease,current,closed=True)

    def test_preexisting_hidden_root_foreign_component_or_ack_without_actual_opened_root_is_not_adopted(self):
        original=deepcopy((self.intent,self.opened))
        for fault in ('preexisting','component','absent','sdk-ack','counter','foreign-process','foreign-lookup'):
            if fault=='preexisting':self.intent['original']['navigationInventory']['roots']=[root(shown=False,visible=False)]
            elif fault=='component':self.opened['navigationInventory']['roots'][0]['qmlSource']='qrc:/foreign/AddressBarDialog.qml'
            elif fault=='absent':self.opened['navigationInventory']['roots']=[]
            elif fault=='sdk-ack':self.intent['original']['controls']=[]
            elif fault=='counter':self.opened['navigationDialogSourceSequence']=1
            elif fault=='foreign-process':self.opened['processId']=43
            else:self.intent['lookup']['elements'][0][W3C_ELEMENT]='different-element'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.admit()
            self.intent,self.opened=deepcopy(original)

    def test_replaced_additional_shown_or_focused_root_never_passes_closed_ownership(self):
        lease=self.admit();original=self.retained()
        for fault in ('replacement','additional','shown','focus','visible-control','rewind'):
            current=deepcopy(original);row=current['navigationInventory']['roots'][0]
            if fault=='replacement':row['rootId']=str(uuid.uuid4())
            elif fault=='additional':current['navigationInventory']['roots'].append(root(shown=False,visible=False))
            elif fault=='shown':row['shown']=True
            elif fault=='focus':row['field']['focused']=True
            elif fault=='visible-control':current['controls']=[control('address.field')]
            else:current['navigationDialogSourceSequence']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):roots.current(lease,current,closed=True)

    def test_historical_lease_cannot_invent_root_identity_or_change_original_clocks(self):
        lease=self.admit();original=deepcopy(lease)
        for fault in ('root','clock','intent','version'):
            lease=deepcopy(original)
            if fault=='root':lease['rootId']=str(uuid.uuid4())
            elif fault=='clock':lease['opened']['sampleEpochMs']+=1
            elif fault=='intent':lease['opening']['path']='/actions'
            else:lease['iosNavigationAddressRootVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):roots.validate(lease)
