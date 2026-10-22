"""Normal Places recipes over original iOS tokens and independently read models.

The caller must durably journal each input intent before returning from intent.
No recipe returns saved-bookmark, world-arrival or complete feature evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from urllib.parse import urlsplit

from adapters.native_feature_observation import need,number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context as run_context
from feature_journeys.navigation_fixture import configuration
from ios.adapters import places_controls as controls,places_model as models
from navigation_observation import same_viewpoint

VERSION=1


class IOSPlacesFlow:
    def __init__(self,io,model,binding,run,inputs,instance,lock,guard,intent,*,previous=None,
                 floor=None,monotonic=time.monotonic,sleep=time.sleep,surface=None):
        need(isinstance(io,controls.IOSPlacesIO) and isinstance(model,models.IOSPlacesModel)
             and isinstance(lock,ScriptSourceLock) and all(callable(fn) for fn in (guard,intent,monotonic,sleep)))
        context(binding);identifier(run);controls.identity(instance)
        self.inputs,self.urls=configuration(inputs);need(self.inputs['sourceRevision']==binding['sourceRevision']
             and model.pid==int(binding['processIdentity']) and io.original.native.session==binding['sessionId'])
        self.io,self.model,self.binding,self.run,self.instance=io,model,deepcopy(binding),run,instance
        self.lock,self.guard,self.intent,self.monotonic,self.sleep=lock,guard,intent,monotonic,sleep
        self.ctx=run_context(run);self.last=deepcopy(previous);self.started=self.last_clock=None
        self.root=self.call=None
        self.surface,self.surface_original=surface,None
        self.floor=deepcopy(floor)
        if floor is not None:
            from ios.adapters.normal_input import observation
            observation(floor,int(binding['processIdentity']),floor.get('sampleEpochMs'))
            need(floor['instance']==instance and floor.get('placesControlsVersion')==2)
        if previous is not None:
            controls.snapshot(previous);self.root=self.page(previous)['rootId']
        if surface is not None:
            from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
            need(isinstance(surface,NavigationSurfaceActions) and surface.lock is lock
                and same(surface.binding,binding) and surface.run==run)
            surface.bound();need(surface.state is not None and surface.state['actions'])
            row=surface.state['actions'][-1]
            need(row['phase']=='acknowledged' and row.get('surface',row['call']['verb'])=='open'
                and row['after'] is not None and same(row['page'],surface.page(row['after'])))
            self.surface_original=deepcopy(surface.store.read());surface.decode(self.surface_original)
            self.root=row['page']['rootId']
        self.bound()

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False)
        if self.surface is not None:
            owner=self.surface;owner.bound()
            need(same(owner.store.read(),self.surface_original) and same(owner.envelope(owner.state,
                self.surface_original['iosNavigationSurfaceActionsVersion']),self.surface_original))
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock))
        self.last_clock=now
        if self.started is not None:need(now-self.started<30)
        return now

    @staticmethod
    def row(value,key):
        found=[row for row in value['controls'] if row['id']==key];need(len(found)==1);return found[0]

    def page(self,value):
        controls.snapshot(value);need(value['placesControlsVersion']==2 and value['open'] and value['ready'])
        page=self.row(value,'places.page');need(self.root in (None,page['rootId']));return page

    def capture(self):
        self.bound();value=self.io.capture();page=self.page(value);scope=value['scope']
        need(scope['instance']==self.instance and scope['processId']==int(self.binding['processIdentity']))
        if self.floor is not None:
            need(scope['sequence']>=self.floor['lastSequence'] and scope['sampleEpochMs']>=self.floor['sampleEpochMs']
                 and scope['elapsedMs']>=self.floor['elapsedMs']
                 and scope['observationSequence']>self.floor['placesSourceSequence'])
        if self.last is not None:
            old=self.last['scope']
            need(scope['instance']==old['instance'] and scope['processId']==old['processId']
                 and scope['sequence']>=old['sequence'] and scope['observationSequence']>old['observationSequence']
                 and scope['elapsedMs']>=old['elapsedMs'] and scope['sampleEpochMs']>=old['sampleEpochMs'])
        if self.surface is not None:
            old=self.surface.state['actions'][-1]['after']
            need(scope['sequence']>=old['lastSequence'] and scope['observationSequence']>old['placesSourceSequence']
                and scope['sampleEpochMs']>=old['sampleEpochMs'] and scope['elapsedMs']>=old['elapsedMs'])
        self.root=page['rootId'];self.last=deepcopy(value);self.bound();return value

    def inspect(self):
        self.bound();packet=self.model.read(self.run);value=self.capture()
        root=models.join_controls(packet,value);need(packet['iosPlacesModelVersion']==2)
        self.bound();return value,root

    def wait(self,predicate):
        deadline=self.bound()+10
        for attempt in range(102):
            value,root=self.inspect()
            if predicate(value,root):return value,root
            now=self.bound()
            if now>=deadline or attempt==101:break
            self.sleep(min(.1,deadline-now))
        raise NativeUIError('Normal iOS Places transition was not observed')

    def input(self,key,action='activate',value=None,*,selected=None):
        self.bound();need(self.call is not None and controls.control_id(key,2) and key!='places.page' and action in ('activate','replace'))
        if action=='replace':need(key in ('places.search','places.bookmark-name') and value in
            (self.ctx['name'],self.ctx['renamed'],self.ctx['hidden']))
        else:need(value is None)
        original=self.capture();row=self.row(original,key);need(row['enabled'] and row['inputReady'])
        if controls.ROW.fullmatch(key):need(selected is not None)
        if selected is not None:controls.same_reference(selected,original,key)
        if action=='replace':
            need(row['focused'] and row['value'] in
                (('',self.ctx['name'],self.ctx['hidden']) if key=='places.search' else ('',self.ctx['name'],self.ctx['renamed'])))
        reference=controls.reference(original,key)
        self.intent(dict(iosPlacesInputVersion=VERSION,runId=self.run,controlId=key,action=action,value=value,
            call=deepcopy(self.call),original=deepcopy(original),reference=deepcopy(reference)))
        self.bound()
        if action=='replace':self.io.replace(key,value,reference=reference)
        else:self.io.activate(key,reference=reference)
        after=self.capture();need(after['scope']['sequence']==original['scope']['sequence']+1)
        return original

    def tab(self,index):
        need(type(index) is int and index in (0,1))
        _value,root=self.inspect();need(root['popup']=='none' and not root['loading'])
        if root['tab']!=index:
            self.input('places.tab.places' if index==0 else 'places.tab.bookmarks')
            self.wait(lambda _value,root:root['tab']==index and root['popup']=='none')

    def owned_row(self,kind,name,address):
        value,root=self.inspect();need(root['popup']=='none' and not root['loading'])
        key='places.'+kind+'.'+hashlib.sha256(name.encode()).hexdigest()[:32]
        row=self.row(value,key);need(row['rowName']==name and same_viewpoint(row['rowAddress'],address))
        return controls.reference(value,key)

    def edit_bookmark(self,*,rename=False,cancel=False):
        need(type(rename) is type(cancel) is bool);self.tab(1)
        _value,root=self.inspect()
        selected=None
        if rename:
            selected=self.owned_row('bookmark-rename',self.ctx['name'],self.urls['A']);key=selected['control']['id']
            need(self.ctx['renamed'] not in root['bookmarkAddresses'])
        else:
            need(same_viewpoint(root['currentAddress'],self.urls['A']) and self.ctx['name'] not in root['bookmarkAddresses']
                 and self.ctx['renamed'] not in root['bookmarkAddresses']);key='places.bookmark-add'
        self.input(key,selected=selected);expected=self.ctx['name'] if rename else ''
        def opened(value,root):
            return (root['popup']=='bookmark' and root['dialog']['visible'] and root['dialog']['originalName']==expected
                and same_viewpoint(root['dialog']['address'],self.urls['A'])
                and self.row(value,'places.bookmark-name')['value']==root['dialog']['name']==expected)
        self.wait(opened);name=self.ctx['renamed'] if rename else self.ctx['name']
        self.input('places.bookmark-name');self.wait(lambda value,_root:self.row(value,'places.bookmark-name')['focused'])
        self.input('places.bookmark-name','replace',name)
        self.wait(lambda value,root:self.row(value,'places.bookmark-name')['value']==root['dialog']['name']==name
            and root['dialog']['originalName']==expected and same_viewpoint(root['dialog']['address'],self.urls['A']))
        self.input('places.bookmark-cancel' if cancel else 'places.bookmark-save')
        self.wait(lambda _value,root:root['popup']=='none' and not root['dialog']['visible'])

    def search(self,query):
        need(query in (self.ctx['hidden'],self.ctx['name']));self.tab(0)
        _value,root=self.inspect();need(root['search'] in ('',self.ctx['hidden'],self.ctx['name']))
        self.input('places.search');self.wait(lambda value,_root:self.row(value,'places.search')['focused'])
        self.input('places.search','replace',query)
        self.wait(lambda value,root:self.row(value,'places.search')['value']==root['search']==query)

    def invoke(self,call):
        from feature_journeys.contract import arguments
        # Reuse the closed common action inventory, including exact run text.
        call=deepcopy(arguments('feature.world-navigation.act',call));verb,inputs=call['verb'],call['inputs']
        source=urlsplit(self.inputs['sceneUrl']);expected=source.scheme+'://'+source.netloc+'/feature-fixture/v1/runs/'+self.run+'/'
        need(call['runId']==self.run and call['fixtureUrl']==expected and verb in
            ('bookmark-add-cancel','bookmark-add','bookmark-rename-cancel','bookmark-rename',
            'directory-search','directory-select','bookmark-visit','bookmark-delete'))
        need(self.started is self.call is None);self.started=self.bound();self.call=call
        try:
            if verb.startswith('bookmark-add'):self.edit_bookmark(cancel=verb.endswith('-cancel'))
            elif verb.startswith('bookmark-rename'):self.edit_bookmark(rename=True,cancel=verb.endswith('-cancel'))
            elif verb=='directory-search':self.search(inputs['query'])
            elif verb=='directory-select':
                self.tab(0);selected=self.owned_row('visit',self.ctx['destination'],self.urls['B'])
                self.input(selected['control']['id'],selected=selected)
            else:
                self.tab(1);kind='bookmark-visit' if verb=='bookmark-visit' else 'bookmark-delete'
                selected=self.owned_row(kind,self.ctx['renamed'],self.urls['A'])
                self.input(selected['control']['id'],selected=selected)
            self.bound();return {'performed':True}
        finally:self.started=self.call=None
