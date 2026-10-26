"""Once-only ordinary UIKit inputs retaining actual immutable DOM ownership.

Input ACKs remain delivery metadata. Native UIKit/DOM/key/view originals are
required separately for effects and retirement. No session is created here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError,NativeUI
from adapters.original_frame_store import OriginalFrameStore
from adapters.original_file_reads import record as original_read
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import same,canonical
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.adapters.tablet_web_native_input import TabletWebNativeInput,input_text
from ios.adapters.tablet_web_presentation import point as projected_point
from ios.adapters.tablet_web_segments import sha

VERSION=1
MAX_INPUTS=128


class TabletWebInputs:
    def __init__(self,client,source,reader,lock,clock_ms,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000),historical=False):
        need(isinstance(source,TabletWebPackets) and source.component=='dom' and type(historical) is bool and source.historical==historical
            and isinstance(lock,ScriptSourceLock) and callable(clock_ms))
        lock.assert_held();need(lock.path==source.root/'script-feature-sources.lock')
        self.source,self.reader,self.lock=source,reader,lock
        self.root,self.binding,self.run,self.role=source.root,source.binding,source.run,source.role
        self.monotonic,self.epoch_ms,self.clock_ms=monotonic,epoch_ms,clock_ms;self.historical=historical
        self.store=PrivateFeatureState(self.root/('tabletweb-inputs-'+self.run+'-'+self.role+'.json'))
        self._release_context=(lock,self.store,self.root,deepcopy(self.binding),self.run,self.role)
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,source.guard,self.storage_intent,
            namespace='tabletweb-input',schema_prefix='tabletWebInput',kind='inputs',monotonic=monotonic)
        self.ui=None if historical else TabletWebNativeInput(client,self.binding,clock_ms,self.bound,self.input_intent)
        self.state=self.store.read()
        if self.state is None:
            need(not historical)
            self.state=dict(tabletWebInputsVersion=VERSION,binding=deepcopy(self.binding),runId=self.run,role=self.role,records=[],pending=None,original=None)
            self.store.write(self.state,None)
        self.saved=deepcopy(self.state);self.failed=False;self.decode()

    def bound(self):
        lock,store,root,binding,run,role=self._release_context
        lock.assert_held();need(self.lock is lock and self.store is store and self.root==root and same(self.binding,binding)
            and self.run==run and self.role==role and not self.historical and not self.failed
            and self.source.guard() is not False and same(store.read(),self.saved));return True

    def save(self):
        self.bound();self.store.write(self.state,self.saved);need(same(self.store.read(),self.state));self.saved=deepcopy(self.state)

    def stamp(self):
        value=dict(epochMs=self.epoch_ms(),monotonic=self.monotonic());self.clock(value);return value

    @staticmethod
    def clock(value,previous=None):
        exact(value,{'epochMs','monotonic'});need(integer(value['epochMs'],1) and number(value['monotonic'],0,1e15))
        if previous is not None:need(value['epochMs']>=previous['epochMs'] and value['monotonic']>=previous['monotonic'])
        return value

    def document(self,row):
        need(row['sourceRef'] is not None and integer(row['sourceIndex'],1,len(self.source.state['records'])))
        original=self.source.state['records'][row['sourceIndex']-1];need(same(original,row['sourceRef']))
        record=self.source.originals.read(self.source.originals.expand(original));need(record['status']=='returned')
        _,values=self.source.record(record,row['sourceIndex'],None);need(values)
        document=values[-1];need(sha(canonical(document))==row['sourceSha256'] and document['status']=='ready');return document,record

    def record(self,row,index):
        exact(row,{'tabletWebInputVersion','index','ticket','label','kind','control','text','phase','sourceIndex','sourceRef','sourceSha256','events','before','after'})
        need(type(row['tabletWebInputVersion']) is int and row['tabletWebInputVersion']==VERSION and type(row['index']) is int and row['index']==index)
        identifier(row['ticket']);need(type(row['label']) is str and re.fullmatch('[a-z][a-z0-9-]{0,63}',row['label'])
            and row['kind'] in ('tap','replace') and type(row['control']) is str and row['phase'] in ('reading','prepared','issued','returned','failed')
            and type(row['events']) is list and len(row['events'])<=3)
        if row['kind']=='tap':need(row['text'] is None)
        else:input_text(row['control'],row['text'])
        self.clock(row['before']);need(row['after'] is None or self.clock(row['after'],row['before']))
        need(integer(row['sourceIndex'],1,MAX_INPUTS))
        if row['sourceRef'] is None:need(row['sourceSha256'] is None and not row['events'] and row['phase'] in ('reading','failed'))
        else:
            document,capture=self.document(row);self.clock(capture['before'],row['before']);need(capture['after'] is not None)
            need(any(element['id']==row['control'] for element in document['source']['dom']['elements']))
        seen=set();previous=capture['after'] if row['sourceRef'] is not None else row['before'];unknown=False;touch=None;release=False
        if row['kind']=='replace' and row['sourceRef'] is not None:
            fields=[element for element in document['source']['dom']['elements'] if element['id']==row['control']];need(len(fields)==1)
            planned=(['clear'] if fields[0]['value'] else [])+(['text'] if row['text'] else [])
            kinds=[event.get('request',{}).get('kind') for event in row['events']]
            need(kinds==planned[:len(kinds)] and (row['phase']!='returned' or kinds==planned))
        for event in row['events']:
            exact(event,{'request','issued','returned'});request=event['request']
            exact(request,{'tabletWebNativeInputVersion','id','kind','path','body','ownership'})
            identifier(request['id']);need(request['id'] not in seen and type(request['tabletWebNativeInputVersion']) is int and request['tabletWebNativeInputVersion']==1)
            seen.add(request['id']);self.clock(event['issued'],previous);previous=event['issued']
            if event['returned'] is not None:self.clock(event['returned'],previous);previous=event['returned']
            need(not unknown or request['kind']=='release');unknown=event['returned'] is None
            owner=request['ownership']
            common={'nativeView','domInstance','nativeCapturedEpochMs','requestId','birth','point'}
            exact(owner,common|({'element'} if row['kind']=='tap' else {'field','elementReference','type','accessibilityLabel','rect','beforeTextSha256'}))
            need(row['sourceRef'] is not None and owner['requestId']==document['commandId']
                and owner['nativeCapturedEpochMs']==document['clockAfter']['epochMs'] and same(owner['nativeView'],document['source']['nativeView'])
                and owner['domInstance']==document['source']['dom']['instance'])
            elements=[element for element in document['source']['dom']['elements'] if element['id']==row['control']];need(len(elements)==1)
            element=elements[0];need(owner['birth']==element['birth'] and element['visible'] and element['enabled'])
            point=projected_point(document['source']['presentationAfter'],document['source']['dom']['document'],element)
            if row['kind']=='tap':
                need(request['kind'] in ('touch','release') and request['path']=='/actions' and owner['element']==row['control']
                    and same(owner['point'],[round(value) for value in point]))
                if request['kind']=='touch':
                    need(touch is None and not release);touch=event
                    body=request['body'];exact(body,{'actions'});need(type(body['actions']) is list and len(body['actions'])==1)
                    pointer=body['actions'][0];need(type(pointer) is dict and type(pointer.get('id')) is str and re.fullmatch('tablet-web-[0-9a-f]{32}',pointer['id']))
                    need(same(body,dict(actions=[dict(type='pointer',id=pointer['id'],parameters=dict(pointerType='touch'),actions=[
                        dict(type='pointerMove',duration=0,origin='viewport',x=owner['point'][0],y=owner['point'][1]),dict(type='pointerDown',button=0),
                        dict(type='pause',duration=80),dict(type='pointerUp',button=0)])])))
                else:need(touch is not None and not release and request['body'] is None);release=True;need(same(owner,touch['request']['ownership']))
            else:
                need(request['kind'] in ('clear','text') and owner['field']==row['control'] and row['control'] in ('text','foreign')
                    and owner['type']=='XCUIElementTypeTextField' and owner['accessibilityLabel']==element['accessibilityLabel']
                    and element['accessibilityLabel'] and element['focused'] and same(owner['point'],point)
                    and document['source']['presentationAfter']['responders']
                    and owner['beforeTextSha256']==hashlib.sha256(element['value'].encode()).hexdigest())
                native_element=NativeUI._element(owner['elementReference'])
                need(request['path']==native_element+('/clear' if request['kind']=='clear' else '/value'))
                expected=TabletWebNativeInput.screen_rect(document['source'],element);exact(owner['rect'],{'x','y','width','height'})
                need(all(number(owner['rect'][key],-1e6,1e6) and abs(owner['rect'][key]-expected[key])<=2 for key in expected))
                if request['kind']=='clear':need(event is row['events'][0] and request['body']=={} and element['value'])
                else:need(same(request['body'],dict(text=row['text'],value=list(row['text']))))
        if row['after'] is not None:self.clock(row['after'],previous)
        if row['phase']=='returned':need(row['sourceRef'] is not None and row['after'] is not None
            and all(event['returned'] is not None for event in row['events']) and (row['kind']!='tap' or touch is not None and release))
        return row

    def decode(self):
        self.source.history();value=self.state
        exact(value,{'tabletWebInputsVersion','binding','runId','role','records','pending','original'})
        need(type(value['tabletWebInputsVersion']) is int and value['tabletWebInputsVersion']==VERSION and same(value['binding'],self.binding)
            and value['runId']==self.run and value['role']==self.role and type(value['records']) is list and len(value['records'])<=MAX_INPUTS)
        self.records=[];keys=set();source_index=0;last_clock=None;self.blocked=False
        for index,ref in enumerate(value['records'],1):
            original=self.originals.expand(ref);need(ref['index']==index);row=self.record(self.originals.read(original),index)
            need(row['phase'] in ('returned','failed'));key=(row['ticket'],row['label']);need(key not in keys and row['sourceIndex']>source_index)
            self.clock(row['before'],last_clock);need(row['after'] is not None);last_clock=row['after']
            keys.add(key);source_index=row['sourceIndex'];self.records.append(row);self.blocked|=row['phase']=='failed'
        if value['pending'] is not None:
            row=self.record(value['pending'],len(self.records)+1);self.clock(row['before'],last_clock);need((row['ticket'],row['label']) not in keys and row['sourceIndex']>source_index)
        if value['original'] is not None:
            ref=self.originals.original(value['original']);need(value['pending'] is not None and ref['index']==len(self.records)+1)
            self.inspect_original()
        return deepcopy(self.records)

    def inspect_original(self):
        reference=self.originals.original(self.state['original']);path=self.originals.path(reference)
        if reference['phase']=='planned':need(not os.path.lexists(path));return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),reference);raw=stream.read(reference['bytes']+1);self.originals.file(path,stream.fileno(),reference)
        need(len(raw)<=reference['bytes']);original_read(path)
        complete=len(raw)==reference['bytes'] and sha(raw)==reference['sha256']
        if reference['phase']=='saved':need(complete)
        return dict(bytes=len(raw),sha256=sha(raw),complete=complete)

    def recover_record(self):
        self.bound();self.decode();reference=self.state['original'];need(reference is not None and reference['phase'] in ('opened','saved'))
        row=self.originals.read(reference);need(same(row,self.state['pending']) and row['phase'] in ('returned','failed'))
        self.record(row,len(self.state['records'])+1)
        self.state['records'].append(self.originals.compact(dict(reference,phase='saved')))
        self.state['pending']=self.state['original']=None;self.save();return deepcopy(self.state['records'][-1])

    def abort_pending(self):
        """Archive the confirmed interrupted input as failed, never resend it.

        Current original admission is required again. Source-query ownership
        and unknown request returns remain verbatim; this produces no effect
        or cleanup fact and never relabels a known completed original.
        """
        self.bound();self.state=deepcopy(self.saved);self.decode()
        if self.state['pending'] is None:return None
        need(self.state['original'] is None and self.state['pending']['phase'] in ('reading','prepared','issued','failed'))
        row=deepcopy(self.state['pending']);row['phase']='failed'
        # Existing after is original host delivery/failure metadata. Only an
        # unknown boundary receives this call's administrative closure time.
        if row['after'] is None:row['after']=self.stamp()
        self.record(row,len(self.state['records'])+1);self.state['pending']=row;self.save()
        reference=self.archive();self.decode();return reference

    def release_intent(self,phase,request):
        """Only the original touch's release WAL survives lost live continuity.

        This changes no source/input authority and accepts no new touch. The
        confirmed old intent, exact held lock and private CAS remain required.
        """
        need(not self.historical and phase in ('issued','returned'))
        lock,store,root,binding,run,role=self._release_context;lock.assert_held()
        need(lock.path==root/'script-feature-sources.lock' and same(store.read(),self.saved)
             and same(self.state,self.saved) and same(self.saved['binding'],binding)
             and self.saved['runId']==run and self.saved['role']==role)
        exact(request,{'tabletWebNativeInputVersion','id','kind','path','body','ownership'})
        need(type(request['tabletWebNativeInputVersion']) is int and request['tabletWebNativeInputVersion']==1
             and request['kind']=='release' and request['path']=='/actions' and request['body'] is None)
        identifier(request['id']);value=deepcopy(self.saved);pending=value['pending']
        need(type(pending) is dict and pending['kind']=='tap' and pending['phase']=='issued')
        events=pending['events'];need(events and events[0]['request']['kind']=='touch'
            and events[0]['request']['path']=='/actions' and same(events[0]['request']['ownership'],request['ownership']))
        if phase=='issued':
            need(len(events)==1 and request['id']!=events[0]['request']['id'])
            issued=self.stamp();self.clock(issued,events[0]['returned'] or events[0]['issued'])
            events.append(dict(request=deepcopy(request),issued=issued,returned=None))
        else:
            need(len(events)==2 and same(events[-1]['request'],request) and events[-1]['returned'] is None)
            returned=self.stamp();self.clock(returned,events[-1]['issued']);events[-1]['returned']=returned
        store.write(value,self.saved);need(same(value,store.read()))
        # Keep the same pending object held by perform(); only its confirmed
        # release fields changed. No failed/unknown request is replayed.
        self.state['pending'].clear();self.state['pending'].update(deepcopy(pending));self.saved=deepcopy(value)

    def input_intent(self,phase,request):
        if type(request) is dict and request.get('kind')=='release':return self.release_intent(phase,request)
        self.bound();need(phase in ('issued','returned'));pending=self.state['pending'];need(pending is not None)
        if phase=='issued':
            need(len(pending['events'])<3 and not any(row['request']['id']==request['id'] for row in pending['events']))
            pending['events'].append(dict(request=deepcopy(request),issued=self.stamp(),returned=None));pending['phase']='issued'
        else:
            rows=[row for row in pending['events'] if row['request']['id']==request['id']];need(len(rows)==1 and rows[0]['returned'] is None
                and same(rows[0]['request'],request));rows[0]['returned']=self.stamp()
        self.save()

    def storage_intent(self,kind,reference):
        self.bound();need(kind=='original' and self.state['pending'] is not None);self.originals.original(reference)
        need(reference['index']==len(self.state['records'])+1);self.state['original']=deepcopy(reference);self.save()

    def archive(self):
        row=self.state['pending'];need(row is not None and row['phase'] in ('returned','failed') and self.state['original'] is None)
        ref=self.originals.write(row['index'],row);self.state['records'].append(ref);self.state['pending']=self.state['original']=None;self.save();return deepcopy(ref)

    def perform(self,ticket,label,kind,control,*,text=None):
        self.bound();identifier(ticket);self.decode();need(not self.blocked and self.state['pending'] is self.state['original'] is None)
        prior=[(ref,row) for ref,row in zip(self.state['records'],self.records) if row['ticket']==ticket and row['label']==label]
        if prior:
            ref,row=prior[0];need(row['phase']=='returned' and row['kind']==kind and row['control']==control and row['text']==text);return deepcopy(ref)
        need(len(self.records)<MAX_INPUTS)
        row=dict(tabletWebInputVersion=VERSION,index=len(self.records)+1,ticket=ticket,label=label,kind=kind,control=control,text=text,
            phase='reading',sourceIndex=len(self.source.state['records'])+1,sourceRef=None,sourceSha256=None,events=[],before=self.stamp(),after=None)
        self.record(row,row['index']);self.state['pending']=row;self.save()
        try:
            document=self.source.capture(self.reader);row['sourceRef']=deepcopy(self.source.state['records'][-1]);row['sourceSha256']=sha(canonical(document));row['phase']='prepared';self.save()
            _,capture=self.document(row);floor=capture['before'];last=deepcopy(floor)
            def fresh():
                now=self.stamp();self.clock(now,last);last.update(now)
                need(now['epochMs']-floor['epochMs']<1500 and now['monotonic']-floor['monotonic']<1.5)
            with transport_scope(fresh):
                fresh()
                if kind=='tap':self.ui.tap(document,control)
                else:self.ui.replace(document,control,text)
            row.update(phase='returned',after=self.stamp());self.record(row,row['index']);self.save();return self.archive()
        except Exception:
            if self.state['original'] is None:
                row.update(phase='failed',after=self.stamp());self.save();self.archive()
            self.failed=True;raise
