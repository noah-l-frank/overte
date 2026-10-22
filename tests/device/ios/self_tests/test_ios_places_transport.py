"""Places inputs through actual HTTP/AFC codec and a modeled Qt target only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,places_controls as places
from ios.self_tests import test_ios_normal_input as transport
from ios.self_tests.test_ios_places_controls import row


class Boundary(transport.Boundary):
    def __init__(self):
        super().__init__(field='places.search');self.observations=0;self.ignore=False;self.before_input=None
        self.rows=[row('places.page'),row('places.search')];self.rows[1]['focused']=True

    def observed(self):
        self.observations+=1;original=super().observed()
        original.update(placesControlsVersion=1,placesSourceSequence=self.observations,tabletShown=True,
            sampleEpochMs=int(time.time()*1000),elapsedMs=100+self.observations,
            controls=[dict(deepcopy(item),frame=dict(x=10,y=20,width=300,height=40)) for item in self.rows])
        return original

    def post(self,request,timeout):
        payload=json.loads(request.data)
        if payload['operation']=='edit' and self.before_input:self.before_input()
        result=super().post(request,timeout)
        if payload['operation']=='edit':
            command=payload['input'];items=[item for item in self.rows if item['token']==command['fieldToken']]
            if len(items)!=1 or not items[0]['inputReady']:
                self.receipt['status']['performed']=False
            elif not self.ignore:
                if command['operation']=='replace':items[0]['value']=command['text']
                elif command['operation']=='activate':items[0]['focused']=True
        return result

    def io(self):
        native=self.input()
        return places.IOSPlacesIO(SimpleNamespace(native=native,capture=native.capture))


class PlacesTransportTests(unittest.TestCase):
    def test_actual_field_token_input_and_new_original_value_remain_separate(self):
        boundary=Boundary()
        with patch.object(normal_input,'urlopen',boundary.post):
            io=boundary.io();original=io.capture();reference=places.reference(original,'places.search')
            self.assertEqual({'performed':True},io.replace('places.search','owned search',reference=reference))
            measured=io.capture();self.assertEqual('owned search',measured['controls'][1]['value'])
        command=[item['input'] for item in boundary.requests if item['operation']=='edit'][0]
        self.assertEqual(reference['control']['token'],command['fieldToken']);self.assertEqual(1,command['sequence'])
        self.assertEqual('',reference['control']['value']);self.assertEqual(1,len([x for x in boundary.requests if x['operation']=='edit']))

    def test_ignored_input_ack_cannot_become_observed_text(self):
        boundary=Boundary();boundary.ignore=True
        with patch.object(normal_input,'urlopen',boundary.post):
            io=boundary.io();reference=places.reference(io.capture(),'places.search')
            self.assertEqual({'performed':True},io.replace('places.search','not an effect',reference=reference))
            self.assertEqual('',io.capture()['controls'][1]['value'])

    def test_changed_source_before_delivery_rejects_without_an_input(self):
        for field,change in (('rootId',str(uuid.UUID(int=501))),('value','foreign edit'),('focused',False)):
            boundary=Boundary()
            with self.subTest(field=field),patch.object(normal_input,'urlopen',boundary.post):
                io=boundary.io();reference=places.reference(io.capture(),'places.search');boundary.rows[1][field]=change
                with self.assertRaises(NativeUIError):io.replace('places.search','owned',reference=reference)
                self.assertFalse(any(item['operation']=='edit' for item in boundary.requests))

    def test_root_replacement_at_native_delivery_is_not_retried(self):
        boundary=Boundary()
        def replace_root():
            for item in boundary.rows:item['rootId']=str(uuid.UUID(int=501));item['token']=str(uuid.uuid4())
        with patch.object(normal_input,'urlopen',boundary.post):
            io=boundary.io();reference=places.reference(io.capture(),'places.search');boundary.before_input=replace_root
            with self.assertRaises(NativeUIError):io.replace('places.search','owned',reference=reference)
        self.assertEqual('',boundary.rows[1]['value']);self.assertEqual(1,len([x for x in boundary.requests if x['operation']=='edit']))

    def test_missing_or_boolean_extension_sequence_cannot_admit_normal_input(self):
        for update in (dict(placesControlsVersion=True),dict(placesSourceSequence=True),dict(placesSourceSequence=0)):
            original=Boundary().observed();original.update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):normal_input.observation(original,42,time.time()*1000)

    def test_old_back_alias_without_places_profile_remains_a_legacy_component(self):
        boundary=transport.Boundary(field='places.back');original=boundary.observed()
        original.update(placesControlsVersion=1,placesSourceSequence=1)
        self.assertIs(original,normal_input.observation(original,42,time.time()*1000))
        self.assertEqual([],places.project(original)['controls'])


if __name__=='__main__':unittest.main()
