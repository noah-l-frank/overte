"""One normal Pico tablet close after owned transit, with independent quiet.

Original frames remain source evidence. This does not advertise Navigation,
retime stereo images or prove full Script/XHR/Web resource retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.native_feature_observation import exact,need,number
from adapters.navigation_transit import NavigationTransit
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.graphics_source import PicoGraphicsSource,validate as graphics_packet,PROFILES,accept_inventory
from adapters.pico4.tablet_home import validate as home_packet
from adapters.script_journey.history import canonical,pack,unpack
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.contract import identifier

VERSION=1


class NavigationTabletClose:
    def __init__(self,transit,normal,graphics,path,guard,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(transit,NavigationTransit) and isinstance(normal,TokenScriptUI) and isinstance(normal.io,PicoScriptIO)
             and isinstance(graphics,PicoGraphicsSource) and all(callable(f) for f in (guard,monotonic,sleep)))
        need(transit.state is not None and transit.state['homeMode']=='ray' and transit.state['quiet']
             and normal.io.navigation is transit.ui.io.original.navigation)
        self.transit,self.normal,self.graphics=transit,normal,graphics
        self.run,self.binding,self.guard=transit.run,deepcopy(transit.binding),guard
        self.pid=int(self.binding['processIdentity'].split(':')[0]);need(graphics.pid==self.pid)
        self.monotonic,self.sleep,self.clock,self.deadline=monotonic,sleep,None,None
        self.store=PrivateFeatureState(path);self.disk=self.store.read();self.state=None
        self.origin=hashlib.sha256(canonical(transit.state['original'])).hexdigest()
        if self.disk is not None:
            exact(self.disk,{'navigationTabletCloseVersion','runId','binding','transitOriginalSha256','payload'})
            need(type(self.disk['navigationTabletCloseVersion']) is int and self.disk['navigationTabletCloseVersion']==VERSION
                 and self.disk['runId']==self.run and self.disk['binding']==self.binding and self.disk['transitOriginalSha256']==self.origin)
            rows=unpack(self.disk['payload']);need(len(rows)==1);self.validate(rows[0]);self.state=rows[0]
    def now(self):
        need(self.guard() is not False);now=self.monotonic()
        need(number(now,0,1e15) and (self.clock is None or self.clock<=now) and (self.deadline is None or now<=self.deadline))
        self.clock=now;return now
    def archive(self,value):
        exact(value,{'transit','home','graphics'});group,home,graphics=value['transit'],value['home'],value['graphics']
        self.transit.archive(group);self.transit.final(group)
        home_packet(home,home.get('commandId'),self.pid,graphics['capturedEpochMs'])
        graphics_packet(graphics,graphics.get('commandId'),self.pid,graphics['capturedEpochMs'])
        original=self.transit.state['homeAfter']
        need(all(home[k]==original[k] for k in ('instance','tabletId','homeId'))
             and home['sourceSequence']>original['sourceSequence'] and home['capturedEpochMs']>=original['capturedEpochMs'])
        need(0<=home['capturedEpochMs']-group['pose']['subject']['capturedEpochMs']
             and 0<=graphics['capturedEpochMs']-home['capturedEpochMs']
             and graphics['capturedEpochMs']-group['ui']['observedEpochMs']<=1500
             and home['onHomeScreen'] and home['tabletShown']==group['ui']['open']==graphics['tabletShown']
             and not graphics['editorFocused'] and not graphics['graphicsInventory']['keyboard3D']['raised']
             and not graphics['graphicsInventory']['roots'])
    def advance(self,a,b):
        self.transit.advance(a['transit'],b['transit'])
        for key in ('home','graphics'):
            old,new=a[key],b[key]
            need(old['instance']==new['instance'] and old['generation']==new['generation']
                 and old['commandId']!=new['commandId'] and new['sourceSequence']>old['sourceSequence']
                 and new['elapsedMs']>=old['elapsedMs'] and new['capturedEpochMs']>=old['capturedEpochMs'])
        need(all(a['home'][k]==b['home'][k] for k in ('tabletId','homeId'))
             and a['graphics']['lastCommandSequence']==b['graphics']['lastCommandSequence'])
        accept_inventory(a['graphics']['graphicsInventory'],b['graphics']['graphicsInventory'],profiles=PROFILES)
    def closed(self,value,original):
        need(not value['transit']['ui']['open'] and not value['transit']['ui']['ready'])
        a,b=original['transit']['ui']['scope'],value['transit']['ui']['scope']
        # The physical controller close is independent of Qt control commands.
        need(a['instance']==b['instance'] and a['sequence']==b['sequence'] and a['generation']!=b['generation'])
    def validate(self,value):
        exact(value,{'ticket','phase','before','last','quiet','queries'});identifier(value['ticket'])
        need(value['ticket']==self.transit.state['ticket'] and value['phase'] in ('closing','quiet','closed')
             and type(value['quiet']) is list and len(value['quiet'])<=8
             and type(value['queries']) is list and len(value['queries'])<=1024 and len(set(value['queries']))==len(value['queries']))
        for query in value['queries']:identifier(query)
        self.archive(value['before']);self.archive(value['last']);need(value['before']['transit']['ui']['open'])
        if value['last']!=value['before']:self.advance(value['before'],value['last'])
        for group in (value['before'],value['last']):need(all(q in value['queries'] for q in self.queries(group)))
        need(value['last']['transit']['ui']['scope']['sequence']==value['before']['transit']['ui']['scope']['sequence'])
        if value['phase']!='closing':self.closed(value['last'],value['before'])
        previous=None
        for group in value['quiet']:
            self.archive(group);self.closed(group,value['before']);self.advance(value['before'],group)
            need(all(q in value['queries'] for q in self.queries(group)))
            if previous is not None:
                self.advance(previous,group)
                need(group['transit']['ui']['scope']['generation']==previous['transit']['ui']['scope']['generation']
                     and group['graphics']['capturedEpochMs']-previous['graphics']['capturedEpochMs']<=1500)
            previous=group
        need(bool(value['quiet'])==(value['phase']=='closed'))
        if value['quiet']:
            need(len(value['quiet'])>=3)
            a,b=value['quiet'][0],value['quiet'][-1]
            for key in ('home','graphics'):
                need(b[key]['capturedEpochMs']-a[key]['capturedEpochMs']>=3000 and b[key]['elapsedMs']-a[key]['elapsedMs']>=3000)
            for key in ('observedEpochMs',):need(b['transit']['ui'][key]-a['transit']['ui'][key]>=3000)
            need(b['transit']['ui']['scope']['elapsedMs']-a['transit']['ui']['scope']['elapsedMs']>=3000
                 and b['transit']['pose']['subject']['capturedEpochMs']-a['transit']['pose']['subject']['capturedEpochMs']>=3000)
            if b!=value['last']:self.advance(b,value['last'])
    def save(self,value):
        self.now();self.validate(value)
        disk=dict(navigationTabletCloseVersion=VERSION,runId=self.run,binding=self.binding,transitOriginalSha256=self.origin,payload=pack([value]))
        self.store.write(disk,self.disk);self.disk=deepcopy(disk);self.state=deepcopy(value)
    def queries(self,value):return self.transit.query_ids(value['transit'])+[value['home']['commandId'],value['graphics']['commandId']]
    def sample(self):
        self.now();value=dict(transit=self.transit.sample(),home=self.transit.home.source.capture(),graphics=self.graphics.capture())
        self.now();self.archive(value)
        if self.state is not None:
            self.advance(self.state['last'],value);current=deepcopy(self.state);queries=self.queries(value)
            need(len(set(queries))==len(queries) and all(q not in current['queries'] for q in queries))
            current['queries']+=queries;current['last']=value;self.save(current)
        return value
    def close(self,ticket):
        identifier(ticket);need(ticket==self.transit.state['ticket'] and self.deadline is None);self.deadline=self.now()+20
        try:return self.execute(ticket)
        except NativeUIError:raise
        except Exception:raise NativeUIError('Original Navigation tablet close remains unresolved') from None
        finally:self.deadline=None
    def execute(self,ticket):
        if self.state is None:
            before=self.sample();need(before['transit']['ui']['open']);queries=self.queries(before);need(len(set(queries))==len(queries))
            self.save(dict(ticket=ticket,phase='closing',before=before,last=before,quiet=[],queries=queries))
            # Persist first. An uncertain command is observed, never toggled again.
            self.now();self.normal.io.tablet(False);self.now()
        need(self.state['ticket']==ticket)
        if self.state['phase']=='closed':self.closed(self.sample(),self.state['before']);return dict(performed=True)
        if self.state['phase']=='closing':
            for attempt in range(81):
                value=self.sample()
                if not value['transit']['ui']['open']:
                    self.closed(value,self.state['before']);break
                need(attempt<80);self.sleep(.1)
            current=deepcopy(self.state);current['phase']='quiet';self.save(current)
        groups=[];start=self.now()
        for _ in range(8):
            value=self.sample();self.closed(value,self.state['before']);groups.append(value)
            if self.now()-start>=3:
                current=deepcopy(self.state);current['quiet']=groups;current['phase']='closed';self.save(current);return dict(performed=True)
            self.sleep(.5)
        need(False)
