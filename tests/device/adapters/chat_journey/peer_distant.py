"""Actual held peer distance, rejected Local Send, exact return and input quiet."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.chat_journey.peer_send import ChatPeerSend
from adapters.native_chat_peer_position import NativeChatPeerPosition
from adapters.native_feature_observation import fresh,integer, need, number
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack
from feature_journeys.fixtures import context

VERSION = 1


def distance(a,b): return math.sqrt(sum((a[key]-b[key])**2 for key in ('x','y','z')))


class ChatPeerDistant:
    """Durably retain every original source and uncertain input boundary.

    Restore first holds its exact saved original point for independent reads;
    release resumes the original motion. Fresh passive native actor inspection
    remains available after the script has stopped polling its input callback.
    """
    def __init__(self,sender,positions,store,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(sender,ChatPeerSend) and type(positions) is tuple and len(positions)==2
            and all(isinstance(source,NativeChatPeerPosition) for source in positions)
            and positions[0] is not positions[1] and all(source.pid==sender.roles[0].primary.pid for source in positions)
            and store.path not in (sender.store.path,sender.input.store.path,*[role.store.path for role in sender.roles])
            and callable(monotonic) and callable(sleep) and store.read() is None)
        self.sender,self.positions,self.store=sender,positions,store
        self.monotonic,self.sleep=monotonic,sleep;self.previous=None;self.frames=[]

    def write(self,phase,**values):
        need(self.store.read()==self.previous)
        base=self.previous or dict(chatPeerDistantVersion=VERSION,runId=self.sender.input.run,
            binding=self.sender.roles[0].binding,peerBinding=self.sender.input.files.binding,
            original=None,hold=None,transcript=pack([]))
        value={**base,**values,'phase':phase,'transcript':pack(self.frames)}
        self.store.write(value,self.previous);need(self.store.read()==value);self.previous=deepcopy(value)

    def measure(self,after_epoch):
        self.write('reading');started=self.monotonic();need(number(started,0,1e15))
        observations=self.sender.pair(after_epoch);points=[];avatars=[]
        for role,source in zip(self.sender.roles,self.positions):
            frame=role.frames[-1];p,q=frame['primary']['source'],frame['peer']['source']
            with role.locks[0].held():point=source.read(role.run,p['selfSha256'],q['selfSha256'])
            with role.locks[1].held():avatar=self.sender.input.issue('inspect')
            need(avatar['peerInputVersion']==3 and avatar['avatarSha256']==q['selfSha256']
                and point['capturedEpochMs']>=after_epoch)
            points.append(point);avatars.append(avatar)
        finished=self.monotonic();need(number(finished,started,started+1.5))
        frame=dict(refs=self.sender.references(),positions=points,avatars=avatars)
        self.frames.append(frame);self.write('measured')
        final_started=self.monotonic();need(number(final_started,finished,started+1.5))
        primary_epoch=self.sender.roles[0].primary.clock_ms();peer_epoch=self.sender.input.files.clock_ms()
        ages=[]
        for role,point,avatar in zip(self.sender.roles,points,avatars):
            for key in ('primary','view','lifecycle'):
                captured=role.frames[-1][key]['capturedEpochMs'];fresh(captured,primary_epoch);ages.append(primary_epoch-captured)
            for captured,epoch in ((role.frames[-1]['peer']['capturedEpochMs'],peer_epoch),
                    (point['capturedEpochMs'],primary_epoch),(avatar['capturedEpochMs'],peer_epoch)):
                fresh(captured,epoch);ages.append(epoch-captured)
        self.sender.input.files._check_source()
        need(all(source.guard() is not False for source in self.positions))
        complete=self.monotonic();need(number(complete,final_started,started+1.5)
            and max(ages)+math.ceil((complete-final_started)*1000)<=1500)
        return observations,frame

    def wait_for(self,after_epoch,predicate):
        started=previous=self.monotonic();need(number(started,0,1e15))
        for _index in range(202):
            sample_started=self.monotonic();need(number(sample_started,previous,started+20) and sample_started-previous<=1.5)
            observed,frame=self.measure(after_epoch)
            if predicate(observed,frame):return observed,frame
            now=self.monotonic();need(number(now,previous,started+20));previous=now;self.sleep(.1)
        need(False)

    @staticmethod
    def distant(frame):
        return all(distance(point['source']['selfPosition'],point['source']['peerPosition'])>=30
            and distance(point['source']['selfPosition'],avatar['avatarPosition'])>=30
            and distance(point['source']['peerPosition'],avatar['avatarPosition'])<=.05
            for point,avatar in zip(frame['positions'],frame['avatars']))

    def quiet(self,after_epoch,state,predicate,*,motion=False):
        started=previous=self.monotonic();need(number(started,0,1e15))
        first=None;last=None;polls=None;moved=False
        for _index in range(202):
            sample_started=self.monotonic();need(number(sample_started,previous,started+20) and sample_started-previous<=1.5)
            observed,frame=self.measure(after_epoch)
            need(all(row['state']==state for row in observed) and predicate(observed,frame))
            epochs=[value['capturedEpochMs'] for values in (frame['positions'],frame['avatars']) for value in values]
            if first is None:
                first=deepcopy(frame);first_epochs=epochs;quiet_started=self.monotonic()
                polls=[value['scriptPolls'] for value in frame['avatars']]
            else:
                need(all(now>before for now,before in zip(epochs,last)))
                if motion:
                    need([value['scriptPolls'] for value in frame['avatars']]==polls
                        and all(value['releaseConsumed'] for value in frame['avatars']))
                    moved|=all(distance(value['avatarPosition'],initial['avatarPosition'])>.05
                        and distance(point['source']['peerPosition'],old['source']['peerPosition'])>.05
                        for value,initial,point,old in zip(frame['avatars'],first['avatars'],frame['positions'],first['positions']))
            last=epochs
            now=self.monotonic();need(number(now,previous,started+20));previous=now
            if now-quiet_started>=3 and all(end-begin>=3000 for end,begin in zip(epochs,first_epochs)):
                need(not motion or moved);return frame
            self.sleep(.1)
        need(False)

    def run(self,after_epoch):
        hold_attempted=restored=released=False;failure=False
        try:
            need(integer(after_epoch,1) and self.previous is None)
            self.write('sampling')
            before,baseline=self.measure(after_epoch);state=deepcopy(before[0]['state'])
            point=baseline['positions'][0]['source']['selfPosition']
            target=dict(x=point['x']+40,y=point['y'],z=point['z'])
            self.write('holding');hold_attempted=True
            receipt=self.sender.input.issue('hold',position=target)
            need(receipt['peerInputVersion']==3 and receipt['avatarSha256']==baseline['avatars'][0]['avatarSha256'])
            self.write('holding',original=receipt['avatarPosition'],hold=receipt)
            self.wait_for(after_epoch,lambda _observed,frame:self.distant(frame))
            starts=[deepcopy(role.frames[-1]['primary']['source']) for role in self.sender.roles]
            self.write('sending')
            actual_send=self.sender.input.issue('send',channel='local',textKey='hidden')
            need(actual_send['peerInputVersion']==3 and all(distance(point['source']['selfPosition'],actual_send['avatarPosition'])>=30
                for point in self.frames[-1]['positions']))
            def rejected(observed,frame):
                if not self.distant(frame):return False
                seen=[]
                for role,initial,result in zip(self.sender.roles,starts,observed):
                    events=role.frames[-1]['primary']['source']['events'][len(initial['events']):]
                    need(len(events)<=1 and result['state']==state)
                    if events:
                        event=events[0]
                        need(event['senderSha256']==role.frames[-1]['peer']['source']['selfSha256']
                            and not event['localOnly'] and event['channel']=='local'
                            and event['text']==context(role.run)['hidden'])
                    seen.append(bool(events))
                return all(seen)
            self.wait_for(after_epoch,rejected);self.write('rejecting')
            self.quiet(after_epoch,state,rejected)
            self.write('restoring');restored=True;self.sender.input.issue('restore')
            def returned(_observed,frame):
                original=self.previous['original']
                return all(avatar['avatarPosition']==original and distance(point['source']['peerPosition'],original)<=.05
                    for point,avatar in zip(frame['positions'],frame['avatars']))
            self.wait_for(after_epoch,returned)
            self.write('releasing');released=True;self.sender.input.issue('release')
            def original_motion(_observed,frame):
                original=self.previous['original']
                return all(avatar['releaseConsumed'] and abs(avatar['avatarPosition']['y']-original['y'])<=.001
                    and abs(avatar['avatarPosition']['z']-original['z'])<=.001 and distance(avatar['avatarPosition'],original)<=1.51
                    and distance(point['source']['peerPosition'],avatar['avatarPosition'])<=.2
                    for point,avatar in zip(frame['positions'],frame['avatars']))
            self.quiet(after_epoch,state,original_motion,motion=True)
            self.write('complete');return deepcopy(self.previous)
        except Exception:
            failure=True
            raise NativeUIError('Chat distant peer flow is unresolved; original sources and input ownership are retained') from None
        finally:
            if failure and hold_attempted:
                # Independent proof failure cannot strand an owned distant
                # fixture indefinitely. Attempt original restore/release once;
                # neither ACK retires any source or uncertain-input journal.
                for operation,attempted in (('restore',restored),('release',released)):
                    if attempted:continue
                    try:
                        self.write('failed-'+operation);self.sender.input.issue(operation)
                    except Exception:pass
