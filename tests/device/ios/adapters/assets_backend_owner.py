"""Durable backend observations tied to the ordinary Assets upload successor.

This owner preserves original exports and uncertain requests. Its restoration
proof is narrower than whole Assets admission and never retires old pickers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
import re
import uuid
from adapters.asset_backend_client import AssetsBackendClient,configuration,export as decode_export
from adapters import asset_backend_evidence as evidence,asset_backend_source as source,asset_backend_work as work
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_packet_segments import OriginalPacketSegments
from adapters.script_feature.history import same,pack,unpack,canonical
from ios.adapters.assets_budget import operation
from ios.adapters.assets_upload import OwnedAssetsUpload

VERSION=1
MAX_SAMPLES=32


class BackendSegments(OriginalPacketSegments):PROFILE='assets-backend-sources'


def public_configuration(value):
    configuration(value);return {**{key:deepcopy(item) for key,item in value.items() if key!='token'},'tokenSha256':hashlib.sha256(value['token'].encode()).hexdigest()}


class OwnedAssetsBackend:
    def __init__(self,upload,client,store,*,lock):
        need(isinstance(upload,OwnedAssetsUpload) and isinstance(client,AssetsBackendClient) and isinstance(store,PrivateFeatureState));lock.assert_held()
        self.upload,self.client,self.store,self.lock=upload,client,store,lock;self.monotonic,self.sleep=upload.monotonic,upload.sleep
        self.binding,self.run,self.role=upload.binding,upload.files.run,upload.role;self.config=public_configuration(client.config)
        self.previous=store.read();self.state=None
        self.parts=BackendSegments(store.path.parent,self.binding,self.run,self.role,self.role,self.guard,self.parts_intent,monotonic=self.monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)

    def guard(self):
        self.lock.assert_held();self.upload.guard();need(self.client.guard() is not False);return True

    def config_for_decode(self):
        # Historical parsing needs no credential. Only the token's grammar is
        # consulted by the byte decoder; its SHA remains pinned in the owner.
        return {**{key:deepcopy(value) for key,value in self.config.items() if key!='tokenSha256'},'token':'historical'+'x'*40}

    def decode(self,value):
        need(type(self.config) is dict);source.digest(self.config.get('tokenSha256'));configuration(self.config_for_decode())
        exact(value,{'iosAssetsBackendOwnerVersion','binding','runId','role','fixtureUrl','backendConfiguration','payload'})
        need(type(value['iosAssetsBackendOwnerVersion']) is int and value['iosAssetsBackendOwnerVersion']==VERSION and same(value['binding'],self.binding)
            and value['runId']==self.run and value['role']==self.role and value['fixtureUrl']==self.upload.files.url and same(value['backendConfiguration'],self.config))
        states=unpack(value['payload']);need(len(states)==1);state=states[0]
        exact(state,{'phase','samples','baseline','lease','uploadProof','restoration'});need(state['phase'] in ('reserved','baseline','attached','restored')
            and type(state['samples']) is list and len(state['samples'])<=MAX_SAMPLES)
        seen=set();previous=None;next_chunk=1;pending=False
        for row in state['samples']:
            exact(row,{'slot','query','requests','parts'});need(type(row['slot']) is str and re.fullmatch('[a-z][a-z0-9-]{0,47}',row['slot']) is not None and row['slot'] not in seen and not pending);seen.add(row['slot'])
            from fixture.asset_backend_control import command
            command(row['query']);need(row['query']['operation']=='observe' and row['query']['runId']==self.run and type(row['requests']) is list and len(row['requests'])<=32)
            for index,query in enumerate(row['requests']):
                command(query);need(all(query[key]==row['query'][key] for key in query if key!='operation') and query['operation']==('observe' if index==0 else 'poll'))
            parts=row['parts'];pending=parts is None or not parts['complete']
            if parts is not None:
                self.parts.parent(parts);need(parts['label']=='raw' and parts['first']==next_chunk and parts['tag']==self.tag(row));next_chunk+=max(1,(parts['bytes']+524287)//524288)
                if parts['complete']:
                    need(bool(row['requests']));raw=self.parts.read(parts);original=json.loads(raw);need(canonical(original)==raw)
                    packet=decode_export(original,row['query'],self.config_for_decode());source.accept(previous,packet);previous=packet
                else:self.parts.inspect(parts)
        if state['baseline'] is not None:
            need(integer(state['baseline'],1,len(state['samples'])) and re.fullmatch('baseline-[0-9]+',state['samples'][state['baseline']-1]['slot']) is not None)
            packet=self.packet(state['samples'][state['baseline']-1]);need(evidence.ready_source(packet) and work.drained(packet['source']['workBefore']) and work.drained(packet['source']['workAfter'])
                and not any(path.startswith(('/e2e-'+self.run+'/', '/renamed-'+self.run+'/')) for path in evidence.mapping(packet)))
        if state['phase']!='reserved':need(state['baseline'] is not None)
        if state['lease'] is not None:
            exact(state['lease'],{'fileOwnerToken','page','picker'});need(self.upload.files.state is not None and self.upload.state is not None
                and state['lease']==dict(fileOwnerToken=self.upload.files.state['token'],page=self.upload.state['page'],picker=self.upload.state['picker']))
        if state['phase'] in ('attached','restored'):need(state['lease'] is not None)
        if state['uploadProof'] is not None:
            exact(state['uploadProof'],{'sample','proof'});index=state['uploadProof']['sample'];need(integer(index,1,len(state['samples'])))
            need(same(self.upload_proof(self.packet(state['samples'][index-1])),state['uploadProof']['proof']))
        if state['restoration'] is not None:
            exact(state['restoration'],{'first','last','proof'});first,last=state['restoration']['first'],state['restoration']['last'];need(integer(first,1,len(state['samples'])) and integer(last,first+1,len(state['samples'])))
            proof=self.restoration(state,first,last);need(proof is not None and same(proof,state['restoration']['proof']))
        if state['phase']=='restored':need(state['restoration'] is not None and state['restoration']['last']==len(state['samples']) and not pending
            and self.upload.state['phase']=='retired' and (state['uploadProof'] is not None or self.upload.state['aborted']))
        return state

    def tag(self,row):return hashlib.sha256((self.run+'\0'+self.role+'\0'+row['query']['commandId']).encode()).hexdigest()
    def raw(self,row):need(row['parts'] is not None and row['parts']['complete']);return json.loads(self.parts.read(row['parts']))
    def packet(self,row):return decode_export(self.raw(row),row['query'],self.config_for_decode())

    def save(self):
        self.guard();need(same(self.store.read(),self.previous))
        value=dict(iosAssetsBackendOwnerVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,fixtureUrl=self.upload.files.url,backendConfiguration=self.config,payload=pack([self.state]))
        self.decode(value);self.store.write(value,self.previous)
        directory=os.open(self.store.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        try:os.fsync(directory)
        finally:os.close(directory)
        self.previous=deepcopy(value)

    def parts_intent(self,value):
        need(self.state is not None and bool(self.state['samples']));row=self.state['samples'][-1];need(value['tag']==self.tag(row));row['parts']=deepcopy(value);self.save();return True

    @operation
    def reserve(self):
        need(self.state is None);self.state=dict(phase='reserved',samples=[],baseline=None,lease=None,uploadProof=None,restoration=None);self.save()

    def acquire(self,row,operation):
        need(row['parts'] is None and len(row['requests'])<32);query=dict(row['query'],operation=operation)
        def intent(actual):need(same(actual,query));row['requests'].append(deepcopy(actual));self.save();return True
        response=self.client.request(query,before_send=intent)
        if response['status']=='pending':return None
        need(response['status']=='original');raw=canonical(response['original']);first=1
        for previous in self.state['samples'][:-1]:first+=len(previous['parts']['chunks'])
        self.parts.write('raw',self.tag(row),raw,first);self.save();return self.packet(row)

    @operation
    def sample(self,slot,ticket):
        self.guard();need(self.state is not None and self.state['phase']!='restored')
        from fixture.asset_backend_control import command
        query=dict(schemaVersion=1,operation='observe',commandId='assets-'+uuid.uuid4().hex,runId=self.run,ticket=ticket);command(query)
        need(len(self.state['samples'])<MAX_SAMPLES and not any(row['slot']==slot for row in self.state['samples'])
            and all(row['parts'] is not None and row['parts']['complete'] for row in self.state['samples']))
        row=dict(slot=slot,query=query,requests=[],parts=None);self.state['samples'].append(row);self.save();return self.acquire(row,'observe')

    @operation
    def recover(self,slot):
        self.guard();need(self.state is not None and self.state['samples'][-1]['slot']==slot);row=self.state['samples'][-1]
        need(bool(row['requests']) and row['parts'] is None);return self.acquire(row,'poll')

    @operation
    def checkpoint(self,slot,ticket):
        existing=[row for row in self.state['samples'] if row['slot']==slot]
        if existing:
            need(existing[0]['query']['ticket']==ticket)
            if existing[0]['parts'] is not None and existing[0]['parts']['complete']:return self.packet(existing[0])
            return self.recover(slot)
        return self.sample(slot,ticket)

    @operation
    def admit(self,ticket):
        if self.state is None:self.reserve()
        need(self.state['phase'] in ('reserved','baseline'))
        if self.state['phase']=='baseline':return self.packet(self.state['samples'][self.state['baseline']-1])
        pending=self.state['samples'][-1] if self.state['samples'] and (self.state['samples'][-1]['parts'] is None or not self.state['samples'][-1]['parts']['complete']) else None
        slot=pending['slot'] if pending is not None else 'baseline-'+str(len(self.state['samples'])+1)
        packet=self.checkpoint(slot,ticket)
        if packet is None:return None
        if not evidence.ready_source(packet) or not work.drained(packet['source']['workBefore']) or not work.drained(packet['source']['workAfter']):return None
        self.state.update(phase='baseline',baseline=len(self.state['samples']));self.save();return packet

    @operation
    def attach(self):
        need(self.state['phase']=='baseline' and self.upload.state is not None and self.upload.files.state is not None)
        self.state.update(phase='attached',lease=dict(fileOwnerToken=self.upload.files.state['token'],page=self.upload.state['page'],picker=self.upload.state['picker']));self.save()

    def restoration(self,state,first,last):
        base=state['samples'][state['baseline']-1];start,end=state['samples'][first-1],state['samples'][last-1]
        return evidence.restored(self.raw(base),base['query'],self.raw(start),start['query'],self.raw(end),end['query'],self.config_for_decode())

    def quiescent_baseline(self,packet):
        base=self.packet(self.state['samples'][self.state['baseline']-1])
        return (evidence.ready_source(packet) and work.drained(packet['source']['workBefore']) and work.drained(packet['source']['workAfter'])
            and evidence.mapping(packet)==evidence.mapping(base) and same(evidence.blobs(packet),evidence.blobs(base))
            and same(packet['source']['meta'],base['source']['meta']) and same(packet['source']['workBefore']['jobs'],packet['source']['workAfter']['jobs']))

    def upload_proof(self,packet):
        need(self.upload.state['readback'] is not None and evidence.ready_source(packet));readback=self.upload.state['readback'];binding=readback['binding']
        need(binding['server']==packet['serverId'] and binding['domainId']==packet['domainId'])
        expected={row['path']:row['hash'] for row in readback['mappings']};actual=evidence.mapping(packet);prefix=self.upload.state['destination']
        need({path:digest for path,digest in actual.items() if path.startswith(prefix)}==expected);files=evidence.blobs(packet)
        for row in readback['files']:
            need(row['hash'] in files);raw=source.file(files[row['hash']],name=row['hash'],limit=32768,required=True)
            need(raw is not None and len(raw)==row['body']['bytes'] and hashlib.sha256(raw).hexdigest()==row['body']['sha256'])
        return dict(assetBackendUploadProofVersion=VERSION,requestId=packet['requestId'],serverId=packet['serverId'],domainId=packet['domainId'],mappings=readback['mappings'])

    @operation
    def uploaded(self,slot):
        need(self.state['phase']=='attached' and self.upload.state['phase']=='uploaded');slots=[row['slot'] for row in self.state['samples']];index=slots.index(slot)+1
        proof=self.upload_proof(self.packet(self.state['samples'][index-1]));self.state['uploadProof']=dict(sample=index,proof=proof);self.save();return deepcopy(proof)

    @operation
    def restore(self,first_slot,last_slot):
        need(self.state['phase']=='attached' and self.upload.state['phase']=='retired')
        slots=[row['slot'] for row in self.state['samples']];first,last=slots.index(first_slot)+1,slots.index(last_slot)+1
        proof=self.restoration(self.state,first,last)
        if proof is None:return None
        self.state.update(phase='restored',restoration=dict(first=first,last=last,proof=proof));self.save();self.guard();return deepcopy(proof)
