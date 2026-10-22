"""Normal fixture peer Send joined to two independent original receive reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import math
import uuid

from adapters.chat_journey.samples import ChatSamples,compose
from adapters.chat_peer_input import ChatPeerInput
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_chat_view import measured_keyboard
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import same
from feature_journeys.fixtures import context

VERSION = 2


class ChatPeerSend:
    """Own one actual peer and independent primary/actor reception sources.

    Input consumption and actual reception remain distinct durable phases.
    Receipt loss or source failure cannot trigger another Send.
    """
    def __init__(self, input_owner, primary, actor, store, *, monotonic=time.monotonic, sleep=time.sleep):
        need(isinstance(input_owner, ChatPeerInput) and isinstance(primary, ChatSamples)
            and isinstance(actor, ChatSamples) and primary is not actor
            and primary.role == 'primary' and actor.role == 'actor'
            and primary.run == actor.run == input_owner.run
            and primary.binding == actor.binding and primary.peer_binding == actor.peer_binding == input_owner.files.binding
            and primary.store.path != actor.store.path and store.path not in
                (primary.store.path, actor.store.path, input_owner.store.path, input_owner.files.store.path)
            and callable(monotonic) and callable(sleep)
            and all(first is second for first,second in zip(primary.locks,actor.locks)))
        self.input, self.roles, self.store = input_owner, (primary, actor), store
        self.monotonic, self.sleep = monotonic, sleep; self.previous = store.read()
        if self.previous is not None:
            exact(self.previous,{'chatPeerSendVersion','runId','binding','peerBinding','inputJournal','attempts'})
            need(type(self.previous['chatPeerSendVersion']) is int and self.previous['chatPeerSendVersion']==VERSION
                and self.previous['runId']==input_owner.run and same(self.previous['binding'],primary.binding)
                and same(self.previous['peerBinding'],input_owner.files.binding) and self.previous['inputJournal']==input_owner.store.path.name)
            attempts=self.previous['attempts'];need(type(attempts) is list and 0<len(attempts)<=4)
            used=set();indices=set();last_index=-1;previous_refs=None
            for attempt in attempts:
                exact(attempt,{'channel','textKey','phase','before','after','inputIndex'})
                pair=(attempt['channel'],attempt['textKey'])
                need(pair[0] in ('local','domain') and pair[1] in ('reply','hidden') and pair not in used and attempt['phase']=='received')
                used.add(pair);index=attempt['inputIndex'];need(integer(index,0,len(input_owner.previous['intents'])-1) and index not in indices and index>last_index);indices.add(index);last_index=index
                original=input_owner.previous['intents'][index];command=original['command']
                need(original['phase']=='consumed' and command['operation']=='send' and command['runId']==input_owner.run
                    and command['channel']==pair[0] and command['textKey']==pair[1])
                before,after=self.sources(attempt['before']),self.sources(attempt['after'])
                need(all(old['index']<new['index'] for old,new in zip(attempt['before'],attempt['after'])))
                if previous_refs is not None:need(all(old['index']<new['index'] for old,new in zip(previous_refs,attempt['before'])))
                previous_refs=attempt['after']
                need(all(self.delivery(old,new,*pair) for old,new in zip(before,after)))
            need(same(input_owner.store.read(),input_owner.disk));input_owner.files._check_source()

    def sources(self,refs):
        need(type(refs) is list and len(refs)==2);frames=[]
        for role,reference in zip(self.roles,refs):
            exact(reference,{'index','ticket','queries'});need(integer(reference['index'],0,len(role.frames)-1))
            frame=role.frames[reference['index']]
            need(frame['peer']['instance']==self.input.files.source['instance'] and frame['peer']['processId']==self.input.files.pid)
            need(reference['ticket']==frame['ticket'] and reference['queries']==[frame[key].get('commandId',frame[key].get('requestId')) for key in ('primary','peer','view','lifecycle')]
                and 'state' in compose(role.run,frame,role.primary.pid,role.peer.pid,vr=role.vr))
            frames.append(frame)
        return frames

    def delivery(self,before,current,channel,text_key):
        p,q=current['primary']['source'],current['peer']['source'];old=before['primary']['source']
        need(p['mixerPresent'] and q['mixerPresent'] and p['mixerSha256']==old['mixerSha256']
            and current['lifecycle']['lifecycle']==before['lifecycle']['lifecycle'])
        old_view,new_view=(frame['view']['source'] for frame in (before,current))
        need(all(new_view[key]==old_view[key] for key in ('editorFocused','editorHasDraft'))
            and measured_keyboard(new_view['keyboard'])==measured_keyboard(old_view['keyboard'])
            and new_view['ui']['present']==old_view['ui']['present'])
        if old_view['ui']['present']:need(all(new_view['ui'][key]==old_view['ui'][key] for key in ('channel','draft','keyboardRequested')))
        need([row for row in q['events'] if row['senderSha256']==p['selfSha256']]
            ==[row for row in before['peer']['source']['events'] if row['senderSha256']==old['selfSha256']])
        delta=p['events'][len(old['events']):];need(len(delta)<=1)
        stored,previous=(frame['view']['source']['storage']['events'] for frame in (current,before))
        need(stored[:len(previous)]==previous and len(stored)<=len(previous)+1)
        if not delta:need(stored==previous);return False
        event=delta[0]
        need(event['senderSha256']==q['selfSha256'] and not event['localOnly'] and event['channel']==channel
            and event['text']==context(self.input.run)[text_key] and event['capturedEpochMs']>=before['primary']['capturedEpochMs'])
        if len(stored)==len(previous):return False
        need(stored[-1]['channel']==channel and stored[-1]['text']==event['text']);return True

    def fresh_current(self,started):
        self.input.files._check_source()
        for role in self.roles:
            for reader in (role.primary,role.peer,role.view,role.lifecycle):need(reader.guard() is not False)
        clocks=[];previous=started
        for role in self.roles:
            frame=role.frames[-1]
            for reader,oldest in ((role.primary,min(frame[key]['capturedEpochMs'] for key in ('primary','view','lifecycle'))),(role.peer,frame['peer']['capturedEpochMs'])):
                measured=self.monotonic();need(number(measured,previous,started+1.5));previous=measured
                epoch=reader.clock_ms();fresh(oldest,epoch);clocks.append((measured,epoch,oldest))
        finished=self.monotonic();need(number(finished,previous,started+1.5)
            and all(epoch-oldest+math.ceil((finished-measured)*1000)<=1500 for measured,epoch,oldest in clocks))

    def write(self, value):
        need(same(self.store.read(),self.previous))
        self.store.write(value, self.previous); need(same(self.store.read(),value))
        self.previous = deepcopy(value)

    def pair(self, after_epoch):
        before = self.monotonic(); need(number(before, 0, 1e15))
        observed = [role.read(uuid.uuid4().hex, after_epoch) for role in self.roles]
        after = self.monotonic(); need(number(after, before, before + 1.5))
        self.input.files._check_source()
        for role in self.roles:
            peer = role.frames[-1]['peer']
            need(peer['instance'] == self.input.files.source['instance'] and peer['processId'] == self.input.files.pid)
        need(observed[0]['state'] == observed[1]['state'])
        self.fresh_current(before);self.fresh_started=before
        return observed

    def references(self):
        return [dict(index=len(role.frames)-1, ticket=role.frames[-1]['ticket'],
            queries=[role.frames[-1][key].get('commandId', role.frames[-1][key].get('requestId'))
                for key in ('primary', 'peer', 'view', 'lifecycle')]) for role in self.roles]

    def send(self, channel, text_key, after_epoch):
        try:
            need(channel in ('local', 'domain') and text_key in ('reply', 'hidden') and integer(after_epoch, 1))
            need(self.previous is None or self.previous['attempts'][-1]['phase'] == 'received')
            attempts = [] if self.previous is None else self.previous['attempts']
            need(not any(row['channel'] == channel and row['textKey'] == text_key for row in attempts))
            attempt = dict(channel=channel, textKey=text_key, phase='sampling', before=None, after=None,inputIndex=None)
            base = dict(chatPeerSendVersion=VERSION, runId=self.input.run, binding=self.roles[0].binding,
                peerBinding=self.input.files.binding, inputJournal=self.input.store.path.name, attempts=attempts+[attempt])
            self.write(base)
            before = self.pair(after_epoch)
            starts = [deepcopy(role.frames[-1]) for role in self.roles]
            for role in self.roles:
                source = role.frames[-1]['primary']['source']
                need(source['mixerPresent'] and role.frames[-1]['peer']['source']['mixerPresent'])
            attempt.update(phase='issuing', before=self.references(),inputIndex=len(self.input.previous['intents']))
            self.write({**base, 'attempts': attempts+[deepcopy(attempt)]})
            self.input.issue('send', channel=channel, textKey=text_key)
            attempt['phase'] = 'observing'; self.write({**base, 'attempts': attempts+[deepcopy(attempt)]})
            started = previous = self.monotonic(); need(number(started, 0, 1e15))
            for _index in range(202):
                observed = self.pair(after_epoch); delivered = []
                for role, initial in zip(self.roles, starts):
                    delivered.append(self.delivery(initial,role.frames[-1],channel,text_key))
                now = self.monotonic(); need(number(now, previous, started+20)); previous = now
                if all(delivered):
                    attempt.update(phase='received', after=self.references())
                    self.write({**base, 'attempts': attempts+[deepcopy(attempt)]})
                    value=deepcopy(observed);self.fresh_current(self.fresh_started);return value
                self.sleep(.1)
            need(False)
        except Exception:
            raise NativeUIError('Chat peer Send lacks independent reception; original intent remains without replay') from None
