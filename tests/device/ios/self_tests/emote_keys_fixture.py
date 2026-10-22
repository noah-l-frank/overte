"""Modeled Qt/IME and UIKit originals on the actual Emote native clock."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.native_geometry import OriginalGeometry
from ios.adapters.world_web_keys import IOSWorldWebKeys
from ios.self_tests.test_ios_world_web_keys import QtKeys
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class KeyDomain:
    def __init__(self,scope,domain,*,binding=BINDING,role='primary'):
        self.scope,self.domain,self.binding,self.role=scope,domain,binding,role
        self.qt=QtKeys();self.qt.epoch=domain.epoch();self.birth=max(1,domain.epoch()-1000)
        self.commands=[];self.key_raw=self.geometry_raw='';self.geometry_sequence=0;self.keyboard=False;self.inset=0
        self.fail_read=False;self.fail_geometry=False
        def tick():domain.time+=.001;self.qt.epoch=domain.epoch();return self.qt.epoch
        self.qt.tick=tick;edge=self.qt.edge
        def original_edge(row,kind):
            edge(row,kind);stamp=self.qt.events[-1]['epochMs'];self.qt.events[-1]['monotonicMs']=stamp-self.birth
            row[kind+'MonotonicMs']=stamp-self.birth
        self.qt.edge=original_edge
        if hasattr(domain,'io'):
            replace=domain.io.replace
            def replaced(identifier,text):
                row=self.qt.enter('input-method',commit=text)
                try:return replace(identifier,text)
                finally:self.qt.finish(row)
            domain.io.replace=replaced

    def reader(self):
        d=self.domain
        return IOSWorldWebKeys(self.key_send,self.key_read,d.epoch,lambda:True,int(self.binding['processIdentity']),monotonic=lambda:d.time,sleep=d.sleep)
    def geometry(self):
        d=self.domain
        return OriginalGeometry(self.geometry_send,self.geometry_read,d.epoch,lambda:True,monotonic=lambda:d.time,sleep=d.sleep)

    def key_send(self,query):
        self.commands.append(deepcopy(query));packet=self.qt.packet()
        packet.update(runId=query['runId'],requestId=query['commandId'],processId=int(self.binding['processIdentity']))
        source=packet['source'];source['bornEpochMs']=self.birth;source['startup'].update(epochMs=self.birth+1 if self.qt.started else 0,monotonicMs=1 if self.qt.started else 0)
        for name in ('devices','targets'):
            for row in source[name]:row['bornEpochMs']=self.birth+2
        for clock in ('clockBefore','clockAfter'):packet[clock]['monotonicMs']=packet[clock]['epochMs']-self.birth
        self.key_raw=json.dumps(packet)
    def key_read(self):
        if self.fail_read:raise OSError('Lost original global Qt key read')
        return self.key_raw
    def geometry_send(self,query):
        self.commands.append(deepcopy(query));self.domain.time+=.001;self.geometry_sequence+=1
        self.geometry_raw=json.dumps(dict(schemaVersion=1,commandId=query['commandId'],observation=dict(schemaVersion=1,
            sampleEpochMs=self.domain.epoch(),sampleSequence=self.geometry_sequence,nativeUi=dict(valid=True,surfaceWidth=640,surfaceHeight=480,
                safeInsetLeft=0,safeInsetTop=0,safeInsetRight=0,safeInsetBottom=0,keyboardVisible=self.keyboard,imeInsetBottom=self.inset),
            window=dict(width=640,height=480))))
    def geometry_read(self):
        if self.fail_geometry:raise OSError('Lost original UIKit geometry read')
        return self.geometry_raw
    def owner(self):
        d,s=self.domain,self.scope;pid=int(self.binding['processIdentity'])
        keys=self.reader();geometry=self.geometry()
        return IOSEmoteKeys(PrivateFeatureState(s.root/('ios-emote-'+self.role+'-keys.json')),s.root,self.binding,RUN,self.role,s.lock,
            lambda:True,native=s.native,keys=keys,geometry=geometry,epoch_ms=s.epoch_ms,monotonic=lambda:d.time)
