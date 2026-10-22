"""Original normal Create draft input references; no full Lifecycle verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_feature_observation import exact,need,number
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce,scope
from feature_journeys.fixtures import context

VERSION=1
ID='lifecycle.create.text'
OBJECTS=('fieldId','pageId','contextId','windowId')


def text(value):
    need(type(value) is str and (value=='' or re.fullmatch(r'Overte ä Ω 東京 [0-9a-f]{32}',value)))
    return value


def metadata(row):
    exact(row,{'id','token','enabled','focused','inputReady','text','componentSourceSha256',*OBJECTS})
    need(row['id']==ID and all(nonce(row[key]) for key in ('token',*OBJECTS))
        and all(type(row[key]) is bool for key in ('enabled','focused','inputReady'))
        and type(row['componentSourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['componentSourceSha256']))
    text(row['text']);return row


def snapshot(value):
    exact(value,{'lifecycleControlsVersion','open','ready','scope','controls'})
    need(type(value['lifecycleControlsVersion']) is int and value['lifecycleControlsVersion']==VERSION
        and all(type(value[key]) is bool for key in ('open','ready'))
        and type(value['controls']) is list and len(value['controls'])<=1)
    scope(value['scope'])
    for row in value['controls']:metadata(row)
    need(value['open'] or not value['controls']);return value


def same_reference(before,current,identifier):
    snapshot(before);snapshot(current);need(identifier==ID and len(before['controls'])==len(current['controls'])==1)
    need(all(before['scope'][key]==current['scope'][key] for key in ('instance','generation','sequence','processId'))
        and 0<=current['scope']['elapsedMs']-before['scope']['elapsedMs']<=1500
        and before['controls']==current['controls'])
    return before['controls'][0]


class TokenLifecycleUI:
    def __init__(self,io,intent,run,*,monotonic=time.monotonic,sleep=time.sleep):
        need(nonce(run) and len(run)==32 and callable(intent) and callable(monotonic) and callable(sleep))
        self.io,self.intent,self.run,self.monotonic,self.sleep=io,intent,run,monotonic,sleep
        self.previous=self.last_clock=None
    def now(self):
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock));self.last_clock=now;return now
    def capture(self):
        value=deepcopy(snapshot(self.io.capture()));previous=self.previous
        if previous is not None:
            a,b=previous['scope'],value['scope']
            need(a['instance']==b['instance'] and a['processId']==b['processId'] and a['generation']==b['generation']
                and b['sequence']>=a['sequence'] and b['elapsedMs']>=a['elapsedMs'])
        for row in value['controls']:need(row['text'] in ('',context(self.run)['unicode']))
        self.previous=value;return value
    @staticmethod
    def row(value):
        need(value['open'] and value['ready'] and len(value['controls'])==1)
        row=value['controls'][0];need(row['enabled'] and row['inputReady']);return row
    def input(self,action,value=None):
        need(action in ('activate','replace'))
        if action=='replace':need(value==context(self.run)['unicode']);text(value)
        else:need(value is None)
        before=self.capture();row=self.row(before);started=self.now()
        if action=='replace':need(row['focused'] and row['text']=='')
        self.intent(dict(lifecycleControlInputVersion=1,action=action,controlId=ID,controlToken=row['token'],
            scope=deepcopy(before['scope']),objects={key:row[key] for key in OBJECTS}))
        need(self.now()-started<=1.5)
        if action=='activate':self.io.activate(ID,reference=before)
        else:self.io.replace(ID,value,reference=before)
        after=self.capture();current=self.row(after)
        need(after['scope']['sequence']==before['scope']['sequence']+1
            and after['scope']['generation']==before['scope']['generation']
            and all(current[key]==row[key] for key in (*OBJECTS,'componentSourceSha256')))
        # Only input consumption is established here. Text/focus are read again.
        return before
    def type_owned(self):
        before=self.capture();original=deepcopy(self.row(before));need(original['text']=='')
        self.input('activate');self.wait(original,lambda row:row['focused'] and row['text']=='')
        self.input('replace',context(self.run)['unicode'])
        return self.wait(original,lambda row:row['focused'] and row['text']==context(self.run)['unicode'])
    def wait(self,original,predicate):
        started=self.now()
        for index in range(51):
            current=self.capture();row=self.row(current)
            need(all(row[key]==original[key] for key in (*OBJECTS,'componentSourceSha256')))
            if predicate(row):need(self.now()-started<5);return current
            need(index<50 and self.now()-started<5);self.sleep(.1)
        raise NativeUIError('Original Create draft input effect was not observed')
