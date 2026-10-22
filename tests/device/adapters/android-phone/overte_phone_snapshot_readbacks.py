"""Guarded asynchronous original Save readback source; ACKs are not files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_exports import uri

FILE='phone-snapshot-readback.json'
OPERATIONS={'observe','read','cancel','remove-copy','retire-copies'}
ROOTS={'/data/'+base+'/io.github.noah_be.overte.phone/files/' for base in ('user/0','data')}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None
def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','operation','exportRequest','resourceId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-snapshot-readback'
        and nonce(value['commandId']) and nonce(value['runId']) and value['operation'] in OPERATIONS)
    operation=value['operation'];request=value['exportRequest'];id=value['resourceId']
    if operation in ('observe','retire-copies'):need(request==id=='')
    elif operation=='read':need(nonce(request) and nonce(id))
    else:need(request=='' and nonce(id))
    return value


def original(value,epoch):
    exact(value,{'id','request','path','phase','bytes','sha256','capturedEpochMs'})
    need(nonce(value['id']) and nonce(value['request']) and value['phase'] in ('planned','reading','failed','complete')
        and integer(value['bytes'],0,256*1024*1024) and integer(value['capturedEpochMs'],0,epoch))
    need(type(value['path']) is str and any(re.fullmatch(re.escape(root)+r'overte-snapshot-e2e-[0-9a-f]{32}/'+value['id']+r'\.bin',value['path']) for root in ROOTS))
    if value['phase']=='complete' or value['bytes']:
        need(value['bytes']>0 and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256'])
            and value['capturedEpochMs']>0)
    else:need(value['sha256']=='' and value['capturedEpochMs']==0)
    return value


def source(value):
    exact(value,{'accepted','source'});need(type(value['accepted']) is bool)
    row=value['source'];need(type(row) is dict)
    if 'initialized' in row:
        exact(row,{'snapshotExportReadbacksVersion','initialized','complete'})
        need(type(row['snapshotExportReadbacksVersion']) is int and row['snapshotExportReadbacksVersion']==1
            and row['initialized'] is False and row['complete'] is True and value['accepted'] is False)
        return value # Uninitialized means unavailable, never an empty OS destination inventory.
    exact(row,{'snapshotExportReadbacksVersion','instance','sequence','elapsedMs','complete','copiesRetired','capturedEpochMs',
        'workersTerminated','destinations','jobs','files','removedCopies'})
    need(type(row['snapshotExportReadbacksVersion']) is int and row['snapshotExportReadbacksVersion']==1
        and nonce(row['instance']) and integer(row['sequence'],1) and integer(row['elapsedMs'],0)
        and row['complete'] is True and type(row['copiesRetired']) is bool and type(row['workersTerminated']) is bool
        and integer(row['capturedEpochMs'],1) and all(type(row[key]) is list and len(row[key])<=64 for key in ('destinations','jobs','files','removedCopies')))
    need(not row['workersTerminated'] or row['copiesRetired'])
    destinations={}
    for destination in row['destinations']:
        exact(destination,{'request','uri','inserted','published'});uri(destination['uri'])
        need(nonce(destination['request']) and destination['request'] not in destinations
            and type(destination['inserted']) is bool and type(destination['published']) is bool)
        destinations[destination['request']]=destination
    files={};folders=set()
    for item in row['files']:
        original(item,row['capturedEpochMs']);need(item['id'] not in files and item['request'] in destinations)
        files[item['id']]=item;folders.add(item['path'].rsplit('/',1)[0])
    need(len(folders)<=1 and len(set(row['removedCopies']))==len(row['removedCopies'])
        and all(nonce(id) and id not in files for id in row['removedCopies']))
    jobs=set()
    for job in row['jobs']:
        exact(job,{'id','request','phase','startedEpochMs','completedEpochMs','original'})
        need(nonce(job['id']) and job['id'] not in jobs and job['request'] in destinations
            and destinations[job['request']]['published'] and job['phase'] in ('queued','reading','complete','failed'))
        jobs.add(job['id'])
        need(integer(job['startedEpochMs'],0,row['capturedEpochMs']) and integer(job['completedEpochMs'],0,row['capturedEpochMs']))
        if job['phase']=='queued':need(job['startedEpochMs']==job['completedEpochMs']==0 and job['original'] is None)
        elif job['phase']=='reading':need(job['startedEpochMs']>0 and job['completedEpochMs']==0 and job['original'] is None)
        else:need(job['startedEpochMs']>0 and job['completedEpochMs']>=job['startedEpochMs'])
        if job['original'] is not None:
            item=original(job['original'],job['completedEpochMs']);need(item['request']==job['request'] and item['phase']=='complete'
                and job['phase'] in ('complete','failed') and (files.get(item['id'])==item or item['id'] in row['removedCopies']))
        if job['phase']=='complete':need(job['original'] is not None)
    if row['copiesRetired']:need(not files and all(job['phase'] in ('complete','failed') for job in row['jobs']))
    return value


def continuity(before,after):
    need(after['runId']==before['runId'] and after['instance']==before['instance'] and after['processId']==before['processId']
        and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source']['source'],after['source']['source']
    if 'initialized' in a:return
    need('initialized' not in b and b['instance']==a['instance'] and b['sequence']>a['sequence']
        and b['elapsedMs']>=a['elapsedMs'] and b['capturedEpochMs']>=a['capturedEpochMs']
        and (not a['copiesRetired'] or b['copiesRetired']) and b['removedCopies'][:len(a['removedCopies'])]==a['removedCopies'])
    destinations={row['request']:row for row in b['destinations']}
    for row in a['destinations']:
        current=destinations.get(row['request']);need(current is not None
            and all(current[key]==row[key] for key in ('request','uri','inserted')) and (not row['published'] or current['published']))
    jobs={row['id']:row for row in b['jobs']}
    for row in a['jobs']:
        current=jobs.get(row['id']);need(current is not None and current['request']==row['request'])
        if row['phase'] in ('complete','failed'):need(current==row)
        elif row['phase']=='reading':need(current['phase']!='queued' and current['startedEpochMs']==row['startedEpochMs'])


class PhoneSnapshotReadbacks:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def request(self,run,operation='observe',export_request='',resource_id=''):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-readback',runId=run,
                operation=operation,exportRequest=export_request,resourceId=resource_id))
            need(self.guard() is not False);start=previous=self.monotonic();requested=self.clock_ms()
            need(number(start,0,1e15) and integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-start<5);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
                    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==run and nonce(value['instance'])
                        and integer(value['sequence'],1) and type(value['processId']) is int and value['processId']==self.pid
                        and integer(value['requestedEpochMs'],requested) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
                        and value['capturedEpochMs']-value['requestedEpochMs']<1500)
                    fresh(value['capturedEpochMs'],self.clock_ms());source(value['source']);component=value['source']['source']
                    if 'initialized' not in component:need(integer(component['capturedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']))
                    if self.last is not None:continuity(self.last,value)
                    need(self.guard() is not False);fresh(value['capturedEpochMs'],self.clock_ms())
                    now=self.monotonic();need(number(now,previous,1e15) and now-start<5)
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone Snapshot readback source is unavailable or invalid') from None
        raise NativeUIError('Original Phone Snapshot readback did not produce this request')
