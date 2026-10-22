"""Original Places metadata/ref counterexamples; no native compiler or device."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters import places_controls as places


def row(identifier,*,name='',address='',modal=False):
    return dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier)),enabled=True,focused=False,
        profile=places.PROFILE,rootId=str(uuid.UUID(int=500)),qmlSource='qrc:/scripts/system/places/PicoPlaces.qml',
        rowName=name,rowAddress=address,value='',modal=modal,
        inputReady=identifier!='places.page' and modal==(identifier in places.MODAL))


def value(*extra):
    return dict(placesControlsVersion=1,open=True,ready=True,
        scope=dict(instance=str(uuid.UUID(int=100)),processId=42,sequence=0,observationSequence=1,
            elapsedMs=100,sampleEpochMs=20000),controls=[row('places.page'),*extra])


class PlacesControlsTests(unittest.TestCase):
    def test_original_row_identity_binds_actual_name_and_address(self):
        name='owned-bookmark';key=hashlib.sha256(name.encode()).hexdigest()[:32]
        current=value(row('places.bookmark-visit.'+key,name=name,address='http://fixture.invalid/scene.json'))
        self.assertIs(current,places.snapshot(current))
        changed=deepcopy(current);changed['controls'][-1]['rowName']='foreign-bookmark'
        with self.assertRaises(NativeUIError):places.snapshot(changed)
        changed=deepcopy(current);changed['controls'][-1]['rowAddress']=''
        with self.assertRaises(NativeUIError):places.snapshot(changed)

    def test_another_root_or_duplicate_token_cannot_join_the_current_page(self):
        original=value(row('places.search'))
        for field,changed in (('rootId',str(uuid.UUID(int=501))),('token',original['controls'][0]['token'])):
            current=deepcopy(original);current['controls'][1][field]=changed
            with self.assertRaises(NativeUIError):places.snapshot(current)

    def test_modal_eligibility_is_original_and_cannot_enable_background_controls(self):
        current=value(row('places.bookmark-cancel',modal=True));current['controls'][0]['modal']=True
        self.assertEqual(True,places.snapshot(current)['controls'][1]['inputReady'])
        for field,changed in (('modal',False),('enabled',False)):
            invalid=deepcopy(current);invalid['controls'][1][field]=changed
            with self.assertRaises(NativeUIError):places.snapshot(invalid)

    def test_boolean_versions_unknown_fields_and_unrooted_rows_fail(self):
        original=value(row('places.search'))
        for update in (dict(placesControlsVersion=True),dict(extra=True),dict(controls=[row('places.search')]),dict(open=False)):
            with self.subTest(update=update),self.assertRaises(NativeUIError):places.snapshot(original|update)

    def test_foreign_http_qml_query_traversal_and_wrong_page_are_not_native_places_sources(self):
        for source in ('https://fixture.invalid/system/places/PicoPlaces.qml',
                       'qrc:/scripts/system/places/PicoPlaces.qml?borrowed=1',
                       'qrc:/scripts/%2e%2e/system/places/PicoPlaces.qml',
                       'qrc:/scripts/system/places/Other.qml'):
            current=value();current['controls'][0]['qmlSource']=source
            with self.subTest(source=source),self.assertRaises(NativeUIError):places.snapshot(current)

    def test_read_only_capture_advances_original_observation_not_input_sequence(self):
        original=value(row('places.search'));reference=places.reference(original,'places.search')
        current=deepcopy(original);current['scope'].update(observationSequence=2,elapsedMs=101,sampleEpochMs=20001)
        self.assertEqual(current['controls'][1],places.same_reference(reference,current,'places.search'))
        self.assertEqual(1,reference['scope']['observationSequence']);self.assertEqual(0,reference['scope']['sequence'])

    def test_retimed_same_source_sequence_new_input_foreign_pid_and_elapsed_expiry_reject_reference(self):
        original=value(row('places.search'));reference=places.reference(original,'places.search')
        for update in (dict(observationSequence=1),dict(sequence=1),dict(processId=43),
                       dict(instance=str(uuid.UUID(int=101))),dict(elapsedMs=5100),dict(sampleEpochMs=19999)):
            current=deepcopy(original);current['scope'].update(observationSequence=2,elapsedMs=101,sampleEpochMs=20001)
            current['scope'].update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):places.same_reference(reference,current,'places.search')

    def test_changed_field_value_or_focus_cannot_borrow_a_reference(self):
        original=value(row('places.search'));reference=places.reference(original,'places.search')
        for update in (dict(value='another input'),dict(focused=True),dict(rootId=str(uuid.UUID(int=501)))):
            current=deepcopy(original);current['scope'].update(observationSequence=2,elapsedMs=101,sampleEpochMs=20001)
            current['controls'][1].update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):places.same_reference(reference,current,'places.search')

    def test_original_projection_preserves_clocks_and_excludes_legacy_other_page_aliases(self):
        original=value(row('places.search'));scope=original['scope']
        controls=[dict(item,frame=dict(x=0,y=0,width=100,height=30)) for item in original['controls']]
        controls.append(dict(id='places.back',token=str(uuid.UUID(int=999)),enabled=True,focused=False,frame={}))
        native=dict(placesControlsVersion=1,tabletShown=True,ready=True,instance=scope['instance'],processId=42,
            lastSequence=0,placesSourceSequence=1,elapsedMs=100,sampleEpochMs=20000,controls=controls)
        self.assertEqual(original,places.project(native))
        self.assertEqual(20000,native['sampleEpochMs']);self.assertIn('frame',native['controls'][0])


if __name__=='__main__':unittest.main()
