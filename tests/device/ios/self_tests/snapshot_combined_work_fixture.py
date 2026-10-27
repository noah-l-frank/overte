"""Explicit combined-manager Qt/V8 boundary using actual repository bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
URL='qrc:/scripts/'
EPOCH=1700000000000
RUN='a'*32
FILES=('defaultScripts.js','system/snapshot.js','modules/request.js','system/snapshot/featureSnapshotWork.js')


def code(epoch=EPOCH):
    rows=[]
    for index,path in enumerate(FILES):
        raw=(ROOT/'scripts'/path).read_bytes().decode('utf-8').encode('utf-16-le')
        rows.append(dict(sequence=index+1,url=URL+path,submittedEpochMs=epoch-1000+index*100,
            encoding='utf-16le-code-units',codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()))
    return rows


def caller(paths,epoch=EPOCH):
    rows={row['url']:row for row in code(epoch)};frames=[];modules=[]
    for index,path in enumerate(paths):
        url=URL+path;row=rows[url];url_sha=hashlib.sha256(url.encode()).hexdigest()
        frames.append(dict(scriptId=FILES.index(path)+1,line=23,column=1,sourceUrlSha256=url_sha,
            compiled=dict(urlSha256=url_sha,encoding=row['encoding'],codeUnits=row['codeUnits'],sha256=row['sha256'],firstObservedEpochMs=epoch-680),isEval=False,isConstructor=False))
        modules.append(dict(frame=index,url=url))
    return dict(emitStackVersion=1,instance='9'*32,complete=True,frames=frames),modules


def entry(identifier,paths,epoch=EPOCH):
    stack,modules=caller(paths,epoch);return dict(id=identifier,callerStack=stack,callerModules=modules)


def packet(epoch=EPOCH):
    rows=code(epoch);member=dict(instance='b'*32,assigned=True,url=URL+'defaultScripts.js',loadGeneration=1,assignedEpochMs=epoch-1100)
    submitted=dict(submitted=True,encoding=rows[0]['encoding'],codeUnits=rows[0]['codeUnits'],sha256=rows[0]['sha256'],submittedEpochMs=epoch-1010)
    sources=dict(snapshotCombinedSourcesVersion=1,complete=True,evaluations=rows)
    state=dict(nativeReview=True,revision=0,captureId='',captureCounter=0,mode='still',timerHandles=[],pendingUploads=0,overlaysHidden=False,open=True)
    original=dict(sequence=1,callerSequence=1,capturedEpochMs=epoch-650,invokedEpochMs=epoch-650,event='snapshot',closure='',call=0,state=deepcopy(state),callerStackId='c'*32)
    latest=dict(original,sequence=2,callerSequence=2,capturedEpochMs=epoch+990,invokedEpochMs=epoch+990,callerStackId='d'*32)
    row=dict(sourceUrl=URL+'system/snapshot.js',manager=member,code=submitted,codeSources=sources,calls=[],events=[original],ended=False,state=state,latest=latest)
    native=dict(membership=deepcopy(member),code=deepcopy(submitted),running=True,stopping=False,finished=False,done=False,codeSources=deepcopy(sources),
        timerWork=dict(snapshotCombinedTimerWorkVersion=1,instance='e'*32,complete=True,timers=[],callerStacks=[]))
    return dict(iosSnapshotCombinedWorkVersion=1,requestId='ios-'+'1'*32,runId=RUN,instance='2'*32,sequence=1,processId=42,
        clockDomain='native-main-snapshot-combined-work',clockBefore=dict(epochMs=epoch+1000,monotonicMs=1000),clockAfter=dict(epochMs=epoch+1001,monotonicMs=1001),
        source=dict(complete=True,eventSequence=2,workers=[row],timerSources=dict(complete=True,revision=1,workers=[native]),callerStacks=[
            entry('c'*32,('system/snapshot/featureSnapshotWork.js','system/snapshot.js','defaultScripts.js'),epoch),
            entry('d'*32,('system/snapshot/featureSnapshotWork.js',),epoch)]))


def timer(value,epoch=EPOCH):
    work=value['source']['timerSources']['workers'][0]['timerWork'];work['callerStacks'].append(entry('f'*32,('system/snapshot.js','system/snapshot/featureSnapshotWork.js','defaultScripts.js'),epoch))
    row=dict(timerId='3'*32,handle=1,callerStackId='f'*32,createdEpochMs=epoch-500,singleShot=True,intervalMs=350,activeAtBirth=True,remainingAtBirthMs=350,
        destroyedEpochMs=epoch-149,fired=1,entered=1,left=1,depth=0,pendingDispatch=0,lastFiredEpochMs=epoch-150,lastCallbackEpochMs=epoch-148,lastDispatchEpochMs=epoch-147)
    work['timers'].append(row);return row


def advance(value):
    result=deepcopy(value);result.update(requestId='ios-'+'4'*32,sequence=value['sequence']+1)
    for clock in ('clockBefore','clockAfter'):
        result[clock]['epochMs']+=10;result[clock]['monotonicMs']+=10
    return result


class Boundary:
    def __init__(self,epoch=20000):self.epoch,self.time,self.sequence=epoch,1000,0;self.value=packet(epoch);self.raw='';self.queries=[];self.mutate=None
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;value=deepcopy(self.value);self.time+=1
        value.update(requestId=query['commandId'],runId=query['runId'],sequence=self.sequence,clockBefore=dict(epochMs=self.epoch+self.time,monotonicMs=self.time))
        self.time+=1;value['clockAfter']=dict(epochMs=self.epoch+self.time,monotonicMs=self.time)
        if self.mutate:self.mutate(value)
        self.raw=json.dumps(value)
