"""Normal Pico Go To -> owned native 404 -> original physically visible modal.

This owner does not dismiss or close the modal. Its original lookup ticket and
submit barrier belong to the separate normal dismissal/whole-area finalizer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_location_bookmarks import validate as bookmark_packet
from adapters.native_navigation_modals import validate as modal_packet,validate_continuation,matching,presented,MESSAGE_SHA256
from adapters.native_navigation_replies import validate as reply_packet,origin,join_missing
from adapters.navigation_arrival import pose_packet,advance as pose_advance
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_lookup import PicoNavigationLookup,packet as lookup_packet,control_id
from adapters.pico4.tablet_home import PicoTabletHome,validate as home_packet
from adapters.script_journey.history import pack,unpack
from adapters.token_create_ui import scope,nonce
from feature_journeys.contract import identifier
from feature_journeys.navigation_fixture import configuration,validate_status

VERSION=1
EMPTY=hashlib.sha256(b'').hexdigest()


class NavigationMissing:
    def __init__(self,ui_factory,arrival,home,bookmarks,replies,modals,status,path,run,binding,provider_instance,inputs,owned_origin,guard,
                 *,monotonic=time.monotonic,sleep=time.sleep):
        identifier(run);identifier(provider_instance);context(binding);configuration(inputs);origin(owned_origin)
        need(isinstance(home,PicoTabletHome) and inputs['sourceRevision']==binding['sourceRevision']
             and all(callable(f) for f in (ui_factory,status,guard,monotonic,sleep)))
        self.run,self.binding,self.provider,self.inputs,self.origin=run,deepcopy(binding),provider_instance,deepcopy(inputs),owned_origin
        self.arrival,self.home,self.bookmarks,self.replies,self.modals,self.status=arrival,home,bookmarks,replies,modals,status
        self.guard,self.monotonic,self.sleep=guard,monotonic,sleep;self.clock=self.deadline=None
        self.pid=int(binding['processIdentity'].split(':')[0]);self.url='hifi://hidden-'+run;self.url_sha=hashlib.sha256(self.url.encode()).hexdigest()
        need(home.source.pid==bookmarks.pid==replies.pid==modals.pid==self.pid and arrival.scene_url==inputs['sceneUrl'])
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None
        self.ui=ui_factory(self.intent);need(isinstance(self.ui,PicoNavigationLookup) and self.ui.run==run)
        self.navigation=self.ui.normal.io.navigation
        if self.disk is not None:
            exact(self.disk,{'navigationMissingVersion','runId','binding','providerInstance','inputs','origin','payload'})
            need(type(self.disk['navigationMissingVersion']) is int and self.disk['navigationMissingVersion']==VERSION
                 and self.disk['runId']==run and self.disk['binding']==binding and self.disk['providerInstance']==provider_instance
                 and self.disk['inputs']==inputs and self.disk['origin']==owned_origin)
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.validate(rows[0]);self.state=rows[0]
        old=getattr(self.navigation.address_authority,'__self__',None)
        need(self.navigation.address_authority is None or isinstance(old,NavigationMissing)
             and old.store.path==self.store.path and old.run==run and old.binding==binding)
        self.navigation.address_authority=self.authorize
    def now(self):
        need(self.guard() is not False);now=self.monotonic()
        need(number(now,0,1e15) and (self.clock is None or now>=self.clock) and (self.deadline is None or now<=self.deadline))
        self.clock=now;return now
    def authorize(self,url):
        self.now();need(self.deadline is not None and self.store.read()==self.disk)
        pending=None if self.state is None else self.state['pending']
        return url==self.url and pending is not None and pending['kind']=='qt' and pending['input']['controlId']=='navigation.address' \
            and pending['input']['action'] in ('replace','submit')
    def archive(self,group):
        exact(group,{'ui','pose','home','bookmarks','reply','modal','provider'});lookup_packet(group['ui'],self.run)
        end=group['modal']['capturedEpochMs'];pose_packet(group['pose'],self.run,self.binding,self.inputs['sceneUrl'],end)
        home_packet(group['home'],group['home'].get('commandId'),self.pid,end)
        for key,validator,action in (('bookmarks',bookmark_packet,'feature-location-bookmarks'),('reply',reply_packet,'feature-navigation-replies'),('modal',modal_packet,'feature-navigation-modals')):
            packet=group[key];validator(packet,dict(schemaVersion=1,commandId=packet.get('commandId'),action=action,runId=self.run),self.pid,end)
        validate_status(group['provider'],instance=self.provider,run=self.run,inputs=self.inputs)
        ui,modal=group['ui'],group['modal'];s=ui['scope']
        need(s['instance']==self.binding['sessionId'] and s['processId']==self.pid and group['reply']['navigationReplyVersion']==2
             and all(modal[k]==s[j] for k,j in (('uiBridgeId','instance'),('uiGeneration','generation'),('uiInputSequence','sequence'))))
        need(modal['tabletOpen']==ui['open']==group['home']['tabletShown']
             and pose_packet(group['pose'],self.run,self.binding,self.inputs['sceneUrl'],end)=='B'
             and group['ui']['observedEpochMs']<=group['ui']['native']['capturedEpochMs']<=group['pose']['subject']['capturedEpochMs']
             and group['pose']['subject']['capturedEpochMs']<=group['home']['capturedEpochMs']<=group['bookmarks']['capturedEpochMs']
             and group['bookmarks']['capturedEpochMs']<=group['reply']['capturedEpochMs']<=end
             and 0<=end-ui['observedEpochMs']<=1500)
    def advance(self,a,b):
        from adapters.native_navigation_panels import continuation
        pose_advance(a['pose'],b['pose']);continuation(a['ui']['native'],b['ui']['native']);validate_continuation(a['modal'],b['modal'])
        need(b['reply']['instance']==a['reply']['instance'] and b['reply']['sequence']>a['reply']['sequence']
             and b['reply']['capturedEpochMs']>=a['reply']['capturedEpochMs'] and b['reply']['currentLookupGeneration']>=a['reply']['currentLookupGeneration']
             and b['reply']['events'][:len(a['reply']['events'])]==a['reply']['events'])
        need(b['bookmarks']['instance']==a['bookmarks']['instance'] and b['bookmarks']['sequence']>a['bookmarks']['sequence']
             and b['bookmarks']['storage']==a['bookmarks']['storage'] and b['bookmarks']['capturedEpochMs']>=a['bookmarks']['capturedEpochMs'])
        need(all(a['home'][k]==b['home'][k] for k in ('instance','tabletId','homeId'))
             and b['home']['sourceSequence']>a['home']['sourceSequence'] and b['home']['elapsedMs']>=a['home']['elapsedMs']
             and b['home']['capturedEpochMs']>=a['home']['capturedEpochMs'])
        validate_status(b['provider'],instance=self.provider,run=self.run,inputs=self.inputs,previous=a['provider'])
    @staticmethod
    def queries(group):
        return [group['ui']['native']['commandId'],group['pose']['subject']['requestId'],group['home']['commandId'],
            group['bookmarks']['commandId'],group['reply']['commandId'],group['modal']['commandId']]
    @staticmethod
    def live(group):return [r for r in group['ui']['native']['roots'] if r['alive']]
    def stable(self,group,value):
        need(group['provider']['active'] and group['provider']['ticket']==value['ticket']
             and group['bookmarks']['storage']==value['original']['bookmarks']['storage'])
        owned=value['addressRoot'];pending=value['pending']
        if owned is None and pending is not None and pending['kind']=='qt' and pending['input']['controlId']=='navigation.goto':
            address=group['ui']['native']['lookup']['address']
            if address is not None:
                owned=address['rootId'];need(owned not in {r['rootId'] for r in pending['before']['ui']['native']['roots']})
        rows=self.live(group);need(not rows or len(rows)==1 and rows[0]['rootId']==owned and rows[0]['profile']=='pico-address-v1')
    def join(self,group,value):
        joined=join_missing(group['reply'],group['provider'],value['ticket'],value['submitEpochMs'],self.origin)
        need(group['reply']['currentLookupActive'] and joined['event']['lookupGeneration']==group['reply']['currentLookupGeneration'])
        return joined
    def validate(self,value):
        exact(value,{'ticket','phase','original','last','pending','queries','visited','homeRoot','homeCount','addressRoot','submitEpochMs','joined','history'})
        identifier(value['ticket']);need(value['phase'] in ('opening','home','address','filled','submitted','visible'))
        need(type(value['queries']) is list and len(value['queries'])<=1024 and len(set(value['queries']))==len(value['queries']))
        for query in value['queries']:identifier(query)
        self.archive(value['original']);self.archive(value['last'])
        need(not value['original']['ui']['open'] and value['original']['home']['onHomeScreen'] and not self.live(value['original'])
             and not any(r['rootAlive'] or r['listenerAlive'] for r in value['original']['modal']['records']))
        if value['last']!=value['original']:self.advance(value['original'],value['last'])
        for group in (value['original'],value['last']):need(all(q in value['queries'] for q in self.queries(group)))
        need(type(value['visited']) is list and len(value['visited'])<=32 and len(set(value['visited']))==len(value['visited'])
             and all(integer(n,0,31) for n in value['visited']) and integer(value['homeCount'],0,32))
        if value['homeRoot'] is not None:identifier(value['homeRoot'])
        if value['addressRoot'] is not None:identifier(value['addressRoot'])
        if value['phase']!='opening':need(value['homeRoot'] is not None and value['homeCount']>0)
        if value['phase'] in ('address','filled','submitted','visible'):need(value['addressRoot'] is not None)
        if value['submitEpochMs'] is not None:need(integer(value['submitEpochMs'],1))
        if value['joined'] is not None:
            need(value['submitEpochMs'] is not None and value['joined']==self.join(value['last'],value))
            row=matching(value['last']['modal'],value['joined']['event'])
            need(row['profile']=='pico-tablet-critical-v1' and row['rootAlive'] and row['listenerAlive'] and not row['callbackFinished']
                 and row['messageSha256']==row['createdMessageSha256']==MESSAGE_SHA256)
        if value['phase']=='visible':need(value['joined'] is not None and value['pending'] is None);presented(value['last']['modal'],value['joined']['event'])
        need(type(value['history']) is list and len(value['history'])<=40)
        cursor=deepcopy(value);cursor.update(phase='opening',homeRoot=None,homeCount=0,addressRoot=None,submitEpochMs=None,joined=None,pending=None)
        previous=value['original'];sequence=previous['ui']['scope']['sequence']
        for entry in value['history']:
            exact(entry,{'kind','before','input','after'})
            before,after=entry['before'],entry['after'];self.archive(before);self.archive(after)
            need(before['ui']['scope']['sequence']==sequence)
            sequence+=1 if entry['kind']=='qt' else 0
            need(after['ui']['scope']['sequence']==sequence)
            if before!=previous:self.advance(previous,before)
            self.advance(before,after)
            need(all(q in value['queries'] for group in (before,after) for q in self.queries(group)))
            pending={k:entry[k] for k in ('kind','before','input')};cursor['pending']=pending
            if pending['kind']=='qt' and pending['input']['action']=='submit':cursor['submitEpochMs']=before['modal']['capturedEpochMs']
            self.validate_pending(pending,cursor);self.effect(after,cursor);self.apply_effect(cursor,after,pending);previous=after
        need(all(value[k]==cursor[k] for k in ('homeRoot','homeCount','addressRoot','joined')))
        submit=value['pending'] is not None and value['pending']['kind']=='qt' and value['pending']['input']['action']=='submit'
        need(value['submitEpochMs']==(value['pending']['before']['modal']['capturedEpochMs'] if submit else cursor['submitEpochMs']))
        need(value['phase']==cursor['phase'] or cursor['phase']=='submitted' and value['phase']=='visible' and value['pending'] is None)
        if previous!=value['last']:self.advance(previous,value['last'])
        pending_qt=value['pending'] is not None and value['pending']['kind']=='qt'
        need(sequence<=value['last']['ui']['scope']['sequence']<=sequence+(1 if pending_qt else 0))
        if value['pending'] is not None:need(value['pending']['before']['ui']['scope']['sequence']==sequence)
        self.validate_pending(value['pending'],value)
        self.stable(value['last'],value)
    def validate_pending(self,pending,value):
        if pending is not None:
            exact(pending,{'kind','before','input'});need(pending['kind'] in ('open','reopen','qt'))
            before=pending['before'];self.archive(before)
            need(all(q in value['queries'] for q in self.queries(before)))
            if pending['kind']=='qt':
                p=pending['input'];exact(p,{'navigationLookupInputVersion','controlId','action','controlToken','scope','native'}|({'text'} if p.get('action')=='replace' else set()))
                need(type(p['navigationLookupInputVersion']) is int and p['navigationLookupInputVersion']==1 and control_id(p['controlId']) and nonce(p['controlToken']))
                scope(p['scope']);s=before['ui']['scope'];need(all(p['scope'][k]==s[k] for k in ('instance','generation','sequence','processId')))
                from adapters.native_navigation_panels import validate as panels_packet
                panels_packet(p['native'],dict(schemaVersion=1,commandId=p['native'].get('commandId'),action='feature-navigation-panels',runId=self.run),self.pid,p['native'].get('capturedEpochMs'))
                need(p['native']['navigationPanelsVersion']==2 and p['native']['lookup']['complete']
                     and p['native']['commandId'] in value['queries'] and p['native']['lookup']==before['ui']['native']['lookup']
                     and p['native']['roots']==before['ui']['native']['roots']
                     and all(p['native']['ui'][k]==p['scope'][j] for k,j in (('bridgeId','instance'),('generation','generation'),('sequence','sequence'))))
                need(0<=p['scope']['elapsedMs']-s['elapsedMs']<=1500
                     and 0<=p['native']['capturedEpochMs']-before['modal']['capturedEpochMs']<=1500)
                need((value['phase']=='home' and p['action']=='activate' and (p['controlId']=='navigation.goto' or p['controlId'].startswith('tablet.page.')))
                     or value['phase']=='address' and p['controlId']=='navigation.address' and p['action'] in ('activate','replace')
                     or value['phase']=='filled' and p['controlId']=='navigation.address' and p['action']=='submit')
                row=self.ui.row(before['ui'],p['controlId']);need(row is not None and row['token']==p['controlToken'])
                if p['action']=='replace':need(p['text']==self.url)
            else:need(pending['input'] is None and value['phase']==('opening' if pending['kind']=='open' else 'submitted'))
    def apply_effect(self,current,group,pending):
        current['pending']=None
        if pending['kind']=='open':
            home=group['ui']['native']['lookup']['home'];current.update(phase='home',homeRoot=home['rootId'],homeCount=home['pageCount'])
        elif pending['kind']=='reopen':current['phase']='visible'
        elif pending['input']['controlId']=='navigation.goto':current.update(phase='address',addressRoot=group['ui']['native']['lookup']['address']['rootId'])
        elif pending['input']['action']=='replace':current['phase']='filled'
        elif pending['input']['action']=='submit':current.update(phase='submitted',joined=self.join(group,current))
    def save(self,value):
        self.now();self.validate(value)
        disk=dict(navigationMissingVersion=VERSION,runId=self.run,binding=self.binding,providerInstance=self.provider,inputs=self.inputs,origin=self.origin,payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def intent(self,value):
        self.now();need(self.state is not None and self.state['pending'] is None)
        current=deepcopy(self.state);query=value['native']['commandId'];need(query not in current['queries']);current['queries'].append(query)
        current['pending']=dict(kind='qt',before=deepcopy(current['last']),input=deepcopy(value))
        if value['action']=='submit':current['submitEpochMs']=current['last']['modal']['capturedEpochMs']
        self.save(current)
    def sample(self):
        self.now();provider=self.status();ui=self.ui.capture();pose=self.arrival.read(floor=None if self.state is None else self.state['last']['pose'])
        value=dict(ui=ui,pose=pose,home=self.home.source.capture(),bookmarks=self.bookmarks.read(self.run),reply=self.replies.read(self.run),modal=self.modals.read(self.run),provider=provider)
        self.now();self.archive(value)
        if self.state is not None:
            self.advance(self.state['last'],value);current=deepcopy(self.state);queries=self.queries(value)
            need(len(set(queries))==len(queries) and all(q not in current['queries'] for q in queries))
            current['queries']+=queries;current['last']=value;self.save(current)
        return value
    def effect(self,group,value=None):
        value=self.state if value is None else value
        p=value['pending'];before=p['before'];self.stable(group,value)
        base=before['ui']['scope']['sequence'];need(group['ui']['scope']['sequence']==base+(1 if p['kind']=='qt' else 0))
        if p['kind'] in ('open','reopen'):
            need(group['ui']['open'] and group['ui']['ready'] and group['ui']['scope']['generation']!=before['ui']['scope']['generation'])
            if p['kind']=='reopen':presented(group['modal'],value['joined']['event']);return
            home=group['ui']['native']['lookup']['home'];need(home is not None and home['visible'] and home['pageIndex']>=0 and home['pageCount']>0
                 and group['home']['onHomeScreen'] and not self.live(group));return
        control,action=p['input']['controlId'],p['input']['action']
        if control.startswith('tablet.page.'):
            home=group['ui']['native']['lookup']['home'];need(home is not None and home['rootId']==value['homeRoot']
                and home['pageCount']==value['homeCount'] and home['pageIndex']==int(control[12:])-1);return
        address=group['ui']['native']['lookup']['address']
        if control=='navigation.goto':
            rows=self.live(group);need(address is not None and address['visible'] and len(rows)==1 and rows[0]['rootId']==address['rootId']
                and rows[0]['profile']=='pico-address-v1' and address['rootId'] not in {r['rootId'] for r in before['ui']['native']['roots']}
                and address['textSha256']==EMPTY and address['textLength']==0);return
        if action=='submit':
            need(group['reply']['currentLookupGeneration']>before['reply']['currentLookupGeneration'])
            joined=self.join(group,value);row=matching(group['modal'],joined['event'])
            need(row['rootAlive'] and row['listenerAlive'] and not row['callbackFinished'] and row['profile']=='pico-tablet-critical-v1'
                 and row['messageSha256']==row['createdMessageSha256']==MESSAGE_SHA256);return
        need(address is not None and address['rootId']==value['addressRoot'] and address['focused'] and address['inputReady'])
        if action=='replace':need(address['textSha256']==self.url_sha and address['textLength']==len(self.url))
    def act(self,ticket):
        identifier(ticket);need(self.deadline is None);self.deadline=self.now()+20
        try:result=self.execute(ticket);self.now();return result
        except NativeUIError:raise
        except Exception:raise NativeUIError('Original normal Go To lookup remains unresolved') from None
        finally:self.deadline=None
    def execute(self,ticket):
        need(self.store.read()==self.disk)
        if self.state is None:
            value=self.sample();need(value['ui']['native']['lookup']['complete'])
            self.save(dict(ticket=ticket,phase='opening',original=value,last=value,pending=None,queries=self.queries(value),visited=[],
                homeRoot=None,homeCount=0,addressRoot=None,submitEpochMs=None,joined=None,history=[]))
        need(self.state['ticket']==ticket)
        if self.state['phase']=='visible':
            group=self.sample();presented(group['modal'],self.state['joined']['event']);return dict(performed=True)
        while self.state['phase']!='visible':
            group=self.sample();phase=self.state['phase']
            if self.state['pending'] is None:
                if phase in ('opening','submitted'):
                    if phase=='submitted' and group['ui']['open']:
                        presented(group['modal'],self.state['joined']['event']);current=deepcopy(self.state);current['phase']='visible';self.save(current);continue
                    current=deepcopy(self.state);current['pending']=dict(kind='open' if phase=='opening' else 'reopen',before=deepcopy(group),input=None)
                    self.save(current);self.ui.normal.io.tablet(True)
                elif phase=='home':
                    home=group['ui']['native']['lookup']['home'];need(home is not None and home['rootId']==self.state['homeRoot'] and home['pageCount']==self.state['homeCount'])
                    if self.ui.row(group['ui'],'navigation.goto'):self.ui.input('navigation.goto',original=group['ui'])
                    else:
                        current=deepcopy(self.state)
                        if home['pageIndex'] not in current['visited']:current['visited'].append(home['pageIndex']);self.save(current)
                        choices=[n for n in range(home['pageCount']) if n not in self.state['visited']];need(choices)
                        self.ui.input('tablet.page.'+str(choices[0]+1),original=group['ui'])
                elif phase=='address':
                    address=group['ui']['native']['lookup']['address'];need(address is not None and address['rootId']==self.state['addressRoot']
                        and address['textSha256']==EMPTY and address['textLength']==0)
                    self.ui.input('navigation.address','replace' if address['focused'] and address['inputReady'] else 'activate',
                        original=group['ui'],text=self.url if address['focused'] and address['inputReady'] else None)
                else:self.ui.input('navigation.address','submit',original=group['ui'])
            pending=self.state['pending'];before=pending['before']['ui']['scope']['sequence'];qt=pending['kind']=='qt'
            for attempt in range(81):
                group=self.sample();need(before<=group['ui']['scope']['sequence']<=before+(1 if qt else 0))
                try:self.effect(group);break
                except NativeUIError:need(attempt<80);self.sleep(.1)
            current=deepcopy(self.state);current['history'].append(dict(deepcopy(pending),after=deepcopy(group)))
            self.apply_effect(current,group,pending)
            self.save(current)
        return dict(performed=True)
