"""Normal Chat inputs joined to fresh original local/storage/remote observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import math
import uuid
from adapters.chat_journey.samples import ChatSamples,compose,transition_ready
from adapters.chat_journey.erase_restore import references
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI
from adapters.token_create_ui import nonce
from adapters.script_journey.history import pack,unpack
from adapters.native_chat_view import measured_keyboard
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context

VERSION=1
VERBS=('open','type','select-channel','send','close')


def arguments(verb,inputs,run):
    need(verb in VERBS)
    if verb=='type':exact(inputs,{'text'});need(inputs['text'] in (context(run)['unicode'],context(run)['retry']))
    elif verb=='select-channel':exact(inputs,{'channel'});need(inputs['channel'] in ('local','domain'))
    else:exact(inputs,set())


class ChatNormalInput:
    """Never repeat an input attempt, including after process reconstruction.

    Source frames remain owned by the two original independent role journals.
    This owner stores only original source references and actual input intents.
    """
    def __init__(self,roles,controls,store,*,enter=False,monotonic=time.monotonic,sleep=time.sleep):
        need(type(roles) is tuple and len(roles)==2 and all(isinstance(role,ChatSamples) for role in roles)
            and roles[0] is not roles[1] and roles[0].role=='primary' and roles[1].role=='actor'
            and roles[0].run==roles[1].run and roles[0].binding==roles[1].binding
            and roles[0].peer_binding==roles[1].peer_binding
            and len({role.store.path for role in roles}|{store.path})==3
            and type(enter) is bool and all(callable(callback) for callback in (controls,monotonic,sleep)))
        self.roles,self.store,self.run,self.enter=roles,store,roles[0].run,enter
        self.monotonic,self.sleep=monotonic,sleep;self.last_clock=None;self.deadline=None
        self.previous=store.read();self.base=dict(chatNormalInputVersion=VERSION,runId=self.run,binding=roles[0].binding,
            peerBinding=roles[0].peer_binding,transcripts=[role.store.path.name for role in roles],enter=enter,attempts=[])
        if self.previous is not None:
            exact(self.previous,set(self.base));need(all(self.previous[key]==self.base[key] for key in set(self.base)-{'attempts'}))
            attempts=unpack(self.previous['attempts']);need(0<len(attempts)<=32)
            tickets=set()
            for attempt in attempts:
                exact(attempt,{'ticket','verb','inputs','afterEpochMs','phase','before','after','inputIntents','quiet'})
                identifier(attempt['ticket']);need(attempt['ticket'] not in tickets);tickets.add(attempt['ticket'])
                arguments(attempt['verb'],attempt['inputs'],self.run)
                need(integer(attempt['afterEpochMs'],1) and attempt['phase'] in ('sampling','issuing','observing','quiet','observed')
                    and type(attempt['inputIntents']) is list and len(attempt['inputIntents'])<=8
                    and type(attempt['quiet']) is list and len(attempt['quiet'])<=64)
                for key in ('before','after'):
                    if attempt[key] is not None:self.sources(attempt[key])
                for value in attempt['inputIntents']:self.input_shape(value,attempt['verb'])
                for row in attempt['quiet']:
                    exact(row,{'roles','hostMonotonic'});self.sources(row['roles']);need(number(row['hostMonotonic'],0,1e15))
                if attempt['phase']=='observed':
                    need(attempt['before'] is not None and attempt['after'] is not None)
                    self.check_inputs(attempt)
                    need(self.reached(attempt,self.sources(attempt['before']),self.sources(attempt['after'])))
                    self.check_quiet(attempt)
            self.base={**deepcopy(self.previous),'attempts':attempts}
        self.ui=controls(self.intent);need(isinstance(self.ui,TokenChatUI) and self.ui.run==self.run)
        # This source only captures actual controls; no input occurs here.
        # Old controls are requalified against the candidate and original bridge
        # inside the already-bound input route before a later operation.

    def now(self):
        value=self.monotonic();need(number(value,0,1e15) and (self.last_clock is None or value>=self.last_clock))
        if self.deadline is not None:need(value<=self.deadline)
        self.last_clock=value;return value

    def sources(self,refs):
        need(type(refs) is list and len(refs)==2)
        frames=[]
        for role,reference in zip(self.roles,refs):
            exact(reference,{'index','ticket','queries','epochs'})
            need(integer(reference['index'],0,len(role.frames)-1));frame=role.frames[reference['index']]
            need(reference['ticket']==frame['ticket']
                and reference['queries']==[frame[key].get('commandId',frame[key].get('requestId')) for key in ('primary','peer','view','lifecycle')]
                and reference['epochs']==[frame[key]['capturedEpochMs'] for key in ('primary','peer','view','lifecycle')])
            frames.append(frame)
        return frames

    def write(self,attempt):
        need(self.store.read()==self.previous)
        attempts=deepcopy(self.base['attempts'])
        if attempts and attempts[-1]['ticket']==attempt['ticket']:attempts[-1]=deepcopy(attempt)
        else:need(len(attempts)<32);attempts.append(deepcopy(attempt))
        value={**self.base,'attempts':attempts};disk={**value,'attempts':pack(attempts)}
        self.store.write(disk,self.previous);need(self.store.read()==disk)
        self.previous=deepcopy(disk);self.base=deepcopy(value)

    @staticmethod
    def input_shape(value,verb):
        exact(value,{'controlId','action','instance','generation','sequence'})
        allowed={'open':{'tablet.open','tablet.home','chat.entry'},'type':{'chat.input'},
            'select-channel':{'chat.local','chat.domain'},'send':{'chat.input','chat.send'},'close':{'chat.close'}}[verb]
        need(value['controlId'] in allowed and value['action'] in ('activate','replace','submit','controller-open')
            and nonce(value['instance']) and (integer(value['generation']) or nonce(value['generation'])) and integer(value['sequence']))
        if value['action']=='controller-open':need(verb=='open' and value['controlId']=='tablet.open')
        elif value['controlId']=='tablet.open':need(False)
        elif value['action']=='replace':need(verb=='type' and value['controlId']=='chat.input')
        elif value['action']=='submit':need(verb=='send' and value['controlId']=='chat.input')

    def check_inputs(self,attempt):
        inputs=attempt['inputIntents'];verb=attempt['verb']
        pairs=[(row['controlId'],row['action']) for row in inputs]
        if verb=='open':
            need(pairs in ([('chat.entry','activate')],[('tablet.home','activate'),('chat.entry','activate')],
                [('tablet.open','controller-open'),('chat.entry','activate')],
                [('tablet.open','controller-open'),('tablet.home','activate'),('chat.entry','activate')]))
        elif verb=='type':need(pairs==[('chat.input','activate'),('chat.input','replace')])
        elif verb=='select-channel':need(pairs in ([],[('chat.'+attempt['inputs']['channel'],'activate')]))
        elif verb=='send':need(pairs==[('chat.input','submit') if self.enter else ('chat.send','activate')])
        else:need(pairs==[('chat.close','activate')])

    def check_quiet(self,attempt):
        before=self.sources(attempt['before']);required=attempt['verb']=='close' or (attempt['verb']=='send' and not before[0]['primary']['source']['mixerPresent'])
        rows=attempt['quiet']
        if not required:need(rows==[]);return
        need(len(rows)>=2 and rows[-1]['roles']==attempt['after'])
        first=rows[0];previous=None;state=None;events=None
        for row in rows:
            frames=self.sources(row['roles']);need(self.reached(attempt,before,frames))
            current=[compose(self.run,frame,role.primary.pid,role.peer.pid,vr=role.vr)['state'] for role,frame in zip(self.roles,frames)]
            actual_events=[[frame[key]['source']['events'] for key in ('primary','peer')] for frame in frames]
            epochs=[epoch for ref in row['roles'] for epoch in ref['epochs']]
            if previous is None:state=current;events=actual_events
            else:
                old_epochs=[epoch for ref in previous['roles'] for epoch in ref['epochs']]
                need(0<row['hostMonotonic']-previous['hostMonotonic']<=1.5
                    and all(0<end-begin<=1500 for begin,end in zip(old_epochs,epochs)))
            need(current==state and actual_events==events);previous=row
        first_epochs=[epoch for ref in first['roles'] for epoch in ref['epochs']]
        need(rows[-1]['hostMonotonic']-first['hostMonotonic']>=3
            and all(end-begin>=3000 for begin,end in zip(first_epochs,epochs)))

    def intent(self,value):
        attempt=deepcopy(self.base['attempts'][-1]);need(attempt['phase']=='issuing' and len(attempt['inputIntents'])<8)
        self.input_shape(value,attempt['verb']);need(value['instance']==self.ui.instance)
        if not self.roles[0].component_only:need(value['instance']==self.roles[0].binding['sessionId'])
        attempt['inputIntents'].append(deepcopy(value));self.write(attempt);self.now()

    def pair(self,after_epoch,*,transition=False):
        started=self.now();observed=[(role.read_transition if transition else role.read)(uuid.uuid4().hex,after_epoch) for role in self.roles]
        for role in self.roles:
            for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
        for role in self.roles:
            frame=role.frames[-1]
            fresh(min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle')),role.primary.clock_ms())
            fresh(frame['peer']['capturedEpochMs'],role.peer.clock_ms())
        need(self.now()-started<=1.5)
        if not transition:need(observed[0]['state']==observed[1]['state'])
        self.fresh_current(started);self.fresh_started=started
        return observed

    def fresh_current(self,started):
        for role in self.roles:
            for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
        clocks=[]
        for role in self.roles:
            frame=role.frames[-1]
            for reader,oldest in ((role.primary,min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))),
                                  (role.peer,frame['peer']['capturedEpochMs'])):
                measured=self.now();epoch=reader.clock_ms();fresh(oldest,epoch);clocks.append((measured,epoch,oldest))
        finished=self.now();need(finished-started<=1.5 and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))

    def stable(self,before,after):
        for old,new in zip(before,after):
            need(old['lifecycle']['lifecycle']==new['lifecycle']['lifecycle'])
            for key in ('primary','peer'):
                a,b=old[key]['source'],new[key]['source']
                need(a['mixerPresent']==b['mixerPresent'] and a['mixerSha256']==b['mixerSha256'])

    def reached(self,attempt,before,current=None):
        live=current is None;current=[role.frames[-1] for role in self.roles] if live else current;self.stable(before,current)
        verb=attempt['verb'];send=verb=='send';expected=attempt['inputs'].get('text')
        ready=[]
        for role,old,new in zip(self.roles,before,current):
            p,q=new['primary']['source'],new['peer']['source'];oldp,oldq=old['primary']['source'],old['peer']['source']
            deltas=[p['events'][len(oldp['events']):],q['events'][len(oldq['events']):]]
            storage,previous=new['view']['source']['storage']['events'],old['view']['source']['storage']['events']
            if send:
                ui=old['view']['source']['ui'];channel,draft=ui['channel'],ui['draft']
                need(channel in ('local','domain') and draft in (context(self.run)['unicode'],context(self.run)['retry']))
                need(len(deltas[0])<=1 and len(deltas[1])<=(1 if p['mixerPresent'] else 0) and len(storage)<=len(previous)+1)
                if deltas[0]:
                    event=deltas[0][0];need(event['senderSha256']==p['selfSha256'] and event['channel']==channel
                        and event['text']==draft and event['localOnly']==(not p['mixerPresent'])
                        and event['capturedEpochMs']>=old['primary']['capturedEpochMs'])
                if deltas[1]:
                    event=deltas[1][0];need(event['senderSha256']==p['selfSha256'] and event['channel']==channel
                        and event['text']==draft and event['localOnly'] is False
                        and event['capturedEpochMs']>=old['peer']['capturedEpochMs'])
                if len(storage)>len(previous):need(storage[-1]['channel']==channel and storage[-1]['text']==draft)
                ready.append(bool(deltas[0]) and len(storage)==len(previous)+1 and (bool(deltas[1]) if p['mixerPresent'] else True)
                    and new['view']['source']['ui']['present'] and new['view']['source']['ui']['channel']==channel
                    and new['view']['source']['ui']['draft']=='' and not new['view']['source']['editorHasDraft'])
            else:
                need(not any(deltas) and storage==previous)
                ui=new['view']['source']['ui'];source=new['view']['source']
                if verb=='open':ready.append(ui['present'] and ui['channel']=='local' and not ui['draft'] and not source['editorFocused']
                    and not measured_keyboard(source['keyboard']))
                elif verb=='type':ready.append(ui['present'] and ui['draft']==expected and source['editorFocused'] and measured_keyboard(source['keyboard']))
                elif verb=='select-channel':ready.append(ui['present'] and ui['channel']==attempt['inputs']['channel'] and ui['draft']==old['view']['source']['ui']['draft'])
                else:ready.append(not ui['present'] and not source['editorFocused'] and not source['editorHasDraft'])
        return all(ready) and (all(transition_ready(role) if role.frames[-1].get('transition') else True for role in self.roles)
            if live else all(not frame.get('transition') and not frame.get('settings') for frame in current))

    def quiet(self,attempt):
        first=previous=None;started=self.now();state=None;events=None;previous_host=None
        for _ in range(42):
            observed=self.pair(attempt['afterEpochMs']);refs=references(self.roles);now=self.now()
            epochs=[epoch for ref in refs for epoch in ref['epochs']]
            actual_events=[[deepcopy(role.frames[-1][key]['source']['events']) for key in ('primary','peer')] for role in self.roles]
            if first is None:first=epochs;started=now;state=deepcopy(observed[0]['state']);events=actual_events
            else:need(all(0<end-begin<=1500 for begin,end in zip(previous,epochs)) and now-previous_host<=1.5
                and all(value['state']==state for value in observed) and actual_events==events)
            previous=epochs;previous_host=now;attempt['quiet'].append(dict(roles=refs,hostMonotonic=now));self.write(attempt)
            if now-started>=3 and all(end-begin>=3000 for begin,end in zip(first,epochs)):return observed
            self.sleep(.1)
        need(False)

    def perform(self,ticket,verb,inputs,after_epoch):
        try:
            identifier(ticket);arguments(verb,inputs,self.run);need(integer(after_epoch,1))
            need(not self.base['attempts'] or self.base['attempts'][-1]['phase']=='observed')
            need(all(row['ticket']!=ticket for row in self.base['attempts']))
            self.deadline=None;self.deadline=self.now()+20
            attempt=dict(ticket=ticket,verb=verb,inputs=deepcopy(inputs),afterEpochMs=after_epoch,phase='sampling',
                before=None,after=None,inputIntents=[],quiet=[]);self.write(attempt)
            self.pair(after_epoch);attempt['before']=references(self.roles);before=self.sources(attempt['before'])
            state=compose(self.run,before[0],self.roles[0].primary.pid,self.roles[0].peer.pid,vr=self.roles[0].vr)['state']
            if verb=='open':need(not state['open'])
            else:need(state['open'])
            if verb=='send':need(state['draft'] in (context(self.run)['unicode'],context(self.run)['retry']))
            controls=self.ui.capture();need(controls['scope']['processId']==self.roles[0].primary.pid)
            old_instances={value['instance'] for old in self.base['attempts'] for value in old['inputIntents']}
            need(not old_instances or old_instances=={controls['scope']['instance']})
            if not self.roles[0].component_only:need(controls['scope']['instance']==self.roles[0].binding['sessionId'])
            attempt['phase']='issuing';self.write(attempt)
            if verb=='open':self.ui.open()
            elif verb=='type':self.ui.type(inputs['text'])
            elif verb=='select-channel':self.ui.select_channel(inputs['channel'])
            elif verb=='send':self.ui.send(enter=self.enter)
            else:self.ui.close()
            # Intent callbacks update the durable attempt during the operation.
            attempt=deepcopy(self.base['attempts'][-1]);attempt['phase']='observing';self.write(attempt)
            for _ in range(42):
                self.pair(after_epoch,transition=True)
                if self.reached(attempt,before):
                    observed=self.pair(after_epoch);need(self.reached(attempt,before))
                    break
                self.sleep(.5)
            else:need(False)
            if verb=='close' or verb=='send' and not before[0]['primary']['source']['mixerPresent']:
                attempt['phase']='quiet';self.write(attempt);observed=self.quiet(attempt)
            self.check_inputs(attempt);attempt['after']=references(self.roles);attempt['phase']='observed'
            self.check_quiet(attempt);self.write(attempt);result=deepcopy(observed)
            self.fresh_current(self.fresh_started)
            return result
        except Exception:
            raise NativeUIError('Normal Chat input lacks fresh original closure; no uncertain input is resent') from None
