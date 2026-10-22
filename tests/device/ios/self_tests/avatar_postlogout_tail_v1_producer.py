"""Frozen three-channel Tail1 producer for stored-original compatibility.

The capture procedure is retained from 6b7abf86a3. It emits v1 at creation;
no v2 packet is stripped or relabeled. Common source readers and private-file
ownership remain real, while the reader under test validates old originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters import original_marker_clock_queries as clock_queries
from adapters.native_clock_join import NativeClockAcquisition
from adapters.native_feature_observation import need
from adapters.script_feature.history import same,pack
from ios.adapters.avatar_postlogout_tail import IOSAvatarPostLogoutTail,CHANNELS
from ios.adapters.authentication_causality import check as account_causality
VERSION=1


class Tail1Producer(IOSAvatarPostLogoutTail):
    def envelope(self,state,version=1):return super().envelope(state,1)

    def capture(self):
        self.bound();self.recover();need(len(self.state['rows'])<128)
        actual=self.factory();need(same(actual['binding'],self.binding));self.native=actual['clock_source'];need(not self.native.native_clock_bound)
        readers={name:getattr(actual['observer'],{'scripts':'avatar_scripts','http':'avatar_social_http','people':'people_model'}[name])(self.native) for name in CHANNELS}
        last=next((self.record(row['reference']) for row in reversed(self.state['rows']) if row['status']=='observed'),None)
        if last is not None:
            from adapters.native_clock_source_history import restore
            restore(self.native,last['clockJoin']['nativeAfter'])
            for name,reader in readers.items():reader.last=deepcopy(last['packets'][name])
        p=dict(index=len(self.state['rows'])+1,nativeQueries=[],queries={},raws={},widgetsQuery=None,widgetsReceipt=None,join=None,record=None)
        self.state['pending']=p;self.save();packets={}
        with clock_queries.owned(self):
            window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(self.epoch_ms())
            account_causality(dict(contractVersion=16,runId=self.inputs['childRunId'],fixtureUrl=self.inputs['fixtureUrl'],
                ticket=self.inputs['ticket'],verb='logout',inputs={}),self.inputs['logoutBefore'],window.started['nativeBefore'],window.started['nativeBefore']['capturedEpochMs'])
            for name,reader in readers.items():
                send,read=reader.send,reader.original
                def sending(query,name=name,send=send):p['queries'][name]=deepcopy(query);p['raws'][name]=[];self.save();return send(query)
                def reading(name=name,read=read):
                    raw=read();rows=p['raws'][name]
                    if not rows or rows[-1]!=raw:rows.append(raw);self.save()
                    return raw
                reader.send,reader.original=sending,reading
                try:packets[name]=reader.read(self.run)
                finally:reader.send,reader.original=send,read
            widgets=actual['native'];intent=getattr(widgets,'observe_intent',None)
            def own(query):need(p['widgetsQuery'] is None);p['widgetsQuery']=deepcopy(query);self.save()
            widgets.observe_intent=own
            try:observed=widgets.capture()
            finally:
                if widgets.last_receipt is not None:p['widgetsReceipt']=deepcopy(widgets.last_receipt);self.save()
                widgets.observe_intent=intent
            originals=deepcopy(packets);originals['widgets']=observed;fields=[]
            for name,packet in packets.items():originals[name+'Clock']=dict(capturedEpochMs=packet['clockAfter']['epochMs']);fields.append((name+'Clock','capturedEpochMs'))
            fields.append(('widgets','sampleEpochMs'))
            join=window.finish(originals,fields);p['join']=join;self.save()
        value=dict(index=p['index'],nativeQueries=deepcopy(p['nativeQueries']),queries=deepcopy(p['queries']),packets=packets,
            widgetsQuery=deepcopy(p['widgetsQuery']),widgetsReceipt=deepcopy(p['widgetsReceipt']),clockJoin=join)
        self.validate(value,last)
        for row in self.state['rows']:
            if row['status']=='abandoned':self.floors(row['partial'],value)
        p['record']=dict(iosAvatarPostLogoutTailOriginalVersion=VERSION,runId=self.run,role=self.role,subject=self.subject,binding=self.binding,payload=pack([value]));self.save()
        row=self.recover();self.proof(row);a=join;now,mono=self.epoch_ms(),self.monotonic()
        need(a['hostAfterEpochMs']<=now<a['hostBeforeEpochMs']+1500 and a['hostAfterMonotonic']<=mono<a['hostBeforeMonotonic']+1.5
            and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250);return row

