"""Durable read-only backend admission and same-native-upload original join.

Every request is a closed GET. This owner cannot prepare accounts, POST an
upload, publish an actor, remove backend rows or change native UI state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import time
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from feature_journeys.snapshot_domain_client import public_configuration
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_upload_owner import IOSSnapshotUploadOwner
from ios.adapters import snapshot_upload_backend_source as source


class IOSSnapshotUploadBackendOwner:
    def __init__(self,native,client,*,epoch_ms,monotonic,sleep,domain_policy=None):
        need(type(native) is IOSSnapshotUploadOwner and native.historical and native.state['result'] is not None and isinstance(client,Client))
        need(client.url+'/runs/'+native.run+'/'==native.fixture_url);source.origin(client.url)
        self.domain_policy=None if domain_policy is None else deepcopy(public_configuration(domain_policy));self.version=3 if native.frontend_http else 1 if domain_policy is None else 2
        self.native,self.client,self.epoch_ms,self.monotonic,self.sleep=native,client,epoch_ms,monotonic,sleep;self.historical=False;self.setup()
    @classmethod
    def history(cls,native,*,domain_policy=None):
        owner=object.__new__(cls);owner.native=native;owner.historical=True;owner.client=None;owner.monotonic=time.monotonic;owner.epoch_ms=owner.sleep=None
        owner.domain_policy=None if domain_policy is None else deepcopy(public_configuration(domain_policy));owner.version=3 if native.frontend_http else 1 if domain_policy is None else 2
        owner.setup();need(owner.previous is not None);return owner
    def setup(self):
        need(self.version!=3 or self.domain_policy is not None)
        native=self.native;need(native.historical and native.state['result'] is not None);self.run,self.binding,self.lock,self.fixture_url=native.run,deepcopy(native.binding),native.lock,native.fixture_url
        self.lock.assert_held();self.root=native.root;self.store=PrivateFeatureState(self.root/'snapshot-upload-backend-owner.json')
        self.pins=dict(nativeUploadOwnerSha256=digest(native.previous),nativeUploadResultSha256=digest(native.proof()))
        if self.version>=2:self.pins['domainPolicySha256']=digest(self.domain_policy)
        self.previous=self.store.read();self.state=dict(slots=[],role=None,authority=None,admission=None,scope=None,joined=None,bodies=[],result=None)
        if self.version>=2:self.state.update(preflight=None,preflightJoined=None)
        if self.previous is not None:self.state=self.load(self.previous)
        elif not self.historical:
            need(not any(path.name.startswith('snapshot-upload-backend-') for path in self.root.iterdir()));self.save()
    def guard(self):
        self.lock.assert_held();self.native.capture.bound();need(same(self.native.store.read(),self.native.previous) and same(self.store.read(),self.previous))
        return True
    def envelope(self):return dict(snapshotUploadBackendOwnerVersion=self.version,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,pins=self.pins,payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.guard();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def frames(self,live=False):
        return OriginalFrameStore(self.root,self.binding,self.run,'primary',self.guard if live else lambda:True,self.storage if live else lambda *_:need(False),
            namespace='snapshot-upload-backend',schema_prefix='snapshotUploadBackend',monotonic=self.monotonic)
    def query(self,value):
        exact(value,{'snapshotUploadBackendQueryVersion','kind','runId','requestId','upload','offset'})
        need(type(value['snapshotUploadBackendQueryVersion']) is int and value['snapshotUploadBackendQueryVersion']==self.version and value['runId']==self.run
            and value['kind'] in (('role','authority','source','body') if self.version==1 else ('role','authority','source','body','preflight')));identifier(value['requestId'])
        if value['kind']=='body':identifier(value['upload']);need(integer(value['offset'],0,source.IMAGE_LIMIT-1) and value['offset']%source.PART==0)
        else:need(value['upload'] is value['offset'] is None)
        return value
    def frame(self,index):
        need(integer(index,1,len(self.state['slots'])));slot=self.state['slots'][index-1];need(slot['phase']=='retained')
        return self.validate_frame(self.frames().read(self.frames().expand(slot['proof'])),slot['query'])
    def validate_frame(self,frame,query):
        exact(frame,{'query','response','acquisition'});need(same(self.query(frame['query']),query));span=frame['acquisition']
        exact(span,{'hostBeforeEpochMs','hostBeforeMonotonic','hostAfterEpochMs','hostAfterMonotonic'})
        need(number(span['hostBeforeEpochMs'],1,1e15) and number(span['hostAfterEpochMs'],span['hostBeforeEpochMs'],1e15)
            and number(span['hostBeforeMonotonic'],0,1e15) and number(span['hostAfterMonotonic'],span['hostBeforeMonotonic'],1e15))
        need(abs(span['hostAfterEpochMs']-span['hostBeforeEpochMs']-(span['hostAfterMonotonic']-span['hostBeforeMonotonic'])*1000)<=250)
        if query['kind']=='role':
            value=frame['response'];exact(value,{'fixtureAdapterAccessVersion','role','canMutate','canPublish','peerFactsVisible'})
            need(type(value['fixtureAdapterAccessVersion']) is int and value['fixtureAdapterAccessVersion']==1 and value['role']=='adapter' and value['canMutate'] is value['canPublish'] is value['peerFactsVisible'] is False)
        elif query['kind']=='authority':
            value=frame['response'];exact(value,{'providerVersion','instance','transport','tlsVersion','internalErrors'})
            need(type(value['providerVersion']) is int and value['providerVersion']==2 and value['transport']=='https' and value['tlsVersion'] in ('TLSv1.2','TLSv1.3') and type(value['internalErrors']) is int and value['internalErrors']==0);identifier(value['instance'])
        elif query['kind']=='preflight':source.concurrency_export(frame['response'],query,self.domain_policy)
        else:source.export(frame['response'],query)
        return frame
    def packet(self,index):
        frame=self.frame(index)
        return source.concurrency_export(frame['response'],frame['query'],self.domain_policy) if frame['query']['kind']=='preflight' else source.export(frame['response'],frame['query'])
    def qualified(self,index):
        frame=self.frame(index);need(self.timely(frame));return frame
    def timely(self,frame):
        span=frame['acquisition']
        if span['hostAfterMonotonic']-span['hostBeforeMonotonic']>=5:return False
        if frame['query']['kind'] in ('source','body','preflight'):
            packet=source.concurrency_export(frame['response'],frame['query'],self.domain_policy) if frame['query']['kind']=='preflight' else source.export(frame['response'],frame['query'])
            clock=packet['clockAfter'] if frame['query']['kind']=='body' else packet['clock']
            return span['hostBeforeEpochMs']-250<=clock['epochMs']<=span['hostAfterEpochMs']+250 and span['hostAfterEpochMs']-clock['epochMs']<=1500
        return True
    def load(self,value):
        exact(value,{'snapshotUploadBackendOwnerVersion','binding','runId','fixtureUrl','pins','payload'});rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(type(value['snapshotUploadBackendOwnerVersion']) is int and same(value,self.envelope()) and type(state['slots']) is list and len(state['slots'])<=64)
            labels=set();nonces=set();pending=False;previous_source=previous_preflight=None
            for index,slot in enumerate(state['slots'],1):
                exact(slot,{'label','query','phase','started','storage','proof'});need(type(slot['label']) is str and slot['label'] not in labels and not pending and slot['phase'] in ('reserved','issued','retained'))
                labels.add(slot['label']);self.query(slot['query']);need(slot['query']['requestId'] not in nonces);nonces.add(slot['query']['requestId']);pending=slot['phase']!='retained'
                if slot['phase']=='reserved':need(slot['started'] is slot['storage'] is slot['proof'] is None)
                else:
                    exact(slot['started'],{'hostBeforeEpochMs','hostBeforeMonotonic'});need(number(slot['started']['hostBeforeEpochMs'],1,1e15) and number(slot['started']['hostBeforeMonotonic'],0,1e15))
                if slot['storage'] is not None:self.frames().original(slot['storage']);need(slot['storage']['index']==index)
                if slot['phase']=='retained':
                    frame=self.frame(index);need(all(frame['acquisition'][key]==slot['started'][key] for key in slot['started']) and same(slot['proof'],self.frames().compact(slot['storage'])))
                    if slot['query']['kind']=='source':previous_source=source.accept(previous_source,self.packet(index))
                    if slot['query']['kind']=='preflight':previous_preflight=source.concurrency_accept(previous_preflight,self.packet(index))
                else:need(slot['proof'] is None)
            for key,kind in (('role','role'),('authority','authority'),('admission','source')):
                if state[key] is not None:need(self.qualified(state[key])['query']['kind']==kind)
            if self.version>=2 and state['preflight'] is not None:
                need(state['joined'] is not None and self.qualified(state['preflight'])['query']['kind']=='preflight'
                    and all(state[key] is not None and state[key]<state['preflight'] for key in ('role','authority','admission')))
            if state['scope'] is not None:
                first=next(index for index,slot in enumerate(state['slots'],1) if slot['phase']=='retained' and slot['query']['kind']=='source');need(same(state['scope'],self.scope(self.packet(first))))
                for index,slot in enumerate(state['slots'],1):
                    if slot['phase']=='retained' and slot['query']['kind'] in ('source','body','preflight'):
                        packet=self.packet(index);need(all(packet[key]==state['scope'][key] for key in ('instance','processId','clockDomain')))
                        if slot['query']['kind']=='preflight':need(same(self.scope(packet),state['scope']))
            if state['admission'] is not None:self.admitted()
            if state['joined'] is not None:need(same(state['joined'],self.join()))
            if self.version>=2 and state['preflightJoined'] is not None:need(same(state['preflightJoined'],self.preflight_join()))
            need(type(state['bodies']) is list and len(state['bodies'])<=16)
            for offset,index in enumerate(state['bodies']):
                packet=self.packet(index);need(packet['offset']==offset*source.PART and packet['upload']==state['joined']['upload']['instance'])
                if self.version>=2:need(state['preflightJoined'] is not None and index>state['preflight'])
            if state['result'] is not None:need(same(state['result'],self.proof()))
        finally:self.state=prior
        return deepcopy(state)
    def storage(self,kind,value):
        self.guard();need(kind=='original' and self.state['slots'] and self.state['slots'][-1]['phase']=='issued');slot=self.state['slots'][-1];self.frames().original(value);need(value['index']==len(self.state['slots']))
        old=slot['storage']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase']) and all(same(old[key],value[key]) for key in old if key not in ('phase','file')) and (old['phase']=='planned' or same(old['file'],value['file'])))
        slot['storage']=deepcopy(value);self.save();return True
    def path(self,query):
        if query['kind']=='role':return '/adapter-reader'
        if query['kind']=='authority':return '/account-provider'
        if query['kind']=='preflight':return '/runs/'+self.run+'/snapshots/preflight/original'
        return '/runs/'+self.run+'/snapshots/'+('source' if query['kind']=='source' else 'bodies/'+query['upload']+'/'+str(query['offset']))
    def sample(self,label,kind,*,upload=None,offset=None):
        need(not self.historical);self.guard();slots=self.state['slots'];found=[(index,row) for index,row in enumerate(slots,1) if row['label']==label]
        if found:
            index,slot=found[0];need(slot['query']['kind']==kind and slot['query']['upload']==upload and slot['query']['offset']==offset)
        else:
            need(len(slots)<64 and all(row['phase']=='retained' for row in slots));query=self.query(dict(snapshotUploadBackendQueryVersion=self.version,kind=kind,runId=self.run,requestId=uuid.uuid4().hex,upload=upload,offset=offset))
            slot=dict(label=label,query=query,phase='reserved',started=None,storage=None,proof=None);slots.append(slot);index=len(slots);self.save()
        if slot['phase']=='retained':return index
        if slot['phase']=='reserved':slot.update(phase='issued',started=dict(hostBeforeEpochMs=self.epoch_ms(),hostBeforeMonotonic=self.monotonic()));self.save()
        saved=slot['storage']
        if saved is not None:
            need(saved['phase'] in ('opened','saved'));frame=self.validate_frame(self.frames().read(saved),slot['query'])
            if saved['phase']=='opened':self.storage('original',dict(saved,phase='saved'))
            proof=self.frames().compact(slot['storage'])
        else:
            query=slot['query'];self.guard();response=self.client.request(self.path(query),method='GET',adapter_access=True,snapshot_nonce=query['requestId'] if kind in ('source','body','preflight') else None)
            frame=dict(query=deepcopy(query),response=response,acquisition=dict(slot['started'],hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic()));self.validate_frame(frame,query)
            proof=self.frames(True).write(index,frame)
        slot.update(phase='retained',proof=proof);self.save();return index
    @staticmethod
    def scope(packet):return {key:deepcopy(packet[key]) for key in ('instance','processId','clockDomain','accountProvider','accountRun','principalSha256','created')}
    def admitted(self):
        need(self.state['role'] is not None and self.state['authority'] is not None and self.state['admission'] is not None and self.state['scope'] is not None)
        self.qualified(self.state['role']);authority=self.qualified(self.state['authority'])['response'];packet=self.packet(self.state['admission']);self.qualified(self.state['admission'])
        need(same(self.scope(packet),self.state['scope']) and packet['accountProvider']==authority['instance']);return packet
    def join(self):
        packet=self.admitted();native_packet=self.native.packet('uploads',self.native.state['decision']);file=self.native.file
        joined=source.joined(packet,native_packet,self.native.state['job'],file,self.fixture_url)
        requests={row['instance']:row for row in packet['requests']};need(all(requests[joined[key]['request']]['ticket']==self.native.state['ticket'] for key in ('upload','story')));return joined
    @operation
    def admit(self):
        need(not self.historical);self.guard()
        for key in ('role','authority'):
            if self.state[key] is None:self.state[key]=self.sample(key,key);self.qualified(self.state[key]);self.save()
        while self.state['admission'] is None:
            earlier=[(index,slot) for index,slot in enumerate(self.state['slots'],1) if slot['label']=='admission' or slot['label'].startswith('admission-')]
            if earlier and (earlier[-1][1]['phase']!='retained' or self.timely(self.frame(earlier[-1][0]))):label=earlier[-1][1]['label']
            else:label='admission' if not earlier else 'admission-'+str(len(earlier)+1)
            index=self.sample(label,'source');packet=self.packet(index)
            if self.state['scope'] is None:self.state['scope']=self.scope(packet);self.save()
            else:need(same(self.scope(packet),self.state['scope']))
            previous=[number for number,slot in earlier if number<index and slot['phase']=='retained']
            if previous:source.accept(self.packet(previous[-1]),packet)
            if not self.timely(self.frame(index)):continue
            self.state['admission']=index;self.save()
        joined=self.join();self.state['joined']=joined;self.save()
        if self.version>=2:self.admit_preflight()
        return deepcopy(joined)
    def preflight_join(self):
        need(self.version>=2 and self.state['preflight'] is not None and self.state['joined'] is not None)
        self.qualified(self.state['preflight']);packet=self.packet(self.state['preflight']);backend=self.admitted();source.after(packet['clock'],backend['clock'])
        return source.concurrency_joined(packet,backend,self.state['joined'],self.native.state['ticket'])
    def admit_preflight(self):
        need(self.version>=2 and not self.historical)
        while self.state['preflight'] is None:
            earlier=[(index,slot) for index,slot in enumerate(self.state['slots'],1) if slot['label']=='preflight' or slot['label'].startswith('preflight-')]
            if earlier and (earlier[-1][1]['phase']!='retained' or self.timely(self.frame(earlier[-1][0]))):label=earlier[-1][1]['label']
            else:label='preflight' if not earlier else 'preflight-'+str(len(earlier)+1)
            index=self.sample(label,'preflight');packet=self.packet(index);need(same(self.scope(packet),self.state['scope']))
            previous=[number for number,slot in earlier if number<index and slot['phase']=='retained']
            if previous:source.concurrency_accept(self.packet(previous[-1]),packet)
            if not self.timely(self.frame(index)):continue
            self.state['preflight']=index;self.save()
        self.state['preflightJoined']=self.preflight_join();self.save()
    def proof(self):
        need(self.state['joined'] is not None and same(self.state['joined'],self.join()) and digest(self.native.proof())==self.pins['nativeUploadResultSha256'])
        upload=self.state['joined']['upload'];raw=[];expected=upload['file']
        need(len(self.state['bodies'])==(expected['bytes']+source.PART-1)//source.PART)
        previous_clock=self.admitted()['clock']
        if self.version>=2:
            preflight_clock=self.packet(self.state['preflight'])['clock'];source.after(preflight_clock,previous_clock);previous_clock=preflight_clock
        for offset,index in enumerate(self.state['bodies']):
            packet=self.packet(index);need(packet['upload']==upload['instance'] and packet['offset']==offset*source.PART and packet['totalBytes']==expected['bytes'] and packet['sha256']==expected['sha256']
                and all(packet[key]==self.state['scope'][key] for key in ('instance','processId','clockDomain')));source.after(packet['clockBefore'],previous_clock);previous_clock=packet['clockAfter'];raw.append(base64.b64decode(packet['data'],validate=True))
        actual=b''.join(raw);artifact=self.native.capture.history('artifact',self.native.capture.state['artifact'])
        need(actual==artifact.read() and len(actual)==expected['bytes'] and hashlib.sha256(actual).hexdigest()==expected['sha256'])
        result=dict(snapshotUploadBackendResultVersion=self.version,runId=self.run,binding=self.binding,pins=self.pins,scope=self.state['scope'],upload=upload['instance'],story=self.state['joined']['story']['id'],file=expected,
            authenticatedProtocolOriginalJoined=True,backendBodyOriginalRetained=True,readOnlyRoleAdmitted=True,backendServiceProcessAdmissionRequired=True,
            renderedReviewRequired=True,backendFixtureRetirementRequired=True,sourceJournalRetirementRequired=True,transportProcessProofRequired=True,wholeFeatureRequired=True)
        if self.version>=2:
            preflight=self.preflight_join();need(same(preflight,self.state['preflightJoined']))
            result.update(controlledDomainPreflightOriginalJoined=True,domainPolicy=deepcopy(self.domain_policy),preflight=preflight,frontendResponseConsumptionRequired=True,externalMetaverseRegistrationRequired=True)
        if self.version==3:
            from ios.adapters.snapshot_frontend_consumption import joined
            result.update(frontendResponseConsumptionRequired=False,frontendConsumption=joined(self),frontendBranchAcceptanceRequired=True)
        return result
    @operation
    def original(self):
        need(not self.historical);self.guard()
        if self.state['result'] is not None:return self.proof()
        if self.state['joined'] is None:self.admit()
        if self.version>=2 and self.state['preflightJoined'] is None:self.admit_preflight()
        upload=self.state['joined']['upload'];total=upload['file']['bytes']
        while len(self.state['bodies'])*source.PART<total:
            offset=len(self.state['bodies'])*source.PART;index=self.sample('body-'+str(offset),'body',upload=upload['instance'],offset=offset);self.state['bodies'].append(index);self.save()
        result=self.proof();self.state['result']=deepcopy(result);self.save();return result


@contextmanager
def backend_context(runtime,selector,run,client,binding,*,epoch_ms,monotonic,sleep,domain_policy=None,combined=False,frontend_http=False):
    """Reopen exact original main binding; no SDK, native input or OS getter."""
    need(type(combined) is type(frontend_http) is bool and (not frontend_http or combined))
    lock=ScriptSourceLock(runtime.state_path(selector).with_name('script-feature-sources.lock'))
    with lock.held():
        native=IOSSnapshotUploadOwner.history(PrivateFeatureState(lock.path.with_name('snapshot-upload-owner.json')),lock,binding,run,client.url+'/runs/'+run+'/',combined=combined,frontend_http=frontend_http)
        yield IOSSnapshotUploadBackendOwner(native,client,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep,domain_policy=domain_policy)
