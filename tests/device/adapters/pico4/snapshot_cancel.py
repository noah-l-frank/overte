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
from adapters.pico4.snapshot_originals import validate as capture_packet,accept as capture_accept,nonce
from adapters.pico4.snapshot_script_originals import validate as script_packet,accept as script_accept
from adapters.pico4.snapshot_review import validate as review
from adapters.pico4.navigation import identifier,NativeNavigationIO
from adapters.script_journey.lock import ScriptSourceLock
import hashlib
from adapters.native_script_work import validate as work_packet,scope as work_scope

VERSION=1
LIMIT=262144

def text(value,limit):return type(value) is str and len(value)<=limit

class PicoSnapshotCancelIO(NativeNavigationIO):
    DIRECTORY='files/overte-e2e/snapshot-cancel-ui-'


def input_command(value,*,cancel=False):
    exact(value,{'schemaVersion','commandId','action','controlId','controlToken','bridgeId','generation','sequence','observedElapsedMs'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and identifier(value['commandId'])
        and value['action']=='activate' and value['controlId']==('snapshot.cancel' if cancel else 'snapshot.capture')
        and all(identifier(value[key]) for key in ('controlToken','bridgeId','generation'))
        and integer(value['sequence'],1) and integer(value['observedElapsedMs']))


def command(value):
    extra={'closedReadWorkRequestId'} if type(value) is dict and 'closedReadWorkRequestId' in value else set()
    exact(value,{'schemaVersion','commandId','action','runId','jobId','operation','request'}|extra)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-pico-snapshot-cancel'
        and all(nonce(value[key]) for key in ('commandId','runId','jobId'))
        and value['operation'] in ('start','observe','retire') and type(value['request']) is dict)
    if value['operation']=='start':
        input_command(value['request'])
    else:need(value['request']=={})
    if extra:need(value['operation'] in ('observe','retire') and nonce(value['closedReadWorkRequestId']))
    return value


