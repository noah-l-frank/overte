"""Durable ownership of independent Assets read requests, not server data.

Original inventory/GetInfo/raw replies are retained separately from ordinary
input acknowledgements and client upload holders. No namespace is adopted or
mutated, and no model/oven/full-feature capability is projected here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import re
import secrets
import uuid
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import check as transport_check
from adapters.script_feature.history import MAX_RAW,canonical,pack,unpack,same
from feature_journeys.asset_fixture import BUNDLES,bundle
from feature_journeys.contract import identifier
from ios.adapters.assets_budget import operation
from ios.adapters import assets_replies as source
from ios.adapters import assets_reply_protocol as wire
from ios.adapters.assets_reply_sources import ReplySources
from ios.adapters.assets_file_sources import sync

VERSION=1
OWNER_VERSION=2


class OwnedAssetsReplyReads:
    def __init__(self,native,store,binding,run,url,*,lock,role='primary'):
        need(isinstance(native,source.IOSAssetsReplies) and isinstance(store,PrivateFeatureState));context(binding);identifier(run)
        need(str(native.pid)==binding['processIdentity']);self.native,self.store,self.binding,self.run,self.url,self.lock=native,store,deepcopy(binding),run,url,lock
        lock.assert_held();self.previous=store.read();self.state=None
        self.role=role;self.storage_version=OWNER_VERSION;self.sources=ReplySources(self,role,self.source_guard,self.save)
        if self.previous is not None:
            self.state=self.decode(self.previous)
            for record in self.state['originals']:
                packet=record['packet'];job=packet['source']['job']['request']['commandId'];native.last=deepcopy(packet);native.jobs[job]=deepcopy(packet)

    def source_guard(self):self.lock.assert_held();PrivateFeatureState(self.store.path)._parent();return True

    def legacy_state(self,value):
        exact(value,{'iosAssetsReplyOwnerVersion','binding','runId','fixtureUrl','payload'})
        need(type(value['iosAssetsReplyOwnerVersion']) is int and value['iosAssetsReplyOwnerVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['fixtureUrl']==self.url)
        decoded=unpack(value['payload']);need(len(decoded)==1);return self.validate_state(decoded[0])

    def decode(self,value):
        need(type(value) is dict and type(value.get('iosAssetsReplyOwnerVersion')) is int)
        if value['iosAssetsReplyOwnerVersion']==VERSION:self.storage_version=VERSION;return self.legacy_state(value)
        exact(value,{'iosAssetsReplyOwnerVersion','binding','runId','fixtureUrl','role','payload'})
        need(value['iosAssetsReplyOwnerVersion']==OWNER_VERSION and same(value['binding'],self.binding) and value['runId']==self.run and value['fixtureUrl']==self.url and value['role']==self.role)
        decoded=unpack(value['payload']);need(len(decoded)==1);stored=decoded[0]
        exact(stored,{'phase','ticket','token','resource','namespace','commands','jobs','sources'});self.sources.load(stored['sources']);entries=[]
        for index,reference in enumerate(self.sources.refs):
            record=self.sources.read_record(reference)
            if record['kind']=='legacy-owner':
                need(index==0 and self.sources.migration is not None);legacy=self.legacy_state(decode(base64.b64decode(record['rawBase64']).decode('utf-8'),limit=65536))
                need(all(same(legacy[key],stored[key]) for key in ('ticket','token','resource','namespace')) and stored['commands'][:len(legacy['commands'])]==legacy['commands'] and len(stored['jobs'])>=len(legacy['jobs']))
                for old,new in zip(legacy['jobs'],stored['jobs']):need(all(same(old[key],new[key]) for key in ('slot','query','issuedEpochMs')))
                entries.extend(deepcopy(legacy['originals']))
            else:entries.append(dict(query=deepcopy(record['query']),packet=decode(record['raw'])))
        state={key:deepcopy(stored[key]) for key in ('phase','ticket','token','resource','namespace','commands','jobs')};state['originals']=entries
        need(self.sources.pending is None or state['phase']!='closed');self.storage_version=OWNER_VERSION;return self.validate_state(state)

    def validate_state(self,state):
        need(len(canonical([state]))<=MAX_RAW)
        exact(state,{'phase','ticket','token','resource','namespace','commands','jobs','originals'})
        need(state['phase'] in ('open','closed') and type(state['token']) is str and re.fullmatch('[a-f0-9]{64}',state['token'])
            and state['namespace'] in ('original','renamed') and type(state['jobs']) is list and len(state['jobs'])<=32
            and type(state['commands']) is list and len(state['commands'])<=512 and type(state['originals']) is list and len(state['originals'])<=256)
        identifier(state['ticket']);bundle(self.run,state['ticket'],self.url,state['resource'])
        jobs={};slots=set()
        for job in state['jobs']:
            exact(job,{'slot','query','issuedEpochMs','phase','proof','retireQuery'})
            need(type(job['slot']) is str and re.fullmatch('[a-z][a-z0-9-]{0,47}',job['slot']) and job['slot'] not in slots
                and job['phase'] in ('issued','complete','failed','retiring','retired') and integer(job['issuedEpochMs'],1))
            slots.add(job['slot']);query=source.command(job['query']);need(query['operation'] in source.STARTS and query['commandId'] not in jobs)
            need(all(query[key]==expected for key,expected in (('runId',self.run),('ticket',state['ticket']),('ownerToken',state['token']),('resource',state['resource']),('namespace',state['namespace']))))
            if query['operation']!='inventory':need(query['sourceJob'] in jobs)
            jobs[query['commandId']]=job
            if job['proof'] is not None:need(integer(job['proof'],0,len(state['originals'])-1))
            if job['retireQuery'] is not None:
                source.command(job['retireQuery']);need(job['retireQuery']['operation']=='retire' and job['retireQuery']['jobId']==query['commandId'])
        commands={}
        for query in state['commands']:
            source.command(query);need(query['commandId'] not in commands and all(query[key]==expected for key,expected in (
                ('runId',self.run),('ticket',state['ticket']),('ownerToken',state['token']),('resource',state['resource']),('namespace',state['namespace']))))
            target=query.get('jobId',query['commandId']);need(target in jobs)
            if query['operation'] in source.STARTS:need(same(query,jobs[target]['query']))
            elif query['operation']=='retire':need(same(query,jobs[target]['retireQuery']))
            commands[query['commandId']]=query
        previous=None;latest={};seen=set()
        for record in state['originals']:
            exact(record,{'query','packet'});query=record['query'];packet=record['packet'];target=query.get('jobId',query['commandId'])
            need(query['commandId'] in commands and same(query,commands[query['commandId']]) and query['commandId'] not in seen);seen.add(query['commandId'])
            source.validate(packet,query,self.native.pid,previous=previous,previous_job=latest.get(target))
            need(same(packet['source']['job']['request'],jobs[target]['query']) and packet['source']['job']['created']['epochMs']>=jobs[target]['issuedEpochMs'])
            previous=packet;latest[target]=packet
        proofs={}
        for key,job in jobs.items():
            if job['proof'] is not None:
                packet=state['originals'][job['proof']]['packet'];need(packet['source']['job']['request']['commandId']==key)
                actual=source.qualified(packet);self._join(packet,actual,proofs);proofs[key]=(packet,actual)
            if job['phase']=='complete':need(job['proof'] is not None)
            if job['phase']=='retired':need(key in latest and source.drained(latest[key]))
        if state['phase']=='closed':need(all(job['phase']=='retired' for job in state['jobs']))
        return state

    @staticmethod
    def _join(packet,actual,proofs):
        job=packet['source']['job'];query=job['request'];kind=query['operation']
        if kind=='inventory':return
        parent_id=query['sourceJob'];need(parent_id in proofs);parent,original=proofs[parent_id]
        need(packet['source']['instance']==parent['source']['instance'] and actual['binding']==original['binding'])
        source.clock_after(job['created'],parent['source']['clock'])
        if kind in ('mapping','info'):
            need(original['kind']=='inventory');rows=[row for row in original['mappings'] if row['path']==actual['path']]
            need(len(rows)<=1 and job['inputs']['hash']==(rows[0]['hash'] if rows else ''))
            if kind=='info':need(rows and actual['hash']==rows[0]['hash'])
            elif not actual['redirected']:need(rows and actual['hash']==rows[0]['hash'])
        else:
            need(original['kind']=='info' and actual['path']==original['path'] and actual['hash']==original['hash']
                and actual['body']['bytes']==original['bytes'] and job['inputs']['size']==str(original['bytes']))

    def save(self):
        self.lock.assert_held();transport_check();need(self.native.guard() is not False and same(self.store.read(),self.previous))
        if self.storage_version==VERSION:self.sources.prepare_migration(self.previous);self.storage_version=OWNER_VERSION
        state={key:deepcopy(self.state[key]) for key in ('phase','ticket','token','resource','namespace','commands','jobs')};state['sources']=self.sources.manifest()
        value=dict(iosAssetsReplyOwnerVersion=OWNER_VERSION,binding=self.binding,runId=self.run,fixtureUrl=self.url,role=self.role,payload=pack([state]))
        need(same(self.decode(value),self.state));transport_check();self.store.write(value,self.previous);sync(self.store.path.parent);need(same(self.store.read(),value));self.previous=deepcopy(value)

    @operation
    def reserve(self,ticket,resource='gltf-bundle/main.gltf',namespace='original'):
        need(self.state is None);identifier(ticket);bundle(self.run,ticket,self.url,resource);need(namespace in ('original','renamed'))
        self.state=dict(phase='open',ticket=ticket,token=secrets.token_hex(32),resource=resource,namespace=namespace,commands=[],jobs=[],originals=[]);self.save()

    def _query(self,kind,**values):
        need(self.state is not None and self.state['phase']=='open')
        return source.command(dict(schemaVersion=VERSION,commandId='ios-'+uuid.uuid4().hex,action=source.ACTION,
            runId=self.run,ticket=self.state['ticket'],ownerToken=self.state['token'],resource=self.state['resource'],namespace=self.state['namespace'],operation=kind,**values))

    def _retain(self,query,packet):
        raw=self.native.original();need(type(raw) is str and same(decode(raw),packet));return self._retain_raw(query,packet,raw)

    def _retain_raw(self,query,packet,raw):
        need(len(self.state['originals'])<256 and self.sources.pending is None and same(decode(raw),packet));self.sources.capture(query,raw);return self.recover_capture()

    def recover_capture(self):
        reference,record=self.sources.completed_capture();query=record['query'];packet=decode(record['raw']);target=query.get('jobId',query['commandId'])
        previous=self.state['originals'][-1]['packet'] if self.state['originals'] else None
        earlier=[entry['packet'] for entry in self.state['originals'] if entry['packet']['source']['job']['request']['commandId']==target]
        source.validate(packet,query,self.native.pid,previous=previous,previous_job=earlier[-1] if earlier else None)
        self.sources.accept_capture();self.state['originals'].append(dict(query=deepcopy(query),packet=packet));self.save();return packet

    def _exchange(self,query):
        if self.storage_version==VERSION:self.save()
        need(len(self.state['commands'])<512 and len(self.state['originals'])<256 and self.sources.pending is None);self.state['commands'].append(deepcopy(query));self.save()
        return self.native.request(query,retain_raw=self._retain_raw)

    def _job(self,slot):
        jobs=[job for job in self.state['jobs'] if job['slot']==slot];need(len(jobs)==1);return jobs[0]

    @operation
    def read(self,slot,kind='inventory',*,source_slot=None,relative_path=None):
        need(self.state['phase']=='open' and len(self.state['jobs'])<32 and not any(job['slot']==slot for job in self.state['jobs']))
        values={}
        if kind!='inventory':
            parent=self._job(source_slot);need(parent['phase']=='complete' and parent['proof'] is not None)
            values=dict(sourceJob=parent['query']['commandId'],relativePath=relative_path)
        query=self._query(kind,**values);need(kind in source.STARTS);issued=self.native.clock_ms();need(integer(issued,1))
        job=dict(slot=slot,query=query,issuedEpochMs=issued,phase='issued',proof=None,retireQuery=None);self.state['jobs'].append(job);self.save()
        packet=self._exchange(query);return self._wait(job,packet)

    def _wait(self,job,packet=None):
        for attempt in range(201):
            transport_check();need(self.native.guard() is not False)
            if packet is not None and source.drained(packet):
                try:
                    actual=source.qualified(packet);proofs={}
                    for earlier in self.state['jobs']:
                        if earlier['proof'] is not None:
                            original=self.state['originals'][earlier['proof']]['packet'];proofs[earlier['query']['commandId']]=(original,source.qualified(original))
                    self._join(packet,actual,proofs)
                except (NativeUIError,ValueError):
                    job['phase']='failed';self.save();raise NativeUIError('Original Assets server read did not qualify') from None
                index=next(index for index,record in enumerate(self.state['originals']) if record['packet']['requestId']==packet['requestId'])
                job['proof']=index;job['phase']='complete';self.save();return deepcopy(actual)
            if attempt:self.native.sleep(.1)
            packet=self._exchange(self._query('observe',jobId=job['query']['commandId']))
        raise NativeUIError('Original Assets read holders did not drain')

    @operation
    def recover(self,slot):
        job=self._job(slot);need(job['phase']=='issued');return self._wait(job)

    def proof(self,slot):
        job=self._job(slot);need(job['proof'] is not None);return source.qualified(self.state['originals'][job['proof']]['packet'])

    @operation
    def observe_bundle(self):
        """Actual server bytes/paths only; no upload/model/bake success verdict."""
        first=self.read('bundle-inventory');prefix='/'+('e2e-' if self.state['namespace']=='original' else 'renamed-')+self.run+'/'
        actual=[row for row in first['mappings'] if row['path'].startswith(prefix)]
        expected=bundle(self.run,self.state['ticket'],self.url,self.state['resource']);names=[row['path'][len(prefix):] for row in actual]
        need(set(names)==set(BUNDLES[self.state['resource']][1]));files=[]
        primary=self.read('bundle-primary-mapping','mapping',source_slot='bundle-inventory',relative_path=expected['primaryPath'])
        for index,row in enumerate(actual):
            path=row['path'][len(prefix):];self.read('bundle-info-'+str(index),'info',source_slot='bundle-inventory',relative_path=path)
            raw=self.read('bundle-raw-'+str(index),'raw-server',source_slot='bundle-info-'+str(index),relative_path=path)
            wanted=next(item for item in expected['files'] if item['relativePath']==path)
            need(raw['hash']==row['hash'] and raw['body']['sha256']==wanted['sha256'] and raw['body']['bytes']==wanted['bytes'])
            files.append(dict(relativePath=path,hash=raw['hash'],body=raw['body'],captured=raw['captured'],binding=raw['binding']))
        final=self.read('bundle-final-inventory');last=[row for row in final['mappings'] if row['path'].startswith(prefix)]
        need(same(actual,last) and first['binding']==final['binding'])
        return dict(iosAssetsSourceBundleVersion=VERSION,resource=self.state['resource'],namespace=self.state['namespace'],
            mappings=deepcopy(last),files=files,primaryMapping=primary,binding=final['binding'],captured=final['captured'])

    @operation
    def close(self):
        """Retire read holders only; server mappings and cached data are untouched."""
        if self.state['phase']=='closed':
            self.lock.assert_held();need(self.native.guard() is not False and same(self.store.read(),self.previous));self.decode(self.previous);return
        need(self.state['phase']=='open')
        for job in self.state['jobs']:
            packet=self._exchange(self._query('observe',jobId=job['query']['commandId']))
            if not source.drained(packet):
                if job['retireQuery'] is None:
                    job['phase']='retiring';job['retireQuery']=self._query('retire',jobId=job['query']['commandId']);self.save();self._exchange(job['retireQuery'])
                for _ in range(201):
                    packet=self._exchange(self._query('observe',jobId=job['query']['commandId']))
                    if source.drained(packet):break
                    self.native.sleep(.1)
                need(source.drained(packet))
            job['phase']='retired';self.save()
        self.state['phase']='closed';self.save()
