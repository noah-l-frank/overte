"""Explicit native/Qt/protocol boundary models with real weak references.

No socket, server, compiler, Qt runtime or device is used. Binary replies are
produced from independent controlled bytes; adapters do not generate results.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import uuid
import weakref
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.asset_fixture import BUNDLES
from feature_journeys.fixtures import companion,pinned_resource
from ios.adapters.assets_replies import IOSAssetsReplies
from ios.adapters.assets_reply_owner import OwnedAssetsReplyReads

RUN,TICKET='a'*32,'b'*32
URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'
EPOCH=1900000000000
BINDING=dict(sourceRevision='d'*40,artifactSha256='e'*64,processIdentity='42',sessionId='bound-assets-replies',generation=1,targetFingerprint='f'*64)


def binary(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),retained=True,base64=base64.b64encode(raw).decode())
def string(value):raw=value.encode();return struct.pack('<I',len(raw))+raw
def nonce():return uuid.uuid4().hex


class Message:
    pass


class Control:
    pass


class ReadObject:
    def __init__(self,job,control):self.job,self.control=job,control
    def __del__(self):self.job.event('destroyed',{})


class Job:
    def __init__(self,boundary,query,inputs,control):
        self.boundary,self.query,self.inputs=boundary,deepcopy(query),inputs;self.created=boundary.stamp();self.identity=nonce()
        self.token=weakref.ref(control);self.object=None;self.events=[];self.messages=[];self.stack=[];self.result=None;self.result_raw=None;self.token_expired=None;self.retire=False
        self.wire_id=len(boundary.jobs)+1
    def event(self,kind,details):
        self.boundary.tick();self.events.append(dict(sequence=len(self.events)+1,eventId=nonce(),kind=kind,clock=self.boundary.stamp(),details=deepcopy(details)))
    def enter(self,kind,original=None):
        body=nonce();self.stack.append(body);self.event('callback-enter',dict(bodyId=body,callback=kind,original={} if original is None else original));return body
    def leave(self,body):
        assert self.stack.pop()==body;self.event('callback-return',dict(bodyId=body,normal=True))
    def snapshot(self):
        messages=[]
        for row in self.messages:
            alive=row['weak']() is not None
            if not alive and row['expired'] is None:
                row['expired']=self.boundary.stamp();self.event('message-expired-observed',dict(messageObject=row['messageObject']))
            messages.append({key:deepcopy(value) for key,value in row.items() if key!='weak'}|dict(alive=alive))
        token_alive=self.token() is not None
        if not token_alive and self.token_expired is None:
            self.token_expired=self.boundary.stamp();self.event('token-expired-observed',{})
        return dict(objectId=self.identity,request=deepcopy(self.query),inputs=deepcopy(self.inputs),created=self.created,
            alive=self.object() is not None,pendingBodies=len(self.stack),messages=messages,tokenAlive=token_alive,tokenExpired=self.token_expired,
            retireIssued=self.retire,events=deepcopy(self.events),result=deepcopy(self.result),resultBase64=self.result_raw)


class Boundary:
    def __init__(self,resource='gltf-bundle/main.gltf'):
        self.elapsed=0;self.requests=[];self.jobs={};self.pending={};self.held_messages={};self.held_controls={}
        self.hold_messages=self.hold_controls=self.defer=False;self.lost=None;self.available=True;self.bad_wire=False;self.size_override=None
        self.packet=None;self.sequence=0;self.trace_sequence=0;self.mutate=None;self.resource=resource
        self.binding=dict(server='11111111-1111-4111-8111-111111111111',serverInstance='c'*32,domainId='22222222-2222-4222-8222-222222222222')
        self.data={};self.status={};self.redirect=None
        for path in BUNDLES[resource][1]:
            name=resource if resource=='asset-stand.fbx' else resource.split('/')[0]+'/'+path
            self.data['/e2e-'+RUN+'/'+path]=pinned_resource(name) if resource=='asset-stand.fbx' else companion(name)
    def tick(self,amount=1):self.elapsed+=amount;return self.clock()
    def clock(self):return EPOCH+self.elapsed
    def stamp(self):return dict(epochMs=self.clock(),monotonicMs=self.elapsed+5000)
    def monotonic(self):return self.elapsed/1000
    def sleep(self,seconds):self.elapsed+=round(seconds*1000)
    def scope(self,query):return '/'+('e2e-' if query['namespace']=='original' else 'renamed-')+query['runId']+'/'+query['relativePath']
    def rows(self):
        return [dict(path=path,hash=hashlib.sha256(raw).hexdigest(),status=self.status.get(path,(0,''))[0],bakingErrors=self.status.get(path,(0,''))[1])
            for path,raw in sorted(self.data.items(),key=lambda pair:pair[0].encode('utf-16be'))]
    def start(self,query):
        kind=query['operation'];inputs=dict(path='',hash='',sourceJob=query.get('sourceJob',''),size='')
        if kind!='inventory':
            inputs['path']=self.scope(query);parent=self.jobs[query['sourceJob']]
            if kind in ('mapping','info'):
                matching=[row for row in parent.result['mappings'] if row['path']==inputs['path']];inputs['hash']=matching[0]['hash'] if matching else ''
            else:inputs.update(hash=parent.result['hash'],size=parent.result['size'])
        control=Control();job=Job(self,query,inputs,control);obj=ReadObject(job,control);job.object=weakref.ref(obj)
        self.jobs[query['commandId']]=job;self.pending[query['commandId']]=obj;job.event('started',{})
        if self.available:
            params={} if kind=='inventory' else dict(path=inputs['path']) if kind=='mapping' else dict(hash=inputs['hash']) if kind=='info' else dict(hash=inputs['hash'],**{'from':'0','to':inputs['size']})
            job.event('sent',dict(operation='raw' if kind=='raw-server' else kind,messageId=job.wire_id,inputs=params,**self.binding))
        if not self.defer:self.complete(query['commandId'])
    def complete(self,key):
        job=self.jobs[key];obj=self.pending[key];control=obj.control;kind=job.query['operation'];inputs=job.inputs
        rows=self.rows();data_by_hash={row['hash']:self.data[row['path']] for row in rows};received=self.available;error=0
        message=None;details=None
        if received:
            message=Message();identity=nonce();role='mapping' if kind in ('mapping','inventory') else 'info' if kind=='info' else 'raw'
            job.messages.append(dict(messageObject=identity,kind=role,sourceId=5,packetType=10,packetVersion=1,
                observed=self.stamp(),expired=None,weak=weakref.ref(message)))
            job.event('message-observed',dict(messageObject=identity,kind=role))
            details=dict(sender=self.binding['server'],serverInstance=self.binding['serverInstance'],messageId=job.wire_id,sameTarget=True,messageObject=identity)
        if kind=='inventory':
            payload=struct.pack('<I',len(rows))+b''.join(string(row['path'])+bytes.fromhex(row['hash'])+struct.pack('<i',row['status'])
                +(string(row['bakingErrors']) if row['status']==5 else b'') for row in rows)
            if self.bad_wire:payload+=b'not-a-mapping'
            result=dict(error=0 if received else 2,complete=True,mappings=deepcopy(rows) if received else [])
            if received:job.event('mapping-reply',details|dict(serverError=0,payload=binary(payload),messageComplete=True,messageFailed=False))
        elif kind=='mapping':
            selected=next((row for row in rows if row['path']==inputs['path']),None);error=0 if selected else 1
            redirect=self.redirect is not None and error==0
            digest=self.redirect['hash'] if redirect else selected['hash'] if selected else ''
            destination=self.redirect['path'] if redirect else ''
            payload=(bytes.fromhex(digest)+bytes([int(redirect)])+(string(destination) if redirect else b'')) if selected else b''
            result=dict(error=0 if received and selected else 1 if received else 2,hash=digest if received else '',redirected=redirect,redirectedPath=destination)
            if received:job.event('mapping-reply',details|dict(serverError=error,payload=binary(payload),messageComplete=True,messageFailed=False))
        elif kind=='info':
            raw=data_by_hash.get(inputs['hash']);error=0 if raw is not None else 1;size=self.size_override if self.size_override is not None else len(raw or b'')
            result=dict(responseReceived=received,serverError=error if received else 0,hash=inputs['hash'] if received else '',size=str(size if received else 0))
            if received:
                header=struct.pack('<I32sBq',job.wire_id,bytes.fromhex(inputs['hash']),error,size)
                job.event('info-reply',details|dict(serverError=error,hash=inputs['hash'],size=str(size),messageBytes=str(len(header)),messageComplete=True,messageFailed=False))
        else:
            raw=data_by_hash.get(inputs['hash']);size=int(inputs['size']);error=0 if raw is not None and size<=len(raw) else 2
            raw=raw[:size] if error==0 else b''
            result=dict(responseReceived=received,serverError=error if received else 0,body=binary(raw if received else b''))
            if received:
                job.event('raw-header',details|dict(serverError=error,hash=inputs['hash'],length=str(len(raw))))
                job.event('raw-body',details|dict(responseReceived=True,serverError=error,payload=binary(raw)))
        network=job.enter('network',dict(responseReceived=received,serverError=error if received else 0))
        reader=job.enter('reader') if kind in ('inventory','mapping') else None
        job.result=result
        # Deliberately preserve another valid JSON encoding. The reader must
        # hash these exact original bytes, not re-encode the parsed object.
        encoded=json.dumps(result,ensure_ascii=True,indent=1).encode();job.result_raw=base64.b64encode(encoded).decode()
        job.event('result',dict(bytes=len(encoded),sha256=hashlib.sha256(encoded).hexdigest()))
        if reader:job.leave(reader)
        job.leave(network)
        if self.hold_messages and message is not None:self.held_messages[key]=message
        if self.hold_controls:self.held_controls[key]=control
        self.pending.pop(key)
    def send(self,query):
        self.requests.append(deepcopy(query));before=self.tick();kind=query['operation']
        if kind in ('inventory','mapping','info','raw-server'):self.start(query);key=query['commandId']
        else:
            key=query['jobId'];job=self.jobs[key]
            if kind=='retire' and job.object() is not None:
                assert not job.retire;job.retire=True;job.event('retire-issued',{});self.pending.pop(key,None)
        job=self.jobs[key];snapshot=job.snapshot();self.trace_sequence+=1;self.sequence+=1;now=self.stamp();after=self.tick()
        self.packet=dict(iosAssetsRepliesVersion=1,requestId=query['commandId'],runId=query['runId'],instance='e'*32,sequence=self.sequence,processId=42,
            clockDomain='native-main-assets-replies',clockBefore=dict(epochMs=before,monotonicMs=before-EPOCH+2000),
            clockAfter=dict(epochMs=after,monotonicMs=after-EPOCH+2000),source=dict(iosAssetReplyTraceVersion=1,instance='d'*32,sequence=self.trace_sequence,
                processId=42,clock=now,layout=dict(byteOrder='little',messageIdBytes=4,hashBytes=32,bakingStatusBytes=4),complete=True,job=snapshot))
        if self.mutate:self.mutate(self.packet)
        if self.lost==kind:self.lost=None;raise NativeUIError('Modeled original return was lost')
    def original(self):return json.dumps(self.packet)
    def native(self):return IOSAssetsReplies(self.send,self.original,self.clock,lambda:True,42,monotonic=self.monotonic,sleep=self.sleep)


class Fixture:
    def __init__(self,directory,resource='gltf-bundle/main.gltf'):
        self.boundary=Boundary(resource);self.lock=ScriptSourceLock(Path(directory)/'assets-replies.lock');self.guard=self.lock.held();self.guard.__enter__()
        self.store=PrivateFeatureState(Path(directory)/'assets-replies.json');self.owner=self.restore();self.owner.reserve(TICKET,resource)
    def restore(self):return OwnedAssetsReplyReads(self.boundary.native(),self.store,BINDING,RUN,URL,lock=self.lock)
    def close(self):self.guard.__exit__(None,None,None)
