"""Once-only extension queries, exact source JSON and independent quiet clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from adapters.native_clock_join import digest
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner
from ios.adapters.snapshot_share_archive_runtime import IOSSnapshotShareArchiveRuntime
from ios.adapters import snapshot_share_process as source,snapshot_share_original as receiver_source


class ShareExtensionQueryPending(NativeUIError):pass


def host_clock(value,previous=None):
    exact(value,{'epochMs','monotonicMs'});need(number(value['epochMs'],1,1e15) and number(value['monotonicMs'],0,1e15))
    if previous is not None:need(value['epochMs']>=previous['epochMs'] and value['monotonicMs']>=previous['monotonicMs']
        and abs(value['epochMs']-previous['epochMs']-(value['monotonicMs']-previous['monotonicMs']))<=250)
    return value


class SnapshotShareQueryOwner:
    def __init__(self,ctx,lock,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(ctx,source.SnapshotShareArchiveContext) and isinstance(lock,ScriptSourceLock)
            and ctx.admission.lock is lock and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.ctx,self.lock,self.historical=ctx,lock,False
        self.binding,self.run,self.fixture_url=deepcopy(context(ctx.binding)),identifier(ctx.admission.run),ctx.admission.fixture_url
        self.artifact,self.os_scope,self.admission=deepcopy(ctx.artifact),deepcopy(ctx.os_scope),ctx.admission
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep;self.setup()

    @classmethod
    def history(cls,store,lock,binding,run,fixture_url,artifact_path,admission_store):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result=object.__new__(cls);result.ctx=None;result.lock=lock;result.historical=True;result.monotonic=time.monotonic
        result.binding,result.run,result.fixture_url=deepcopy(context(binding)),identifier(run),fixture_url
        result.admission=IOSSnapshotShareAdmissionOwner.archive(admission_store,lock,binding,run,fixture_url,artifact_path)
        result.admission.result();result.artifact,result.os_scope=deepcopy(result.admission.artifact),deepcopy(result.admission.os_scope)
        result.setup(store);need(result.previous is not None);return result

    def setup(self,store=None):
        self.lock.assert_held();root=self.admission.store.path.parent
        self.store=store or PrivateFeatureState(root/'snapshot-share-query-owner.json')
        need(self.store.path==root/'snapshot-share-query-owner.json' and self.lock.path==root/'script-feature-sources.lock')
        self.admission.result();self.admission_hash=digest(self.admission.previous);self.previous=self.store.read()
        self.state=dict(queries=[],anchorQuery=None,receiver=dict(wire=None,proof=None),quiet=[])
        self.frames=OriginalFrameStore(root,self.binding,self.run,'primary',self.local_check,self.intent,
            namespace='share-extension-query',schema_prefix='shareExtensionQuery')
        self.receiver_files=OriginalFrameStore(root,self.binding,self.run,'primary',self.local_check,self.receiver_intent,
            namespace='share-extension-receiver',schema_prefix='shareExtensionReceiver')
        if self.previous is not None:self.state=self.load(self.previous)
        else:self.inventory(set())

    def local_check(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous));self.admission.bound();return True
    def check(self):
        self.local_check()
        if not self.historical:self.ctx.probe()
        return True
    def stamp(self):return host_clock(dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000))
    def envelope(self):return dict(snapshotShareQueryOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,
        admissionSha256=self.admission_hash,osScope=self.os_scope,payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.check();value=self.envelope();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def inventory(self,paths):
        for path in self.store.path.parent.iterdir():
            if path.name.startswith(('share-extension-query-','share-extension-receiver-')):need(path in paths)
            if path.name.startswith('snapshot-share-query-'):need(path==self.store.path)

    def frame(self,row,previous=None):
        ref=row['wire'] if row['proof'] is None else self.frames.expand(row['proof']);need(ref is not None)
        value=self.frames.read(ref);exact(value,{'snapshotShareQueryFrameVersion','commandId','retired','original','hostBefore','hostAfter'})
        need(type(value['snapshotShareQueryFrameVersion']) is int and value['snapshotShareQueryFrameVersion']==1
            and value['commandId']==row['nonce'] and type(value['retired']) is bool and value['retired']==row['retired']
            and same(value['hostBefore'],row['before']))
        host_clock(value['hostBefore']);host_clock(value['hostAfter'],value['hostBefore'])
        packet=source.stored_original(value['original'],row['nonce'],self.artifact,self.os_scope['source'],previous)
        need(packet is not None and packet['kind']==('retired' if row['retired'] else 'live'))
        need(packet['clockAfter']['monotonicMs']-packet['clockBefore']['monotonicMs']<=value['hostAfter']['monotonicMs']-value['hostBefore']['monotonicMs']+250)
        return value,packet
    def query_original(self,index):
        need(integer(index,1,len(self.state['queries'])));row=self.state['queries'][index-1];need(row['proof'] is not None)
        return self.frame(row)[1]
    def receiver(self):
        row=self.state['receiver'];ref=row['wire'] if row['proof'] is None else self.receiver_files.expand(row['proof']);need(ref is not None)
        value=self.receiver_files.read(ref);exact(value,{'snapshotShareReceiverFrameVersion','raw','hostBefore','hostAfter'})
        need(type(value['snapshotShareReceiverFrameVersion']) is int and value['snapshotShareReceiverFrameVersion']==1
            and type(value['raw']) is str and len(value['raw'])<=349528)
        host_clock(value['hostBefore']);host_clock(value['hostAfter'],value['hostBefore'])
        raw=base64.b64decode(value['raw'],validate=True);need(base64.b64encode(raw).decode()==value['raw'] and 1<=len(raw)<=262144)
        packet=decode(raw.decode('utf-8'));receiver_source.original(packet)
        need(packet['runId']==self.run and packet['phase']=='complete' and packet['events'][-1]['kind']=='finish-issued'
            and self.state['anchorQuery'] is not None)
        source.receiver_anchor(self.query_original(self.state['anchorQuery']),packet,self.artifact,self.os_scope['source']);return packet,raw
    def load(self,value):
        exact(value,{'snapshotShareQueryOwnerVersion','binding','runId','fixtureUrl','admissionSha256','osScope','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['snapshotShareQueryOwnerVersion']) is int and value['snapshotShareQueryOwnerVersion']==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()) and type(state['queries']) is list and len(state['queries'])<=128
                and type(state['quiet']) is list and len(state['quiet'])<=3)
            exact(state['receiver'],{'wire','proof'});paths=set();labels=set();nonces=set();previous=None;first_anchor=None
            for at,row in enumerate(state['queries'],1):
                exact(row,{'index','label','nonce','retired','phase','before','wire','proof'})
                need(type(row['index']) is int and row['index']==at and type(row['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',row['label'])
                    and row['label'] not in labels and type(row['nonce']) is str and re.fullmatch('ios-[a-f0-9]{32}',row['nonce']) and row['nonce'] not in nonces
                    and type(row['retired']) is bool and row['phase'] in ('reserved','issued','retained'))
                labels.add(row['label']);nonces.add(row['nonce'])
                if row['phase']=='reserved':need(row['before'] is None and row['wire'] is None and row['proof'] is None)
                else:host_clock(row['before'])
                if row['wire'] is not None:
                    self.frames.original(row['wire']);need(row['wire']['index']==at and row['phase']=='issued' and row['proof'] is None);paths.add(self.frames.path(row['wire']))
                    if row['wire']['phase']!='planned':self.frame(row,previous)
                if row['proof'] is not None:
                    ref=self.frames.expand(row['proof']);need(ref['index']==at and row['wire'] is None and row['phase']=='retained');paths.add(self.frames.path(ref))
                    frame,packet=self.frame(row,previous);previous=packet
                    if packet['anchor'] is not None and first_anchor is None:
                        need(not row['retired'] and packet['anchor']['sequence']==packet['sequence']);first_anchor=at
                else:need(row['phase']!='retained' and at==len(state['queries']))
            need(state['anchorQuery']==first_anchor and (first_anchor is None or type(state['anchorQuery']) is int))
            recv=state['receiver']
            if recv['wire'] is not None:
                self.receiver_files.original(recv['wire']);need(recv['wire']['index']==1 and recv['proof'] is None);paths.add(self.receiver_files.path(recv['wire']))
                if recv['wire']['phase']!='planned':self.receiver()
            if recv['proof'] is not None:
                ref=self.receiver_files.expand(recv['proof']);need(ref['index']==1 and recv['wire'] is None);paths.add(self.receiver_files.path(ref));self.receiver()
            old_index=0
            for index in state['quiet']:
                need(integer(index,old_index+1,len(state['queries'])));old_index=index;self.qualified(index)
                source.absent(self.query_original(index),self.receiver()[0],self.artifact,self.os_scope['source'])
            if len(state['quiet'])==3:self.quiet_result()
            self.inventory(paths)
        finally:self.state=prior
        return deepcopy(state)

    def transition(self,files,old,value,index):
        files.original(value);need(value['index']==index)
        if old is None:need(value['phase']=='planned')
        else:
            need((old['phase'],value['phase']) in (('planned','opened'),('opened','saved'))
                and all(same(old[key],value[key]) for key in old if key not in ('phase','file'))
                and (old['file'] is None or same(old['file'],value['file'])))
    def intent(self,kind,value):
        need(kind=='original');row=self.state['queries'][-1];need(row['phase']=='issued' and row['proof'] is None)
        self.transition(self.frames,row['wire'],value,row['index']);row['wire']=deepcopy(value);self.save()
    def receiver_intent(self,kind,value):
        need(kind=='original');row=self.state['receiver'];need(row['proof'] is None)
        self.transition(self.receiver_files,row['wire'],value,1);row['wire']=deepcopy(value);self.save()
    def qualified(self,index):
        need(integer(index,1,len(self.state['queries'])));frame,packet=self.frame(self.state['queries'][index-1])
        need(frame['hostAfter']['epochMs']-frame['hostBefore']['epochMs']<5500
            and frame['hostAfter']['monotonicMs']-frame['hostBefore']['monotonicMs']<5500);return packet

    @operation
    def query(self,label,*,retired=False):
        need(not self.historical and type(retired) is bool and type(label) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',label));self.check()
        rows=[row for row in self.state['queries'] if row['label']==label]
        if rows:row=rows[0];need(row['retired']==retired)
        else:
            need(len(self.state['queries'])<128 and (not self.state['queries'] or self.state['queries'][-1]['phase']=='retained'))
            row=dict(index=len(self.state['queries'])+1,label=label,nonce='ios-'+uuid.uuid4().hex,retired=retired,phase='reserved',before=None,wire=None,proof=None)
            self.state['queries'].append(row);self.save()
        if row['proof'] is not None:return self.query_original(row['index'])
        previous=None if row['index']==1 else self.query_original(row['index']-1)
        if row['phase']=='reserved':
            row['phase']='issued';row['before']=self.stamp();self.save()
            self.ctx.extension_query(row['nonce'],retired=retired,previous=previous)
        if row['wire'] is None:
            original=self.ctx.extension_original(row['nonce'],previous=previous)
            if source.stored_original(original,row['nonce'],self.artifact,self.os_scope['source'],previous) is None:
                raise ShareExtensionQueryPending('Original extension query remains unresolved')
            frame=dict(snapshotShareQueryFrameVersion=1,commandId=row['nonce'],retired=retired,original=original,hostBefore=deepcopy(row['before']),hostAfter=self.stamp())
            row['proof']=self.frames.write(row['index'],frame)
        else:
            self.frame(row,previous);wire=row['wire'];need(wire['phase'] in ('opened','saved'))
            if wire['phase']=='opened':self.intent('original',dict(wire,phase='saved'));wire=row['wire']
            row['proof']=self.frames.compact(wire)
        row['wire']=None;row['phase']='retained';packet=self.query_original(row['index'])
        if packet['anchor'] is not None and self.state['anchorQuery'] is None:
            need(not retired and packet['anchor']['sequence']==packet['sequence']);self.state['anchorQuery']=row['index']
        self.save();return deepcopy(packet)

    @operation
    def bind_receiver(self,archive):
        need(not self.historical and isinstance(archive,IOSSnapshotShareArchiveRuntime) and same(archive.binding,self.binding)
            and same(archive.artifact,self.artifact) and archive.archive_admission.lock is self.lock
            and same(archive.archive_admission.previous,self.admission.previous));self.check()
        row=self.state['receiver']
        if row['proof'] is not None:return self.receiver()[0]
        need(self.state['anchorQuery'] is not None)
        if row['wire'] is None:
            before=self.stamp();raw=archive.original_path('snapshot-share-'+self.run+'/original-extension.json',262144)
            frame=dict(snapshotShareReceiverFrameVersion=1,raw=base64.b64encode(raw).decode(),hostBefore=before,hostAfter=self.stamp())
            row['proof']=self.receiver_files.write(1,frame)
        else:
            self.receiver();wire=row['wire'];need(wire['phase'] in ('opened','saved'))
            if wire['phase']=='opened':self.receiver_intent('original',dict(wire,phase='saved'));wire=row['wire']
            row['proof']=self.receiver_files.compact(wire)
        row['wire']=None;packet=self.receiver()[0];self.save();return packet

    def quiet_result(self):
        need(len(self.state['quiet'])==3);frames=[];packets=[];receiver=self.receiver()[0]
        for index in self.state['quiet']:
            frames.append(self.frame(self.state['queries'][index-1])[0]);packet=self.qualified(index)
            source.absent(packet,receiver,self.artifact,self.os_scope['source']);packets.append(packet)
        host_a,host_b=frames[0]['hostAfter'],frames[-1]['hostBefore'];host_clock(host_b,host_a)
        node_a,node_b=packets[0]['clockAfter'],packets[-1]['clockBefore'];source.stamp(node_b,node_a)
        need(min(host_b['epochMs']-host_a['epochMs'],host_b['monotonicMs']-host_a['monotonicMs'],
            node_b['epochMs']-node_a['epochMs'],node_b['monotonicMs']-node_a['monotonicMs'])>=3000)
        return dict(snapshotShareExtensionQuietVersion=1,runId=self.run,receiverSha256=digest(receiver),originalPid=receiver['processId'],
            queryIndices=deepcopy(self.state['quiet']),nodeMilliseconds=node_b['monotonicMs']-node_a['monotonicMs'],
            hostMilliseconds=host_b['monotonicMs']-host_a['monotonicMs'],historicalOriginalsOnly=True,
            filesystemRetirementRequired=True,wholeFeatureRequired=True)

    @operation
    def quiet(self):
        need(not self.historical and self.state['receiver']['proof'] is not None);self.check()
        while len(self.state['quiet'])<3:
            if self.state['quiet']:self.sleep(1.6)
            rows=self.state['queries'];last=rows[-1] if rows else None
            label=last['label'] if last is not None and last['phase']!='retained' and last['label'].startswith('quiet-') else 'quiet-'+str(len(rows)+1)
            packet=self.query(label,retired=True);index=self.state['queries'][-1]['index'];self.qualified(index)
            try:source.absent(packet,self.receiver()[0],self.artifact,self.os_scope['source'])
            except NativeUIError:raise ShareExtensionQueryPending('Original extension process remains present or unknown') from None
            self.state['quiet'].append(index);self.save()
        return self.quiet_result()
