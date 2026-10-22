"""Versioned original settings/control joins; native/SDK boundaries modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input,places_controls as controls,places_model as models,places_preferences as preferences
from ios.self_tests.test_ios_places_controls import row as legacy_row,value as legacy_value
from ios.self_tests.test_ios_places_transport import Boundary as LegacyTransport
from ios.self_tests.test_ios_places_model import Boundary as ModelBoundary
from ios.self_tests import test_ios_places_model as model_tests
from ios.self_tests.test_ios_location_bookmarks import RUN

ORIGIN='http://controlled.invalid:49121'
SERVER='places.server-fetch.'+hashlib.sha256(ORIGIN.encode()).hexdigest()[:32]


def row(identifier,*,popup='none',checked=None,index=None,name='',address=''):
    value=legacy_row(identifier,name=name,address=address,modal=popup=='bookmark')
    value.update(profile=controls.PROFILES[2],popup=popup,checked=checked,rowIndex=index)
    value['inputReady']=identifier!='places.page' and (identifier in controls.MODAL if popup=='bookmark' else
        controls.RATING.fullmatch(identifier) is not None if popup=='ratings' else
        popup=='none' and identifier not in controls.MODAL and controls.RATING.fullmatch(identifier) is None)
    return value


def observation(*extra,popup='none'):
    value=legacy_value();value.update(placesControlsVersion=2,controls=[row('places.page',popup=popup),*extra]);return value


def original_preferences():
    values={}
    for key in preferences.KEYS:
        array=['everyone','teen'] if key==preferences.MATURITY else []
        values[key]=dict(present=True,kind='list',value=array,valueSha256=hashlib.sha256(('QVariantList:'+key+repr(array)).encode()).hexdigest())
    return dict(placesPreferenceVersion=1,values=values,metaverseOrigin=ORIGIN,protocolSignature='AAAAAAAAAAAAAAAAAAAAAA==')


class Boundary(LegacyTransport):
    def __init__(self):
        super().__init__();self.rows=[row('places.page'),row(SERVER,checked=False,index=0,name=ORIGIN,address=ORIGIN)]
    def observed(self):
        value=super().observed();value['placesControlsVersion']=2;return value
    def post(self,request,timeout):
        result=super().post(request,timeout);payload=json.loads(request.data)
        if payload['operation']=='edit' and not self.ignore:
            command=payload['input'];items=[item for item in self.rows if item['token']==command['fieldToken']]
            if self.receipt['status']['performed'] and len(items)==1 and items[0]['checked'] is not None:
                items[0]['checked']=not items[0]['checked']
        return result


class PlacesSettingsTests(unittest.TestCase):
    def test_version_two_server_controls_bind_actual_url_row_index_and_checked_state(self):
        value=observation(row(SERVER,checked=False,index=3,name=ORIGIN,address=ORIGIN))
        self.assertIs(value,controls.snapshot(value));self.assertEqual(3,value['controls'][1]['rowIndex'])
        for update in (dict(rowName=ORIGIN+'/foreign'),dict(rowAddress='http://foreign.invalid'),dict(rowIndex=True),
                       dict(checked=0),dict(rowIndex=None),dict(rowName='http://user:secret@controlled.invalid')):
            changed=deepcopy(value);changed['controls'][1].update(update)
            with self.subTest(update=update),self.assertRaises((NativeUIError,ValueError)):controls.snapshot(changed)

    def test_actual_rating_checkbox_is_eligible_only_in_its_original_popup(self):
        value=observation(row('places.rating.everyone',popup='ratings',checked=False),popup='ratings')
        self.assertTrue(controls.snapshot(value)['controls'][1]['inputReady'])
        for update in (dict(popup='none'),dict(modal=True),dict(checked=None)):
            changed=deepcopy(value);changed['controls'][1].update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):controls.snapshot(changed)
        value['controls'][1]['inputReady']=False;value['controls'][1]['popup']='none'
        value['controls'][0]['popup']='none'
        self.assertIs(value,controls.snapshot(value))

    def test_popup_cannot_enable_a_background_server_or_bookmark_control(self):
        for popup in ('ratings','location','bookmark'):
            value=observation(row(SERVER,popup=popup,checked=False,index=0,name=ORIGIN,address=ORIGIN),popup=popup)
            value['controls'][1]['inputReady']=True
            with self.subTest(popup=popup),self.assertRaises(NativeUIError):controls.snapshot(value)

    def test_v1_originals_still_read_but_cannot_borrow_new_controls_or_profile(self):
        old=legacy_value();self.assertIs(old,controls.snapshot(old))
        for update in (dict(placesControlsVersion=2),dict(controls=[row('places.page')]),
                       dict(controls=[legacy_row('places.page'),legacy_row('places.server-url')])):
            with self.assertRaises(NativeUIError):controls.snapshot(old|update)
        value=observation(row('places.server-url'));self.assertIs(value,controls.snapshot(value))
        with self.assertRaises(NativeUIError):controls.snapshot(value|dict(placesControlsVersion=1))

    def test_changed_checkbox_row_or_popup_invalidates_the_callers_original_reference(self):
        before=observation(row(SERVER,checked=False,index=0,name=ORIGIN,address=ORIGIN));ref=controls.reference(before,SERVER)
        for update in (dict(checked=True),dict(rowIndex=1),dict(popup='ratings',inputReady=False)):
            after=deepcopy(before);after['scope'].update(observationSequence=2,elapsedMs=101,sampleEpochMs=20001)
            after['controls'][1].update(update)
            with self.subTest(update=update),self.assertRaises(NativeUIError):controls.same_reference(ref,after,SERVER)
        self.assertFalse(ref['control']['checked'])

    def test_http_afc_normal_checkbox_input_is_distinct_from_actual_observed_effect(self):
        source=Boundary()
        with patch.object(normal_input,'urlopen',source.post):
            io=source.io();before=io.capture();ref=controls.reference(before,SERVER)
            self.assertEqual({'performed':True},io.activate(SERVER,reference=ref));after=io.capture()
        self.assertFalse(ref['control']['checked']);self.assertTrue(after['controls'][1]['checked'])
        commands=[item['input'] for item in source.requests if item['operation']=='edit']
        self.assertEqual(1,len(commands));self.assertEqual(ref['control']['token'],commands[0]['fieldToken'])
        self.assertNotIn('checked',commands[0]);self.assertNotIn('expected',commands[0])

    def test_ignored_checkbox_ack_does_not_become_a_measured_preference_change(self):
        source=Boundary();source.ignore=True
        with patch.object(normal_input,'urlopen',source.post):
            io=source.io();ref=controls.reference(io.capture(),SERVER)
            self.assertEqual({'performed':True},io.activate(SERVER,reference=ref));self.assertFalse(io.capture()['controls'][1]['checked'])

    def test_changed_checkbox_before_delivery_is_not_resent_or_replaced_by_a_new_reference(self):
        source=Boundary()
        with patch.object(normal_input,'urlopen',source.post):
            io=source.io();ref=controls.reference(io.capture(),SERVER);source.rows[1]['checked']=True
            with self.assertRaises(NativeUIError):io.activate(SERVER,reference=ref)
        self.assertFalse(any(item['operation']=='edit' for item in source.requests))

    def test_original_server_field_uses_normal_focused_ime_not_a_settings_setter(self):
        source=Boundary();source.rows=[row('places.page'),row('places.server-url')];source.rows[1]['focused']=True
        with patch.object(normal_input,'urlopen',source.post):
            io=source.io();ref=controls.reference(io.capture(),'places.server-url')
            io.replace('places.server-url',ORIGIN,reference=ref);self.assertEqual(ORIGIN,io.capture()['controls'][1]['value'])
        command=[item['input'] for item in source.requests if item['operation']=='edit'][0]
        self.assertEqual('replace',command['operation']);self.assertEqual(ORIGIN,command['text'])

    def test_server_field_refuses_credentials_and_uncontrolled_path_or_query_before_input(self):
        for value in ('http://user:secret@controlled.invalid','http://controlled.invalid/path','http://controlled.invalid?token=private'):
            source=Boundary();source.rows=[row('places.page'),row('places.server-url')];source.rows[1]['focused']=True
            with patch.object(normal_input,'urlopen',source.post):
                io=source.io();ref=controls.reference(io.capture(),'places.server-url')
                with self.subTest(value=value),self.assertRaises(NativeUIError):io.replace('places.server-url',value,reference=ref)
                self.assertFalse(any(item['operation']=='edit' for item in source.requests))

    def test_original_typed_preferences_preserve_absence_empty_array_and_qt_list_type(self):
        baseline=original_preferences();self.assertIs(baseline,preferences.validate(baseline))
        self.assertTrue(preferences.restored(baseline,deepcopy(baseline)))
        for change in (dict(present=False,kind='absent',value=None),dict(kind='string-list'),dict(value=['http://unowned.invalid']),
                       dict(valueSha256='f'*64)):
            current=deepcopy(baseline);current['values'][preferences.PINNED].update(change)
            self.assertFalse(preferences.restored(baseline,current))
        # Same membership but changed order is still a different original.
        current=deepcopy(baseline);current['values'][preferences.MATURITY]['value'].reverse()
        self.assertFalse(preferences.restored(baseline,current))

    def test_unknown_typed_values_are_retained_as_unsupported_and_never_repaired(self):
        value=original_preferences();value['values'][preferences.MATURITY].update(kind='unsupported',value=None)
        self.assertIs(value,preferences.validate(value))
        with self.assertRaises(NativeUIError):preferences.ordinary_maturity_plan(value)
        for change in (dict(present=1),dict(kind='absent'),dict(valueSha256='main'),dict(kind='list',value=[False])):
            current=deepcopy(value);current['values'][preferences.MATURITY].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):preferences.validate(current)

    def test_normal_maturity_admission_refuses_a_change_that_cannot_restore_original_type_or_presence(self):
        value=original_preferences();entry=value['values'][preferences.MATURITY]
        self.assertFalse(preferences.ordinary_maturity_plan(value)['change'])
        entry.update(kind='absent',present=False,value=None)
        self.assertEqual(dict(change=False,original=None),preferences.ordinary_maturity_plan(value))
        entry.update(kind='string-list',present=True,value=['teen'])
        with self.assertRaises(NativeUIError):preferences.ordinary_maturity_plan(value)
        entry.update(kind='list');plan=preferences.ordinary_maturity_plan(value)
        self.assertTrue(plan['change']);self.assertEqual(entry,plan['original'])
        entry['value'].append('adult');self.assertNotEqual(entry,plan['original'])
        for ratings in (['teen','teen'],['unrecognized']):
            entry['value']=ratings
            with self.assertRaises(NativeUIError):preferences.ordinary_maturity_plan(value)

    def model(self):
        source=ModelBoundary();old=source.reader().read(RUN);value=deepcopy(old)
        value.update(iosPlacesModelVersion=2,preferences=original_preferences())
        value['roots'][0].update(popup='none',serverDraft='')
        return source,old,value

    def test_v2_model_keeps_loaded_preferences_independent_from_visible_checkbox_and_raw_model(self):
        source,old,value=self.model();self.assertIs(value,models.original(value))
        current=models.current(value)
        self.assertTrue(current['lists']['servers']['rows'][0]['fetched'])
        self.assertEqual([],value['preferences']['values'][preferences.FETCHED]['value'])
        # UI construction defaults and stored values are separate actual facts.
        self.assertEqual('',current['serverDraft']);self.assertNotIn('preferences',old)

    def test_actual_http_afc_factory_preserves_v2_preferences_and_native_clocks(self):
        source=ModelBoundary();harness=model_tests.PlacesModelTests();self.addCleanup(harness.doCleanups)
        def upgrade(value):
            value.update(iosPlacesModelVersion=2,preferences=original_preferences())
            for root in value['roots']:root.update(popup='none',serverDraft='')
        source.mutate=upgrade;native,observer=harness.transport(source)
        reader=observer.places_model();original=reader.read(RUN)
        self.assertEqual(source.last,original);self.assertEqual(original_preferences(),original['preferences'])
        self.assertLess(reader.acquisition['nativeRequestedEpochMs'],original['clockBefore']['epochMs'])
        self.assertGreater(reader.acquisition['nativeAfterEpochMs'],original['clockAfter']['epochMs'])
        self.assertEqual(3,len(native.commands));self.assertEqual(3,len(native.reads))

    def test_missing_v2_preferences_or_retained_hidden_popup_cannot_become_clean_state(self):
        source,old,value=self.model();value['tabletShown']=False;value['roots'][0].update(active=False,visible=False)
        value['roots'][0]['lists']['places']['visible']=False
        self.assertTrue(models.drained(value))
        value['roots'][0]['popup']='ratings';self.assertFalse(models.drained(value))
        broken=deepcopy(value);broken.pop('preferences')
        with self.assertRaises(NativeUIError):models.original(broken)
        broken=deepcopy(value);broken['iosPlacesModelVersion']=1
        with self.assertRaises(NativeUIError):models.original(broken)

    def test_version_two_model_history_cannot_silently_downgrade_after_preferences_have_been_observed(self):
        source,old,value=self.model();new=deepcopy(old);new.update(requestId='ios-'+'e'*32,sequence=2)
        for clock in ('clockBefore','clockAfter'):
            for key in new[clock]:new[clock][key]+=100
        query=dict(schemaVersion=1,commandId=new['requestId'],action=models.ACTION,runId=RUN)
        with self.assertRaises(NativeUIError):models.validate(new,query,42,previous=value)

    def run_original(self,program):
        root=Path(__file__).resolve().parents[4]
        setup=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const qml=fs.readFileSync(process.argv[1],'utf8'),script=fs.readFileSync(process.argv[2],'utf8');
function part(source,a,b){let start=source.indexOf(a),end=source.indexOf(b,start+a.length);
assert(start>=0&&end>start,'Original function boundary changed');return source.slice(start,end);}
'''
        result=subprocess.run(['node','-e',setup+program,str(root/'scripts/system/places/PicoPlaces.qml'),
            str(root/'scripts/system/places/places.js')],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_original_qml_toggle_preserves_unrelated_ratings_and_restores_original_order(self):
        self.run_original(r'''
let sent=[];const source={maturityFilter:['teen','adult'],rebuildPlaces:()=>{},dispatch:(action,data)=>sent.push({action,data})};
vm.createContext(source);vm.runInContext(part(qml,'    function toggleMaturity(', '    function changeServer('),source);
source.toggleMaturity('everyone',true);assert.deepEqual(Array.from(source.maturityFilter),['teen','adult','everyone']);
source.toggleMaturity('everyone',false);assert.deepEqual(Array.from(source.maturityFilter),['teen','adult']);
assert.equal(sent[0].action,'SET_MATURITY_FILTER');assert.deepEqual(Array.from(sent[1].data.filter),['teen','adult']);
''')

    def test_original_unpin_and_unfetch_remove_owned_external_server_without_deleting_unowned_servers(self):
        self.run_original(r'''
const values={placesAppPinnedMetaverse:['https://owned.test'],placesAppMetaverseToFetch:['https://owned.test']};
const source={metaverseServers:[],getFederationData:()=>JSON.stringify([{node:'https://unowned.test'}]),
 Settings:{getValue:(key,fallback)=>values[key]??fallback},AccountServices:{metaverseServerURL:'https://current.test'},sortOrder:()=>0};
vm.createContext(source);vm.runInContext(part(script,'    var SETTING_METAVERSE_TO_FETCH =', '    var REQUEST_TIMEOUT ='),source);
vm.runInContext(part(script,'    function buildMetaverseServerList (', '    function getLocationBookmarks('),source);
source.buildMetaverseServerList();assert.equal(source.metaverseServers.find(row=>row.url==='https://owned.test').fetch,true);
values.placesAppPinnedMetaverse=[];values.placesAppMetaverseToFetch=[];source.metaverseServers=[];source.buildMetaverseServerList();
assert.equal(source.metaverseServers.some(row=>row.url==='https://owned.test'),false);
assert.equal(source.metaverseServers.some(row=>row.url==='https://unowned.test'),true);
assert.equal(source.metaverseServers.some(row=>row.url==='https://current.test'),true);
''')


if __name__=='__main__':unittest.main()
