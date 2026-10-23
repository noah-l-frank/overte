"""Bounded original server-response archives after browser authority closes.

These are HTTP inventory/denial originals only, never native document, callback,
quiet or renderer facts. The active browser resource provider remains closed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import threading
from urllib.parse import urlsplit
from .contract import identifier

MAX_RUNS=64
MAX_ATTEMPTS=256
RESOURCE_NAMES={'index.html','reference.html','page-b.html','recovery.html','reference.js','client.js','injected.js','feature-marker.js','marker.png','reference.mp4'}


class BrowserRetirements:
    def __init__(self,clock_ms):
        self.clock_ms,self.lock,self.runs=clock_ms,threading.RLock(),{}
    def contains(self,run):
        with self.lock:return identifier(run) in self.runs
    def close(self,run,inventory):
        identifier(run)
        with self.lock:
            if run in self.runs:raise ValueError('Browser retired identity was reused')
            try:stamp=self.clock_ms()
            except Exception:stamp=None
            floor=max((entry['capturedEpochMs'] for entry in inventory['responses']),default=0)
            available=type(stamp) is int and max(1,floor)<=stamp<=2**53-1
            self.runs[run]=dict(inventory=deepcopy(inventory),complete=available,attempts=[],epoch=stamp if available else 0,closedEpochMs=stamp if available else None)
            while len(self.runs)>MAX_RUNS:del self.runs[next(iter(self.runs))]
    def epoch(self,row):
        try:epoch=self.clock_ms()
        except Exception:row['complete']=False;return None
        if type(epoch) is not int or not 0<epoch<=2**53-1 or epoch<row['epoch']:
            row['complete']=False;return None
        row['epoch']=epoch;return epoch
    def snapshot(self,run):
        with self.lock:
            row=self.runs[identifier(run)];value=deepcopy(row['inventory'])
            # New writer only on the explicit retired endpoint. Original
            # response IDs, bytes, status, timestamps and instance stay exact.
            value['browserFixtureVersion']=2
            value['retirement']=dict(browserRetirementVersion=1,runId=run,complete=row['complete'],closedEpochMs=row['closedEpochMs'],attempts=deepcopy(row['attempts']))
            return value
    def begin(self,run,ticket,resource,origin,method):
        with self.lock:
            row=self.runs.get(run)
            if row is None:return None
            if len(row['attempts'])>=MAX_ATTEMPTS:row['complete']=False;return None
            epoch=self.epoch(row)
            if epoch is None:return None
            attempt=dict(sequence=len(row['attempts'])+1,ticket=ticket,resource=resource,origin=origin,method=method,
                enteredEpochMs=epoch,headers=None,write=None,finallyEpochMs=None)
            row['attempts'].append(attempt);return run,row['inventory']['instance'],attempt['sequence']
    def update(self,token,stage,value=None):
        if token is None:return
        with self.lock:
            run,instance,index=token;row=self.runs.get(run)
            if row is None or row['inventory']['instance']!=instance:return
            attempt=row['attempts'][index-1];epoch=self.epoch(row)
            if epoch is None:return
            if stage in ('headers','write') and attempt['finallyEpochMs'] is not None:row['complete']=False;return
            if stage=='headers':
                if attempt['headers'] is not None or not 400<=value['status']<=599:row['complete']=False;return
                attempt['headers']=dict(value,observedEpochMs=epoch)
            elif stage=='write':
                if attempt['headers'] is None or attempt['write'] is not None or type(value) is not int or value!=attempt['headers']['bytes']:
                    row['complete']=False;return
                attempt['write']=dict(bytes=value,observedEpochMs=epoch)
            elif stage=='finally':
                if attempt['finallyEpochMs'] is not None:row['complete']=False;return
                attempt['finallyEpochMs']=epoch
            else:row['complete']=False


def begin(handler):
    """Observe only actual known fixture-resource requests, including denials."""
    handler.browser_retired_attempt=None
    parsed=urlsplit(handler.path);prefix='/feature-fixture/v1/'
    if not parsed.path.startswith(prefix):return
    parts=parsed.path[len(prefix):].split('/')
    if len(parts)!=5 or parts[0]!='runs' or parts[2]!='tickets' or parts[4] not in RESOURCE_NAMES:return
    try:run,ticket=identifier(parts[1]),identifier(parts[3])
    except ValueError:return
    handler.browser_retired_attempt=handler.server.browser_resources.retirements.begin(run,ticket,parts[4],
        'foreign' if handler.server.browser_peer else 'primary',handler.command)


def headers(handler,body):
    token=getattr(handler,'browser_retired_attempt',None)
    if token is None:return
    line=handler._headers_buffer[0].split(b' ',2)
    if len(line)!=3 or not line[1].isdigit():
        handler.server.browser_resources.retirements.update(token,'invalid');return
    handler.server.browser_resources.retirements.update(token,'headers',dict(status=int(line[1]),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))


def written(handler,count):
    token=getattr(handler,'browser_retired_attempt',None)
    if token is not None:handler.server.browser_resources.retirements.update(token,'write',count)


def finally_observed(handler):
    # This records actual finally entry, not callback return or native drain.
    token=getattr(handler,'browser_retired_attempt',None)
    if token is not None:handler.server.browser_resources.retirements.update(token,'finally')
