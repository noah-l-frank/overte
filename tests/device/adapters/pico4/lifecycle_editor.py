"""Durable normal Create opening/focus/draft with independent original UI facts.

Partial editor composition. Immutable histories stay owned through every error;
no input is replayed, and no Qt retirement or whole-feature verdict is returned.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_source as ui
from adapters.pico4.lifecycle_back import PicoLifecycleBack,frame
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_create_ui import TokenCreateUI,scope,nonce
from adapters.token_lifecycle_ui import TokenLifecycleUI,ID,OBJECTS
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from openxr_input.controller_protocol import validate_envelope
from feature_journeys.fixtures import context as fixture

VERSION=1
PHASES=('prepared','tablet-issued','tablet-open','opening','opened','focusing','focused','typing','typed')


class PicoLifecycleEditor:
    def __init__(self,path,run,binding,source,session,route,field,source_lock):
        need(ui.nonce(run) and isinstance(source,ui.PicoLifecycleSource) and isinstance(session,PicoOpenXrAdapterSession)
            and isinstance(route,TokenCreateUI) and isinstance(field,TokenLifecycleUI)
            and isinstance(source_lock,ScriptSourceLock) and source.source_lock is source_lock and field.run==run)
        self.run,self.binding,self.source,self.session=run,deepcopy(context(binding)),source,session
        self.pid=source.pid;need(int(binding['processIdentity'].split(':')[0])==self.pid)
        self.route,self.field,self.lock=route,field,source_lock;self.store=PrivateFeatureState(path)
        need(self.store.path.name=='lifecycle-editor-owner.json' and self.lock.path==self.store.path.with_name('script-sources.lock'))
        self.disk=self.state=None;self.last_clock=None;self.acquisition=None
        self.route.intent=self.intent;self.field.intent=self.intent
        with self.lock.held():self.load()
    def now(self):
        need(self.source.guard() is not False);now=self.source.monotonic()
        need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock));self.last_clock=now;return now
    def packet(self,row):
        exact(row,{'raw','sha256'});need(frame(row['raw'])==row);value=decode(row['raw'])
        ui.validate(value,value,self.pid,value['capturedEpochMs']);need(value['runId']==self.run);return value
    def bound_scope(self,value):
        scope(value);need(value['instance']==self.binding['sessionId'] and value['processId']==self.pid);return value
    def input_meta(self,value):
        if 'createInputVersion' in value:
            exact(value,{'createInputVersion','action','controlId','controlToken','scope'})
            need(type(value['createInputVersion']) is int and value['createInputVersion']==1 and value['action']=='activate'
                and (value['controlId'] in ('tablet.home','create.entry','create.tab.0')
                    or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',value['controlId'])))
        else:
            exact(value,{'lifecycleControlInputVersion','action','controlId','controlToken','scope','objects'})
            need(type(value['lifecycleControlInputVersion']) is int and value['lifecycleControlInputVersion']==1
                and value['controlId']==ID and value['action'] in ('activate','replace'))
            exact(value['objects'],set(OBJECTS));need(all(nonce(value['objects'][key]) for key in OBJECTS))
        need(nonce(value['controlToken']));self.bound_scope(value['scope']);return value
    def consumed(self,before,after):
        self.bound_scope(before);self.bound_scope(after)
        need(all(before[key]==after[key] for key in ('instance','generation','processId'))
            and after['sequence']==before['sequence']+1 and after['elapsedMs']>=before['elapsedMs'])
    def validate(self,state):
        exact(state,{'phase','frames','tablet','inputs','originalId','fieldObjects'})
        need(state['phase'] in PHASES and type(state['frames']) is list and 1<=len(state['frames'])<=64
            and type(state['inputs']) is list and len(state['inputs'])<=48)
        previous=None;seen=set()
        for row in state['frames']:
            packet=self.packet(row);need(packet['commandId'] not in seen);seen.add(packet['commandId'])
            previous=ui.accept(previous,ui.summary(packet))
        first=self.packet(state['frames'][0]);need(not first['source']['tabletShown'] and ui.current_editor(first) is None
            and measured_keyboard(first['source']['keyboard']) is False)
        tablet=state['tablet']
        if state['phase']=='prepared':need(tablet is None)
        else:
            exact(tablet,{'envelope','neutral'});envelope=tablet['envelope']
            if envelope is None:need(state['phase']=='tablet-issued' and tablet['neutral'] is None)
            else:
                validate_envelope(envelope,self.session.profile);need(len(envelope['commands'])==1
                    and envelope['commands'][0]==dict(id='tablet-open-'+str(envelope['sequence']),operation='tablet.open',arguments=dict(holdMilliseconds=1000)))
                neutral=tablet['neutral']
                if state['phase']!='tablet-issued':need(neutral is not None)
                if neutral is not None:PicoLifecycleBack.neutral(neutral,envelope,first['capturedEpochMs'])
        for index,row in enumerate(state['inputs']):
            exact(row,{'phase','intent','consumed'});need(row['phase'] in ('opening','focusing','typing'))
            self.input_meta(row['intent'])
            if row['phase']=='opening':need('createInputVersion' in row['intent'])
            else:need('lifecycleControlInputVersion' in row['intent'] and row['intent']['action']==('activate' if row['phase']=='focusing' else 'replace'))
            if row['consumed'] is not None:self.consumed(row['intent']['scope'],row['consumed'])
            else:need(index==len(state['inputs'])-1 and state['phase'] in ('opening','focusing','typing'))
        for index,row in enumerate(state['inputs'][1:],1):
            prior=state['inputs'][index-1];need(prior['consumed'] is not None)
            a,b=prior['consumed'],row['intent']['scope']
            need(all(a[key]==b[key] for key in ('instance','generation','sequence','processId')) and b['elapsedMs']>=a['elapsedMs'])
        original=state['originalId'];objects=state['fieldObjects']
        if original is None:need(objects is None and state['phase'] in PHASES[:4])
        else:
            need(ui.nonce(original) and any(row['phase']=='opening' and row['intent']['controlId']=='create.entry' and row['consumed'] is not None for row in state['inputs']))
            if state['phase'] in ('focused','typing','typed'):need(any(row['phase']=='focusing' and row['consumed'] is not None for row in state['inputs']))
            if state['phase']=='typed':need(any(row['phase']=='typing' and row['consumed'] is not None for row in state['inputs']))
            exact(objects,set(OBJECTS));need(all(nonce(objects[key]) for key in OBJECTS))
            current=ui.current_editor(self.packet(state['frames'][-1]));need(current is not None and current['id']==original and current['kind']=='create')
            need(original not in {row['id'] for row in first['source']['editors']})
            if state['phase'] in ('focused','typing','typed'):
                need(current['focused'] and current['visible'] and measured_keyboard(self.packet(state['frames'][-1])['source']['keyboard']) is True)
            need(current['text']==(fixture(self.run)['unicode'] if state['phase']=='typed' else ''))
    def load(self):
        self.lock.assert_held();self.now();disk=self.store.read()
        if self.disk is not None:need(disk==self.disk)
        if disk is None:need(self.state is None);return
        exact(disk,{'lifecycleEditorOwnerVersion','runId','binding','payload'})
        need(type(disk['lifecycleEditorOwnerVersion']) is int and disk['lifecycleEditorOwnerVersion']==VERSION
            and disk['runId']==self.run and disk['binding']==self.binding)
        value=unpack(disk['payload']);need(len(value)==1);self.validate(value[0])
        expected=ui.summary(self.packet(value[0]['frames'][-1]))
        if self.source.previous is None:self.source.restore(expected)
        elif self.source.previous!=expected:ui.accept(expected,self.source.previous)
        self.disk,self.state=deepcopy(disk),deepcopy(value[0])
    def save(self,state):
        self.lock.assert_held();need(self.store.read()==self.disk);self.validate(state)
        disk=dict(lifecycleEditorOwnerVersion=VERSION,runId=self.run,binding=deepcopy(self.binding),payload=pack([state]))
        self.store.write(disk,self.disk);need(self.store.read()==disk);self.disk,self.state=deepcopy(disk),deepcopy(state)
    def capture(self):
        self.lock.assert_held();started=self.now();requested=self.source.clock_ms();value=self.source.capture(self.run)
        row=frame(self.source.last_raw);need(row['sha256']==self.source.last_sha256 and decode(row['raw'])==value)
        self.acquisition=(started,requested,value['capturedEpochMs']);return row,value
    def fresh(self):
        need(self.acquisition is not None);started,requested,captured=self.acquisition
        final=self.now();need(self.source.guard() is not False);epoch=self.source.clock_ms();completed=self.source.monotonic()
        need(integer(epoch,1) and number(completed,0,1e15) and completed>=final and completed-started<=1.5
            and -250<=epoch-captured and max(epoch-captured,requested-captured+(completed-started)*1000)<=1500)
        self.last_clock=completed
    def prepare(self):
        with self.lock.held():
            self.load();need(self.state is None);row,value=self.capture()
            need(not value['source']['tabletShown'] and ui.current_editor(value) is None and measured_keyboard(value['source']['keyboard']) is False)
            self.save(dict(phase='prepared',frames=[row],tablet=None,inputs=[],originalId=None,fieldObjects=None));self.fresh()
    def intent(self,value):
        # Called before the existing normal bridge's first possible mutation.
        self.lock.assert_held();need(self.state is not None and self.state['phase'] in ('opening','focusing','typing'))
        self.input_meta(value);state=deepcopy(self.state)
        if state['inputs'] and state['inputs'][-1]['consumed'] is None:
            self.consumed(state['inputs'][-1]['intent']['scope'],value['scope']);state['inputs'][-1]['consumed']=deepcopy(value['scope'])
        if state['phase']=='opening':need('createInputVersion' in value)
        else:
            need(value.get('objects')==state['fieldObjects'] and value['action']==('activate' if state['phase']=='focusing' else 'replace'))
        state['inputs'].append(dict(phase=state['phase'],intent=deepcopy(value),consumed=None));self.save(state)
    def finish_cursor(self,state):
        if not state['inputs'] or state['inputs'][-1]['consumed'] is not None:return
        reader=self.route if state['inputs'][-1]['phase']=='opening' else self.field
        current=reader.capture();self.consumed(state['inputs'][-1]['intent']['scope'],current['scope'])
        state['inputs'][-1]['consumed']=deepcopy(current['scope'])
    def tablet(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='prepared');row,value=self.capture()
            need(not value['source']['tabletShown'] and ui.current_editor(value) is None and measured_keyboard(value['source']['keyboard']) is False)
            state=deepcopy(self.state);state['frames'].append(row);state.update(phase='tablet-issued',tablet=dict(envelope=None,neutral=None));self.save(state);self.fresh()
            def intent(envelope):
                state=deepcopy(self.state);state['tablet']['envelope']=deepcopy(envelope);self.save(state)
                # Pure host freshness only: this callback holds the session lock.
                started,requested,captured=self.acquisition;now=self.source.monotonic()
                need(number(now,0,1e15) and now>=self.last_clock and requested-captured+(now-started)*1000<=1500)
            self.session.stage(self.binding['processIdentity'],'tablet.open',dict(holdMilliseconds=1000),intent=intent)
            return self.reconcile()
    def reconcile(self):
        try:
            with self.lock.held():
                self.load();need(self.state is not None);state=deepcopy(self.state);phase=state['phase']
                if phase=='tablet-issued':
                    need(state['tablet']['envelope'] is not None)
                    state['tablet']['neutral']=deepcopy(self.session.require_owned_neutral(self.binding['processIdentity'],state['tablet']['envelope']))
                    row,value=self.capture();need(value['source']['tabletShown'] and value['source']['onHomeScreen'] and ui.current_editor(value) is None
                        and measured_keyboard(value['source']['keyboard']) is False)
                    state['frames'].append(row);state['phase']='tablet-open'
                elif phase in ('opening','focusing','typing'):
                    self.finish_cursor(state);normal=self.field.capture();field=self.field.row(normal)
                    row,value=self.capture();current=ui.current_editor(value)
                    need(current is not None and current['kind']=='create' and value['source']['tabletShown'] and current['visible'])
                    if phase=='opening':
                        need(current['text']=='' and field['text']=='')
                        state.update(originalId=current['id'],fieldObjects={key:field[key] for key in OBJECTS},phase='opened')
                    else:
                        need(current['id']==state['originalId'] and all(field[key]==state['fieldObjects'][key] for key in OBJECTS)
                            and current['focused'] and field['focused'] and measured_keyboard(value['source']['keyboard']) is True)
                        expected=fixture(self.run)['unicode'] if phase=='typing' else ''
                        need(current['text']==field['text']==expected);state['phase']='typed' if phase=='typing' else 'focused'
                    state['frames'].append(row)
                else:need(False)
                self.save(state);result=self.report();self.fresh();return result
        except Exception:raise NativeUIError('Lifecycle editor effects unresolved; original inputs retained, none repeated') from None
    def open_create(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='tablet-open')
            state=deepcopy(self.state);state['phase']='opening';self.save(state)
            self.route.open_create();self.route.tab(0)
            return self.reconcile()
    def focus_create(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='opened')
            state=deepcopy(self.state);state['phase']='focusing';self.save(state);self.field.input('activate');return self.reconcile()
    def type_create(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase']=='focused')
            state=deepcopy(self.state);state['phase']='typing';self.save(state)
            self.field.input('replace',fixture(self.run)['unicode']);return self.reconcile()
    def observe(self):
        with self.lock.held():
            self.load();need(self.state is not None and self.state['phase'] in ('opened','focused','typed'))
            normal=self.field.row(self.field.capture());need(all(normal[key]==self.state['fieldObjects'][key] for key in OBJECTS))
            row,value=self.capture();current=ui.current_editor(value);need(current is not None and current['id']==self.state['originalId']
                and current['text']==normal['text'] and current['focused']==normal['focused'])
            state=deepcopy(self.state);state['frames'].append(row);self.save(state);result=self.report();self.fresh();return result
    def report(self):
        current=ui.current_editor(self.packet(self.state['frames'][-1]))
        if current is not None:need(current['kind']=='create' and current['id']==self.state['originalId'])
        return dict(editor='create' if current else 'none',text=current['text'] if current else '',generation=1 if current else 0,
            focused=bool(current and current['focused']),keyboard=measured_keyboard(self.packet(self.state['frames'][-1])['source']['keyboard']),
            originalId=self.state['originalId'],journalRetained=True)


def run_create_world_back(editor,joined):
    """Compose existing owners through first Create draft, blocked gesture and X.

    This is only the first shared journey segment. Existing journals decide
    recovery; no issued normal input, world gesture or X press is repeated.
    """
    from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
    need(isinstance(editor,PicoLifecycleEditor) and isinstance(joined,PicoLifecycleXJoin))
    world=joined.world
    need(editor.lock is world.lock and editor.run==world.run and editor.binding==world.binding and editor.pid==world.pid)
    def typed_before_world():
        need(editor.state is not None and editor.state['phase']=='typed')
        typed=next((editor.packet(row) for row in editor.state['frames']
            if (current:=ui.current_editor(editor.packet(row))) is not None
            and current['id']==editor.state['originalId'] and current['text']==fixture(editor.run)['unicode']),None)
        need(typed is not None)
        before=world.originals(world.state['frames'][world.state['attempts'][0]['before']])['ui']
        current=ui.current_editor(before);need(current is not None and current['id']==editor.state['originalId']
            and current['text']==fixture(editor.run)['unicode'])
        ui.accept(ui.summary(typed),ui.summary(before))
    with world.lock.held():
        world.load();editor.load();joined.load()
        if world.state is None:world.prepare()
        need(len(world.state['attempts'])<=1)
        if world.state['attempts']:typed_before_world()
        if joined.state is not None:
            need(editor.state is not None and editor.state['phase']=='typed' and joined.state['originalId']==editor.state['originalId'])
            result=joined.reconcile()
        else:
            if editor.state is None:need(not world.state['attempts']);editor.prepare()
            if editor.state['phase']=='prepared':editor.tablet()
            elif editor.state['phase']=='tablet-issued':editor.reconcile()
            if editor.state['phase']=='tablet-open':editor.open_create()
            elif editor.state['phase']=='opening':editor.reconcile()
            if editor.state['phase']=='opened':editor.focus_create()
            elif editor.state['phase']=='focusing':editor.reconcile()
            if editor.state['phase']=='focused':editor.type_create()
            elif editor.state['phase']=='typing':editor.reconcile()
            need(editor.state['phase']=='typed');editor.observe()
            if not world.state['attempts']:world.world_input(editor_id=editor.state['originalId'])
            else:
                if world.state['attempts'][0]['phase']!='quiet':world.reconcile()
            typed_before_world()
            if world.state['attempts'][0]['phase']!='quiet':world.release()
            result=joined.back_once()
        current=result['originals']['ui'];need(ui.current_editor(current) is None and current['source']['onHomeScreen']
            and measured_keyboard(current['source']['keyboard']) is False)
        # These values come from that original current UI/World observation;
        # the editor's typed snapshot remains historical, never current proof.
        result.update(editor='none',text='',generation=0,focused=False,keyboard=False,editorJournalRetained=True)
        return world.final_result(result)
