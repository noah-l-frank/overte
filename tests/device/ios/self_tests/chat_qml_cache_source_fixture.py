"""Explicit Qt/QObject/FD/SDK producer model; reviewed QML input bytes are real.

This new model creates its own receipts. No retained original is relabeled.
Actual host FD/write/mmap cases live in the separate cache-original packet.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib,json
from ios.adapters import chat_qml_sources as source
from ios.self_tests.chat_qml_source_fixture import ROOT,URL,RUN,EPOCH,packet


def clock(epoch,offset):return dict(epochMs=epoch+offset,monotonicMs=offset)
def compiler(value):return value['source']['cacheAtLoad']['unit']['mappingOriginal']['writeOriginal']['compilerInput']
def unit(value,current=False):return value['source']['cacheAtRead' if current else 'cacheAtLoad']['unit']


def cache_packet(epoch=EPOCH):
    result=packet(epoch);loaded=result['source'];original=loaded.pop('compilerInput')
    prefix={key:deepcopy(value) for key,value in original.items()
        if key not in ('unitBytes','unitSha256','unitGeneration','compiledEpochMs')}
    prefix.update(sourceBeforeEpochMs=epoch+10,sourceAfterEpochMs=epoch+11)
    file=dict(device='36',inode='1001',bytes=2048,modifiedSeconds=epoch//1000,
        modifiedNanoseconds=0,changedSeconds=epoch//1000,changedNanoseconds=0)
    write=dict(qtOverteQmlCacheWriteVersion=1,clockDomain='native-qt-steady-clock',writerId='6'*32,
        processId=42,compilerOwnerId='7'*32,compilerOwnerGeneration=1,compilerInput=prefix,
        writeSequence=1,writeBefore=clock(epoch,20),writeAfter=clock(epoch,21),bytes=2048,
        writeArgumentSha256='8'*64,fileBefore=dict(file,bytes=0),written=2048,committed=True,fileCommitted=file)
    mapped=dict(qtOverteQmlCacheMappingVersion=1,clockDomain='native-qt-steady-clock',mappingId='9'*32,
        mappingSequence=2,processId=42,mapBefore=clock(epoch,30),mapAfter=clock(epoch,31),
        mappedFile=deepcopy(file),mappedBytes=2048,mappedSha256='8'*64,writeOriginal=write)
    at_load=dict(qtOverteQmlCacheUnitVersion=1,clockDomain='native-qt-steady-clock',processId=42,
        unitOwnerId='a'*32,unitReadBefore=clock(epoch,100),unitReadAfter=clock(epoch,101),
        unitGeneration=3,unitBytes=2048,unitSha256='8'*64,mappingOriginal=mapped)
    object_load=dict(qtOverteQmlObjectCacheReceiptVersion=1,processId=42,executableUnitId='b'*32,componentMatched=True,
        unitSourceUrl=URL,unitFinalUrl=URL,unit=at_load)
    object_read=deepcopy(object_load);object_read['componentMatched']=False
    object_read['unit']['unitReadBefore']=clock(epoch,1000);object_read['unit']['unitReadAfter']=clock(epoch,1001)
    loaded.update(iosLoadedQmlSourceVersion=2,sourceKind='observed-cache',cacheAtLoad=object_load,
        cacheAtRead=object_read,coverage=dict(importGraphAvailable=False,aotGraphAvailable=False,installedQtSourceAvailable=False))
    return result


def advance(value):
    result=deepcopy(value);result.update(sequence=value['sequence']+1,requestId='ios-'+'6'*32)
    for name in ('clockBefore','clockAfter'):
        result[name]['epochMs']+=10;result[name]['monotonicMs']+=10
    unit(result,True)['unitReadBefore']=deepcopy(result['clockBefore'])
    unit(result,True)['unitReadAfter']=deepcopy(result['clockAfter']);return result


class Boundary:
    def __init__(self,epoch=20000):
        self.epoch,self.time,self.sequence=epoch,1000,0
        self.value,self.raw,self.queries,self.mutate=cache_packet(epoch),'',[],None
    def send(self,query):
        self.queries.append(deepcopy(query));self.sequence+=1;self.time+=1
        result=deepcopy(self.value);result.update(requestId=query['commandId'],runId=query['runId'],sequence=self.sequence,
            clockBefore=clock(self.epoch,self.time))
        self.time+=1;result['clockAfter']=clock(self.epoch,self.time)
        unit(result,True)['unitReadBefore']=deepcopy(result['clockBefore'])
        unit(result,True)['unitReadAfter']=deepcopy(result['clockAfter'])
        if self.mutate:self.mutate(result)
        self.raw=json.dumps(result)
