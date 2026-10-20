"""Durable ordinary Graphics preferences; GPU effects remain independent facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI,on_grid
from feature_journeys.contract import arguments,identifier
from overte_phone_graphics_scene import PhoneGraphicsScene,operation
from overte_phone_graphics_samples import restore_native
from overte_phone_script_history import pack,unpack,same

VERSION=1
VERBS=frozenset({'open','close','set-resolution','set-haze','set-mirrors','restore-original'})
FIELDS=('requestedResolutionScale','hazeSetting','mirrorsSetting')


def advance(before,after):
    native_packet(after,after['requestId'],before['processId'],after['capturedEpochMs'])
    need(after['instance']==before['instance'] and after['sequence']>before['sequence']
        and after['capturedEpochMs']>=before['capturedEpochMs']
        and all(after['lifecycle'][key]>=before['lifecycle'][key] for key in before['lifecycle']))


class PhoneGraphicsPreferences:
    """One process, original preferences and one-send scalar/page action intent.

    This internal owner does not implement restart/background, perform scene
    input, publish measurements or advertise a complete feature capability.
    """
    def __init__(self,scene,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(scene,PhoneGraphicsScene) and callable(monotonic) and callable(sleep))
        self.scene,self.adapter,self.selector,self.run,self.lock=scene,scene.adapter,scene.selector,scene.run,scene.lock
        self.monotonic,self.sleep,self.started,self.last_clock=monotonic,sleep,None,None
        self.restoring=False
        self.fixture_url=scene.client.url+'/runs/'+self.run+'/'
        self.store=PrivateFeatureState(scene.store.path.with_name('phone-graphics-preferences.json'))
        self.previous=self.store.read();self.state=None
        if self.previous is not None:self.state=self.decode(self.previous)

    def decode(self,value):
        exact(value,{'graphicsPreferencesVersion','runId','fixtureUrl','payload'})
        need(type(value['graphicsPreferencesVersion']) is int and value['graphicsPreferencesVersion']==VERSION
            and value['runId']==self.run and value['fixtureUrl']==self.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','original','native','phase','tickets','current','restoration'})
        need(same(context(state['binding']),self.scene.binding) and state['phase'] in ('ready','issued','acknowledged','cleaned')
            and type(state['tickets']) is list and len(state['tickets'])<=128
            and len({identifier(ticket) for ticket in state['tickets']})==len(state['tickets']))
        pid=int(state['binding']['processIdentity'].split(':')[0])
        for packet in (state['original'],state['native']):native_packet(packet,packet['requestId'],pid,packet['capturedEpochMs'])
        if not same(state['original'],state['native']):advance(state['original'],state['native'])
        current=state['current']
        if current is None:need(state['phase'] in ('ready','cleaned') and not state['tickets'])
        else:
            exact(current,{'arguments','barrier','steps','intents','proof'})
            call=arguments('feature.graphics.act',current['arguments'])
            need(call['verb'] in VERBS and call['runId']==self.run and call['fixtureUrl']==self.fixture_url
                and bool(state['tickets']) and call['ticket']==state['tickets'][-1]
                and type(current['steps']) is list and len(current['steps'])<=3
                and type(current['intents']) is list and len(current['intents'])<=128)
            before=current['barrier'];native_packet(before,before['requestId'],pid,before['capturedEpochMs'])
            need(before['instance']==state['original']['instance'])
            kinds=set()
            for step in current['steps']:
                exact(step,{'kind','phase'});need(step['kind'] in self.steps(call) and step['kind'] not in kinds
                    and step['phase'] in ('issued','observed'));kinds.add(step['kind'])
            for row in current['intents']:
                exact(row,{'step','stage','control','subject','graphics','native'})
                need(row['step'] in kinds and type(row['stage']) is str and len(row['stage'])<=80
                    and type(row['control']) is str and len(row['control'])<=256)
                self.scene.validate_subject(row['subject'],pid);advance(before,row['native']);before=row['native']
            if not same(before,state['native']):advance(before,state['native'])
            if state['phase']=='acknowledged':
                need([step['kind'] for step in current['steps']]==self.steps(call)
                    and all(step['phase']=='observed' for step in current['steps']) and current['proof'] is not None)
        need(type(state['restoration']) is list and len(state['restoration'])<=5)
        for row in state['restoration']:
            exact(row,{'field','phase','intents','proof'});need(row['field'] in ('open','resolution','haze','mirrors','close')
                and row['phase'] in ('issued','observed') and type(row['intents']) is list and len(row['intents'])<=128)
            before=state['original']
            for item in row['intents']:
                exact(item,{'step','stage','control','subject','graphics','native'})
                need(item['step']==row['field'] and type(item['stage']) is str and type(item['control']) is str)
                self.scene.validate_subject(item['subject'],pid);advance(before,item['native']);before=item['native']
            need(row['phase']!='observed' or row['proof'] is not None)
        need(len({row['field'] for row in state['restoration']})==len(state['restoration']))
        if state['phase']=='cleaned':need(bool(state['restoration']) and state['restoration'][-1]['field']=='close'
            and all(row['phase']=='observed' for row in state['restoration']))
        return state

    def bound(self):
        self.lock.assert_held();need(self.scene.guard() is not False and same(self.scene.store.read(),self.scene.previous))
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock)
            and (self.started is None or 0<=now-self.started<30));self.last_clock=now

    def save(self):
        self.bound();need(same(self.store.read(),self.previous))
        value=dict(graphicsPreferencesVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def source(self):
        self.bound();_ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),self.scene.binding))
        source=self.adapter._native_feature_observer(self.selector,read_only=True)
        if self.state is not None:restore_native(source,self.state['native'])
        packet=source.read(source.sequence);need(guard() is not False);self.bound()
        need(packet['instance']==self.scene.state['subject']['instance'])
        if self.state is not None:advance(self.state['native'],packet);self.state['native']=deepcopy(packet);self.save()
        return packet

    @operation
    def prepare(self):
        self.bound();need(self.scene.state['phase']=='active')
        if self.state is None:
            first=self.source();second=self.source();advance(first,second)
            need(first['graphics']==second['graphics'] and first['lifecycle']==second['lifecycle']
                and not any(self.scene.state['leases'].values()))
            self.state=dict(binding=deepcopy(self.scene.binding),original=first,native=second,
                phase='ready',tickets=[],current=None,restoration=[]);self.save()
        else:self.source()
        return deepcopy(self.state)

    @staticmethod
    def steps(call):
        return ['resolution','haze','mirrors'] if call['verb']=='restore-original' else [call['verb']]

    def surface(self):
        surface=self.adapter._graphics_surface(self.selector,self.run,self.intent,
            lambda field:self.scene.state['leases'][field],self.scene.lease,lambda _url:False,lock=self.lock)
        surface.subject.last=deepcopy(self.scene.state['subject']);return surface

    def intent(self,stage,subject,graphics,control):
        self.bound();current=self.state['current']
        if self.restoring:
            step=self.state['restoration'][-1];need(step['phase']=='issued');kind=step['field'];intents=step['intents']
        else:
            need(self.state['phase']=='issued' and bool(current['steps']) and current['steps'][-1]['phase']=='issued')
            kind=current['steps'][-1]['kind'];intents=current['intents']
        need(len(intents)<128)
        self.scene.accept_subject(subject);packet=self.source()
        intents.append(dict(step=kind,stage=stage,control=control,
            subject=deepcopy(subject),graphics=deepcopy(graphics),native=packet));self.save()

    def status(self):
        surface=self.surface();value=surface.graphics.capture();page=TokenGraphicsUI.row(value,'graphics.page')
        visible=surface.tablet.tablet_visible();self.bound()
        need(page is None or visible and page['profile']=='phone-immediate-v1')
        return surface,value,visible

    def scalar(self,call,kind):
        field={'set-resolution':'requestedResolutionScale','resolution':'requestedResolutionScale',
            'set-haze':'hazeSetting','haze':'hazeSetting','set-mirrors':'mirrorsSetting','mirrors':'mirrorsSetting'}[kind]
        wanted=(self.state['original']['graphics'][field] if call['verb']=='restore-original'
            else call['inputs']['value' if kind=='set-resolution' else 'enabled'])
        return field,wanted

    def observe_step(self,call,kind):
        surface,value,visible=self.status();page=TokenGraphicsUI.row(value,'graphics.page')
        native=self.source();self.bound()
        if kind=='open':need(page is not None and visible and self.scene.state['leases']['tablet'])
        elif kind=='close':
            need(page is None and not visible)
            # Lost close replies can retire a lease only through fresh absence;
            # these calls cannot send UI input after the absence gate above.
            surface.close_address();surface.close_tablet()
            need(not any(self.scene.state['leases'].values()))
        else:
            field,wanted=self.scalar(call,kind);need(page is not None and visible and self.scene.state['leases']['tablet'])
            identifier_={'requestedResolutionScale':'graphics.resolution','hazeSetting':'graphics.haze','mirrorsSetting':'graphics.mirrors'}[field]
            row=TokenGraphicsUI.row(value,identifier_);need(row is not None)
            measured=native['graphics'][field];actual=row['nativeValue' if field=='requestedResolutionScale' else 'nativeChecked']
            need(abs(measured-wanted)<1e-4 and abs(actual-measured)<1e-4 if field=='requestedResolutionScale' else measured is wanted and actual is measured)
        return dict(native=deepcopy(native),graphics=deepcopy(value),tabletVisible=visible)

    def deliver_step(self,call,kind):
        surface=self.surface()
        if kind=='open':surface.open()
        elif kind=='close':surface.close_address();surface.close_tablet()
        else:
            _existing,value,visible=self.status();need(visible and self.scene.state['leases']['tablet'])
            row=TokenGraphicsUI.row(value,'graphics.resolution')
            need(row is not None and on_grid(self.state['original']['graphics']['requestedResolutionScale'],row))
            field,wanted=self.scalar(call,kind)
            if field=='requestedResolutionScale':surface.set_resolution(wanted)
            else:surface.toggle('graphics.haze' if field=='hazeSetting' else 'graphics.mirrors',wanted)
        self.bound()

    def unchanged_other_preferences(self,call,packet):
        if call['verb']=='restore-original':need(packet['graphics']==self.state['original']['graphics']);return
        changed={'set-resolution':{'requestedResolutionScale','applicationResolutionScale'},
            'set-haze':{'hazeSetting'},'set-mirrors':{'mirrorsSetting'}}.get(call['verb'],set())
        before=self.state['current']['barrier']['graphics']
        need(all(packet['graphics'][field]==before[field] for field in before if field not in changed))

    @operation
    def act(self,call):
        call=deepcopy(arguments('feature.graphics.act',call))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['verb'] in VERBS)
        self.bound();need(self.state is not None and not self.state['restoration'])
        need(same(self.store.read(),self.previous))
        if call['ticket'] in self.state['tickets']:
            need(self.state['current'] is not None and same(self.state['current']['arguments'],call))
            if self.state['phase']=='acknowledged':
                proof=self.observe_step(call,self.steps(call)[-1]);self.unchanged_other_preferences(call,proof['native'])
                self.bound();return {'performed':True}
        else:
            need(self.state['phase'] in ('ready','acknowledged') and len(self.state['tickets'])<128)
            before=self.source();self.state.update(phase='issued',tickets=self.state['tickets']+[call['ticket']],current=dict(
                arguments=call,barrier=before,steps=[],intents=[],proof=None));self.save()
        current=self.state['current']
        for kind in self.steps(call):
            rows=[row for row in current['steps'] if row['kind']==kind]
            if not rows:
                current['steps'].append(dict(kind=kind,phase='issued'));self.save();self.deliver_step(call,kind)
            # Existing issued substeps receive reads only, including lost input returns.
            proof=self.observe_step(call,kind)
            row=next(row for row in current['steps'] if row['kind']==kind);row['phase']='observed'
            current['proof']=proof;self.save()
        self.unchanged_other_preferences(call,current['proof']['native'])
        self.state['phase']='acknowledged';self.save();self.bound();return {'performed':True}

    @operation
    def cleanup(self):
        """Restore only original preferences and close owned UI; no world verdict."""
        self.bound();need(self.state is not None)
        if self.state['phase']=='cleaned':
            self.observe_step(dict(verb='restore-original'),'close');packet=self.source()
            need(packet['graphics']==self.state['original']['graphics']);return deepcopy(packet)
        packet=self.source();changed=any(packet['graphics'][field]!=self.state['original']['graphics'][field] for field in FIELDS)
        steps=['open','resolution','haze','mirrors','close'] if changed or any(row['field']=='open' for row in self.state['restoration']) else ['close']
        call=dict(verb='restore-original')
        self.restoring=True
        try:
            for kind in steps:
                rows=[row for row in self.state['restoration'] if row['field']==kind]
                if rows and rows[0]['phase']=='observed':continue
                if not rows:
                    self.state['restoration'].append(dict(field=kind,phase='issued',intents=[],proof=None));self.save()
                    self.deliver_step(call,kind)
                proof=self.observe_step(call,kind);row=next(row for row in self.state['restoration'] if row['field']==kind)
                row.update(phase='observed',proof=proof);self.save()
            packet=self.source();need(packet['graphics']==self.state['original']['graphics'])
            self.state['phase']='cleaned';self.save();self.bound();return deepcopy(packet)
        finally:self.restoring=False

    @operation
    def retire(self):
        self.cleanup();need(self.state['phase']=='cleaned');self.decode(self.previous)
        need(same(self.store.read(),self.previous));self.store.discard(self.previous)
        need(self.store.read() is None)
