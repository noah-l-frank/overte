"""Declared native producer model, independently hashed real Script inputs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from ios.adapters import chat_script_sources as source

ROOT=Path(__file__).resolve().parents[4]
URL='qrc:/scripts/'
RUN='a'*32
EPOCH=1700000000000


def packet(epoch=EPOCH):
    rows=[]
    for index,name in enumerate(source.FILES,1):
        raw=(ROOT/'scripts'/name).read_bytes().decode('utf-8').encode('utf-16le')
        rows.append(dict(sequence=index,url=URL+name,submittedEpochMs=epoch-1010+index*10,
            encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()))
    member=dict(instance='b'*32,assigned=True,url=URL+source.FILES[0],loadGeneration=1,assignedEpochMs=epoch-1100)
    code={key:rows[0][key] for key in ('encoding','codeUnits','sha256')};code.update(submitted=True,submittedEpochMs=epoch-1010)
    row=dict(membership=member,code=code,codeSources=dict(chatScriptSourcesVersion=1,complete=True,evaluations=rows),
        running=True,stopping=False,finished=False,done=False)
    return dict(iosChatScriptSourcesVersion=1,requestId='ios-'+'1'*32,runId=RUN,instance='2'*32,sequence=1,processId=42,
        clockDomain='native-main-chat-script-sources',clockBefore=dict(epochMs=epoch+1000,monotonicMs=1000),
        clockAfter=dict(epochMs=epoch+1001,monotonicMs=1001),source=dict(complete=True,revision=1,workers=[row]))


def advance(value):
    result=deepcopy(value);result.update(requestId='ios-'+'4'*32,sequence=value['sequence']+1)
    for clock in ('clockBefore','clockAfter'):
        result[clock]['epochMs']+=10;result[clock]['monotonicMs']+=10
    return result


class Boundary:
    def __init__(self,epoch=20000):
        self.epoch,self.time,self.sequence=epoch,1000,0;self.value=packet(epoch);self.raw='';self.queries=[];self.mutate=None
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;value=deepcopy(self.value);self.time+=1
        value.update(requestId=query['commandId'],runId=query['runId'],sequence=self.sequence,
            clockBefore=dict(epochMs=self.epoch+self.time,monotonicMs=self.time))
        self.time+=1;value['clockAfter']=dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)
