"""Owned normal Chat draft following the actual Lifecycle Create/X history.

No message is sent. Background, later editors and full cleanup stay separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_source as ui
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.pico4.lifecycle_editor import PicoLifecycleEditor
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
from adapters.script_journey.history import canonical,pack,unpack
from adapters.token_chat_ui import TokenChatUI,snapshot
from feature_journeys.fixtures import context as fixture

VERSION=1
PHASES=('prepared','opening','opened','focusing','focused','typing','typed')


class PicoLifecycleChatDraft:
    # Reuse the exact original-source, binding and final-age helpers. These
    # helpers perform no Create input and assign no generation themselves.
    packet=PicoLifecycleEditor.packet
    now=PicoLifecycleEditor.now
    capture=PicoLifecycleEditor.capture
    fresh=PicoLifecycleEditor.fresh
    bound_scope=PicoLifecycleEditor.bound_scope
    consumed=PicoLifecycleEditor.consumed

    def __init__(self,joined,source,route,path):
        need(isinstance(joined,PicoLifecycleXJoin) and isinstance(source,ui.PicoLifecycleSource) and isinstance(route,TokenChatUI))
        self.joined,self.source,self.route=joined,source,route
        world=joined.world;self.run,self.binding,self.pid,self.lock=world.run,deepcopy(world.binding),world.pid,world.lock
        need(source.pid==self.pid and source.source_lock is self.lock and route.run==self.run)
        self.store=PrivateFeatureState(path);need(self.store.path==world.store.path.with_name('lifecycle-chat-owner.json'))
        self.disk=self.state=None;self.last_clock=self.acquisition=None;route.intent=self.intent
        with self.lock.held():self.load()

    def join_hash(self):
        self.joined.load();need(self.joined.state is not None and self.joined.state['phase']=='observed')
        return hashlib.sha256(canonical(self.joined.disk)).hexdigest()

    def reference(self,value,phase):
        exact(value,{'phase','intent','reference','consumed'});need(value['phase']==phase)
        request=value['intent'];exact(request,{'controlId','action','instance','generation','sequence'})
        original=snapshot(value['reference']);before=original['scope'];self.bound_scope(before)
        need(request['instance']==before['instance'] and request['generation']==before['generation']
            and type(request['generation']) is type(before['generation']) and integer(request['sequence'],1)
            and request['sequence']==before['sequence']+1 and original['open'] and original['ready'])
        allowed=('tablet.home','chat.entry') if phase=='opening' else ('chat.input',)
        need(request['controlId'] in allowed and request['action']==('replace' if phase=='typing' else 'activate')
            and self.route.row(original,request['controlId']) is not None)
        if phase=='typing':need(self.route.row(original,'chat.input')['focused'])
        if value['consumed'] is not None:self.consumed(before,value['consumed'])
        return before

    def validate(self,state):
        exact(state,{'phase','joinSha256','frames','inputs','originalId','page'})
        need(state['phase'] in PHASES and state['joinSha256']==self.join_hash()
            and type(state['frames']) is list and 1<=len(state['frames'])<=64
            and type(state['inputs']) is list and len(state['inputs'])<=16)
        previous=None;commands=set()
        for frame in state['frames']:
            packet=self.packet(frame);need(packet['commandId'] not in commands);commands.add(packet['commandId'])
            previous=ui.accept(previous,ui.summary(packet))
        first=self.packet(state['frames'][0]);PicoLifecycleBack.home(first,self.joined.state['originalId'])
        old=self.joined.world.originals(self.joined.state['after'])['ui'];ui.accept(ui.summary(old),ui.summary(first))
        prior=None
        for index,row in enumerate(state['inputs']):
            need(row['phase'] in ('opening','focusing','typing'));before=self.reference(row,row['phase'])
            if prior is not None:
                need(prior is not None and all(before[key]==prior[key] for key in ('instance','generation','sequence','processId'))
                    and before['elapsedMs']>=prior['elapsedMs'])
            if row['consumed'] is None:need(index==len(state['inputs'])-1 and state['phase']==row['phase'])
            prior=row['consumed']
        original=state['originalId'];page=state['page']
        if original is None:need(page is None and state['phase'] in ('prepared','opening'));return
        need(ui.nonce(original) and state['phase'] in ('opened','focusing','focused','typing','typed')
            and any(row['intent']['controlId']=='chat.entry' and row['consumed'] is not None for row in state['inputs']))
        exact(page,{'channel','localRowCount','domainRowCount','componentSourceSha256'})
        need(page['channel'] in ('local','domain','settings') and all(integer(page[key],0,1000) for key in ('localRowCount','domainRowCount'))
            and type(page['componentSourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',page['componentSourceSha256']))
        current=ui.current_editor(self.packet(state['frames'][-1]))
        need(current is not None and current['id']==original and current['kind']=='chat'
            and original not in {row['id'] for row in first['source']['editors']}
            and current['text']==(fixture(self.run)['reply'] if state['phase']=='typed' else ''))
        create=next(row for row in first['source']['editors'] if row['id']==self.joined.state['originalId'])
        need(all(current[key]!=create[key] for key in ('fieldId','pageId','contextId')))
        if state['phase'] in ('focused','typing','typed'):
            need(current['focused'] and measured_keyboard(self.packet(state['frames'][-1])['source']['keyboard']) is True
                and any(row['phase']=='focusing' and row['consumed'] is not None for row in state['inputs']))
        if state['phase']=='typed':need(any(row['phase']=='typing' and row['consumed'] is not None for row in state['inputs']))

    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecycleChatOwnerVersion','runId','binding','payload'})
        need(type(disk['lifecycleChatOwnerVersion']) is int and disk['lifecycleChatOwnerVersion']==VERSION
            and disk['runId']==self.run and disk['binding']==self.binding)
        value=unpack(disk['payload']);need(len(value)==1);self.validate(value[0])
        expected=ui.summary(self.packet(value[0]['frames'][-1]))
        if self.source.previous is None:self.source.restore(expected)
        elif self.source.previous!=expected:ui.accept(expected,self.source.previous)
        self.disk,self.state=deepcopy(disk),deepcopy(value[0])

    def save(self,state):
        self.lock.assert_held();need(self.store.read()==self.disk);self.validate(state)
        disk=dict(lifecycleChatOwnerVersion=VERSION,runId=self.run,binding=deepcopy(self.binding),payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)

    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);join_hash=self.join_hash();row,value=self.capture()
            PicoLifecycleBack.home(value,self.joined.state['originalId'])
            self.save(dict(phase='prepared',joinSha256=join_hash,frames=[row],inputs=[],originalId=None,page=None));self.fresh()

    def intent(self,request):
        self.lock.assert_held();need(self.state is not None and self.state['phase'] in ('opening','focusing','typing'))
        state=deepcopy(self.state);reference=self.route.capture();self.bound_scope(reference['scope'])
        if state['inputs'] and state['inputs'][-1]['consumed'] is None:
            self.consumed(state['inputs'][-1]['reference']['scope'],reference['scope']);state['inputs'][-1]['consumed']=deepcopy(reference['scope'])
        row=dict(phase=state['phase'],intent=deepcopy(request),reference=deepcopy(reference),consumed=None)
        self.reference(row,state['phase'])
        if state['phase']=='opening':
            observed,value=self.capture();PicoLifecycleBack.home(value,self.joined.state['originalId'])
        else:
            observed,_value,_current,_field,_page=self.read_draft(state)
        state['frames'].append(observed);state['inputs'].append(row);self.save(state);self.fresh()

    def finish_cursor(self,state):
        if state['inputs'] and state['inputs'][-1]['consumed'] is None:
            actual=self.route.capture()['scope'];self.consumed(state['inputs'][-1]['reference']['scope'],actual)
            state['inputs'][-1]['consumed']=deepcopy(actual)

    def read_draft(self,state):
        normal=self.route.capture();page=self.route.page(normal);field=self.route.row(normal,'chat.input',enabled=False)
        need(field is not None);self.bound_scope(normal['scope'])
        facts={key:page[key] for key in ('channel','localRowCount','domainRowCount','componentSourceSha256')}
        if state['page'] is not None:need(facts==state['page'])
        row,value=self.capture();current=ui.current_editor(value)
        need(current is not None and current['kind']=='chat' and current['visible'] and value['source']['tabletShown']
            and current['text']==field['text'] and current['focused']==field['focused'])
        if state['originalId'] is not None:need(current['id']==state['originalId'])
        return row,value,current,field,facts

    def reconcile(self):
        try:
            with self.lock.held():
                self.load();need(self.state is not None and self.state['phase'] in ('opening','focusing','typing'))
                state=deepcopy(self.state);self.finish_cursor(state);row,value,current,field,page=self.read_draft(state)
                if state['phase']=='opening':need(current['text']=='');state.update(originalId=current['id'],page=page,phase='opened')
                else:
                    need(current['focused'] and measured_keyboard(value['source']['keyboard']) is True)
                    need(current['text']==('' if state['phase']=='focusing' else fixture(self.run)['reply']))
                    state['phase']='focused' if state['phase']=='focusing' else 'typed'
                state['frames'].append(row);self.save(state);result=self.report();self.fresh();return result
        except Exception:raise NativeUIError('Lifecycle Chat draft unresolved; original normal inputs retained, none repeated') from None

    def issue(self,phase,prior,callback):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']==prior)
            state=deepcopy(self.state);state['phase']=phase;self.save(state);callback();return self.reconcile()
    def open_chat(self):return self.issue('opening','prepared',self.route.open)
    def focus_chat(self):return self.issue('focusing','opened',lambda:self.route.input('chat.input'))
    def type_chat(self):return self.issue('typing','focused',lambda:self.route.input('chat.input','replace',fixture(self.run)['reply']))

    def observe(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase'] in ('opened','focused','typed'))
            state=deepcopy(self.state);row,_value,_current,_field,_page=self.read_draft(state)
            state['frames'].append(row);self.save(state);result=self.report();self.fresh();return result

    def report(self):
        current=ui.current_editor(self.packet(self.state['frames'][-1]))
        need(current is not None and current['id']==self.state['originalId'] and current['kind']=='chat')
        return dict(editor='chat',text=current['text'],generation=2,focused=current['focused'],
            keyboard=measured_keyboard(self.packet(self.state['frames'][-1])['source']['keyboard']),originalId=current['id'],journalRetained=True)


def run_chat_draft(owner):
    need(isinstance(owner,PicoLifecycleChatDraft))
    with owner.lock.held():
        owner.load()
        if owner.state is None:owner.prepare()
        if owner.state['phase']=='prepared':owner.open_chat()
        elif owner.state['phase']=='opening':owner.reconcile()
        if owner.state['phase']=='opened':owner.focus_chat()
        elif owner.state['phase']=='focusing':owner.reconcile()
        if owner.state['phase']=='focused':owner.type_chat()
        elif owner.state['phase']=='typing':owner.reconcile()
        need(owner.state['phase']=='typed');return owner.observe()
