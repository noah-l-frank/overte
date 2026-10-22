"""Ordinary SDK input in an originally resolved Android Snapshot chooser.

The owner supplies its original OS resolution and a candidate/kernel/session
continuity guard valid across this explicit handoff. Existing foreground-only
native command guards remain unchanged. UI transition is never consumption.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import uuid
import xml.etree.ElementTree as ET

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_ui import NativeUI,NativeUIError
from overte_phone_snapshot_consumer import PACKAGE as RECEIVER,COMPONENT as RECEIVER_COMPONENT

PRIMARY='io.github.noah_be.overte.phone'
LABEL='Overte Snapshot Evidence'
NAME=re.compile(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+')
PACKAGE_NAME=re.compile(r'(?:android|[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)')


def component(package,activity):
    need(type(package) is str and PACKAGE_NAME.fullmatch(package) and type(activity) is str)
    if activity.startswith('.'):activity=package+activity
    need(NAME.fullmatch(activity))
    return package+'/'+activity


def tree(raw):
    need(type(raw) is str and 0<len(raw.encode())<=262144 and '<!DOCTYPE' not in raw.upper() and '<!ENTITY' not in raw.upper())
    try:root=ET.fromstring(raw)
    except ET.ParseError:need(False)
    need(len(list(root.iter()))<=4096)
    return root


def bounds(node):
    value=node.get('bounds');need(type(value) is str)
    matched=re.fullmatch(r'\[([0-9]{1,5}),([0-9]{1,5})\]\[([0-9]{1,5}),([0-9]{1,5})\]',value)
    need(matched is not None);x0,y0,x1,y1=map(int,matched.groups())
    need(0<=x0<x1<=16384 and 0<=y0<y1<=16384);return x0,y0,x1,y1


class PhoneSnapshotSystemUI:
    def __init__(self,ui,intent,clock_ms,chooser_component):
        need(isinstance(ui,NativeUI) and callable(intent) and callable(clock_ms)
            and type(chooser_component) is str and chooser_component.count('/')==1)
        package,activity=chooser_component.split('/')
        self.chooser=component(package,activity);self.package=package
        need(package not in (PRIMARY,RECEIVER))
        self.ui,self.intent,self.clock_ms=ui,intent,clock_ms

    def capture(self):
        try:
            self.ui._check();started=self.ui._now();requested=self.clock_ms();need(integer(requested,1))
            package=self.ui._request('GET','/appium/device/current_package')
            activity=self.ui._request('GET','/appium/device/current_activity')
            actual=component(package,activity)
            need(package in (PRIMARY,self.package,RECEIVER) and (actual==self.chooser if package==self.package else True))
            if package==RECEIVER:need(actual==RECEIVER_COMPONENT)
            raw=self.ui._request('GET','/source');root=tree(raw)
            # Accessibility overlays may contain system bars. The actual active
            # component and at least one displayed node must be the same owner.
            need(any(node.get('package')==package and node.get('displayed','true')=='true' for node in root.iter()))
            after=component(self.ui._request('GET','/appium/device/current_package'),self.ui._request('GET','/appium/device/current_activity'))
            self.ui._check();captured=self.clock_ms();finished=self.ui._now()
            need(after==actual and integer(captured,requested) and captured-requested<=1500 and finished-started<=1.5)
            return dict(snapshotSystemUiVersion=1,observationId=uuid.uuid4().hex,component=actual,
                requestedEpochMs=requested,capturedEpochMs=captured,sourceSha256=hashlib.sha256(raw.encode()).hexdigest(),xml=raw)
        except Exception:raise NativeUIError('Original owned Snapshot system UI is unavailable or changed') from None

    def wait(self,predicate):
        started=self.ui._now()
        for attempt in range(51):
            value=self.capture()
            if predicate(value):return value
            now=self.ui._now();need(now-started<5 and attempt<50)
            self.ui.sleep(min(.1,max(0,5-(now-started))))
        need(False)

    def _intent(self,action,original,details):
        need(self.intent(dict(snapshotSystemInputVersion=1,action=action,original=deepcopy(original),details=deepcopy(details))) is not False)
        # Re-read after durable intent, before normal input. A changed source
        # cannot move an already authorized touch to another target/window.
        current=self.capture();need(current['component']==original['component'] and current['sourceSha256']==original['sourceSha256']
            and 0<=current['capturedEpochMs']-original['capturedEpochMs']<=1500)

    def back(self,*,receiver=False):
        need(type(receiver) is bool)
        before=self.capture();need(before['component']==(RECEIVER_COMPONENT if receiver else self.chooser))
        self._intent('receiver-back' if receiver else 'share-cancel',before,{})
        self.ui._request('POST','/back',{})
        return self.wait(lambda actual:actual['component'].split('/')[0]==PRIMARY)

    def select_receiver(self,identity):
        try:
            exact(identity,{'package','apkSha256','uid','processId','processIdentity'})
            need(identity['package']==RECEIVER and type(identity['apkSha256']) is str and re.fullmatch('[0-9a-f]{64}',identity['apkSha256'])
                and integer(identity['uid'],1) and integer(identity['processId'],1)
                and type(identity['processIdentity']) is str and re.fullmatch(str(identity['processId'])+':[0-9]+',identity['processIdentity']))
            before=self.capture();need(before['component']==self.chooser)
            root=tree(before['xml']);parents={child:parent for parent in root.iter() for child in parent}
            rows=[node for node in root.iter() if node.get('package')==self.package and node.get('text')==LABEL
                and node.get('displayed','true')=='true' and node.get('enabled')=='true']
            need(len(rows)==1);node=rows[0];label=bounds(node)
            while node.get('clickable')!='true':
                need(node in parents);node=parents[node]
            need(node.get('package')==self.package and node.get('enabled')=='true' and node.get('displayed','true')=='true')
            area=bounds(node);need(area[0]<=label[0]<label[2]<=area[2] and area[1]<=label[1]<label[3]<=area[3])
            x,y=(label[0]+label[2])//2,(label[1]+label[3])//2
            self._intent('share-select-owned',before,dict(receiver=identity,point=[x,y]))
            try:
                self.ui._request('POST','/actions',{'actions':[dict(type='pointer',id='overte-snapshot-share',parameters={'pointerType':'touch'},
                    actions=[dict(type='pointerMove',duration=0,origin='viewport',x=x,y=y),dict(type='pointerDown',button=0),
                        dict(type='pause',duration=50),dict(type='pointerUp',button=0)])]})
            finally:self.ui.release_actions()
            return self.wait(lambda actual:actual['component'].split('/')[0] in (PRIMARY,RECEIVER))
        except Exception:raise NativeUIError('Normal owned Snapshot receiver selection did not complete') from None
