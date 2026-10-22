"""Normal owned directory/bookmark selection, native arrival and Places retirement.

Stereo source evidence is retained separately; current-challenge/changed-world
pixels and the full Navigation actor/finalizer are not inferred here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_location_bookmarks import validate as bookmarks_packet
from adapters.native_navigation_directory import validate as roots_packet,continuation as roots_advance
from adapters.navigation_arrival import pose_packet,advance as pose_advance,stereo_frame
from adapters.navigation_stereo import NavigationStereo
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack,unpack,canonical
from adapters.token_create_ui import scope,nonce
from adapters.token_places_ui import snapshot,sha,TokenPlacesUI
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context as fixture_context
from navigation_observation import viewpoint_urls

VERSION=1

class NavigationTransit:
    def __init__(self,ui_factory,arrival,roots,bookmarks,stereo_factory,path,run,binding,scene_url,guard,*,directory=None,
                 monotonic=time.monotonic,sleep=time.sleep):
        identifier(run);context(binding);viewpoint_urls(scene_url)
        need(all(callable(f) for f in (ui_factory,stereo_factory,guard,monotonic,sleep)))
        self.arrival,self.roots,self.bookmarks,self.stereo_factory=arrival,roots,bookmarks,stereo_factory
        self.run,self.binding,self.scene_url,self.guard=run,deepcopy(binding),scene_url,guard
        self.directory,self.monotonic,self.sleep=directory,monotonic,sleep
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None;self.clock=self.deadline=None
        self.ui=ui_factory(self.intent);need(isinstance(self.ui,TokenPlacesUI) and self.ui.run==run)
        if self.disk is not None:
            exact(self.disk,{'navigationTransitVersion','runId','binding','sceneUrl','payload'})
            need(type(self.disk['navigationTransitVersion']) is int and self.disk['navigationTransitVersion']==VERSION
                 and self.disk['runId']==run and self.disk['binding']==binding and self.disk['sceneUrl']==scene_url)
            values=unpack(self.disk['payload']);need(len(values)==1);self.validate(values[0]);self.state=values[0]
    def now(self):
        need(self.guard() is not False);value=self.monotonic()
        need(number(value,0,1e15) and (self.clock is None or value>=self.clock) and (self.deadline is None or value<=self.deadline))
        self.clock=value;return value
    @staticmethod
    def page(ui):
        rows=[r for r in ui['controls'] if r['id']=='places.page'];need(len(rows)<=1);return rows[0] if rows else None
    def archive(self,group):
        exact(group,{'ui','pose','roots','bookmarks'});snapshot(group['ui'])
        pose=group['pose'];epoch=pose['subject']['capturedEpochMs'];pid=int(self.binding['processIdentity'].split(':',1)[0])
        pose_packet(pose,self.run,self.binding,self.scene_url,epoch)
        for name,validator,action in (('roots',roots_packet,'feature-navigation-directory'),('bookmarks',bookmarks_packet,'feature-location-bookmarks')):
            packet=group[name];validator(packet,dict(schemaVersion=1,commandId=packet.get('commandId'),action=action,runId=self.run),pid,packet.get('capturedEpochMs'))
        ui=group['ui'];frame=group['roots']['ui']
        need(ui['scope']['instance']==frame['bridgeId']==self.binding['sessionId'] and ui['scope']['processId']==pid
             and ui['scope']['generation']==frame['generation'] and ui['scope']['sequence']==frame['sequence']
             and 0<=epoch-ui['observedEpochMs']<=1500
             and 0<=group['roots']['capturedEpochMs']-epoch<=1500
             and 0<=group['bookmarks']['capturedEpochMs']-epoch<=1500)
    def advance(self,a,b):
        pose_advance(a['pose'],b['pose']);roots_advance(a['roots'],b['roots'])
        need(b['bookmarks']['instance']==a['bookmarks']['instance'] and b['bookmarks']['sequence']>a['bookmarks']['sequence']
             and b['bookmarks']['capturedEpochMs']>=a['bookmarks']['capturedEpochMs']
             and all(b['ui']['scope'][k]>=a['ui']['scope'][k] for k in ('sequence','elapsedMs'))
             and b['ui']['observedEpochMs']>=a['ui']['observedEpochMs'])
    def validate(self,value):
        exact(value,{'ticket','kind','stage','original','last','pending','scrollDirection','scrolls','stereoSha256','quiet','queries'})
        identifier(value['ticket']);need(value['kind'] in ('directory','bookmark') and integer(value['stage'],0,5)
            and value['scrollDirection'] in ('up','down') and integer(value['scrolls'],0,64)
            and type(value['quiet']) is list and len(value['quiet'])<=8)
        self.archive(value['original']);self.archive(value['last'])
        if value['last']!=value['original']:self.advance(value['original'],value['last'])
        initial=self.page(value['original']['ui']);need(initial is not None and not initial['dialog']['visible']
            and not initial['loading'] and initial['queueCount']==0 and not initial['dispatchTimerRunning']
            and self.location(value['original'])==('A' if value['kind']=='directory' else 'B'))
        roots=[r for r in value['original']['roots']['roots'] if r['rootId']==initial['rootInstance']]
        need(len(roots)==1 and roots[0]['alive'] and roots[0]['current'] and roots[0]['sourceSha256']==initial['componentSourceSha256'])
        need(value['last']['bookmarks']['storage']==value['original']['bookmarks']['storage'])
        need(type(value['queries']) is list and len(value['queries'])<=768 and len(set(value['queries']))==len(value['queries']))
        for query in value['queries']:identifier(query)
        for group in (value['original'],value['last']):need(all(q in value['queries'] for q in self.query_ids(group)))
        pending=value['pending']
        if pending is not None:
            exact(pending,{'input','before'});snapshot(pending['before']);p=pending['input']
            exact(p,{'placesInputVersion','action','controlId','controlToken','scope'});scope(p['scope'])
            need(type(p['placesInputVersion']) is int and p['placesInputVersion']==1 and nonce(p['controlToken'])
                 and p['scope']==pending['before']['scope'] and value['stage']<4
                 and p['controlId']==('places.tab.'+str(0 if value['kind']=='directory' else 1) if value['stage']==0
                    else 'places.scroll.'+('directory' if value['kind']=='directory' else 'bookmarks') if value['stage']==1
                    else self.row_id(value['kind']) if value['stage']==2 else 'tablet.home')
                 and p['action']==('scroll' if value['stage']==1 else 'activate'))
            control=self.ui.row(pending['before'],p['controlId'])
            need(control is not None and control['token']==p['controlToken']
                 and p['scope']['instance']==self.binding['sessionId']
                 and p['scope']['generation']==value['original']['ui']['scope']['generation'])
        if value['stereoSha256'] is not None:
            need(type(value['stereoSha256']) is str and len(value['stereoSha256'])==64)
            stereo=self.stereo_factory(value['ticket']);need(isinstance(stereo,NavigationStereo) and stereo.state['phase']=='complete'
                and hashlib.sha256(canonical(stereo.disk)).hexdigest()==value['stereoSha256'])
            facts=stereo_frame(stereo.state['frame'],stereo.image_bytes(),self.run,self.binding,self.scene_url)
            need(facts['location']==self.target(value['kind'])
                 and all(q in value['queries'] for q in self.stereo_queries(stereo)))
        if value['stage']==5:need(value['stereoSha256'] is not None)
        previous=None
        for group in value['quiet']:
            self.archive(group);self.final(group,value);self.advance(value['original'],group)
            need(all(q in value['queries'] for q in self.query_ids(group)))
            if previous is not None:
                self.advance(previous,group)
                need(group['ui']['scope']['sequence']==previous['ui']['scope']['sequence']
                     and group['ui']['scope']['generation']==previous['ui']['scope']['generation']
                     and group['pose']['subject']['capturedEpochMs']-previous['pose']['subject']['capturedEpochMs']<=1500)
            previous=group
        if value['quiet']:
            need(value['stage']==5 and value['pending'] is None and len(value['quiet'])>=3)
            a,b=value['quiet'][0],value['quiet'][-1]
            need(b['pose']['subject']['capturedEpochMs']-a['pose']['subject']['capturedEpochMs']>=3000
                and b['ui']['observedEpochMs']-a['ui']['observedEpochMs']>=3000
                and b['ui']['scope']['elapsedMs']-a['ui']['scope']['elapsedMs']>=3000)
            if b['pose']['subject']['sequence']==value['last']['pose']['subject']['sequence']:need(b==value['last'])
            else:self.advance(b,value['last'])
    def save(self,value):
        self.now();self.validate(value)
        disk=dict(navigationTransitVersion=VERSION,runId=self.run,binding=self.binding,sceneUrl=self.scene_url,payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def intent(self,value):
        need(self.state is not None and self.state['pending'] is None)
        current=deepcopy(self.state);current['pending']=dict(input=value,before=deepcopy(self.ui.last));self.save(current)
    @staticmethod
    def query_ids(group):return [group['pose']['subject']['requestId'],group['roots']['commandId'],group['bookmarks']['commandId']]
    @staticmethod
    def stereo_queries(stereo):
        frame=stereo.state['frame']
        return [frame['before']['subject']['requestId'],frame['capture']['requestId'],frame['after']['subject']['requestId']]
    def sample(self):
        self.now();ui=self.ui.capture();pose=self.arrival.read(floor=None if self.state is None else self.state['last']['pose'])
        group=dict(ui=ui,pose=pose,roots=self.roots.read(self.run),bookmarks=self.bookmarks.read(self.run));self.now();self.archive(group)
        if self.state is not None:
            self.advance(self.state['last'],group)
            if self.state['pending'] is None:need(group['ui']['scope']['sequence']==self.state['last']['ui']['scope']['sequence'])
            need(group['bookmarks']['storage']==self.state['original']['bookmarks']['storage'])
            page=self.page(group['ui']);initial=self.page(self.state['original']['ui'])
            if page is not None:
                need(page['rootInstance']==initial['rootInstance'] and page['componentSourceSha256']==initial['componentSourceSha256']
                     and group['ui']['scope']['generation']==self.state['original']['ui']['scope']['generation']
                     and not page['loading'] and not page['dialog']['visible'] and page['queueCount']==0 and not page['dispatchTimerRunning']
                     and all(page[k]==initial[k] for k in ('directory','bookmarks','servers','maturity','querySha256','queryLength')))
            ids=self.query_ids(group)
            need(all(q not in self.state['queries'] for q in ids) and len(set(ids))==3)
            current=deepcopy(self.state);current['last']=group;current['queries']+=ids;self.save(current)
        return group
    @staticmethod
    def target(kind):return 'B' if kind=='directory' else 'A'
    def row_id(self,kind):return ('places.visit.' if kind=='directory' else 'places.bookmark.visit.')+sha(fixture_context(self.run)['name' if kind=='directory' else 'renamed'])
    def location(self,group):return pose_packet(group['pose'],self.run,self.binding,self.scene_url,group['pose']['subject']['capturedEpochMs'])
    def final(self,group,state=None):
        state=self.state if state is None else state;initial=self.page(state['original']['ui']);roots=group['roots']['roots']
        old=[r for r in roots if r['rootId']==initial['rootInstance']]
        need(self.location(group)==self.target(state['kind']) and self.page(group['ui']) is None and len(old)==1 and not old[0]['alive']
             and group['bookmarks']['storage']==state['original']['bookmarks']['storage'])
    def pending_effect(self,group):
        stage=self.state['stage'];p=self.state['pending'];before=p['input']['scope'];current=group['ui']['scope']
        need(current['sequence']==before['sequence']+1)
        page=self.page(group['ui'])
        if stage<3:
            need(page is not None and page['rootInstance']==self.page(self.state['original']['ui'])['rootInstance']
                 and current['generation']==before['generation'])
        if stage==0:need(page['tab']==(0 if self.state['kind']=='directory' else 1))
        elif stage==1:
            a=self.ui.row(p['before'],p['input']['controlId']);b=self.ui.row(group['ui'],p['input']['controlId'])
            need(a is not None and b is not None and (b['position']<a['position'] if self.state['scrollDirection']=='up' else b['position']>a['position']))
        elif stage==2:need(self.location(group)==self.target(self.state['kind']))
        else:self.final(group)
    def act(self,ticket,kind):
        identifier(ticket);need(kind in ('directory','bookmark') and self.deadline is None);self.deadline=self.now()+20
        try:return self.execute(ticket,kind)
        except NativeUIError:raise
        except Exception:raise NativeUIError('Original navigation transit remains unresolved') from None
        finally:self.deadline=None
    def execute(self,ticket,kind):
        if self.state is None:
            group=self.sample();page=self.page(group['ui'])
            need(page is not None and not page['loading'] and not page['dialog']['visible']
                 and self.location(group)==('A' if kind=='directory' else 'B'))
            self.save(dict(ticket=ticket,kind=kind,stage=0,original=group,last=group,pending=None,scrollDirection='up',scrolls=0,
                stereoSha256=None,quiet=[],queries=self.query_ids(group)))
        need(self.state['ticket']==ticket and self.state['kind']==kind)
        if self.state['quiet']:self.final(self.sample());return dict(performed=True)
        while self.state['stage']<4:
            stage=self.state['stage'];group=self.sample();page=self.page(group['ui'])
            if self.state['pending'] is None:
                need(page is not None)
                if stage==0 and page['tab']==(0 if kind=='directory' else 1):
                    current=deepcopy(self.state);current['stage']=1;self.save(current);continue
                if stage==1:
                    if self.ui.row(group['ui'],self.row_id(kind)):
                        current=deepcopy(self.state);current['stage']=2;self.save(current);continue
                    area='directory' if kind=='directory' else 'bookmarks';bar=self.ui.row(group['ui'],'places.scroll.'+area)
                    need(bar is not None and self.state['scrolls']<64)
                    if self.state['scrollDirection']=='up' and bar['position']<=.000001:
                        current=deepcopy(self.state);current['scrollDirection']='down';self.save(current);continue
                    need(self.state['scrollDirection']=='up' or bar['position']+bar['size']<.999999)
                    self.ui.input('places.scroll.'+area,'scroll',self.state['scrollDirection'])
                elif stage==2:
                    row=self.ui.row(group['ui'],self.row_id(kind));need(row is not None and row['addressSha256']==sha(viewpoint_urls(self.scene_url)[self.target(kind)]))
                    if kind=='directory':
                        need(self.directory is not None);witness=self.directory.observe_current(ticket)
                        need(witness['ui']['scope']['instance']==group['ui']['scope']['instance']
                             and witness['ui']['scope']['generation']==group['ui']['scope']['generation']
                             and witness['ui']['scope']['sequence']==group['ui']['scope']['sequence'])
                    else:
                        names=[r for r in group['bookmarks']['storage']['owned'] if r['name']==fixture_context(self.run)['renamed']]
                        need(len(names)==1 and names[0]['addressSha256']==row['addressSha256'])
                    self.ui.input(self.row_id(kind))
                else:self.ui.input('places.tab.'+str(0 if kind=='directory' else 1) if stage==0 else 'tablet.home')
            p=self.state['pending']['input']
            for attempt in range(81):
                group=self.sample();need(p['scope']['sequence']<=group['ui']['scope']['sequence']<=p['scope']['sequence']+1)
                try:self.pending_effect(group);break
                except NativeUIError:need(attempt<80);self.sleep(.1)
            current=deepcopy(self.state);current['pending']=None
            if stage==1:current['scrolls']+=1
            else:current['stage']+=1
            self.save(current)
        if self.state['stage']==4:
            stereo=self.stereo_factory(ticket);result=stereo.acquire(ticket)
            need(stereo_frame(result['frame'],stereo.image_bytes(),self.run,self.binding,self.scene_url)['location']==self.target(kind))
            current=deepcopy(self.state);ids=self.stereo_queries(stereo)
            need(len(set(ids))==3 and all(q not in current['queries'] for q in ids))
            current['queries']+=ids;current['stereoSha256']=hashlib.sha256(canonical(stereo.disk)).hexdigest();current['stage']=5;self.save(current)
        groups=[];start=self.now()
        for _ in range(8):
            group=self.sample();self.final(group)
            if groups:need(group['ui']['scope']['sequence']==groups[-1]['ui']['scope']['sequence'] and group['pose']['subject']['capturedEpochMs']-groups[-1]['pose']['subject']['capturedEpochMs']<=1500)
            groups.append(group)
            if self.now()-start>=3:
                current=deepcopy(self.state);current['quiet']=groups;self.save(current);return dict(performed=True)
            self.sleep(.5)
        raise NativeUIError('Original transit quiet state remains unresolved')
