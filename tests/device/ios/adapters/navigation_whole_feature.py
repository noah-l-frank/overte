"""Whole Worlds action/observation/restoration coordination.

Capability admission remains closed until terminal end and all partial-setup
paths are integrated and qualified. Child originals own uncertain deliveries.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import arguments
from ios.adapters.navigation_feature import IOSNavigationFeature,NavigationFeaturePending
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
from ios.adapters.navigation_restoration import NavigationRestoration
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions

VERSION=1


class NavigationWholeFeature:
    def __init__(self,flow):
        need(type(flow) is IOSNavigationFeature);self.flow,self.lock=flow,flow.lock
        self.store=PrivateFeatureState(flow.store.path.with_name('ios-navigation-whole-feature.json'))
        self.previous=self.state=None

    def envelope(self,state):
        return dict(iosNavigationWholeFeatureVersion=VERSION,runId=self.flow.run,artifactRoot=str(self.flow.root),payload=pack([state]))

    def load(self):
        self.lock.assert_held();self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)

    def decode(self,value):
        exact(value,{'iosNavigationWholeFeatureVersion','runId','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosNavigationWholeFeatureVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','cleanup'})
        need(state['phase'] in ('preparing','active','cleaning','restored','cleaned'))
        if state['cleanup'] is not None:
            row=state['cleanup'];exact(row,{'call','started','formsSha256','surfaceSha256','returnSha256'})
            exact(row['started'],{'epochMs','monotonic'})
            need(number(row['started']['epochMs'],1,1e15) and number(row['started']['monotonic'],0,1e15))
            checker=object.__new__(NavigationSurfaceActions);checker.run=self.flow.run;checker.admission=SimpleNamespace(fixture=self.flow.fixture)
            checker.call(row['call']);need(row['call']['verb']=='cleanup')
            for key in ('formsSha256','surfaceSha256','returnSha256'):need(row[key] is None or type(row[key]) is str and len(row[key])==64)
        if state['phase'] in ('restored','cleaned'):need(state['cleanup'] is not None and all(state['cleanup'][key] is not None for key in ('formsSha256','surfaceSha256','returnSha256')))
        return deepcopy(state)

    def save(self):
        self.lock.assert_held();self.flow.clock();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def prepare(self):
        f=self.flow
        with f.held():
            f.load();self.load()
            if self.state is None:
                if f.role!='primary':raise NavigationFeaturePending('Primary Worlds whole preparation is pending')
                self.state=dict(phase='preparing',cleanup=None);self.save()
            if self.state['phase']=='preparing':
                if f.role!='primary':raise NavigationFeaturePending('Original Worlds preparation remains owned by Primary')
                NavigationWholePreparation(f).prepare();self.state['phase']='active';self.save()
            f.prepare()

    def restoration(self):
        f=self.flow;f.load();preparation=NavigationWholePreparation(f);preparation.load()
        images,_initial=preparation.originals();return NavigationRestoration(f,images[f.role])

    def act(self,call):
        f=self.flow;need(f.role=='primary');call=arguments('feature.world-navigation.act',call)
        need(call['runId']==f.run);self.prepare()
        with f.held():
            f.load();self.load();need(self.state['phase']=='active')
            return f.act(call)

    def observe(self,call):
        f=self.flow;call=arguments('feature.world-navigation.observe',call);need(call['runId']==f.run)
        self.prepare()
        with f.held():
            f.load();self.load();phase=f.fixture.read()
            if self.state['phase'] in ('cleaning','restored','cleaned') or phase['verb']=='cleanup':
                if self.state['phase'] not in ('restored','cleaned'):raise NavigationFeaturePending('Ordinary Worlds restoration is pending')
                owner=self.restoration();value=owner.advance();need(value['sequence']>call['afterSequence']);return value
            return f.observe(call['afterSequence'])

    def publish(self):
        f=self.flow;need(f.role=='actor');self.prepare()
        with f.held():
            f.load();self.load();phase=f.fixture.read()
            if self.state['phase'] in ('cleaning','restored','cleaned') or phase['verb']=='cleanup':
                if self.state['phase'] not in ('restored','cleaned'):raise NavigationFeaturePending('Ordinary Worlds restoration is pending')
                owner=self.restoration();owner.load()
                publications=owner.publications()
                original=publications.state()
                if original is not None and original['pending'] is not None:return publications.resolve(f.client)
                owner.advance()
                publications=owner.publications()
                return publications.publish(f.client,restored=True)
            observer=f.observer();publications=f.publications(observer);state=publications.state()
            if state is not None and state['pending'] is not None:return publications.resolve(f.client)
            f.observe(0);observer=f.observer();return f.publications(observer).publish(f.client)

    def cleanup(self,call):
        f=self.flow;need(f.role=='primary');call=arguments('feature.world-navigation.cleanup',call);need(call['runId']==f.run)
        outer=f.operation_clock;f.operation_clock=dict(epochMs=f.epoch_ms(),monotonic=f.clock())
        try:return self._cleanup(call)
        finally:f.operation_clock=outer

    def _cleanup(self,call):
        f=self.flow
        self.prepare()
        with f.held():
            f.load();self.load();phase=f.fixture.read();need(phase['verb']=='cleanup' and phase['inputs']=={})
            if self.state['phase']=='active':
                private=dict(iosNavigationCleanupCallVersion=1,contractVersion=16,runId=f.run,ticket=phase['ticket'],verb='cleanup',inputs={},fixtureUrl=f.fixture.fixture_url)
                self.state.update(phase='cleaning',cleanup=dict(call=private,started=deepcopy(f.operation_clock),
                    formsSha256=None,surfaceSha256=None,returnSha256=None));self.save()
            need(self.state['phase'] in ('cleaning','restored','cleaned') and self.state['cleanup']['call']['ticket']==phase['ticket'])
            if self.state['phase']!='cleaned':f.operation_clock=deepcopy(self.state['cleanup']['started']);f.clock()
            need(f.state['phase']=='ready' and (f.state['lastCall'] is None or f.state['lastCall']['phase']=='acknowledged'))
            if self.state['phase']=='cleaning':
                row=self.state['cleanup'];admission=f.admission();runtime=f.runtime
                with runtime.existing_input_session(f.selector):
                    surface=runtime._navigation_surface_actions(f.selector,admission)
                    if row['formsSha256'] is None:
                        original=surface.capture()
                        if not original['tabletShown']:surface.act(row['call'],surface='open')
                        forms=runtime._navigation_places_cleanup(f.selector,admission);forms.cleanup(row['call'])
                        row['formsSha256']=digest(forms.store.read());self.save()
                    surface=runtime._navigation_surface_actions(f.selector,admission);original=surface.capture()
                    if original['tabletShown']:surface.act(row['call'],surface='close')
                    row['surfaceSha256']=digest(surface.store.read());self.save()
                    f.return_to_original()
                    returned=(runtime._navigation_scene_inputs(f.selector,admission) if f.state['stage']==0
                        else runtime._navigation_process_return(f.selector,admission))
                    need(returned.state is not None and returned.state['phase']==('return-delivered' if f.state['stage']==0 else 'delivered'))
                    row['returnSha256']=digest(returned.store.read());self.state['phase']='restored';self.save()
        # Separate acquisitions release the source lock so Actor can retain its
        # own source/PNG cuts and actual witness deliveries between them.
        owner=None
        for index in range(3):
            if index:f.sleep(1.6)
            with f.held():owner=self.restoration()
            owner.advance()
        with f.held():
            owner.load();owner.quiet();self.load();self.state['phase']='cleaned';self.save()
        return {'performed':True}
