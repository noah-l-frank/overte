"""Closed native removal/original existence queries for issued image receipts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import math
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

FILE='world-render-receipt-result.json'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','requestId','receiptId','operation'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-world-render-receipt'
         and value['operation'] in ('remove','inspect'))
    for key in ('commandId','requestId','receiptId'):
        need(type(value[key]) is str and re.fullmatch(('ios-' if ios else '(?:ios-)?')+'[0-9a-f]{32}',value[key]))
    return value


class NativeWorldReceiptCleanup:
    def __init__(self,send,read,clock_ms,guard,pid,ownership,native_instance,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,ownership,native_instance,monotonic,sleep))
             and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.ownership,self.native_instance=ownership,native_instance
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.sequence=0

    def request(self,operation,name):
        try:
            need(type(name) is str and re.fullmatch(r'world-render-storage-[0-9a-f]{32}\.json',name))
            receipt=('ios-' if self.ios else '')+name[len('world-render-storage-'):-len('.json')]
            owner=self.ownership()
            need(receipt in owner['receipts'] and self.guard() is not False)
            instance=self.native_instance();need(type(instance) is str and re.fullmatch('[0-9a-f]{32}',instance))
            request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
                action='feature-world-render-receipt',requestId=owner['capture']['commandId'],receiptId=receipt,operation=operation)
            command(request,ios=self.ios)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            self.send(request) # One mutation; original-file polling cannot replay removal.
            for attempt in range(51):
                need(self.guard() is not False and self.ownership()==owner)
                raw=self.original();need(type(raw) in (str,bytes) and len(raw.encode() if type(raw) is str else raw)<=4096)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5));previous=now
                need(self.guard() is not False and self.native_instance()==instance and self.ownership()==owner)
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    exact(value,{'receiptVersion','commandId','requestId','receiptId','operation','instance','sequence','processId','capturedEpochMs','source'})
                    need(type(value['receiptVersion']) is int and value['receiptVersion']==1
                         and all(value[k]==request[k] for k in ('requestId','receiptId','operation'))
                         and value['instance']==instance and integer(value['sequence'],self.sequence+1)
                         and integer(value['processId'],1) and value['processId']==self.pid
                         and integer(value['capturedEpochMs'],1) and (self.ios or value['capturedEpochMs']>=requested))
                    freshness_started=self.monotonic();need(number(freshness_started,0,1e15) and freshness_started>=previous)
                    epoch=value['capturedEpochMs'] if self.ios else self.clock_ms()
                    need(integer(epoch,1) and (self.ios or epoch>=requested))
                    fresh(value['capturedEpochMs'],epoch)
                    exact(value['source'],{'performed'} if operation=='remove' else {'exists'})
                    need(type(value['source'].get('performed' if operation=='remove' else 'exists')) is bool)
                    need(self.guard() is not False and self.native_instance()==instance and self.ownership()==owner)
                    finished=self.monotonic()
                    need(number(finished,0,1e15) and finished>=freshness_started
                         and finished-started<(1.5 if self.ios else 5)
                         and epoch-value['capturedEpochMs']+math.ceil((finished-freshness_started)*1000)<=1500)
                    self.sequence=value['sequence']
                    return value['source']
                if attempt<50:self.sleep(.03)
        except Exception:
            raise NativeUIError('Original world receipt removal or inventory is unavailable') from None
        raise NativeUIError('Original world receipt query did not produce this request')

    def remove(self,name):need(self.request('remove',name)['performed'] is True)
    def absent(self,name):return self.request('inspect',name)['exists'] is False


class NativeWorldReceiptFiles:
    """Original transport reads; native-issued digest/ownership gates deletion."""
    def __init__(self,files,cleanup):
        need(callable(getattr(files,'read',None)) and isinstance(cleanup,NativeWorldReceiptCleanup))
        self.files,self.cleanup=files,cleanup

    def read(self,name):return self.files.read(name)
    def remove(self,name):return self.cleanup.remove(name)
    def absent(self,name):return self.cleanup.absent(name)
