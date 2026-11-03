"""Declared TSI routing model for early Policy2 refusal/no legacy fallback.

No Qt/native method or observed Overte packet is generated. Policies are
execution requests; actual original Parent clocks and actual files back tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import re
from adapters.script_journey.history import canonical
from adapters.pico4.emote_stream_capacity import descriptor

POLICY_KEYS={'picoRemoteAvatarStreamPolicyVersion','runId','parentScopeSha256','parentBaselineSha256',
    'parentHostProcessIdentity','role','processId','originalNativeEpochMs','deadlineNativeEpochMs',
    'originalHostStartedMonotonic','originalHostDeadlineMonotonic','nativeFrameLimit','sampleIntervalMs'}


class CaptureRoutingModel:
    def __init__(self,root,clock,delay):
        self.root,self.clock,self.delay=root,clock,delay;self.selected=False;self.publisher=None
        self.failure=None;self.requests=[];self.legacy_writes=self.legacy_removes=0
        self.policy_failed=False;self.modeled_initial_publications=0;self.modeled_arm_confirmations=0

    @staticmethod
    def canonical_policy(text):
        # Native policy() already performs this check BEFORE gate/file/timer
        # creation. This is a declared model of that existing source predicate,
        # not a new native fix or a Qt execution result.
        try:
            value=json.loads(text);version=value.get('picoRemoteAvatarStreamPolicyVersion')
            if type(version) is not int or version not in (1,2):return False
            extra={} if version==1 else descriptor()
            if set(value)!=POLICY_KEYS|set(extra) or any(value[key]!=item for key,item in extra.items()):return False
            normalized={}
            for key,item in value.items():
                if type(item) is str:
                    if re.fullmatch('[0-9A-Za-z:.+\\-]+',item) is None:return False
                    normalized[key]=item
                elif type(item) in (int,float) and int(item)==item and 0<=item<=10**15:normalized[key]=int(item)
                else:return False
            return canonical(normalized).decode()==text
        except (ValueError,TypeError,AttributeError):return False

    def select(self,command):
        if command.get('operation')!='arm' or type(command.get('ownerPolicy')) is not str:return
        text=command['ownerPolicy'];legacy=False
        if len(text)<=8192 and len(text.encode())<=8192:
            try:
                value=json.loads(text);legacy=type(value) is dict and set(value)==POLICY_KEYS and type(value['picoRemoteAvatarStreamPolicyVersion']) is int and value['picoRemoteAvatarStreamPolicyVersion']==1
                normalized={}
                for key,item in value.items():
                    if type(item) is str:
                        if re.fullmatch('[0-9A-Za-z:.+\\-]+',item) is None:legacy=False
                        normalized[key]=item
                    elif type(item) in (int,float) and int(item)==item and 0<=item<=10**15:normalized[key]=int(item)
                    else:legacy=False
                legacy=legacy and canonical(normalized).decode()==text
            except (ValueError,TypeError,AttributeError):legacy=False
        if not legacy:self.selected=True

    def arm(self,command):
        request=dict(command=command,started=self.clock());self.requests.append(request)
        self.select(command) # Before ANY dispatch/queue/lifecycle/fresh refusal.
        if self.policy_failed:return False
        if self.failure in ('queue','remote'):return False
        if self.failure=='late':self.delay(2000)
        if self.clock()-request['started']>=1.5 or self.failure=='lifecycle':return False
        if not self.canonical_policy(command['ownerPolicy']):self.policy_failed=True;return False
        if self.failure=='publisher':return False
        self.modeled_initial_publications+=1;self.modeled_arm_confirmations+=1;return True

    def save(self,name,raw):
        if self.selected:
            if self.publisher is None:return False
            self.publisher.publish(name,'a'*32,raw);return True
        self.legacy_writes+=1;path=self.root/name;path.write_bytes(raw);path.chmod(0o600);return True

    def remove(self,name):
        if self.selected:return False # Absent/unavailable publisher cannot authorize removal.
        self.legacy_removes+=1;(self.root/name).unlink();return True
