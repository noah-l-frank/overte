"""Real Worlds input/HTTP/JS/image owners; physical Qt/native/GPU modeled.

One producer timeline and one ordinary Go To effect feed every receiver. No
retained original packet is rewritten to bridge otherwise unrelated fixtures.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from unittest.mock import patch

from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.navigation_observation_owner import NavigationObservationOwner
from ios.adapters.navigation_observer import NavigationObserver
from ios.adapters.navigation_sample import NavigationSampleOwner
from ios.adapters.navigation_samples import NavigationSamples
from ios.self_tests.test_ios_navigation_feature import NavigationFeatureTests
from ios.self_tests import test_ios_navigation_samples as pictures
from ios.self_tests import test_ios_navigation_observation_owner as fields
from ios.self_tests.test_ios_places_settings import row as control
from ios.self_tests.test_ios_navigation_state import Boundary as NavigationBoundary


class Whole:
    def __init__(self, test):
        original=NavigationBoundary.__init__
        def viewport(producer):
            original(producer);producer.source['view']['aspectRatio']=1.6
        patcher=patch.object(NavigationBoundary,'__init__',viewport);patcher.start();test.addCleanup(patcher.stop)
        self.flow_fixture=NavigationFeatureTests();self.flow_fixture.setUp()
        test.addCleanup(self.flow_fixture.doCleanups)
        f=self.flow_fixture
        self.flow=f.flow();self.root=f.root;self.lock=self.flow.lock
        self.fixture=f.fixture;self.run=self.fixture.run;self.binding=deepcopy(f.f.admission.binding)
        self.harness=f.h.fixture.harness;self.sdk=pictures.SDK(self.harness,self.run)
        native_base=(f.h.native_first-self.sdk.gpu.offset)/1000
        self.sdk.gpu.__class__=type('SharedWorld',(type(self.sdk.gpu),),{
            'clock':property(lambda _world:native_base+f.h.ms/1000+f.b.clock,
                lambda _world,value:setattr(f.b,'clock',max(f.b.clock,value-native_base-f.h.ms/1000)))})
        self.now=f.epoch;self.mono=f.mono;self.gpu=pictures.GPU(self.sdk)
        run_source=deepcopy(self.sdk.navigation.source)
        initial=f.h.fixture.originals
        # These are physical model producers, installed before their first
        # future response, not changes to the retained static admission.
        self.sdk.navigation.source=deepcopy(initial['navigation']['source'])
        self.sdk.navigation.url=f.b.current
        self.sdk.navigation.sequence=initial['navigation']['sequence']
        self.sdk.native_boundary.sequence=f.f.admission.native.sequence
        self.fetch_directory=True
        inventory=f.h.fixture.inventory
        def loads(value):
            value['source']['sceneLoads'].update(currentGeneration=inventory.generation,requests=deepcopy(inventory.loads))
        self.sdk.navigation.mutate=loads
        original_call=f.b.call
        def ordinary(method,path,body=None):
            was=f.b.screen;url_before=f.b.current
            result=original_call(method,path,body)
            if f.b.current.startswith(self.harness.inputs['sceneUrl']):
                if f.b.current!=url_before:
                    _status,raw,_response=self.harness.get('/navigation/scene.json')
                    inventory.clock=self.sdk.gpu.clock;inventory.url=f.b.current;inventory.body=raw
                    inventory.raw={row['id'].strip('{}'):json.dumps(row,sort_keys=True).encode() for row in json.loads(raw)['Entities']}
                    inventory.revision=inventory.after_revision=3;inventory.commit()
                self.sdk.navigation.url=f.b.current
                self.sdk.navigation.source=deepcopy(run_source)
                self.sdk.navigation.source['sceneUrl']=f.b.current
            if was!='places' and f.b.screen=='places' and not f.f.ignore_places and self.fetch_directory:
                self.materialize()
            return result
        f.b.call=ordinary
        self.books=fields.BookSource(self.sdk,f.h.fixture.books.path)
        self.books.loaded=deepcopy(f.h.fixture.books.loaded)
        self.books.sequence=initial['bookmarks']['sequence']
        self.model=fields.ModelSource(self.sdk);self.model.sequence=initial['model']['sequence']
        mutate=self.model.mutate
        def preferences(value):
            mutate(value);value['preferences']['metaverseOrigin']=self.harness.origin
        self.model.mutate=preferences
        self.http=fields.HttpSource(self.sdk);self.http.sequence=initial['http']['sequence']
        self.dialogs=fields.DialogSource(self.sdk);self.dialogs.sequence=initial['dialogs']['sequence']
        self.reply_queries=[];self.reply_sequence=initial['replies']['sequence']
        def replies():
            self.sdk.gpu.clock+=.001;self.reply_sequence+=1
            return json.dumps(dict(navigationReplyVersion=1,commandId=self.reply_queries[-1]['commandId'],
                runId=self.run,instance='e'*32,sequence=self.reply_sequence,processId=42,
                capturedEpochMs=self.sdk.gpu.epoch(),currentLookupGeneration=1,currentLookupActive=False,events=[]))
        self.sources=dict(bookmarks=self.books.reader(),model=self.model.reader(),http=self.http.reader(),
            dialogs=self.dialogs.reader(),ui=f.f.h.native,replies=NativeNavigationReplies(self.reply_queries.append,
                replies,self.sdk.gpu.epoch,lambda:self.sdk.okay,42,ios=True,monotonic=self.mono,sleep=f.b.sleep))
        observed=f.b.observed
        def ui():
            value=observed()
            if f.b.screen=='places' and self.model.pages:
                page=self.model.pages[0]
                for name in ('places.search',):
                    item=control(name);item.update(rootId=page['rootId'],qmlSource=page['qmlSource'],
                        frame=dict(x=10,y=20,width=300,height=40));value['controls'].append(item)
            return value
        f.b.observed=ui
        self.native=self.sdk.native();self.navigation=self.sdk.navigation.reader()
        f.runtime._navigation_observer=lambda _selector,_client,_run,role,_stage,_root,_lock:self.observer(role,lock=_lock)

    def observer(self,role='primary',*,lock=None):
        lock=self.lock if lock is None else lock
        def child(request):
            return NavigationSampleOwner(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-'+request[4:]+'-sample.json')),
                self.root,self.binding,self.run,role,0,request,lock,lambda:self.sdk.okay,native=self.native,
                navigation=self.navigation,fixture=self.fixture,frame_factory=self.gpu.factory,
                epoch_ms=self.now,monotonic=self.mono,sleep=self.sdk.gpu.sleep)
        images=NavigationSamples(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-samples.json')),
            self.root,self.binding,self.run,role,0,lock,lambda:self.sdk.okay,factory=child)
        def owner(request,previous):
            return NavigationObservationOwner(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-'+request+'-observation.json')),
                images,self.binding,self.run,role,0,request,lock,lambda:self.sdk.okay,native=self.native,
                navigation=self.navigation,sources=self.sources,fixture=self.fixture,previous=previous,
                epoch_ms=self.now,monotonic=self.mono)
        return NavigationObserver(PrivateFeatureState(self.root/('ios-navigation-'+role+'-0-observer.json')),
            images,factory=owner,epoch_ms=self.now,monotonic=self.mono)

    def open_directory(self):
        call=self.flow_fixture.f.call('open');self.gpu.marker=call['ticket']
        self.flow.act(call)
        return call

    def materialize(self):
        self.http.begin(self.harness.origin)
        status,raw,response=self.harness.get('/api/v1/places?status=online&per_page=1000')
        if status!=200:raise AssertionError('Actual Places response failed')
        self.http.response(raw,response)
        page=self.http.model(raw,origin=self.harness.origin,run=self.run)['roots'][0]
        page.update(bookmarkAddresses={},popup='none',serverDraft='')
        page['lists']['bookmarks']['rows']=[]
        self.model.pages=[page];self.model.shown=True
