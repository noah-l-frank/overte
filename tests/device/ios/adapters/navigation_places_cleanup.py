"""Durable normal Places recovery under the actual cleanup phase.

Each token input is retained before transport. A completed recipe is delivery
only; independent whole restoration must still prove original product state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from navigation_observation import viewpoint_urls,same_viewpoint
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_process_scope import NavigationProcessScope,owner_path
from ios.adapters.navigation_places_inputs import IOSPlacesFlow
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.adapters import places_controls as controls,places_model as models,navigation_places_state as places
from feature_journeys.fixtures import context

VERSION=1


class NavigationPlacesCleanup:
    def __init__(self,store,admission,surface,factory):
        need(isinstance(store,PrivateFeatureState) and isinstance(admission,(NavigationAdmissionOwner,NavigationProcessScope))
            and type(surface) is NavigationSurfaceActions and surface.admission is admission and callable(factory)
            and store.path==owner_path(admission,'ios-navigation-places-cleanup.json'))
        self.store,self.admission,self.surface,self.factory=store,admission,surface,factory
        self.binding,self.run,self.lock=admission.binding,admission.run,admission.lock
        self.lock.assert_held();self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosNavigationPlacesCleanupVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([state]))

    def call(self,value):
        self.surface.call(value);need(value['verb']=='cleanup' and value.get('iosNavigationCleanupCallVersion')==1);return value

    def packet(self,value):
        exact(value,{'controls','model','root'});controls.snapshot(value['controls'])
        scope=value['controls']['scope'];floor=self.admission.archive()['originals']['ui']
        need(scope['processId']==int(self.binding['processIdentity']) and scope['instance']==floor['instance']
            and scope['sequence']>=floor['lastSequence'] and scope['sampleEpochMs']>=floor['sampleEpochMs'])
        root=models.join_controls(value['model'],value['controls']);need(same(root,value['root'])
            and value['model']['runId']==self.run and value['model']['processId']==int(self.binding['processIdentity']))
        return root

    def decode(self,value):
        exact(value,{'iosNavigationPlacesCleanupVersion','binding','runId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosNavigationPlacesCleanupVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'call','phase','fixture','before','intents','after'})
        call=self.call(state['call']);need(state['phase'] in ('checking','issued','delivered') and type(state['intents']) is list and len(state['intents'])<=64)
        if state['fixture'] is not None:
            from ios.adapters.navigation_observation_owner import fixture_original
            phase=state['fixture'];fixture_original(phase,self.run,self.admission.fixture.inputs,self.admission.fixture.instance)
            need(phase['verb']=='cleanup' and phase['ticket']==call['ticket'] and phase['inputs']=={})
        if state['phase']!='checking':need(state['fixture'] is not None and state['before'] is not None)
        previous=None
        if state['before'] is not None:
            root=self.packet(state['before']);previous=state['before']['controls'];ctx=context(self.run)
            need(root['popup'] in ('none','bookmark'))
            if root['popup']=='bookmark':
                dialog=root['dialog'];need(dialog['originalName'] in ('',ctx['name'],ctx['renamed'])
                    and dialog['name'] in ('',ctx['name'],ctx['renamed'])
                    and same_viewpoint(dialog['address'],viewpoint_urls(self.admission.fixture.inputs['sceneUrl'])['A']))
        for event in state['intents']:
            exact(event,{'iosPlacesInputVersion','runId','controlId','action','value','call','original','reference'})
            need(type(event['iosPlacesInputVersion']) is int and event['iosPlacesInputVersion']==1
                and event['runId']==self.run and same(event['call'],call) and event['action'] in ('activate','replace'))
            controls.snapshot(event['original']);need(same(event['reference'],controls.reference(event['original'],event['controlId'])))
            ctx=context(self.run);key=event['controlId'];control=event['reference']['control']
            need(control['enabled'] and control['inputReady'])
            deletions={'places.bookmark-delete.'+hashlib.sha256(name.encode()).hexdigest()[:32]:name for name in (ctx['name'],ctx['renamed'])}
            if event['action']=='replace':
                need(key=='places.search' and event['value']=='' and control['focused']
                    and control['value'] in ('',ctx['name'],ctx['hidden']))
            else:
                need(event['value'] is None and key in {'places.tab.places','places.tab.bookmarks','places.search','places.bookmark-cancel'}|set(deletions))
                if key in deletions:need(control['rowName']==deletions[key]
                    and same_viewpoint(control['rowAddress'],viewpoint_urls(self.admission.fixture.inputs['sceneUrl'])['A']))
            if previous is not None:
                a,b=previous['scope'],event['original']['scope'];need(a['instance']==b['instance'] and a['processId']==b['processId']
                    and a['sequence']<=b['sequence'] and a['observationSequence']<b['observationSequence']
                    and a['sampleEpochMs']<=b['sampleEpochMs'] and a['elapsedMs']<=b['elapsedMs'])
            previous=event['original']
        if state['after'] is not None:
            root=self.packet(state['after']);ctx=context(self.run)
            need(root['popup']=='none' and not root['dialog']['visible'] and root['search']==''
                and not ({ctx['name'],ctx['renamed']}&set(root['bookmarkAddresses'])))
        need((state['after'] is not None) if state['phase']=='delivered' else state['after'] is None)
        return deepcopy(state)

    def bound(self):
        self.admission.bound();self.surface.bound();need(same(self.store.read(),self.previous))
        if self.state is not None:
            phase=self.admission.fixture.read();need(phase['verb']=='cleanup' and phase['inputs']=={}
                and phase['ticket']==self.state['call']['ticket'])

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,value):
        self.bound();need(self.state['phase']=='issued' and len(self.state['intents'])<64)
        self.state['intents'].append(deepcopy(value));self.save()

    def cleanup(self,call):
        call=deepcopy(self.call(call));self.bound()
        if self.state is not None:
            need(self.state['phase']=='delivered' and same(call,self.state['call']));self.decode(self.previous);return {'performed':True}
        initial=self.admission.original_admission() if isinstance(self.admission,NavigationProcessScope) else self.admission.archive()
        baseline=places.baseline_entries(initial['bookmarkBaseline'],self.run,initial['binding']);ctx=context(self.run)
        need(not ({ctx['name'],ctx['renamed']}&set(baseline)))
        self.state=dict(call=call,phase='checking',fixture=None,before=None,intents=[],after=None);self.save()
        self.state['fixture']=self.admission.fixture.read();self.save()
        flow=self.factory(self.intent);need(type(flow) is IOSPlacesFlow and flow.lock is self.lock and flow.surface is self.surface
            and flow.run==self.run and same(flow.binding,self.binding))
        guard=flow.guard
        def checked():
            self.bound();return guard()
        flow.guard=checked
        value,root=flow.inspect();self.state['before']=dict(controls=deepcopy(value),model=deepcopy(flow.model_original),root=deepcopy(root));self.save()
        self.state['phase']='issued';self.save();flow.cleanup(call)
        value,root=flow.inspect();self.state['after']=dict(controls=deepcopy(value),model=deepcopy(flow.model_original),root=deepcopy(root))
        self.state['phase']='delivered';self.save();return {'performed':True}
