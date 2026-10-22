"""Durable one-send iOS Emote ordinary input; observations remain independent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from adapters.script_feature.history import canonical,pack,unpack,same
from adapters.token_emote_ui import TokenEmoteUI,snapshot,same_reference
from feature_journeys.contract import arguments
from ios.adapters.emote_controls import IOSEmoteIO
from ios.adapters.emote_sources import IOSEmoteSources

VERSION=1


class IOSEmoteActions:
    def __init__(self,store,sources,native_ui):
        need(isinstance(store,PrivateFeatureState) and isinstance(sources,IOSEmoteSources)
            and not sources.historical and sources.role=='primary' and isinstance(native_ui,NativeUI))
        self.store,self.source,self.sdk=store,sources,native_ui
        self.lock=sources.lock;self.lock.assert_held();self.previous=store.read()
        self.state=dict(history=[],current=None) if self.previous is None else self.decode(self.previous)
        self.failed=False

    def envelope(self,state):
        return dict(iosEmoteActionsVersion=VERSION,runId=self.source.run,binding=self.source.binding,payload=pack([state]))

    def reference(self,frame):
        need(frame is self.source.frames[-1] or same(frame,self.source.frames[-1]))
        return dict(revision=len(self.source.frames),sha256=hashlib.sha256(canonical(frame)).hexdigest())

    def original(self,ref):
        exact(ref,{'revision','sha256'});need(integer(ref['revision'],1,len(self.source.frames)))
        frame=self.source.frames[ref['revision']-1];need(hashlib.sha256(canonical(frame)).hexdigest()==ref['sha256']);return frame

    def decode(self,value):
        exact(value,{'iosEmoteActionsVersion','runId','binding','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'history','current'});need(type(state['history']) is list and len(state['history'])<=256)
        tickets=set()
        for row in state['history']+([state['current']] if state['current'] else []):
            exact(row,{'call','phase','before','intents'})
            call=arguments('feature.emotes.act',row['call']);need(call['runId']==self.source.run
                and call['fixtureUrl']==self.source.phase.fixture_url and call['ticket'] not in tickets)
            tickets.add(call['ticket']);need(row['phase'] in ('acting','issuing','acknowledged') and type(row['intents']) is list)
            if row['before'] is not None:self.original(row['before'])
            else:need(not row['intents'])
            pending=0
            for index,intent in enumerate(row['intents']):
                exact(intent,{'kind','input','barrier','after'})
                need(intent['kind'] in ('qt','sdk'))
                self.original(intent['barrier'])
                if intent['kind']=='qt':
                    data=intent['input'];exact(data,{'controlId','action','sequence','instance','generation','direction','original'})
                    original=snapshot(data['original']);need(data['sequence']==original['scope']['sequence']+1)
                    if intent['after'] is not None:
                        after=snapshot(intent['after']);left,right=original['scope'],after['scope']
                        need(all(left[k]==right[k] for k in ('instance','generation','processId'))
                            and right['sequence']==data['sequence'] and right['sourceSequence']>left['sourceSequence'])
                else:need(intent['input'] in ('open','close'))
                if intent['after'] is None:pending+=1;need(index==len(row['intents'])-1)
            need(pending==(1 if row['phase']=='issuing' else 0))
            if row['phase']=='acknowledged':need(row['before'] is not None)
        need(all(row['phase']=='acknowledged' for row in state['history']));return deepcopy(state)

    def bound(self):
        self.source.bound();need(not self.failed and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def capture(self):
        frame=self.source.read();return self.reference(frame)

    def active(self,call,frame):
        status=frame['phaseAfter'];need(status['active'] and status['activations'])
        row=status['activations'][-1]
        need(row['ticket']==call['ticket'] and row['stimulus']['verb']==call['verb'] and same(row['stimulus']['inputs'],call['inputs']))

    def intent(self,value):
        self.bound();row=self.state['current'];need(row['phase']=='acting')
        barrier=self.capture();frame=self.original(barrier);self.active(row['call'],frame)
        same_reference(value['original'],frame['ui'],value['controlId'])
        row['intents'].append(dict(kind='qt',input=deepcopy(value),barrier=barrier,after=None))
        row['phase']='issuing';self.save()

    def receipt(self,value):
        self.bound();row=self.state['current'];need(row['phase']=='issuing')
        item=row['intents'][-1];need(item['kind']=='qt' and same(item['input'],value['intent']) and item['after'] is None)
        item['after']=deepcopy(value['after']);row['phase']='acting';self.save()

    def tablet(self,opened):
        need(type(opened) is bool);row=self.state['current'];need(row['phase']=='acting')
        ref=self.capture();frame=self.original(ref);self.active(row['call'],frame)
        if frame['ui']['open']==opened:return
        row['intents'].append(dict(kind='sdk',input='open' if opened else 'close',barrier=ref,after=None))
        row['phase']='issuing';self.save()
        self.sdk.click(Locator('accessibility id','OverteTabletOpen' if opened else 'OverteTabletClose'))
        after=self.capture();need(self.original(after)['ui']['open']==opened)
        row['intents'][-1]['after']=after;row['phase']='acting';self.save()

    def act(self,call):
        call=deepcopy(arguments('feature.emotes.act',call));self.bound()
        need(call['runId']==self.source.run and call['fixtureUrl']==self.source.phase.fixture_url)
        current=self.state['current']
        if current:
            if current['call']['ticket']==call['ticket']:
                need(same(current['call'],call) and current['phase']=='acknowledged');return {'performed':True}
            # An uncertain or interrupted delivery retains responsibility.
            need(current['phase']=='acknowledged' and len(self.state['history'])<255)
            self.state['history'].append(deepcopy(current))
        self.state['current']=dict(call=call,phase='acting',before=None,intents=[]);self.save()
        row=self.state['current'];row['before']=self.capture();self.active(call,self.original(row['before']));self.save()
        # Refuse adopting an unowned pre-existing override/tablet at first input.
        if not self.state['history']:
            first=self.original(row['before'])
            need(not first['ui']['open'] and first['group']['native']['animation']['overrideActive'] is False)
        ui=TokenEmoteUI(self.source.readers['ui'],self.intent,receipt=self.receipt,
            monotonic=self.source.monotonic,sleep=self.sdk.sleep)
        verb=call['verb']
        if verb in ('open','play','sit','override','cancel'):
            self.tablet(True);ui.open()
            if verb in ('play','sit','override'):ui.play('Sit' if verb=='sit' else call['inputs']['name'])
            elif verb=='cancel':ui.cancel()
        elif verb=='close':
            if self.source.readers['ui'].capture()['open']:ui.close();self.tablet(False)
        else:need(verb=='wait-complete') # Timer/evaluated idle, never a restore setter.
        row['phase']='acknowledged';self.save();self.bound();return {'performed':True}
