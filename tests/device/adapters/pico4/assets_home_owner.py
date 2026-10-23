"""Durable normal Assets X/Home; original context retention remains explicit."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.chat_journey.source_chunks import json_digest
from adapters.phase_input_fence import PhaseInputFence
from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
from adapters.pico4.assets_files import NativeAssetsFiles
from adapters.pico4.assets_pages import PicoAssetsPages,IDENTITIES
from adapters.pico4.lifecycle_back import BUTTON,envelope,PicoLifecycleBack
from adapters.script_journey.history import pack,unpack,same,MAX_RAW,MAX_FRAMES,canonical
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as validate_phase
from openxr_input.adapter_session import PicoOpenXrAdapterSession

VERSION=1


class HomeFence(PhaseInputFence):
    def original(self):return self.owner.state()['phaseOriginal']


class OwnedAssetsHome:
    def __init__(self,store,cancel,pages,session,phase,source_lock):
        need(isinstance(cancel,OwnedAssetsCancel) and isinstance(pages,PicoAssetsPages)
            and isinstance(session,PicoOpenXrAdapterSession) and isinstance(phase,PhaseFixtureReader)
            and isinstance(source_lock,ScriptSourceLock) and phase.run==cancel.run and phase.area=='assets'
            and phase.fixture_url==cancel.url and pages.pid==cancel.files.native.pid==cancel.mappings.pid
            and (pages.source_lock is None or pages.source_lock is source_lock))
        self.store,self.cancel,self.pages,self.session,self.lock=store,cancel,pages,session,source_lock
        pages.source_lock=source_lock;self.identity=cancel.binding['processIdentity'];self.previous=None
        native=cancel.files.native
        # A separate, observe-only transcript leaves the complete original
        # Cancel/File journals untouched while physically checking their lease.
        self.files=NativeAssetsFiles(native.send,native.original,native.clock_ms,native.guard,native.pid,
            monotonic=native.monotonic,sleep=native.sleep,stage=native.stage)
        self.fence=HomeFence(phase);self.fence.owner=self;self.fence.stream_intent=self.stream_intent
        self.anchor=None;self.clock=None
        with self.lock.held():
            value=self.store.read()
            if value is not None:
                self.validate(value);self.pages.restore(unpack(value['pages']));self.files.restore(unpack(value['files']))
                self.previous=deepcopy(value)
    def children(self):
        value=self.cancel.state();files=self.cancel.files.store.read()
        need(value['phase']=='cancel-observed-files-retired' and files['phase']=='retired'
            and json_digest(files)==json_digest(self.cancel.files.previous) and same(files,self.cancel.files.previous))
        self.cancel.files.validate_history();return [value,files]
    def validate(self,value):
        exact(value,{'assetsHomeOwnerVersion','binding','runId','phaseOriginal','phase','originalId','children','pages','files','envelope','neutral','quiet'})
        need(type(value['assetsHomeOwnerVersion']) is int and value['assetsHomeOwnerVersion']==VERSION
            and json_digest(value['binding'])==json_digest(self.cancel.binding) and value['runId']==self.cancel.run
            and value['phase'] in ('reserved','issued','home-retained','home-resources-retired'))
        phase=value['phaseOriginal'];validate_phase(phase,run=self.cancel.run,area='assets',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        need(phase['active'] and phase['activations'][-1]['stimulus']=={'verb':'close','inputs':{}})
        children=unpack(value['children']);need(len(children)==2 and same(children,self.children()) and json_digest(children)==json_digest(self.children()))
        pages=unpack(value['pages']);files=unpack(value['files']);need(1<=len(pages)==len(files)<=64)
        page_check=PicoAssetsPages(self.pages.send,self.pages.original,self.pages.clock_ms,self.pages.guard,self.pages.pid)
        page_check.restore(pages)
        file_check=NativeAssetsFiles(self.files.send,self.files.original,self.files.clock_ms,self.files.guard,self.files.pid,stage=self.files.stage)
        file_check.restore(files)
        base=decode(pages[0]['raw']);rows=[row for row in base['source']['pages'] if row['id']==value['originalId']]
        need(len(rows)==1 and rows[0]['pageAlive'] and rows[0]['contextAlive'] and rows[0]['visible'] and rows[0]['inCurrentTree']
            and base['source']['tabletShown'] and not base['source']['onHomeScreen'])
        for frame in files:
            call=frame['command'];actual=decode(frame['raw'])['source']
            need(call['operation']=='observe' and call['runId']==self.cancel.run and call['ownerToken']==children[1]['ownerToken']
                and actual['retired'] and not actual['exists'])
        counts=len(pages)+len(files)+len(children[0]['unresolvedInputs']);size=value['pages']['bytes']+value['files']['bytes']
        for original in (children[0]['inputs'],children[0]['uiOriginals'],children[0]['originals'],children[1]['originals']):
            counts+=len(unpack(original));size+=original['bytes']
        need(counts<=MAX_FRAMES and size+len(canonical(children[0]['unresolvedInputs']))<=MAX_RAW)
        if value['envelope'] is None:need(value['phase']=='reserved' and value['neutral'] is None and value['quiet'] is None)
        else:envelope(value['envelope'],self.session.profile);need(value['phase']!='reserved')
        if value['phase'].startswith('home-'):
            PicoLifecycleBack.neutral(value['neutral'],value['envelope'],base['capturedEpochMs'])
            quiet=value['quiet'];exact(quiet,{'first','last'})
            need(integer(quiet['first'],1,len(pages)-1) and integer(quiet['last'],quiet['first'],len(pages)-1))
            samples=[decode(frame['raw']) for frame in pages[quiet['first']:quiet['last']+1]]
            need(len(samples)>=2 and samples[-1]['elapsedMs']-samples[0]['elapsedMs']>=3000
                and samples[-1]['capturedEpochMs']-samples[0]['capturedEpochMs']>=3000)
            for packet in samples:self.home(packet,value)
            for before,after in zip(samples,samples[1:]):
                need(all(0<after[key]-before[key]<=500 for key in ('elapsedMs','capturedEpochMs')))
            row=self.row(samples[-1],value);need((value['phase']=='home-resources-retired')==(not row['contextAlive']))
        else:need(value['neutral'] is None and value['quiet'] is None)
    def state(self):
        self.lock.assert_held();value=self.store.read()
        need(value is not None and json_digest(value)==json_digest(self.previous) and same(value,self.previous))
        self.validate(value);return value
    def save(self,value):
        self.lock.assert_held();self.validate(value)
        need(json_digest(self.store.read())==json_digest(self.previous))
        retained=deepcopy(value);self.store.write(value,self.previous);self.previous=retained
    def now(self):
        value=self.pages.monotonic();need(number(value,0,1e15) and (self.clock is None or value>=self.clock));self.clock=value;return value
    def freshness(self):
        started,requested,packets=self.anchor;self.cancel.guard();now=self.now();epoch=self.pages.clock_ms()
        need(integer(epoch,requested) and now-started<1.5)
        for packet in packets:fresh(packet['capturedEpochMs'],max(epoch,requested+math.ceil((now-started)*1000)))
    def host_freshness(self):
        # The original session lock is held: no guard, native clock, transport
        # or session reentry is permitted before the original grant writer.
        started,requested,packets=self.anchor;now=self.now();need(now-started<1.5)
        for packet in packets:fresh(packet['capturedEpochMs'],requested+math.ceil((now-started)*1000))
    def capture(self):
        started=self.now();requested=self.pages.clock_ms();children=self.children()
        actual=self.files.request('observe',self.cancel.run,children[1]['ownerToken']);page=self.pages.capture()
        self.anchor=(started,requested,(actual,page));self.freshness();return page
    def record(self):
        original=self.state()
        for reader,key in ((self.pages,'pages'),(self.files,'files')):
            history=unpack(original[key]);need(json_digest(reader.history)==json_digest(history) and same(reader.history,history)
                and same(reader.last,decode(history[-1]['raw'])) and json_digest(reader.last)==json_digest(decode(history[-1]['raw'])))
        page=self.capture();state=self.state();state['pages']=pack(self.pages.history);state['files']=pack(self.files.history);self.save(state)
        self.freshness();return page
    @staticmethod
    def row(packet,state):
        rows=[row for row in packet['source']['pages'] if row['id']==state['originalId']];need(len(rows)==1);return rows[0]
    @classmethod
    def home(cls,packet,state):
        row=cls.row(packet,state);source=packet['source']
        original=cls.row(decode(unpack(state['pages'])[0]['raw']),state)
        need(all(row[key]==original[key] for key in IDENTITIES) and source['tabletShown'] and source['onHomeScreen']
            and not row['pageAlive'] and not row['inCurrentTree'] and not row['visible'] and not source['qmlLoads']['components'])
        return row
    def stream_intent(self,original):
        state=self.state();need(state['phase']=='reserved' and state['envelope'] is None)
        envelope(original,self.session.profile);state.update(phase='issued',envelope=deepcopy(original));self.save(state)
        self.host_freshness()
    def before_publish(self,original):
        state=self.state();need(json_digest(original)==json_digest(state['envelope']) and same(original,state['envelope']))
        self.host_freshness();self.fence.before_publish(original)
    def close_page(self):
        with self.lock.held():
            need(self.previous is None and self.store.read() is None and not self.pages.history and not self.files.history)
            phase=self.fence.source.read();need(phase['verb']=='close' and phase['inputs']=={} and phase['status']['active'])
            before=self.capture();rows=[row for row in before['source']['pages'] if row['pageAlive'] and row['inCurrentTree'] and row['visible']]
            need(len(rows)==1)
            self.save(dict(assetsHomeOwnerVersion=VERSION,binding=deepcopy(self.cancel.binding),runId=self.cancel.run,
                phaseOriginal=phase['status'],phase='reserved',originalId=rows[0]['id'],children=pack(self.children()),
                pages=pack(self.pages.history),files=pack(self.files.history),envelope=None,neutral=None,quiet=None))
            self.freshness();self.fence.mark();self.fence.check()
            self.session.stage(self.identity,'controller.button',deepcopy(BUTTON),intent=self.fence.stage_intent,before_publish=self.before_publish)
            return self.observe()
    def observe(self):
        state=self.state()
        if state['envelope'] is None:return dict(homeObserved=False,retained=True)
        owned=state['envelope'];first_packet=decode(unpack(state['pages'])[0]['raw'])
        neutral=self.session.require_owned_neutral(self.identity,owned);PicoLifecycleBack.neutral(neutral,owned,first_packet['capturedEpochMs'])
        started=self.now();first=None;previous=None
        for attempt in range(41):
            page=self.record();state=self.state();need(self.now()-started<=10)
            need(neutral['updatedEpochMs']<=page['capturedEpochMs']+250)
            self.home(page,state)
            if previous is not None:need(all(0<page[key]-previous[key]<=500 for key in ('elapsedMs','capturedEpochMs')))
            if first is None:first=(len(self.pages.history)-1,page,self.now())
            if self.now()-first[2]>=3 and all(page[key]-first[1][key]>=3000 for key in ('elapsedMs','capturedEpochMs')):
                final=self.session.require_owned_neutral(self.identity,owned);need(json_digest(neutral)==json_digest(final) and same(neutral,final))
                phase=self.fence.source.read(state['phaseOriginal']);need(same(phase['status']['activations'],state['phaseOriginal']['activations']))
                row=self.home(page,state);state.update(phase='home-retained' if row['contextAlive'] else 'home-resources-retired',neutral=deepcopy(neutral),
                    quiet=dict(first=first[0],last=len(self.pages.history)-1));self.save(state)
                result=dict(homeObserved=True,pageRetired=True,contextRetired=not row['contextAlive'],retained=True,page=deepcopy(row))
                self.freshness();return result
            previous=page;need(attempt<40);self.pages.sleep(.25)
        need(False)
    def reconcile(self):
        with self.lock.held():return self.observe() # Original queries only; no repeat X, journal removal or file release.