def original(value,epoch,*,allow_closed=False,caller=None,pid=None):
    extra={'scriptWork'} if type(value) is dict and 'scriptWork' in value else set()
    exact(value,{'capturedEpochMs','native','script','review'}|extra)
    need(integer(value['capturedEpochMs'],1,epoch))
    native,script=value['native'],value['script']
    capture_packet(native,native['runId'],native['commandId'],native['pid'],value['capturedEpochMs'])
    script_packet(script,native['runId'],script['commandId'],native['pid'],value['capturedEpochMs'])
    need(native['snapshotNativeCaptureVersion']==2 and script['snapshotScriptOriginalsVersion']==2
        and native['commandId']!=script['commandId'])
    review(value['review']);need(value['review']['snapshotReviewObservationVersion']==2)
    visible=value['review']['present'] and value['review']['review']['visible']
    if visible:need(not extra)
    else:
        need(allow_closed and extra and caller is not None and integer(pid,1))
        packet=value['scriptWork'];request=dict(schemaVersion=1,commandId=packet['requestId'],action='feature-script-work-observe',managerInstance=caller['manager']['instance'])
        work_packet(packet,request,pid,value['capturedEpochMs'])
        need(typed_equal(packet['source']['manager'],caller['manager']) and typed_equal(packet['source']['code'],caller['code']))
        selected=work_scope(packet,caller['compilation'])
        need(not selected['evaluating'] and not selected['timers'] and not selected['unknownTimers']
            and all(selected[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))
        own=[row for row in packet['source']['work']['activity'] if row['scriptId']==caller['compilation']['scriptId']];need(len(own)==1)
        need(all(own[0][key]>=caller['snapshotWork'][key] for key in ('signalInvocations','timerInvocations','timerRegistrations')))
        need(idle(value))
    return value


def idle(value):
    native=value['native'];ui=value['review']['review'] or {};latest={}
    for row in value['script']['history']['events']:latest[row['id']]=row['kind']
    resources=native['resources']
    return ((bool(ui) or 'scriptWork' in value) and not any(ui.get(key) for key in ('capturing','processing','exportBusy','exportTicket','uploadPath'))
        and value['script']['activeUploads']==0 and not resources['activeRequests'] and not resources['taking360']
        and not resources['waitingOnSnapshot'] and not resources['projectionTimerActive'] and not resources['projectionImagesBytes']
        and all(not row['alive'] for row in native['requests']) and not any(phase in ('pending','processing') for phase in latest.values()))


def prefix(before,after):
    need(typed_equal(before['native']['requests'],after['native']['requests']) and after['script']['activeUploads']==0)
    history_prefix(before,after)


def history_prefix(before,after):
    need(after['capturedEpochMs']>=before['capturedEpochMs'])
    if not typed_equal(before['native'],after['native']):capture_accept(before['native'],after['native'])
    if not typed_equal(before['script'],after['script']):script_accept(before['script'],after['script'])


def receipt(value,request,pid):
    exact(value,{'schemaVersion','commandId','bridgeId','sequence','processId','performed','error','updatedEpochMs'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and type(value['performed']) is bool
        and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1)
        and integer(value['updatedEpochMs'],1) and text(value['error'],128) and (not value['performed'] or value['error']=='')
        and all(typed_equal(value[key],request[key]) for key in ('commandId','bridgeId','sequence')))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source','jobs'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
        and value['runId']==request['runId'] and nonce(value['instance']) and integer(value['sequence'],1)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)
    row=value['source']
    exact(row,{'picoSnapshotFastCancelVersion','instance','job','runId','phase','error','startedEpochMs','completedEpochMs','observedEpochMs',
        'timerActive','retired','request','captureCommand','captureInput','cancelCommand','cancelInput','before','pending','cancelled','retirement','current'})
    need(type(row['picoSnapshotFastCancelVersion']) is int and row['picoSnapshotFastCancelVersion']==1 and nonce(row['instance'])
        and row['job']==request['jobId'] and row['runId']==request['runId']
        and row['phase'] in ('capturing','cancelling','complete','failed') and text(row['error'],128)
        and type(row['timerActive']) is bool and type(row['retired']) is bool
        and integer(row['startedEpochMs'],1,value['capturedEpochMs'])
        and integer(row['observedEpochMs'],value['requestedEpochMs'],value['capturedEpochMs']))
    input_command(row['captureCommand'])
    if request['operation']=='start':need(typed_equal(row['captureCommand'],request['request']))
    terminal=row['phase'] in ('complete','failed')
    need(row['timerActive'] is (not terminal) and (row['phase']=='failed' if row['error'] else row['phase']!='failed'))
    need(integer(row['completedEpochMs'],row['startedEpochMs'],row['observedEpochMs']) if terminal else integer(row['completedEpochMs'],0,0))
    for key in ('before','pending','cancelled'):
        need(type(row[key]) is dict)
        if row[key]:
            original(row[key],row['observedEpochMs']);need(row[key]['native']['pid']==pid and row[key]['native']['runId']==request['runId'])
    selected=row['cancelled'] or row['pending']
    caller=selected['script']['history']['events'][-1]['caller'] if selected else None
    for key in ('retirement','current'):
        need(type(row[key]) is dict)
        if row[key]:
            original(row[key],row['observedEpochMs'],allow_closed=terminal,caller=caller,pid=pid)
            need(row[key]['native']['pid']==pid and row[key]['native']['runId']==request['runId'])
    prior=None;queries={}
    for key in ('before','pending','cancelled','retirement','current'):
        if row[key]:
            for kind in ('native','script'):
                packet=row[key][kind];query=packet['commandId']
                if query in queries:need(queries[query][0]==kind and typed_equal(queries[query][1],packet))
                else:queries[query]=(kind,packet)
            if prior is not None:history_prefix(prior,row[key])
            prior=row[key]
    if 'scriptWork' in row['current']:
        need(request.get('closedReadWorkRequestId')==row['current']['scriptWork']['requestId'])
    need(bool(row['current']) and value['requestedEpochMs']<=row['current']['capturedEpochMs']<=row['observedEpochMs']
        and row['observedEpochMs']-row['current']['capturedEpochMs']<1500)
    if row['captureInput']:receipt(row['captureInput'],row['captureCommand'],pid)
    if row['cancelCommand']:
        input_command(row['cancelCommand'],cancel=True)
        need(row['cancelCommand']['bridgeId']==row['captureCommand']['bridgeId']
            and row['cancelCommand']['generation']==row['captureCommand']['generation']
            and row['cancelCommand']['sequence']==row['captureCommand']['sequence']+1)
        if row['cancelInput']:receipt(row['cancelInput'],row['cancelCommand'],pid)
    else:need(row['cancelInput']=={})
    if row['phase']=='complete':
        before,pending,cancelled=row['before'],row['pending'],row['cancelled']
        need(bool(before) and bool(pending) and bool(cancelled) and idle(before) and idle(cancelled)
            and row['captureInput']['performed'] is True and row['cancelInput']['performed'] is True and not row['error'])
        settings=before['review']['review']
        need(before['review']['snapshotReviewObservationVersion']==2 and settings['captureSettingsLoaded']
            and settings['mode']==1 and settings['format']=='png'
            and settings['captureName']=='parity-'+request['runId'][:16]+'-animated')
        prefix(before,pending);prefix(before,cancelled)
        a,b,c=(item['script']['history']['events'] for item in (before,pending,cancelled))
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


