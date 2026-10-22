"""Fresh modeled Qt/W3C input surface after actual modeled process launch.

Normal token recipes, HTTP/JS/QML materialization and bookmark files are real.
The new UI has independent root/input births and uses the new source cohort.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from types import SimpleNamespace
from urllib.parse import parse_qs,urlsplit
import uuid
from unittest.mock import patch

from ios.adapters import normal_input
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.self_tests.test_ios_navigation_address_inputs import RetainedBoundary
from ios.self_tests.navigation_feature_places_fixture import PlacesWidget
from ios.self_tests.navigation_feature_observer_fixture import Whole
from navigation_observation import viewpoint_urls


class NextUI:
    materialize=Whole.materialize

    def sync_navigation(self):
        current=self.flow_fixture.b.current
        base=self.base_url
        if not current.startswith(base):return Whole.sync_navigation(self)
        if self.inventory.url!=current:
            parts=urlsplit(current);status,raw,_response=self.harness.get(parts.path)
            if status!=200:raise AssertionError('Ordinary static return did not fetch the actual base scene')
            self.inventory.url,self.inventory.body=current,raw
            self.inventory.raw={row['id'].strip('{}'):json.dumps(row,sort_keys=True).encode()
                for row in json.loads(raw)['Entities']}
            self.inventory.revision=self.inventory.after_revision=self.inventory.revision+1
            self.inventory.commit()
        source=self.static_source;self.sdk.navigation.url=current;self.sdk.navigation.source=deepcopy(source)
        self.sdk.navigation.source['sceneUrl']=current
        location=parse_qs(urlsplit(current).query)['location'][0].split('/')
        feet=list(map(float,location[1].split(',')));rotation=list(map(float,location[2].split(',')))
        offset=[a-b for a,b in zip(source['view']['position'],source['avatar']['feetPosition'])]
        self.sdk.navigation.source['avatar'].update(feetPosition=feet,orientation=rotation)
        self.sdk.navigation.source['view'].update(position=[a+b for a,b in zip(feet,offset)],rotation=rotation)

    def __init__(self,cohort,test):
        self.h=cohort.h;self.sdk,self.inventory=cohort.sdk,cohort.inventory
        self.sources=cohort.sources;self.native=cohort.native;self.harness=self.h.harness
        self.books,self.model,self.http=cohort.books,cohort.model,cohort.http
        self.root,self.run=self.h.root,self.h.run;self.fetch_directory=True;self.ignore_motion=False
        self.run_source=deepcopy(self.sdk.navigation.source)
        with self.h.flow.held():
            initial=self.h.flow.initial_admission()
        from ios.self_tests.test_ios_navigation_state import Boundary as StaticNavigation
        from feature_journeys.navigation_scene import marker_id
        self.static_source=StaticNavigation().source
        self.static_source['view']['aspectRatio']=1.6
        self.static_source['challengeMarker']=dict(id=marker_id(self.run),present=False,entity=None)
        self.base_url=initial['base']['url']
        b=RetainedBoundary();physical_clock=self.sdk.gpu
        b.__class__=type('NewQtSurface',(type(b),),{'clock':property(lambda _:physical_clock.clock,
            lambda _,value:setattr(physical_clock,'clock',max(physical_clock.clock,value)))})
        b.native_boundary.pid=43;b.native_boundary.instance=str(uuid.UUID(hex=cohort.name('ui')))
        b.current=viewpoint_urls(self.harness.inputs['sceneUrl'])['A'];b.scene=self.harness.inputs['sceneUrl']
        self.flow_fixture=SimpleNamespace(b=b,f=SimpleNamespace(root_id=str(uuid.uuid4()),ignore_places=False),runtime=self.h.runtime)
        original=b.observed
        def observed():
            value=original();cohort.ui_sequence+=1
            value.update(processId=43,sampleEpochMs=physical_clock.epoch(),elapsedMs=round(physical_clock.clock*1000),
                placesControlsVersion=2,placesSourceSequence=cohort.ui_sequence)
            value['navigationDialogSourceSequence']=cohort.ui_sequence
            return value
        b.observed=observed;b.native_epoch=physical_clock.epoch
        post=b.post
        def native_post(request,timeout):
            response=post(request,timeout);receipt=b.native_boundary.receipt
            if 'status' in receipt:receipt['status']['processId']=43
            return response
        port=patch.object(normal_input,'urlopen',native_post);port.start();test.addCleanup(port.stop)
        self.sources['ui']=normal_input.NativeInput(b.native_boundary,'owned-session',b.target,b.native_boundary.process,
            monotonic=self.h.mono,sleep=b.sleep,native_epoch_ms=physical_clock.epoch)
        source=self.h.runtime._sources
        def current(selector):
            value=source(selector)
            if value['binding']['processIdentity']=='43':
                value.update(client=b,session='owned-session',native=self.sources['ui'],clock_source=self.native)
            return value
        self.h.runtime._sources=current
        call=b.call
        def ordinary(method,path,body=None):
            was=b.screen;value=call(method,path,body);self.sync_navigation()
            if was!='places' and b.screen=='places':self.materialize()
            return value
        b.call=ordinary
        self.widget=PlacesWidget(self,test)
        surface=self.h.runtime._navigation_surface_actions
        def surfaces(selector,admission):
            if admission.binding['processIdentity']=='42':return surface(selector,admission)
            return IOSNavigationRuntime._navigation_surface_actions(self.h.runtime,selector,admission)
        self.h.runtime._navigation_surface_actions=surfaces
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters.navigation_process_return import NavigationProcessReturn
        def returning(selector,scope):
            return NavigationProcessReturn(PrivateFeatureState(scope.store.path.with_name('ios-navigation-process-return-43.json')),
                scope,b.ui,self.sources['ui'],epoch_ms=self.h.now,monotonic=self.h.mono)
        self.h.runtime._navigation_process_return=returning
