"""Whole Avatar recipes on ordinary product controls and original sources.

Recipe and UUID ownership are durable before inputs. Real native creation
returns are retained before asynchronous geometry. Input delivery is never a
complete feature verdict; peer/GPU/lifetime evidence belongs to the full owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from adapters.script_feature.history import canonical,pack,unpack,same
from feature_journeys.contract import arguments
from ios.adapters import avatar_entities,avatar_renderers,avatar_state,avatar_bookmarks,people_model
from ios.adapters.avatar_controls import AvatarUI,same_reference
from ios.adapters.avatar_input_owner import AvatarInputOwner
from ios.adapters.avatar_sources import IOSAvatarSources

VERSION=1


class AvatarActionPending(NativeUIError):pass


class IOSAvatarActions:
    def __init__(self,store,sources,inputs,sdk,peer,expected_code):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSAvatarSources) and not sources.historical
            and sources.role=='primary' and isinstance(inputs,AvatarInputOwner) and isinstance(sdk,NativeUI))
        exact(peer,{'sessionId','username'});avatar_state.session(peer['sessionId']);avatar_state.text(peer['username'],256)
        need(peer['username'].startswith('e2e-') and len(peer['username'])==36 and avatar_state.identity(peer['username'][4:]))
        need(inputs.binding==sources.binding and inputs.run==sources.run and inputs.role=='primary' and inputs.lock is sources.lock
            and inputs.fixture_url==sources.phase.fixture_url and store.path.name=='ios-avatar-primary-actions.json')
        need(type(expected_code) is dict and '/system/avatarapp.js' in expected_code)
        self.store,self.sources,self.inputs,self.sdk=store,sources,inputs,sdk
        self.peer,self.expected_code=deepcopy(peer),deepcopy(expected_code)
        self.lock=sources.lock;self.lock.assert_held();self.previous=store.read();self.failed=False
        self.state=None if self.previous is None else self.decode(self.previous);inputs.load()
        if self.state is not None:
            expected=[row for row in self.state['calls'] if row['inputStarted']]
            need(len(expected)==len(inputs.state['calls']))
            for whole,events in zip(expected,inputs.state['calls']):
                need(same(whole['query'],events['arguments'])
                    and (whole['phase']!='acknowledged' or events['phase']=='acknowledged'))

    def envelope(self,state):
        return dict(iosAvatarActionsVersion=VERSION,runId=self.sources.run,binding=self.sources.binding,
            peer=self.peer,expectedCode=self.expected_code,payload=pack([state]))

    def reference(self,frame):
        need(self.sources.frames and same(frame,self.sources.frames[-1]))
        return dict(revision=len(self.sources.frames),sha256=hashlib.sha256(canonical(frame)).hexdigest())

    def original(self,reference):
        exact(reference,{'revision','sha256'});need(integer(reference['revision'],1,len(self.sources.frames)))
        frame=self.sources.frames[reference['revision']-1]
        need(frame.get('avatarSourceGroupVersion')==2 and hashlib.sha256(canonical(frame)).hexdigest()==reference['sha256'])
        return frame

    def decode(self,value):
        exact(value,{'iosAvatarActionsVersion','runId','binding','peer','expectedCode','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'baseline','calls','owned','savedBookmark'})
        baseline=self.original(state['baseline']);need(type(state['calls']) is list and len(state['calls'])<=32
            and type(state['owned']) is list and len(state['owned'])<=8)
        tickets=set()
        for index,call in enumerate(state['calls']):
            exact(call,{'query','phase','before','after','sdk','inputStarted'})
            query=arguments('feature.avatar-people.act',call['query'])
            need(query['runId']==self.sources.run and query['fixtureUrl']==self.sources.phase.fixture_url and query['ticket'] not in tickets
                and call['phase'] in ('acting','issuing','acknowledged') and type(call['sdk']) is list and len(call['sdk'])<=4
                and type(call['inputStarted']) is bool)
            tickets.add(query['ticket'])
            if call['before'] is not None:self.original(call['before'])
            else:need(call['after'] is None and not call['sdk'] and not call['inputStarted'])
            if call['after'] is not None:self.original(call['after'])
            if index<len(state['calls'])-1 or call['phase']=='acknowledged':need(call['phase']=='acknowledged' and call['after'] is not None)
            for event in call['sdk']:
                exact(event,{'opened','before','after'});need(type(event['opened']) is bool)
                before=self.original(event['before']);need(before['ui']['open'] is not event['opened'])
                if event['after'] is not None:need(self.original(event['after'])['ui']['open'] is event['opened'])
            need(sum(event['after'] is None for event in call['sdk'])==(1 if call['phase']=='issuing' else 0))
        ids=set();self_id=baseline['originals']['state']['source']['sessionId']
        for owned in state['owned']:
            exact(owned,{'id','ticket','resource','before','observed'})
            before=self.original(owned['before']);seen=self.original(owned['observed'])
            original=avatar_entities.returned(seen['originals']['entities'],before['originals']['renderers'],seen['originals']['scripts'],self.expected_code,
                avatar_id=self_id,resource=owned['resource'],after_epoch=before['clockJoin']['nativeAfter']['capturedEpochMs'])
            need(owned['id']==original['entity']['entityId'] and owned['id'] not in ids and owned['ticket'] in tickets);ids.add(owned['id'])
        if state['savedBookmark'] is not None:
            saved=state['savedBookmark'];exact(saved,{'name','entry','observed'})
            seen=self.original(saved['observed']);need(saved['name'] not in baseline['originals']['state']['source']['bookmarks']['entries'])
            need(seen['originals']['state']['source']['bookmarks']['entries'].get(saved['name'])==saved['entry'])
        return deepcopy(state)

    def bound(self):
        self.sources.bound();need(not self.failed and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def active(self,frame):
        call=self.state['calls'][-1]['query'];row=frame['phaseAfter']['activations'][-1]
        need(row['ticket']==call['ticket'] and row['stimulus']['verb']==call['verb'] and same(row['stimulus']['inputs'],call['inputs']))

    def retain_returns(self,frame):
        if not self.state['calls']:return
        call=self.state['calls'][-1];query=call['query']
        if query['verb']!='wearable-add' or call['before'] is None:return
        resource=self.resource(query);events=frame['originals']['entities']['source']['events']
        before=self.original(call['before']);epoch=before['clockJoin']['nativeAfter']['capturedEpochMs']
        if not any(event['kind']=='add-returned' and event['clock']['epochMs']>=epoch and event['entity']['modelUrl']==resource for event in events):return
        original=avatar_entities.returned(frame['originals']['entities'],before['originals']['renderers'],frame['originals']['scripts'],self.expected_code,
            avatar_id=self.self_id,resource=resource,after_epoch=epoch)
        entity_id=original['entity']['entityId']
        if entity_id not in {row['id'] for row in self.state['owned']}:
            self.state['owned'].append(dict(id=entity_id,ticket=query['ticket'],resource=resource,before=deepcopy(call['before']),observed=self.reference(frame)))
            self.save() # Own the actual return before geometry, next input or cleanup.

    def capture(self):
        self.bound();frame=self.sources.read();need(frame.get('avatarSourceGroupVersion')==2)
        if self.state is not None:
            if self.state['calls']:self.active(frame)
            self.retain_returns(frame)
            baseline=self.original(self.state['baseline'])['originals']
            avatar_renderers.preserve_unowned(baseline['renderers'],frame['originals']['renderers'],{row['id'] for row in self.state['owned']})
            names=baseline['state']['source']['bookmarks']['entries'];current=frame['originals']['state']['source']['bookmarks']
            name=self.state['savedBookmark']['name'] if self.state['savedBookmark'] else 'e2e-'+self.sources.run
            need(not current['loadError'] and {key:value for key,value in current['entries'].items() if key!=name}==names)
        return frame

    @property
    def self_id(self):return self.original(self.state['baseline'])['originals']['state']['source']['sessionId']
    def resource(self,query):return self.sources.phase.fixture_url+'tickets/'+query['ticket']+'/'+query['inputs']['resource']

    def prepare(self):
        self.bound();need(self.state is None)
        frame=self.capture();source=frame['originals']['state']['source'];need(source['geometryLoaded'] and source['rigReady'] and source['shouldRender']
            and source['requestedUrl']==source['resourceUrl'] and abs(source['modelScale']-1.)<.0001 and abs(source['targetScale']-1.)<.0001
            and not source['bookmarks']['loadError'] and 'e2e-'+self.sources.run not in source['bookmarks']['entries'])
        avatar_renderers.loaded(frame['originals']['renderers'],source['sessionId'],source['resourceUrl'],source['modelScale'])
        peer=avatar_renderers.avatar(frame['originals']['renderers'],self.peer['sessionId'],remote=True)
        need(peer['geometryLoaded'] and peer['rigReady'] and peer['addedToScene'] and peer['shouldRender'])
        self.state=dict(baseline=self.reference(frame),calls=[],owned=[],savedBookmark=None);self.save();return deepcopy(self.state)

    def wait(self,predicate):
        started=previous=self.sources.monotonic()
        for attempt in range(121):
            frame=self.capture()
            if predicate(frame):return frame
            now=self.sources.monotonic();need(previous<=now<started+12);previous=now
            if attempt<120:self.sdk.sleep(.1)
        raise AvatarActionPending('Original Avatar recipe effect has not settled; ownership is retained')

    def intent(self,value):
        frame=self.capture();same_reference(value['reference'],frame['ui'],value['controlId'])
        call=self.state['calls'][-1];need(call['phase']=='acting')
        if not call['inputStarted']:
            need(self.inputs.begin(call['query']));call['inputStarted']=True;self.save()
        self.inputs.intent(value)

    def tablet(self,opened):
        frame=self.capture()
        if frame['ui']['open'] is opened:return
        call=self.state['calls'][-1];call['sdk'].append(dict(opened=opened,before=self.reference(frame),after=None));call['phase']='issuing';self.save()
        self.sdk.click(Locator('accessibility id','OverteTabletOpen' if opened else 'OverteTabletClose'))
        after=self.wait(lambda value:value['ui']['open'] is opened)
        call['sdk'][-1]['after']=self.reference(after);call['phase']='acting';self.save()

    def act(self,query):
        query=deepcopy(arguments('feature.avatar-people.act',query));self.bound();need(self.state is not None
            and query['runId']==self.sources.run and query['fixtureUrl']==self.sources.phase.fixture_url)
        for call in self.state['calls']:
            if call['query']['ticket']==query['ticket']:
                need(same(call['query'],query) and call['phase']=='acknowledged');return {'performed':True}
        if self.state['calls'] and self.state['calls'][-1]['phase']!='acknowledged':
            raise AvatarActionPending('Original Avatar recipe is unresolved; ordinary input is not repeated')
        call=dict(query=query,phase='acting',before=None,after=None,sdk=[],inputStarted=False)
        self.state['calls'].append(call);self.save();call['before']=self.reference(self.capture());self.save()
        self.tablet(True)
        ui=AvatarUI(self.sources.readers['ui'],self.intent,delivered=self.inputs.delivered,observed=self.inputs.observed,
            monotonic=self.sources.monotonic,sleep=self.sdk.sleep)
        verb=query['verb'];supplied=query['inputs']
        if verb=='avatar-url':
            url=self.resource(query);ui.avatar_url(url)
            def settled(frame):
                source=frame['originals']['state']['source']
                if source['requestedUrl']!=url:return False
                if supplied['resource']=='missing.fst':
                    history=source['modelHistory'];return any(row['kind']=='finished' and row['generation']==history['currentGeneration']
                        and row['requestedUrl']==row['resourceUrl']==url and row['success'] is False for row in history['events'])
                return source['geometryLoaded'] and source['rigReady'] and source['resourceUrl']==url
            self.wait(settled)
        elif verb=='avatar-scale':
            ui.scale(supplied['value']);self.wait(lambda frame:all(abs(frame['originals']['state']['source'][key]-supplied['value'])<.0001 for key in ('targetScale','modelScale')))
        elif verb=='avatar-bookmark-save':
            ui.save_bookmark(supplied['name'])
            frame=self.wait(lambda value:supplied['name'] in value['originals']['state']['source']['bookmarks']['entries'])
            source=frame['originals']['state']['source'];avatar_bookmarks.persisted(source['bookmarkFile'],source['bookmarks'])
            self.state['savedBookmark']=dict(name=supplied['name'],entry=deepcopy(source['bookmarks']['entries'][supplied['name']]),observed=self.reference(frame));self.save()
        elif verb in ('avatar-bookmark-choose','avatar-bookmark-delete'):
            saved=self.state['savedBookmark'];need(saved is not None and saved['name']==supplied['name'])
            ui.choose_bookmark(saved['name'],delete=verb=='avatar-bookmark-delete')
            if verb=='avatar-bookmark-delete':
                frame=self.wait(lambda value:saved['name'] not in value['originals']['state']['source']['bookmarks']['entries'])
                source=frame['originals']['state']['source'];avatar_bookmarks.persisted(source['bookmarkFile'],source['bookmarks'])
            else:
                ui_url=saved['entry'].get('avatarUrl');need(type(ui_url) is str and ui_url)
                self.wait(lambda value:value['originals']['state']['source']['requestedUrl']==ui_url and value['originals']['state']['source']['geometryLoaded']
                    and value['originals']['state']['source']['rigReady'] and value['originals']['state']['source']['resourceUrl']==ui_url
                    and all(abs(value['originals']['state']['source'][key]-1.)<.0001 for key in ('targetScale','modelScale'))
                    and not any(row['id'] in {owned['id'] for owned in self.state['owned']} for row in value['originals']['renderers']['source']['avatarEntities']))
        elif verb=='wearable-add':
            ui.add_wearable(self.resource(query))
            self.wait(lambda frame:any(row['ticket']==query['ticket'] and self.wearable_ready(frame,row) for row in self.state['owned']))
        elif verb=='connection-request':ui.request_connection(self.peer['sessionId'])
        elif verb=='connection-cancel':ui.close_connection()
        elif verb in ('peer-reject','peer-accept'):
            desired='declined' if verb=='peer-reject' else 'success'
            self.wait(lambda frame:any(row['id']=='people.page' and row['connectionState']['phase']==desired for row in frame['ui']['controls']))
            ui.close_connection() # Independent peer supplies consent; primary only closes its actual terminal panel.
        elif verb=='connection-remove':
            ui.remove_connection(self.peer['username'])
            self.wait(lambda frame:self.absent_contact(frame,call))
        elif verb=='avatar-restore':
            for owned in self.state['owned']:
                frame=self.capture()
                if any(row['id']==owned['id'] for row in frame['originals']['renderers']['source']['avatarEntities']):ui.remove_wearable(owned['id'])
            original=self.original(self.state['baseline'])['originals']['state']['source'];ui.avatar_url(original['requestedUrl']);ui.scale(original['targetScale'])
            self.wait(lambda frame:all(frame['originals']['state']['source'][key]==original[key] for key in ('requestedUrl','resourceUrl','geometryLoaded','rigReady'))
                and all(abs(frame['originals']['state']['source'][key]-original[key])<.0001 for key in ('targetScale','modelScale')))
        else:need(False)
        if call['inputStarted']:self.inputs.finish()
        call['after']=self.reference(self.capture());call['phase']='acknowledged';self.save();return {'performed':True}

    def wearable_ready(self,frame,owned):
        rows=[row for row in frame['originals']['renderers']['source']['avatarEntities'] if row['id']==owned['id']]
        need(len(rows)<=1)
        if not rows:return False
        row=rows[0];need(not row['loadFailed'])
        if not row['modelAvailable'] or not row['geometryLoaded'] or not row['addedToScene']:return False
        return avatar_renderers.wearable(frame['originals']['renderers'],owned['id'],self.self_id,owned['resource'])

    def absent_contact(self,frame,call):
        root=people_model.current(frame['originals']['people'])
        page=root['pagination']
        if (not page['initialized'] or not page['retrievedAtLeastOnePage'] or page['requestPending']
                or page['additionalFirstPageRequested'] or page['delayedClear'] or page['currentPageToRetrieve']!=-1
                or page['totalEntries']!=len(root['connectionRows'])):return False
        people_model.relationship(frame['originals']['people'],self.peer['username'],present=False,
            after_epoch=self.original(call['before'])['clockJoin']['nativeAfter']['capturedEpochMs'])
        return True
