"""Durable actual material/resource join for normal Create Model input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import decode,exact,fresh,integer,need
from adapters.normal_feature_state import context
from adapters.pico4.create_model_resources import retired
from adapters.pico4.create_entities import entity_id
from adapters.pico4.create_models import OwnedCreateModels
from adapters.token_create_ui import nonce

VERSION=1


class ResourceJoinedCreateModels(OwnedCreateModels):
    """Keeps property effect and actual bound-resource effect distinct.

    Sampled known resources are retained until actual death. No byte, complete
    allocation-history, GPU, current pixel or peer claim follows from this join.
    """
    def __init__(self,*args,resources,join_store,**kwargs):
        super().__init__(*args,**kwargs)
        self.resources,self.join_store=resources,join_store;self.join_previous=join_store.read();self.current_resources=None
        if self.join_previous is not None:self.validate_join(self.join_previous)
    def validate_join(self,value):
        exact(value,{'schemaVersion','binding','runId','anchors'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and context(value['binding'])==self.binding
            and value['runId']==self.resources.reader.run and type(value['anchors']) is list and len(value['anchors'])<=4)
        keys=[]
        for anchor in value['anchors']:
            exact(anchor,{'ticket','operation','raw','sha256','entityId','model','geometry'})
            need(nonce(anchor['ticket']) and anchor['operation'] in ('create','texture')
                and type(anchor['raw']) is str and hashlib.sha256(anchor['raw'].encode()).hexdigest()==anchor['sha256'])
            packet=decode(anchor['raw']);self.resources.reader.validate(packet,packet['requestId'],self.resources.reader.pid,packet['capturedEpochMs'])
            need(all(anchor[k] is None or nonce(anchor[k]) for k in ('model','geometry'))
                and (anchor['entityId'] is None or entity_id(anchor['entityId']))
                and (anchor['geometry'] is None or anchor['model'] is not None))
            if anchor['operation']=='texture':need(anchor['entityId'] is not None and anchor['model'] is not None and anchor['geometry'] is not None)
            latest=self.resources.reader.last
            if latest is not None:
                if latest!=packet:self.resources.reader.continuity(packet,latest)
                for field,history in (('model','models'),('geometry','geometries')):
                    if anchor[field] is not None:need(anchor[field] in {r['instance'] for r in latest['source'][history]})
            keys.append((anchor['ticket'],anchor['operation']))
        need(len(keys)==len(set(keys)))
    def join_state(self):
        value=self.join_store.read();need(value==self.join_previous)
        if value is not None:self.validate_join(value)
        return value
    def join_write(self,value):
        self.validate_join(value);self.join_store.write(value,self.join_previous);self.join_previous=deepcopy(value)
    def anchor(self,ticket,operation):
        value=self.join_state()
        rows=[] if value is None else [a for a in value['anchors'] if a['ticket']==ticket and a['operation']==operation]
        need(len(rows)<=1);return deepcopy(rows[0]) if rows else None
    def capture(self,initial=False):
        actual=super().capture(initial);packet=self.resources.read();source=packet['source'];entities=actual['entities']
        need(packet['instance']==entities['instance'] and packet['processId']==entities['processId']
            and source['domainSession']==entities['source']['domainSession']
            and {r['entityId'] for r in source['bindings']}==set(entities['source']['absentIds'])|{r['id'] for r in entities['source']['entities']})
        fresh(packet['capturedEpochMs'],self.resources.reader.clock_ms())
        self.join_state()
        actual['resources']=packet;self.current_resources=deepcopy(packet);return actual
    @staticmethod
    def model_binding(packet,entity):
        rows=[r for r in packet['source']['bindings'] if r['entityId']==entity];need(len(rows)==1)
        return rows[0]
    @staticmethod
    def loaded(packet,entity,url):
        row=ResourceJoinedCreateModels.model_binding(packet,entity)
        return row['model'] is not None and row['loaded'] and row['geometry'] is not None and row['loadedSourceSha256']==hashlib.sha256(url.encode()).hexdigest()
    def intent(self,original):
        owner=self.state();step=owner['steps'][-1];operation=owner['pending']['operation']
        if operation in ('create','texture') and self.anchor(step['ticket'],operation) is None:
            packet=self.current_resources;need(packet is not None)
            raw=self.resources.reader.last_raw;need(type(raw) is str and decode(raw)==packet)
            need(packet['source']['domainSession']==step['before']['source']['domainSession'])
            anchor=dict(ticket=step['ticket'],operation=operation,raw=raw,sha256=hashlib.sha256(raw.encode()).hexdigest(),entityId=None,model=None,geometry=None)
            if operation=='create':
                need(not step['submitted'] and all(r['model'] is None for r in packet['source']['bindings']))
            else:
                need(step['texture'] is not None and not step['texture']['submitted'] and step['entityId'] is not None
                    and self.loaded(packet,step['entityId'],step['url']))
                row=self.model_binding(packet,step['entityId']);anchor.update(entityId=step['entityId'],model=row['model'],geometry=row['geometry'])
                original_url=step['url'].rsplit('/',1)[0]+'/textures/checker.png'
                need(self.texture_bound(packet,row,original_url))
            value=self.join_state()
            if value is None:value=dict(schemaVersion=VERSION,binding=self.binding,runId=owner['runId'],anchors=[])
            value['anchors'].append(anchor);self.join_write(value) # Before the first associated normal input.
        super().intent(original)
    @staticmethod
    def texture_bound(packet,row,url):
        textures=[t for t in row['textures'] if t['slot']=='checker.png'];need(textures)
        resources={r['instance']:r for r in packet['source']['resources']}
        return all(resources[t['resource']]['sharedAvailable'] and resources[t['resource']]['state']['url']==url
            and resources[t['resource']]['state']['loaded'] and not resources[t['resource']]['state']['failed'] for t in textures)
    def pin_model(self,anchor,packet,row,entity):
        before=decode(anchor['raw'])
        if anchor['model'] is None:
            need(row['model'] not in {r['instance'] for r in before['source']['models']})
            model=next(r for r in packet['source']['models'] if r['instance']==row['model'])
            need(model['firstObservedEpochMs']>=before['capturedEpochMs'])
            anchor.update(entityId=entity,model=row['model'])
        need(anchor['entityId']==entity and anchor['model']==row['model'])
        if row['loaded']:
            if anchor['geometry'] is None:anchor['geometry']=row['geometry']
            need(anchor['geometry']==row['geometry'])
        value=self.join_state()
        for index,original in enumerate(value['anchors']):
            if original['ticket']==anchor['ticket'] and original['operation']=='create':
                if original!=anchor:value['anchors'][index]=anchor;self.join_write(value)
                break
    def extra_ready(self,actual,operation,row):
        packet=actual['resources'];step=self.state()['steps'][-1]
        if operation=='delete':return all(r['model'] is None for r in packet['source']['bindings'])
        anchor=self.anchor(step['ticket'],'create')
        if row is None or anchor is None:return False
        bound=self.model_binding(packet,row['id'])
        if bound['model'] is None:return False
        self.pin_model(anchor,packet,bound,row['id'])
        if not self.loaded(packet,row['id'],step['url']):return False
        if operation=='texture':
            baseline=self.anchor(step['ticket'],'texture')
            if baseline is None:return False
            before=self.model_binding(decode(baseline['raw']),row['id'])
            need(bound['model']==baseline['model'] and bound['geometry']==baseline['geometry'])
            shape=lambda item:[(t['material'],t['materialIndex'],t['channel'],t['slot']) for t in item['textures']]
            need(shape(bound)==shape(before))
            other=lambda item:[t for t in item['textures'] if t['slot']!='checker.png']
            need(other(bound)==other(before))
            return self.texture_bound(packet,bound,step['texture']['url'])
        return True
    def extra_clocks(self,actual):return (actual['resources']['capturedEpochMs'],)
    def extra_stable(self,actual):return deepcopy(actual['resources']['source'])
    def extra_release_ready(self,actual):
        if self.previous is not None:
            need(all(self.anchor(step['ticket'],'create') is not None for step in self.state()['steps']))
        return retired(actual['resources']['source'])
    def original_readers(self):return super().original_readers()+(self,)
    def retire(self):
        self.resources.retire();self.join_store.discard(self.join_state());self.join_previous=None
