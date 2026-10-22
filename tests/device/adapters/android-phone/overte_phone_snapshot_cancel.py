"""Original bounded normal Capture/Cancel input recipe and historical sources.

This is not a feature verdict: the owner must still pin the real VM source,
join independent current UI/native/files/peer evidence and verify quiet time.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import typed_equal
from overte_phone_snapshot_source import source,review,nonce,text
from overte_phone_snapshot_controls import original_path

FILE='phone-snapshot-cancel.json'


def input_command(value,*,cancel=False):
    exact(value,{'schemaVersion','commandId','action','controlId','controlToken','instance','generation','sequence','observedElapsedMs'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId'])
        and value['action']=='activate' and value['controlId']==('snapshot.cancel-capture' if cancel else 'snapshot.capture')
        and all(nonce(value[key]) for key in ('controlToken','instance','generation'))
        and integer(value['sequence'],1) and integer(value['observedElapsedMs']))


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','jobId','operation','request'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-snapshot-cancel'
        and all(nonce(value[key]) for key in ('commandId','runId','jobId'))
        and value['operation'] in ('start','observe','retire') and type(value['request']) is dict)
    if value['operation']=='start':
        input_command(value['request']);need(value['request']['commandId']==value['jobId'])
    else:need(value['request']=={})
    return value


def original(value,epoch):
    exact(value,{'capturedEpochMs','native','review'})
    need(integer(value['capturedEpochMs'],1,epoch))
    source(value['native'],value['capturedEpochMs'],native_core=True)
    review(value['review'],original_path);need(value['review']['present'])
    return value


def idle(value):
    native=value['native'];ui=value['review']['review'];latest={}
    for row in native['scriptHistory']['events']:latest[row['id']]=row['kind']
    return (not any(ui[key] for key in ('capturing','processing','exportBusy','exportTicket','uploadPath'))
        and not native['captures'] and not native['uploads']
        and not any(phase in ('pending','processing') for phase in latest.values()))


def prefix(before,after):
    a,b=before['native'],after['native']
    need(after['capturedEpochMs']>=before['capturedEpochMs'] and a['storageRoot']==b['storageRoot']
        and typed_equal(a['history'],b['history']) and not b['captures'] and not b['uploads']
        and a['scriptHistory']['instance']==b['scriptHistory']['instance']
        and typed_equal(a['scriptHistory']['events'],b['scriptHistory']['events'][:a['scriptHistory']['sequence']]))


def receipt(value,request,pid):
    exact(value,{'schemaVersion','commandId','instance','generation','sequence','processId','performed'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and type(value['performed']) is bool
        and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1)
        and all(typed_equal(value[key],request[key]) for key in ('commandId','instance','generation','sequence')))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source','jobs'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
        and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)
    row=value['source']
    exact(row,{'snapshotFastCancelVersion','instance','job','runId','phase','error','startedEpochMs','completedEpochMs','observedEpochMs',
        'timerActive','retired','request','captureCommand','captureInput','cancelCommand','cancelInput','before','pending','cancelled','retirement','current'})
    need(type(row['snapshotFastCancelVersion']) is int and row['snapshotFastCancelVersion']==1 and nonce(row['instance'])
        and row['job']==request['jobId'] and row['runId']==request['runId']
        and row['phase'] in ('capturing','cancelling','complete','failed') and text(row['error'],128)
        and type(row['timerActive']) is bool and type(row['retired']) is bool
        and integer(row['startedEpochMs'],1,value['capturedEpochMs'])
        and integer(row['observedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']))
    input_command(row['captureCommand']);need(row['captureCommand']['commandId']==row['job'])
    if request['operation']=='start':need(typed_equal(row['captureCommand'],request['request']))
    terminal=row['phase'] in ('complete','failed')
    need(row['timerActive'] is (not terminal) and (row['phase']=='failed' if row['error'] else row['phase']!='failed'))
    need(integer(row['completedEpochMs'],row['startedEpochMs'],row['observedEpochMs']) if terminal else integer(row['completedEpochMs'],0,0))
    for key in ('before','pending','cancelled','retirement','current'):
        need(type(row[key]) is dict)
        if row[key]:original(row[key],row['observedEpochMs'])
    need(bool(row['current']) and value['requestedEpochMs']<=row['current']['capturedEpochMs']<=row['observedEpochMs']
        and row['observedEpochMs']-row['current']['capturedEpochMs']<1500)
    if row['captureInput']:receipt(row['captureInput'],row['captureCommand'],pid)
    if row['cancelCommand']:
        input_command(row['cancelCommand'],cancel=True)
        need(row['cancelCommand']['instance']==row['captureCommand']['instance']
            and row['cancelCommand']['generation']==row['captureCommand']['generation']
            and row['cancelCommand']['sequence']==row['captureCommand']['sequence']+1)
        if row['cancelInput']:receipt(row['cancelInput'],row['cancelCommand'],pid)
    else:need(row['cancelInput']=={})
    if row['phase']=='complete':
        before,pending,cancelled=row['before'],row['pending'],row['cancelled']
        need(bool(before) and bool(pending) and bool(cancelled) and idle(before) and idle(cancelled)
            and row['captureInput']['performed'] is True and row['cancelInput']['performed'] is True and not row['error'])
        prefix(before,pending);prefix(before,cancelled)
        a,b,c=(item['native']['scriptHistory']['events'] for item in (before,pending,cancelled))
        need(len(b)==len(a)+1 and len(c)==len(b)+1 and typed_equal(c[:-1],b))
        first,last=b[-1],c[-1]
        need(first['kind']=='pending' and first['mode']=='animated' and first['id']==row['request']==last['id']
            and last['kind']=='cancelled' and last['caller']['snapshotWork']['timers']==[]
            and row['startedEpochMs']<=first['capturedEpochMs']<=pending['capturedEpochMs']
            and pending['capturedEpochMs']-row['startedEpochMs']<300
            and last['capturedEpochMs']>=pending['capturedEpochMs']
            and pending['review']['review']['capturing'] and not pending['review']['review']['processing'])
        timers=first['caller']['snapshotWork']['timers']
        need(sorted(item['intervalMs'] for item in timers)==[350,60000]
            and all(item['active'] and item['singleShot'] and item['remainingMs']>=0 for item in timers))
    if row['retired']:
        need(terminal and bool(row['retirement']) and idle(row['retirement']))
    else:need(row['retirement']=={})
    if request['operation']=='retire':need(row['retired'] and idle(row['current']))
    jobs=value['jobs'];need(type(jobs) is list and 1<=len(jobs)<=8);ids=[];instances=[];matches=[]
    for job in jobs:
        exact(job,{'job','runId','instance','phase','timerActive','retired'})
        need(all(nonce(job[key]) for key in ('job','runId','instance')) and job['phase'] in ('capturing','cancelling','complete','failed')
            and type(job['timerActive']) is bool and type(job['retired']) is bool
            and job['timerActive'] is (job['phase'] in ('capturing','cancelling'))
            and (not job['retired'] or job['phase'] in ('complete','failed')))
        ids.append(job['job']);instances.append(job['instance'])
        if job['job']==row['job']:matches.append(job)
    need(ids==sorted(set(ids)) and len(set(instances))==len(instances) and len(matches)==1 and all(typed_equal(matches[0][key],row[key]) for key in matches[0]))
    return value


class PhoneSnapshotCancel:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
        self.jobs={}

    def request(self,run,job,operation,request=None):
        try:
            value=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-cancel',runId=run,
                jobId=job,operation=operation,request={} if request is None else request))
            need(self.guard() is not False);started=previous=self.monotonic();need(number(started,0,1e15))
            barrier=self.clock_ms();need(integer(barrier,1));self.send(value)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:actual=decode(raw) if raw else None
                except json.JSONDecodeError:actual=None
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(actual) is dict and actual.get('requestId')==value['commandId']:
                    validate(actual,value,self.pid,self.clock_ms());need(actual['requestedEpochMs']>=barrier)
                    if self.last is not None:
                        need(actual['instance']==self.last['instance'] and actual['sequence']>self.last['sequence']
                            and actual['capturedEpochMs']>=self.last['capturedEpochMs'])
                        after={row['job']:row for row in actual['jobs']}
                        for prior in self.last['jobs']:
                            need(prior['job'] in after);present=after[prior['job']]
                            need(all(typed_equal(prior[key],present[key]) for key in ('job','runId','instance')))
                            if prior['phase'] in ('complete','failed'):need(present['phase']==prior['phase'])
                            if prior['retired']:need(present['retired'])
                    old=self.jobs.get(job);current=actual['source']
                    if old is not None:
                        need(all(typed_equal(old[key],current[key]) for key in ('instance','job','runId','startedEpochMs','captureCommand')))
                        for key in ('before','pending','cancelled','captureInput','cancelCommand','cancelInput','retirement'):
                            if old[key]:need(typed_equal(old[key],current[key]))
                        if old['phase'] in ('complete','failed'):
                            need(all(typed_equal(old[key],current[key]) for key in ('phase','error','completedEpochMs','request')))
                        if old['retired']:need(current['retired'])
                    need(len(self.jobs)<8 or job in self.jobs)
                    need(self.guard() is not False);fresh(actual['capturedEpochMs'],self.clock_ms())
                    now=self.monotonic();need(number(now,previous,1e15) and now-started<5)
                    self.jobs[job]=deepcopy(current)
                    self.last=deepcopy(actual);return deepcopy(actual)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone Snapshot Capture/Cancel source is unavailable or invalid') from None
        raise NativeUIError('Original Phone Snapshot Capture/Cancel did not produce this request')