class PicoSnapshotCancel:
    """One original NativeNavigationIO publisher; reconciliation never writes."""
    def __init__(self,io,clock_ms,pid,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(io,PicoSnapshotCancelIO) and isinstance(source_lock,ScriptSourceLock)
            and callable(io._before_send) and integer(pid,1) and all(callable(fn) for fn in (clock_ms,monotonic,sleep)))
        self.io,self.clock_ms,self.pid,self.lock=io,clock_ms,pid,source_lock
        self.monotonic,self.sleep=monotonic,sleep;self.last=self.raw=None;self.jobs={};self.issued=set();self.anchor=None
    @staticmethod
    def envelope(run,job,operation,request=None,*,closed_read_work_request_id=None):
        value=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-snapshot-cancel',runId=run,
            jobId=job,operation=operation,request={} if request is None else deepcopy(request))
        if closed_read_work_request_id is not None:value['closedReadWorkRequestId']=closed_read_work_request_id
        command(value);return value
    def restore(self,value,request,*,anchor):
        validate(value,request,self.pid,value['capturedEpochMs']);need(self.last is None)
        exact(anchor,{'hostMonotonic','nativeEpochMs'});need(number(anchor['hostMonotonic'],0,1e15) and integer(anchor['nativeEpochMs'],1)
            and value['capturedEpochMs']-5000<=anchor['nativeEpochMs']<=value['capturedEpochMs']+1500)
        self.anchor=deepcopy(anchor)
        self.last=deepcopy(value);self.jobs={value['source']['job']:deepcopy(value['source'])};self.issued.add(request['commandId'])
    def request(self,value):
        value=deepcopy(value);command(value)
        with self.lock.held():
            need(value['commandId'] not in self.issued and len(self.issued)<4096)
            self.issued.add(value['commandId']) # Uncertain publication is never retried.
            started=self.monotonic();requested=self.clock_ms()
            need(number(started,0,1e15) and integer(requested,1));self.io.bind_input()
            self.io.send(deepcopy(value)) # Exact owner callback after final original NativeNavigationIO guard.
            return self._read(value,started,requested)
    def reconcile(self,value):
        command(value)
        with self.lock.held():return self._read(value,self.monotonic(),None)
    def _read(self,request,started,minimum):
        need(number(started,0,1e15));job=request['jobId'];previous=started
        requested=self.clock_ms() if minimum is None else minimum;need(integer(requested,1))
        for attempt in range(31):
            self.io.guard();raw=self.io._read('status');need(raw is None or type(raw) is str and len(raw.encode())<=LIMIT)
            if raw:
                outer=decode(raw);exact(outer,{'commandId','packet'})
                if outer['commandId']==request['commandId']:
                    actual=outer['packet'];epoch=self.clock_ms();validate(actual,request,self.pid,epoch)
                    need(minimum is None or actual['requestedEpochMs']>=minimum)
                    if self.last is not None and not typed_equal(actual,self.last):
                        need(actual['instance']==self.last['instance'] and actual['sequence']>self.last['sequence']
                            and actual['capturedEpochMs']>=self.last['capturedEpochMs'])
                        after={row['job']:row for row in actual['jobs']}
                        for old in self.last['jobs']:
                            need(old['job'] in after);current=after[old['job']]
                            need(all(typed_equal(old[key],current[key]) for key in ('job','runId','instance')))
                            if old['phase'] in ('complete','failed'):need(current['phase']==old['phase'])
                            if old['retired']:need(current['retired'])
                    current=actual['source'];old=self.jobs.get(job)
                    if old is not None:
                        history_prefix(old['current'],current['current'])
                        need(all(typed_equal(old[key],current[key]) for key in ('instance','job','runId','startedEpochMs','captureCommand')))
                        for key in ('before','pending','cancelled','captureInput','cancelCommand','cancelInput','retirement'):
                            if old[key]:need(typed_equal(old[key],current[key]))
                        if old['phase'] in ('complete','failed'):
                            need(all(typed_equal(old[key],current[key]) for key in ('phase','error','completedEpochMs','request')))
                        if old['retired']:need(current['retired'])
                    need(len(self.jobs)<8 or job in self.jobs)
                    retained=self.last is not None and typed_equal(actual,self.last)
                    anchor=deepcopy(self.anchor) if retained else dict(hostMonotonic=started,nativeEpochMs=requested)
                    exact(anchor,{'hostMonotonic','nativeEpochMs'})
                    result=deepcopy(actual);saved=deepcopy(actual);jobs=deepcopy(self.jobs);jobs[job]=deepcopy(current)
                    self.io.guard();final=self.clock_ms();completed=self.monotonic()
                    need(number(completed,previous,1e15) and completed-started<5 and number(final,epoch,1e15)
                        and -250<=final-actual['capturedEpochMs'] and max(final-actual['capturedEpochMs'],
                            requested-actual['capturedEpochMs']+(completed-started)*1000,
                            anchor['nativeEpochMs']-actual['capturedEpochMs']+(completed-anchor['hostMonotonic'])*1000)<=1500
                        and completed>=anchor['hostMonotonic'] and final>=anchor['nativeEpochMs'])
                    need(request['commandId'] in self.issued or len(self.issued)<4096)
                    self.issued.add(request['commandId']);self.last,self.jobs,self.raw,self.anchor=saved,jobs,raw,anchor;return result
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and attempt<30);previous=now;self.sleep(.1)
        need(False)
    def original(self):
        need(self.raw is not None);return dict(raw=self.raw,sha256=hashlib.sha256(self.raw.encode()).hexdigest(),anchor=deepcopy(self.anchor))
