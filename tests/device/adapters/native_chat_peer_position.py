"""Original native local/remote Avatar positions selected by actual run hashes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import math
import time
import uuid
from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.normal_ui import NativeUIError

VERSION = 1
FILE = 'feature-chat-peer-position.json'


def command(value):
    exact(value, {'schemaVersion','commandId','runId','action','peerSha256'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-chat-peer-position'
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{32}',value[key]) for key in ('commandId','runId'))
        and type(value['peerSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['peerSha256']))
    return value


def position(value):
    exact(value, {'x','y','z'}); need(all(number(point,-100000,100000) for point in value.values())); return value


def validate(value, request, pid, epoch, self_sha):
    command(request)
    exact(value, {'chatPeerPositionVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['chatPeerPositionVersion']) is int and value['chatPeerPositionVersion']==VERSION
        and all(value[key]==request[key] for key in ('commandId','runId'))
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid
        and type(self_sha) is str and re.fullmatch('[0-9a-f]{64}',self_sha))
    fresh(value['capturedEpochMs'],epoch); source=value['source']
    exact(source, {'selfSha256','peerSha256','selfPosition','peerPosition'})
    need(source['selfSha256']==self_sha and source['peerSha256']==request['peerSha256'] and self_sha!=source['peerSha256'])
    position(source['selfPosition']);position(source['peerPosition']);return value


class NativeChatPeerPosition:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep
        self.run=self.instance=self.self_sha=self.peer_sha=None;self.sequence=self.captured=0

    def read(self,run,self_sha,peer_sha):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,runId=run,
                action='feature-chat-peer-position',peerSha256=peer_sha))
            need(self.run in (None,run) and self.self_sha in (None,self_sha) and self.peer_sha in (None,peer_sha)
                and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            issued=self.monotonic();need(number(issued,previous,1e15));previous=issued
            requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(31):
                need(self.guard() is not False);raw=self.original()
                if raw:
                    value=decode(raw);need(type(value) is dict)
                    if value.get('commandId')==request['commandId']:
                        epoch=self.clock_ms();need(integer(epoch,requested))
                        validate(value,request,self.pid,epoch,self_sha)
                        need(self.instance in (None,value['instance']) and value['sequence']>self.sequence
                            and value['capturedEpochMs']>=max(self.captured,requested) and self.guard() is not False)
                        freshness_started=self.monotonic();need(number(freshness_started,previous,started+1.5))
                        final_epoch=self.clock_ms();need(integer(final_epoch,epoch));fresh(value['capturedEpochMs'],final_epoch)
                        need(self.guard() is not False)
                        now=self.monotonic();need(number(now,freshness_started,started+1.5)
                            and max(final_epoch-value['capturedEpochMs']+math.ceil((now-freshness_started)*1000),
                                requested-value['capturedEpochMs']+math.ceil((now-issued)*1000))<=1500)
                        self.run,self.self_sha,self.peer_sha=run,self_sha,peer_sha
                        self.instance,self.sequence,self.captured=(value[key] for key in ('instance','sequence','capturedEpochMs'))
                        return value
                now=self.monotonic();need(number(now,previous,started+1.5));previous=now
                if now-started>=1.5 or attempt==30:break
                self.sleep(min(.05,1.5-(now-started)))
            need(False)
        except Exception:
            raise NativeUIError('Chat original peer position is unavailable') from None
