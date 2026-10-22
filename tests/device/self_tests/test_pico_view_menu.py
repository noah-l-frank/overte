"""Original-reference admission at explicit synthetic native/window boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
import uuid

from adapters.pico4.navigation import validate_snapshot
from adapters.pico4.normal_view_menu import PicoViewMenu,project
from adapters.normal_ui import NativeUIError


class Boundary:
    def __init__(self):
        self.clock=0.;self.calls=[];self.intents=[];self.ready=True;self.checked=False;self.sequence=0
        self.generation=str(uuid.uuid4());self.menu=str(uuid.uuid4());self.edit=None;self.lost=False
        self.original=SimpleNamespace(capture=self.capture,navigation=SimpleNamespace(input=self.input))
    def capture(self):
        row=dict(id='view-menu.third',token=str(uuid.uuid5(uuid.NAMESPACE_URL,self.menu+str(self.checked))),
            menuInstance=self.menu,checked=self.checked,enabled=True,focused=False,inputReady=self.ready)
        value=dict(schemaVersion=1,bridgeId='1'*8+'-1111-4111-8111-'+'1'*12,generation=self.generation,
            processId=31,elapsedMs=int(self.clock*1000),updatedEpochMs=20000,lastCommandSequence=self.sequence,
            open=True,ready=True,viewMenuControlsVersion=1,controls=[row])
        if self.edit:self.edit(value)
        return value
    def input(self,identifier,**kwargs):
        assert self.intents and self.intents[-1]['controlId']==identifier
        row=self.capture()['controls'][0];assert kwargs==dict(token=row['token'])
        self.sequence+=1;self.calls.append((identifier,deepcopy(kwargs)));self.checked=True
        if self.lost:raise NativeUIError('Synthetic lost pointer result')
        return {'performed':True}
    def sleep(self,seconds):self.clock+=seconds
    def flow(self):return PicoViewMenu(self.original,self.intents.append,monotonic=lambda:self.clock,sleep=self.sleep)


class PicoViewMenuTests(unittest.TestCase):
    def test_closed_original_context_and_intent_precede_one_pointer_without_camera_verdict(self):
        b=Boundary();flow=b.flow();before=flow.capture();result=flow.activate('view-menu.third',before)
        self.assertEqual({'performed':True},result);self.assertEqual(1,len(b.calls));self.assertEqual(1,len(b.intents))
        self.assertFalse(b.intents[0]['checkedBefore']);self.assertTrue(flow.capture()['controls'][0]['checked'])
        self.assertNotIn('camera',result)
        with self.assertRaises(NativeUIError):flow.activate('view-menu.third',before)
        self.assertEqual(1,len(b.calls))

    def test_missing_coerced_or_unknown_metadata_never_supplies_normal_menu(self):
        edits=[lambda v:v.pop('viewMenuControlsVersion'),lambda v:v.update(viewMenuControlsVersion=True),
            lambda v:v['controls'][0].update(menuInstance='foreign'),lambda v:v['controls'][0].update(checked=1),
            lambda v:v['controls'][0].update(expectedMode='third person'),lambda v:v['controls'][0].update(id='view-menu.selfie')]
        for edit in edits:
            b=Boundary();b.edit=edit
            with self.subTest(edit=edit),self.assertRaises((ValueError,RuntimeError)):b.flow().capture()
            self.assertEqual([],b.calls)

    def test_original_source_token_generation_and_sequence_cannot_be_recaptured_for_delivery(self):
        for fault in ('menu','checked','generation','sequence'):
            b=Boundary();flow=b.flow();before=flow.capture()
            if fault=='menu':b.menu=str(uuid.uuid4())
            elif fault=='checked':b.checked=True
            elif fault=='generation':b.generation=str(uuid.uuid4())
            else:b.sequence+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):flow.activate('view-menu.third',before)
            self.assertEqual([],b.calls);self.assertEqual([],b.intents)

    def test_intent_storage_failure_and_unready_source_never_send_input(self):
        b=Boundary();flow=b.flow();before=flow.capture()
        flow.intent=lambda _value:False
        with self.assertRaises(NativeUIError):flow.activate('view-menu.third',before)
        b.ready=False;flow=b.flow()
        with self.assertRaises(NativeUIError):flow.activate('view-menu.third',flow.capture())
        self.assertEqual([],b.calls)

    def test_lost_pointer_result_is_not_automatically_replayed(self):
        b=Boundary();flow=b.flow();before=flow.capture();b.lost=True
        with self.assertRaises(NativeUIError):flow.activate('view-menu.third',before)
        self.assertEqual(1,len(b.calls));self.assertEqual(1,len(b.intents))
        with self.assertRaises(NativeUIError):flow.activate('view-menu.third',before)
        self.assertEqual(1,len(b.calls))

    def test_wait_polls_only_originals_with_bounded_monotonic_time(self):
        b=Boundary();b.ready=False;flow=b.flow()
        with self.assertRaises(NativeUIError):flow.wait('view-menu.third')
        self.assertGreaterEqual(b.clock,4.9);self.assertLessEqual(b.clock,5.1);self.assertEqual([],b.calls)

    def test_coerced_original_reference_version_cannot_authorize_input(self):
        b=Boundary();flow=b.flow();reference=flow.capture();reference['viewMenuControlsVersion']=True
        with self.assertRaises(NativeUIError):flow.activate('view-menu.third',reference)
        self.assertEqual([],b.intents);self.assertEqual([],b.calls)

    def test_existing_snapshot_without_optional_menu_extension_remains_compatible(self):
        b=Boundary();value=b.capture();value.pop('viewMenuControlsVersion');value['controls']=[]
        self.assertEqual(value,validate_snapshot(value,31,20000))
        with self.assertRaises(NativeUIError):project(value)


if __name__=='__main__':unittest.main()
