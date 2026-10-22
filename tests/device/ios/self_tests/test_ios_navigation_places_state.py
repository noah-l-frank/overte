"""Actual persistence/provider/JS filtering; native UI and clocks modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import NavigationResources,DIRECTORY,QUERY
from ios.adapters import navigation_places_state as measured
from ios.self_tests.test_ios_location_bookmarks import Boundary as Bookmarks,RUN
from ios.self_tests.test_ios_places_http import Boundary as Http,INPUTS,ORIGIN,TICKET
from ios.self_tests.test_ios_places_settings import original_preferences,row
from ios.self_tests.test_ios_navigation_ui import observed,root as address_root
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from self_tests.test_completed_frame_lease import BINDING
from navigation_observation import viewpoint_urls

BINDING=dict(BINDING,sourceRevision=INPUTS['sourceRevision'])
ROOT=Path(__file__).resolve().parents[4]


def filter_rows(records,query):
    # Execute the unchanged original QML filter, with its ListModel port modeled.
    program=r'''
const fs=require('node:fs'),vm=require('node:vm'),source=fs.readFileSync(process.argv[1],'utf8');
const first=source.indexOf('    function rebuildPlaces('),last=source.indexOf('    function toggleMaturity(',first);
if(first<0||last<=first)throw Error('original filter moved');let rows=[];
const page={records:JSON.parse(process.argv[2]),search:{text:process.argv[3]},maturityFilter:['everyone'],qsTr:s=>s,
 placesModel:{clear:()=>rows=[],append:r=>rows.push(r)}};
vm.createContext(page);vm.runInContext(source.slice(first,last),page);page.rebuildPlaces();process.stdout.write(JSON.stringify(rows));
'''
    value=subprocess.run(['node','-e',program,str(ROOT/'scripts/system/places/PicoPlaces.qml'),json.dumps(records),query],
        capture_output=True,text=True,timeout=5)
    if value.returncode:raise AssertionError(value.stderr)
    return json.loads(value.stdout)


class Harness:
    def __init__(self,path,initial=None):
        self.http=Http();self.bookmarks=Bookmarks(path);self.ctx=context(RUN)
        if initial is not None:path.write_text(json.dumps(initial));self.bookmarks.loaded=deepcopy(initial)
        baseline=self.bookmarks.reader().read(RUN)
        self.baseline=measured.bookmark_baseline(BINDING,RUN,baseline)
        self.http.clock=self.bookmarks.clock+.01
        self.provider=NavigationResources(INPUTS,clock_ms=self.http.epoch)
        self.provider.provision(RUN);self.provider.activate(RUN,TICKET)
        floor=self.provider.snapshot(RUN)['capturedEpochMs'];self.http.begin()
        with self.provider.response(DIRECTORY,QUERY) as response:_status,self.raw,response_id=response
        self.http.response(self.raw,response_id)
        native=self.http.reader().read(RUN);model=self.http.model(self.raw)
        admission=dict(runId=RUN,ticket=TICKET,inputs=INPUTS,origin=ORIGIN,
            nativeAfterEpochMs=self.http.events[0]['clock']['epochMs'],providerAfterEpochMs=floor,afterEvent=0)
        self.proof=measured.directory_proof(BINDING,dict(http=native,model=model,provider=self.provider.snapshot(RUN)),admission)

    def save(self,entries):
        self.bookmarks.loaded=deepcopy(entries);self.bookmarks.path.write_text(json.dumps(entries))

    def read(self,*,panel=True,query='',address=False):
        model=self.http.model(self.raw);model.update(iosPlacesModelVersion=2,preferences=original_preferences(),sequence=2)
        model['tabletShown']=panel;page=model['roots'][0]
        page.update(search=query,bookmarkAddresses=deepcopy(self.bookmarks.loaded),active=panel,visible=panel,popup='none',serverDraft='')
        page['lists']['places'].update(visible=panel,rows=filter_rows(page['records'],query))
        page['lists']['bookmarks']['visible']=False
        self.bookmarks.clock=self.http.clock+.001
        saved=self.bookmarks.reader().read(RUN);self.http.clock=self.bookmarks.clock+.001
        native=self.http.reader().read(RUN);self.http.clock+=.001
        ui=observed(*([address_root()] if address else []));ui.update(tabletShown=panel,sampleEpochMs=self.http.epoch(),
            placesControlsVersion=2,placesSourceSequence=2)
        if panel:
            editor=row('places.search');editor['value']=query
            ui['controls']=[dict(control,frame=dict(x=10,y=20,width=300,height=40)) for control in (row('places.page'),editor)]
        originals=dict(model=model,bookmarks=saved,http=native,ui=ui)
        return originals,join(originals)

    def project(self,sample,**changes):
        options=dict(baseline=self.baseline,directory=self.proof,provider_inputs=INPUTS);options.update(changes)
        return measured.compose(RUN,BINDING,*sample,**options)


def join(originals):
    start=min(value['clockBefore']['epochMs'] for key,value in originals.items() if key!='ui')-1
    end=max([value['clockAfter']['epochMs'] for key,value in originals.items() if key!='ui']+[originals['ui']['sampleEpochMs']])+1
    return dict(clockJoinVersion=1,hostBeforeEpochMs=1_000_000.,hostAfterEpochMs=1_000_000.+end-start,
        hostBeforeMonotonic=10.,hostAfterMonotonic=10.+(end-start)/1000,nativeBefore=global_packet(start,1),
        nativeAfter=global_packet(end,2),originalsSha256=digest(originals),
        sourceTimes=[dict(source='ui',field='sampleEpochMs',epochMs=originals['ui']['sampleEpochMs'])])


class NavigationPlacesStateTests(unittest.TestCase):
    def harness(self,initial=None):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        return Harness(Path(directory.name)/'bookmarks.json',initial)

    def test_six_original_fields_are_separate_from_arrival_error_and_publication(self):
        h=self.harness();sample=h.read();before=deepcopy(sample);result=h.project(sample)
        self.assertEqual(dict(bookmark=False,bookmarkName='',searchQuery='',searchResults=[h.ctx['destination']],
                              panel=True,addressDialog=False),result['fields'])
        self.assertEqual(before,sample);self.assertEqual(measured.FIELDS,set(result['fields']))
        self.assertNotIn('location',result['fields']);self.assertNotIn('error',result['fields']);self.assertNotIn('passed',result)

    def test_actual_qml_search_results_are_never_recomputed_from_requested_input(self):
        h=self.harness();hidden=h.read(query=h.ctx['hidden']);name=h.read(query=h.ctx['name'])
        self.assertEqual([],h.project(hidden)['fields']['searchResults'])
        self.assertEqual([h.ctx['destination']],h.project(name)['fields']['searchResults'])
        ignored=h.read();self.assertEqual('',h.project(ignored)['fields']['searchQuery'])
        # The projection must retain a real bad filtering outcome so the shared
        # checkpoint rejects it, rather than fixing the product model in Python.
        hidden[0]['model']['roots'][0]['lists']['places']['rows']=deepcopy(name[0]['model']['roots'][0]['lists']['places']['rows'])
        self.assertEqual([h.ctx['destination']],h.project((hidden[0],join(hidden[0])))['fields']['searchResults'])

    def test_actual_add_rename_and_delete_preserve_unowned_entries_and_real_file(self):
        h=self.harness({'saved':'hifi://unowned'});url=viewpoint_urls(INPUTS['sceneUrl'])['A']
        for name in (h.ctx['name'],h.ctx['renamed']):
            h.save({'saved':'hifi://unowned',name:url});fields=h.project(h.read())['fields']
            self.assertTrue(fields['bookmark']);self.assertEqual(name,fields['bookmarkName'])
        h.save({'saved':'hifi://unowned'});self.assertFalse(h.project(h.read())['fields']['bookmark'])
        self.assertEqual({'saved':'hifi://unowned'},json.loads(h.bookmarks.path.read_text()))

    def test_bookmark_tab_retains_actual_hidden_directory_model_without_an_input_token(self):
        h=self.harness();originals,_clock=h.read(query=h.ctx['hidden']);page=originals['model']['roots'][0]
        page['tab']=1;page['lists']['places']['visible']=False;page['lists']['bookmarks']['visible']=True
        originals['ui']['controls']=originals['ui']['controls'][:1]
        actual=h.project((originals,join(originals)))['fields']
        self.assertEqual(h.ctx['hidden'],actual['searchQuery']);self.assertEqual([],actual['searchResults'])
        page['lists']['places']['rows']=deepcopy(h.proof['originals']['model']['roots'][0]['lists']['places']['rows'])
        self.assertEqual([h.ctx['destination']],h.project((originals,join(originals)))['fields']['searchResults'])
        originals['ui']['controls'].append(dict(row('places.search'),frame=dict(x=10,y=20,width=300,height=40)))
        with self.assertRaises(NativeUIError):h.project((originals,join(originals)))

    def test_cancelled_or_ignored_input_uses_unchanged_storage_and_not_the_draft(self):
        h=self.harness();self.assertFalse(h.project(h.read())['fields']['bookmark'])
        h.save({h.ctx['name']:viewpoint_urls(INPUTS['sceneUrl'])['A']})
        self.assertEqual(h.ctx['name'],h.project(h.read())['fields']['bookmarkName'])
        h.bookmarks.loaded={h.ctx['renamed']:viewpoint_urls(INPUTS['sceneUrl'])['A']}
        with self.assertRaises(NativeUIError):h.project(h.read())

    def test_deleted_last_entry_leaves_original_empty_container_distinct_from_absence(self):
        h=self.harness();self.assertEqual('absent',h.baseline['original']['file']['status'])
        h.save({});sample=h.read(panel=False)
        self.assertFalse(h.project(sample)['fields']['bookmark']);self.assertTrue(h.bookmarks.path.exists())
        self.assertEqual('ready',sample[0]['bookmarks']['file']['status'])
        self.assertEqual('absent',h.baseline['original']['file']['status'])

    def test_missing_persistence_load_error_wrong_A_or_two_owned_names_do_not_project(self):
        for fault in ('disk','error','wrong-url','two','invalid'):
            h=self.harness();h.save({h.ctx['name']:viewpoint_urls(INPUTS['sceneUrl'])['A']})
            if fault=='disk':h.bookmarks.path.write_text('{}')
            elif fault=='error':h.bookmarks.load_error=True
            elif fault=='wrong-url':h.save({h.ctx['name']:viewpoint_urls(INPUTS['sceneUrl'])['B']})
            elif fault=='two':h.save({key:viewpoint_urls(INPUTS['sceneUrl'])['A'] for key in (h.ctx['name'],h.ctx['renamed'])})
            else:h.bookmarks.path.write_text('{invalid')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project(h.read())

    def test_unowned_bookmark_loss_or_edit_is_not_hidden_by_a_valid_owned_entry(self):
        for current in ({},{'saved':'hifi://changed'},{'saved':'hifi://unowned','foreign-new':'hifi://new'}):
            h=self.harness({'saved':'hifi://unowned'});h.save(current)
            with self.subTest(current=current),self.assertRaises(NativeUIError):h.project(h.read())

    def test_genuine_refresh_original_is_reused_without_retiming_its_native_read(self):
        h=self.harness();proof=deepcopy(h.proof);h.http.clock+=10
        result=h.project(h.read());self.assertTrue(result['fields']['panel'])
        self.assertEqual(proof,h.proof)
        self.assertLess(h.proof['materialized']['nativeRead']['clock']['epochMs'],result['nativeBeforeEpochMs']-5000)

    def test_retimestamped_old_model_cannot_borrow_a_new_response_marker(self):
        h=self.harness()
        with h.provider.response(DIRECTORY,QUERY) as response:_status,new,response_id=response
        self.assertNotEqual(json.loads(h.raw)['data']['places'][0]['description'],json.loads(new)['data']['places'][0]['description'])
        h.raw=new
        with self.assertRaises(NativeUIError):h.project(h.read())

    def test_complete_hidden_queues_and_popups_are_required_even_with_tablet_closed(self):
        for field,value in (('loading',True),('pendingCommands',[dict(channel='com.overte.places',action='ADD_BOOKMARK')]),
                            ('timerRunning',True),('popup','ratings')):
            h=self.harness();originals,_clock=h.read(panel=False);originals['model']['roots'][0][field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):h.project((originals,join(originals)))

    def test_actual_dialog_inventory_survives_input_suppression_and_incomplete_is_not_closed(self):
        h=self.harness();sample=h.read(panel=False,address=True)
        self.assertEqual([],sample[0]['ui']['controls']);self.assertTrue(h.project(sample)['fields']['addressDialog'])
        sample[0]['ui']['navigationInventory'].update(complete=False,roots=[])
        with self.assertRaises(NativeUIError):h.project((sample[0],join(sample[0])))

    def test_input_field_model_pid_selected_page_and_preferences_must_agree(self):
        for fault in ('editor','root','pid','origin','signature','model-bookmarks','maturity','no-proof','unknown-query'):
            h=self.harness();sample=h.read();originals,_clock=sample;model=originals['model'];page=model['roots'][0];change={}
            if fault=='editor':originals['ui']['controls'][1]['value']=h.ctx['name']
            elif fault=='root':originals['ui']['controls'][0]['rootId']='11111111-2222-3333-4444-555555555555'
            elif fault=='pid':originals['bookmarks']['processId']=43
            elif fault=='origin':model['preferences']['metaverseOrigin']='http://foreign.invalid'
            elif fault=='signature':model['preferences']['protocolSignature']='AQEBAQEBAQEBAQEBAQEBAQ=='
            elif fault=='model-bookmarks':page['bookmarkAddresses']={'not-loaded':'hifi://old'}
            elif fault=='maturity':page['maturityFilter']=['teen']
            elif fault=='no-proof':change['directory']=None
            else:page['search']=originals['ui']['controls'][1]['value']='unowned query'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project((originals,join(originals)),**change)

    def test_bounded_clock_join_and_original_source_lifetime_cannot_be_relabelled(self):
        for fault in ('hash','outside','source-birth','model-birth','bookmark-birth','history','lifecycle','candidate'):
            h=self.harness();originals,clock=h.read()
            if fault=='hash':originals['ui']['elapsedMs']+=1
            elif fault=='outside':clock['nativeBefore']['capturedEpochMs']=clock['nativeBefore']['requestedEpochMs']=originals['ui']['sampleEpochMs']
            elif fault=='source-birth':originals['http']['instance']='a'*32;clock=join(originals)
            elif fault=='model-birth':originals['model']['instance']='a'*32;clock=join(originals)
            elif fault=='bookmark-birth':originals['bookmarks']['instance']='a'*32;clock=join(originals)
            elif fault=='history':originals['http']['events']=[];clock=join(originals)
            elif fault=='lifecycle':clock['nativeAfter']['lifecycle']['activations']+=1
            else:h.proof['binding']['artifactSha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project((originals,clock))

    def test_closed_page_cannot_export_retired_query_or_model_as_live_results(self):
        h=self.harness();sample=h.read(panel=False,query=h.ctx['name']);fields=h.project(sample)['fields']
        self.assertEqual('',fields['searchQuery']);self.assertEqual([],fields['searchResults'])
        self.assertEqual(h.ctx['name'],sample[0]['model']['roots'][0]['search'])

    def test_closed_bookmark_observation_does_not_require_a_fresh_directory_fetch(self):
        h=self.harness();h.save({h.ctx['renamed']:viewpoint_urls(INPUTS['sceneUrl'])['A']})
        result=h.project(h.read(panel=False),directory=None)
        self.assertTrue(result['fields']['bookmark']);self.assertEqual(h.ctx['renamed'],result['fields']['bookmarkName'])
        self.assertIsNone(result['directoryProofSha256'])
        with self.assertRaises(NativeUIError):h.project(h.read(panel=False),directory=None,
            provider_inputs=dict(INPUTS,sourceRevision='f'*40))

    def test_modified_frozen_refresh_or_foreign_source_inputs_cannot_be_adopted(self):
        for fault in ('materialized','native-floor','provider-inputs'):
            h=self.harness()
            if fault=='materialized':h.proof['materialized']['record']['description']='borrowed description'
            elif fault=='native-floor':h.proof['admission']['nativeAfterEpochMs']+=1000
            else:h.proof['admission']['inputs']['sourceRevision']='f'*40
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):h.project(h.read())
