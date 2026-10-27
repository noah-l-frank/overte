"""Durable ordinary world touches/Unicode keys from actual source geometry.

The transport result is recorded only as delivery responsibility. It creates no
DOM value/focus, navigation, bridge message, native drain or rendered evidence.
An unknown POST is never repeated by reconstruction of this owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUI,NativeUIError,WEBDRIVER_KEYS
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import world_web_geometry as geometry
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_api_clock import check as api_check

VERSION=1


def key_actions(text):
    need(type(text) is str and len(text.encode('utf-16-le'))//2<=8192
        and all(ord(char)>=32 and ord(char)!=127 and ord(char) not in WEBDRIVER_KEYS for char in text))
    # IOSWebView intentionally refuses Ctrl/Alt/Meta shortcuts. Its original
    # ordinary End/Shift+Home/Backspace route edits the actual focused field.
    pairs=[('\ue010',False),('\ue008',True),('\ue011',False),('\ue008',None),('\ue003',False)]
    result=[]
    for key,hold in pairs:
        if hold is None:result.append(dict(type='keyUp',value=key))
        else:
            result.append(dict(type='keyDown',value=key))
            if not hold:result.append(dict(type='keyUp',value=key))
    for char in text:result.extend((dict(type='keyDown',value=char),dict(type='keyUp',value=char)))
    return result


class WorldWebInput:
    def __init__(self,store,source,ui,entity,guard,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(source,WorldWebSources) and isinstance(ui,NativeUI)
            and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        self.store,self.source,self.ui,self.entity,self.guard=store,source,ui,entity,guard
        self.binding,self.run,self.lock=deepcopy(context(source.binding)),source.run,source.lock
        need(isinstance(self.lock,ScriptSourceLock) and source.role=='primary' and store.path.name=='ios-world-web-inputs.json')
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.previous=store.read();self._proof_cache=set();self.state=dict(records=[])
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):return dict(iosWorldWebInputVersion=VERSION,binding=self.binding,runId=self.run,entityId=self.entity,payload=pack([state]))

    def decode(self,value):
        with self.source.validation_round():return self._decode(value)

    def _decode(self,value):
        exact(value,{'iosWorldWebInputVersion','binding','runId','entityId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosWorldWebInputVersion']) is int and value['iosWorldWebInputVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records'});need(type(state['records']) is list and len(state['records'])<=128);labels=set();last_source=0
        for row in state['records']:
            exact(row,{'ticket','label','kind','control','text','phase','source','window','point','body','releaseReturned'})
            identifier(row['ticket']);need(type(row['label']) is str and 1<=len(row['label'])<=64 and (row['ticket'],row['label']) not in labels)
            labels.add((row['ticket'],row['label']));need(row['kind'] in ('tap','replace') and row['phase'] in ('reading','issued','returned')
                and type(row['releaseReturned']) is bool and row['control'] in geometry.dom.IDS)
            if row['kind']=='tap':need(row['text'] is None)
            else:key_actions(row['text']);need(row['control'] in ('text','foreign'))
            if row['source'] is not None:
                need(row['source']['index']>last_source);last_source=row['source']['index'];self.source.retained(row['source'])
            if row['phase']!='reading':
                # Full actual immutable Source bytes/inodes are checked by
                # the enclosing round; reuse only this exact pure row proof.
                key=self.proof_key(row)
                if key not in self._proof_cache:self.proof(row);self._proof_cache.add(key)
        return deepcopy(state)

    def bound(self):
        api_check();self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value);api_check();self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);api_check()

    def proof_key(self,row):
        # Geometry/body validation reads none of the delivery-phase/ACK fields.
        # Their exact grammar still runs above on every decode. The existing
        # Source round continues reading/pinning all original bytes and every
        # final transport guard checks those actual identities and current WAL.
        original={key:row[key] for key in ('ticket','label','kind','control','text','source','window','point','body')}
        parser=getattr(self.proof,'__func__',self.proof)
        return (digest(original),digest(self.binding),self.run,self.entity,parser)

    def proof(self,row):
        frame=self.source.frame(row['source']);need(frame['ticket']==row['ticket'])
        raw=frame['originals'];document=raw['document'];need(raw['ledgerAfter']['iosWorldWebVersion']>=2 and document is not None and document['source']['dom']['iosWorldWebDOMVersion']>=2
            and not raw['widgets']['tabletShown'])
        if row['kind']=='tap':
            target=self.source.input_point(frame,self.entity,row['control']);need(same(target,row['point']))
            rect=row['window'];exact(rect,{'x','y','width','height'});need(all(number(rect[key],-10000,10000) for key in ('x','y'))
                and abs(rect['width']-target['surfaceWidth'])<=1 and abs(rect['height']-target['surfaceHeight'])<=1)
            body=dict(actions=[dict(type='pointer',id='overte-world-web-'+row['ticket'],parameters=dict(pointerType='touch'),actions=[
                dict(type='pointerMove',duration=0,origin='viewport',x=round(rect['x']+target['x']),y=round(rect['y']+target['y'])),
                dict(type='pointerDown',button=0),dict(type='pause',duration=100),dict(type='pointerUp',button=0)])])
        else:
            fields=[element for element in document['source']['dom']['elements'] if element['id']==row['control']]
            need(len(fields)==1 and fields[0]['focused'] and fields[0]['enabled'] and fields[0]['visible'] and type(fields[0]['value']) is str
                and row['window'] is row['point'] is None)
            body=dict(actions=[dict(type='key',id='overte-world-web-keyboard',actions=key_actions(row['text']))])
        need(same(body,row['body']));return frame

    def perform(self,ticket,label,kind,control,*,text=None):
        self.bound();identifier(ticket);need(type(label) is str and kind in ('tap','replace'))
        old=[row for row in self.state['records'] if row['ticket']==ticket and row['label']==label]
        if old:
            row=old[0];need(row['kind']==kind and row['control']==control and row['text']==text)
            if row['phase']!='returned':raise NativeUIError('World Web input delivery remains owned; observe without replay')
            return deepcopy(row)
        need(len(self.state['records'])<128)
        row=dict(ticket=ticket,label=label,kind=kind,control=control,text=text,phase='reading',source=None,window=None,point=None,body=None,releaseReturned=False)
        self.state['records'].append(row);self.save()
        with self.source.input_round(self.store):
            row['source']=self.source.capture('input-'+label)
            return self._deliver(row,ticket,kind,control,text)

    def _deliver(self,row,ticket,kind,control,text):
        self.save();frame=self.source.frame(row['source']);need(frame['ticket']==ticket)
        raw=frame['originals']
        if kind=='tap':
            row['window']=deepcopy(self.ui._request('GET','/window/rect'))
            row['point']=self.source.input_point(frame,self.entity,control)
            target,rect=row['point'],row['window'];row['body']=dict(actions=[dict(type='pointer',id='overte-world-web-'+ticket,
                parameters=dict(pointerType='touch'),actions=[dict(type='pointerMove',duration=0,origin='viewport',
                x=round(rect['x']+target['x']),y=round(rect['y']+target['y'])),dict(type='pointerDown',button=0),dict(type='pause',duration=100),dict(type='pointerUp',button=0)])])
        else:row['body']=dict(actions=[dict(type='key',id='overte-world-web-keyboard',actions=key_actions(text))])
        self.proof(row);self._proof_cache.add(self.proof_key(row))
        # The final transport guard compares the exact durable intention.
        # Geometry/window/body must therefore be retained before its first
        # check, while the separate issued write still precedes the POST.
        self.save()
        completed=False
        def fresh():
            api_check();self.source.guard_originals();self.source.guard_saved_state()
            need(same(self.store.read(),self.previous) and same(self.previous,self.envelope(self.state)));joined=frame['clockJoin']
            if not completed:need(self.epoch_ms()<joined['hostBeforeEpochMs']+1500 and self.monotonic()<joined['hostBeforeMonotonic']+1.5)
        fresh();row['phase']='issued';self.save()
        try:
            with transport_scope(fresh):
                fresh();self.ui._check();self.ui._request('POST','/actions',row['body']);completed=True;self.ui._check()
        finally:
            # This ACK is merely delivery state. Actual Qt pointer/key/IME
            # originals and native Web lifetimes independently qualify cleanup.
            self.ui.release_actions();row['releaseReturned']=True;self.save()
        row['phase']='returned';self.save();return deepcopy(row)
