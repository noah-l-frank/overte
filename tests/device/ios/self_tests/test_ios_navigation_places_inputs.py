"""Real Python HTTP/AFC codecs/files; Qt model and controls are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.fixtures import context
from ios.adapters import normal_input,places_controls
from ios.adapters.navigation_places_inputs import IOSPlacesFlow
from ios.self_tests import test_ios_places_model as model_tests
from ios.self_tests.test_ios_places_settings import row,original_preferences
from ios.self_tests.test_ios_places_transport import Boundary as Transport
from ios.self_tests.test_ios_location_bookmarks import RUN
from self_tests.test_completed_frame_lease import BINDING
from self_tests.test_navigation_resources import INPUTS
from navigation_observation import viewpoint_urls


class SDK(Transport):
    def __init__(self,path,inputs=INPUTS):
        super().__init__();self.path=path;self.ctx=context(RUN);self.urls=viewpoint_urls(INPUTS['sceneUrl'])
        self.inputs=deepcopy(inputs);self.urls=viewpoint_urls(inputs['sceneUrl'])
        self.model=model_tests.Boundary();self.focus='';self.bookmarks={'unowned':'hifi://unowned'}
        self.page=self.model.pages[0];self.page.update(currentAddress=self.urls['A'],popup='none',serverDraft='',
            bookmarkAddresses=deepcopy(self.bookmarks),records=[],search='')
        def extend(value):value.update(iosPlacesModelVersion=2,preferences=original_preferences())
        self.model.mutate=extend;self.model_reader=self.model.reader();self.arrival=None
        self.persist()

    def persist(self):
        self.page['bookmarkAddresses']=deepcopy(self.bookmarks)
        self.page['lists']['bookmarks']['rows']=[dict(bookmarkName=name,bookmarkAddress=url) for name,url in sorted(self.bookmarks.items())]
        self.path.write_text(json.dumps(self.bookmarks,sort_keys=True))

    def observed(self):
        popup=self.page['popup'];self.rows=[row('places.page',popup=popup)]
        if popup=='bookmark':
            self.rows +=[row(key,popup=popup) for key in ('places.bookmark-name','places.bookmark-save','places.bookmark-cancel')]
            self.rows[1]['value']=self.page['dialog']['name']
        else:
            self.rows +=[row('places.tab.places'),row('places.tab.bookmarks')]
            if self.page['tab']==0:
                self.rows.append(row('places.search'));self.rows[-1]['value']=self.page['search']
                if not self.page['search'] or self.page['search']==self.ctx['name']:
                    key=hashlib.sha256(self.ctx['destination'].encode()).hexdigest()[:32]
                    self.rows.append(row('places.visit.'+key,name=self.ctx['destination'],address=self.urls['B']))
            else:
                self.rows.append(row('places.bookmark-add'))
                for name,url in self.bookmarks.items():
                    key=hashlib.sha256(name.encode()).hexdigest()[:32]
                    self.rows +=[row('places.'+kind+'.'+key,name=name,address=url) for kind in
                        ('bookmark-visit','bookmark-rename','bookmark-delete')]
        for item in self.rows:item['focused']=item['id']==self.focus;item['rootId']=self.page['rootId']
        value=super().observed();value.update(placesControlsVersion=2,sampleEpochMs=self.model.native_clock(),
            elapsedMs=round(self.model.clock*1000));return value

    def post(self,request,timeout):
        payload=json.loads(request.data)
        selected=None
        if payload['operation']=='edit':
            selected=next((deepcopy(item) for item in self.rows if item['token']==payload['input']['fieldToken']),None)
        result=super().post(request,timeout)
        if payload['operation']=='edit':
            self.receipt['status']['sampleEpochMs']=self.model.native_clock()
            if selected is not None and not self.ignore and self.receipt['status']['performed']:
                key=selected['id'];command=payload['input']
                if command['operation']=='replace':
                    if key=='places.search':self.page['search']=command['text']
                    else:self.page['dialog']['name']=command['text']
                elif key in ('places.search','places.bookmark-name'):self.focus=key
                elif key.startswith('places.tab.'):
                    self.page['tab']=0 if key.endswith('.places') else 1;self.focus=''
                elif key=='places.bookmark-add' or key.startswith('places.bookmark-rename.'):
                    name=selected['rowName'] if key!='places.bookmark-add' else ''
                    self.page.update(popup='bookmark',dialog=dict(visible=True,originalName=name,
                        address=selected['rowAddress'] if name else self.page['currentAddress'],name=name));self.focus=''
                elif key in ('places.bookmark-save','places.bookmark-cancel'):
                    if key.endswith('-save'):
                        dialog=self.page['dialog']
                        if dialog['originalName']:del self.bookmarks[dialog['originalName']]
                        self.bookmarks[dialog['name']]=dialog['address'];self.persist()
                    self.page['popup']='none';self.page['dialog']['visible']=False;self.focus=''
                elif key.startswith('places.bookmark-delete.'):
                    del self.bookmarks[selected['rowName']];self.persist()
                elif key.startswith(('places.bookmark-visit.','places.visit.')):self.arrival=selected['rowAddress']
        return result

    def io(self):
        native=normal_input.NativeInput(self,'owned-session',self.target,self.process,
            native_epoch_ms=self.model.native_clock,monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        return places_controls.IOSPlacesIO(SimpleNamespace(native=native,capture=native.capture))


class NavigationPlacesInputsTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.sdk=SDK(self.root/'bookmarks.json');self.io=self.sdk.io();self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock')
        self.store=PrivateFeatureState(self.root/'intents.json');self.intents=[];self.ctx=context(RUN)
        self.http=patch.object(normal_input,'urlopen',self.sdk.post);self.http.start();self.addCleanup(self.http.stop)
    def intent(self,value):
        old=self.store.read();rows=[] if old is None else unpack(old['payload']);rows.append(deepcopy(value))
        self.store.write(dict(payload=pack(rows)),old);self.intents.append(deepcopy(value))
    def flow(self,**changes):
        options=dict(io=self.io,model=self.sdk.model_reader,binding=BINDING,run=RUN,inputs=self.sdk.inputs,
            instance=self.sdk.instance,lock=self.lock,guard=lambda:self.sdk.model.live,intent=self.intent,
            monotonic=lambda:self.sdk.model.clock,sleep=self.sdk.model.sleep);options.update(changes)
        return IOSPlacesFlow(**options)
    def call(self,verb,**inputs):
        from urllib.parse import urlsplit
        source=urlsplit(self.sdk.inputs['sceneUrl'])
        return dict(contractVersion=16,runId=RUN,ticket='b'*32,
            fixtureUrl=source.scheme+'://'+source.netloc+'/feature-fixture/v1/runs/'+RUN+'/',verb=verb,inputs=inputs)
    def act(self,verb,**inputs):return self.flow().invoke(self.call(verb,**inputs))

    def test_cancel_add_rename_visit_search_select_delete_use_normal_original_tokens_and_keep_unowned_file_entries(self):
        with self.lock.held():
            before=self.sdk.path.read_bytes();self.act('bookmark-add-cancel',name=self.ctx['name'])
            self.assertEqual(before,self.sdk.path.read_bytes());self.act('bookmark-add',name=self.ctx['name'])
            saved=json.loads(self.sdk.path.read_text());self.assertEqual(self.sdk.urls['A'],saved[self.ctx['name']])
            self.act('bookmark-rename-cancel',name=self.ctx['renamed']);self.assertEqual(saved,json.loads(self.sdk.path.read_text()))
            self.act('bookmark-rename',name=self.ctx['renamed']);self.assertNotIn(self.ctx['name'],self.sdk.bookmarks)
            self.act('bookmark-visit',name=self.ctx['renamed']);self.assertEqual(self.sdk.urls['A'],self.sdk.arrival)
            self.act('directory-search',query=self.ctx['hidden']);self.assertEqual(self.ctx['hidden'],self.sdk.page['search'])
            self.act('directory-search',query=self.ctx['name']);self.act('directory-select',destination=self.ctx['destination'])
            self.assertEqual(self.sdk.urls['B'],self.sdk.arrival);self.act('bookmark-delete',name=self.ctx['renamed'])
            self.assertEqual({'unowned':'hifi://unowned'},json.loads(self.sdk.path.read_text()))
            events=unpack(self.store.read()['payload']);commands=[row['input'] for row in self.sdk.requests if row['operation']=='edit']
            self.assertEqual(len(events),len(commands));self.assertGreater(len(events),20)
            for event,command in zip(events,commands):
                self.assertEqual(event['reference']['control']['token'],command['fieldToken'])
                self.assertEqual(event['original']['scope']['sequence']+1,command['sequence'])
                self.assertEqual('b'*32,event['call']['ticket'])

    def test_ignored_tab_ack_times_out_without_retrying_an_input(self):
        with self.lock.held():
            self.sdk.ignore=True;before=self.sdk.path.read_bytes()
            with self.assertRaises(NativeUIError):self.act('bookmark-add',name=self.ctx['name'])
            self.assertEqual(1,len(self.intents));self.assertEqual(before,self.sdk.path.read_bytes())
            self.assertEqual(1,len([row for row in self.sdk.requests if row['operation']=='edit']))

    def test_failed_durable_intent_prevents_transport_delivery(self):
        def refused(_value):raise OSError('Synthetic journal write failure')
        with self.lock.held():
            with self.assertRaises(OSError):self.flow(intent=refused).invoke(self.call('bookmark-add',name=self.ctx['name']))
            self.assertFalse(any(row['operation']=='edit' for row in self.sdk.requests))

    def test_changed_root_after_durable_intent_is_not_recaptured_as_another_input(self):
        def replace(value):
            self.intent(value);self.sdk.page['rootId']='00000000-0000-4000-8000-000000000999'
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.flow(intent=replace).invoke(self.call('bookmark-add',name=self.ctx['name']))
            self.assertEqual(1,len(self.intents));self.assertFalse(any(row['operation']=='edit' for row in self.sdk.requests))

    def test_existing_owned_name_or_foreign_current_address_is_refused_before_bookmark_mutation(self):
        for fault in ('collision','address'):
            with self.subTest(fault=fault):
                self.doCleanups();self.setUp();self.sdk.page['tab']=1
                if fault=='collision':self.sdk.bookmarks[self.ctx['name']]='hifi://unowned';self.sdk.persist()
                else:self.sdk.page['currentAddress']=self.sdk.urls['B']
                before=self.sdk.path.read_bytes()
                with self.lock.held(),self.assertRaises(NativeUIError):self.act('bookmark-add',name=self.ctx['name'])
                self.assertEqual([],self.intents);self.assertEqual(before,self.sdk.path.read_bytes())

    def test_foreign_call_run_text_origin_or_unsupported_verb_fails_before_input(self):
        for changed in (dict(runId='f'*32),dict(inputs=dict(name='unowned')),dict(fixtureUrl='http://foreign.invalid/feature-fixture/v1/runs/'+RUN+'/'),
                        dict(verb='restart-app',inputs={})):
            with self.lock.held(),self.subTest(changed=changed),self.assertRaises((NativeUIError,ValueError)):
                self.flow().invoke(self.call('bookmark-add',name=self.ctx['name'])|changed)
        self.assertEqual([],self.intents)

    def test_changed_native_birth_or_previous_input_counter_cannot_start_a_new_flow(self):
        with self.lock.held():
            flow=self.flow();original=flow.capture()
            self.sdk.instance='00000000-0000-4000-8000-000000000999'
            with self.assertRaises(NativeUIError):flow.capture()
            self.sdk.instance=original['scope']['instance'];previous=deepcopy(original);previous['scope']['sequence']=5
            with self.assertRaises(NativeUIError):self.flow(previous=previous).capture()

    def test_missing_source_lock_does_not_even_read_the_model(self):
        with self.assertRaises(NativeUIError):self.flow()
        self.assertEqual([],self.sdk.model.requests)

    def test_selected_bookmark_changed_before_delivery_cannot_borrow_a_new_row_reference(self):
        self.sdk.page['tab']=1;self.sdk.bookmarks[self.ctx['renamed']]=self.sdk.urls['A'];self.sdk.persist()
        with self.lock.held():
            flow=self.flow();select=flow.owned_row
            def changed(*args):
                ref=select(*args);self.sdk.bookmarks[self.ctx['renamed']]=self.sdk.urls['B'];self.sdk.persist();return ref
            flow.owned_row=changed
            with self.assertRaises(NativeUIError):flow.invoke(self.call('bookmark-visit',name=self.ctx['renamed']))
            self.assertIsNone(self.sdk.arrival);self.assertEqual([],self.intents)

    def test_unowned_search_draft_is_preserved_without_typing_over_it(self):
        self.sdk.page['search']='user draft'
        with self.lock.held(),self.assertRaises(NativeUIError):self.act('directory-search',query=self.ctx['name'])
        self.assertEqual('user draft',self.sdk.page['search']);self.assertEqual([],self.intents)

    def test_original_native_input_floor_survives_new_page_flow_without_relabeling_a_reset_counter(self):
        with self.lock.held():
            self.sdk.sequence=4;floor=self.sdk.observed();self.sdk.sequence=0
            with self.assertRaises(NativeUIError):self.flow(floor=floor).capture()
            self.assertEqual([],self.intents)
