"""Foreground-started passive native Snapshot observations during OS handoff.

The SDK reader never sends a client command. Every acquisition retains its
original VM/native timestamps; a paused event loop, expired lease or cached
file cannot become current evidence. This proves source logic, not a device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_account_observation import validate as account_packet,accept as account_continuity
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_readbacks import nonce,validate as readbacks_packet,continuity as readbacks_continuity
from overte_phone_snapshot_capture_source import validate as files_packet,continuity as files_continuity
from overte_phone_snapshot_upload_source import validate as upload_packet,continuity as upload_continuity
from overte_phone_snapshot_measurements import validate as measurements
from overte_phone_snapshot_source import continuity as snapshot_continuity

FILE='phone-snapshot-handoff.json'
CONTROL_FILE='phone-snapshot-handoff-result.json'
MAX_BYTES=1024*1024


def decode(raw):
    need(type(raw) is str and len(raw.encode())<=MAX_BYTES+16384)
    def pairs(items):
        value={}
        for key,item in items:
            need(key not in value);value[key]=item
        return value
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda _value:need(False))


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','handoffId','operation'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='phone-snapshot-handoff'
        and all(nonce(value[key]) for key in ('commandId','runId','handoffId')) and value['operation'] in ('start','observe','retire'))
    return value


def binding(value):
    exact(value,{'snapshotHandoffBindingVersion','runId','handoffId','instance','sourceInstance','processId','startedEpochMs','deadlineEpochMs'})
    need(type(value['snapshotHandoffBindingVersion']) is int and value['snapshotHandoffBindingVersion']==1
        and all(nonce(value[key]) for key in ('runId','handoffId','instance','sourceInstance')) and integer(value['processId'],1)
        and integer(value['startedEpochMs'],1) and value['deadlineEpochMs']==value['startedEpochMs']+60000
        and type(value['deadlineEpochMs']) is int)
    return value


def bound(control):
    """Extract only actual identities from an already validated start result."""
    source=control['source']
    value=dict(snapshotHandoffBindingVersion=1,runId=control['runId'],handoffId=control['handoffId'],instance=control['instance'],
        sourceInstance=source['instance'],processId=control['processId'],startedEpochMs=source['startedEpochMs'],deadlineEpochMs=source['deadlineEpochMs'])
    binding(value);return value


def jobs(value,owner,source):
    need(type(value) is list and 1<=len(value)<=8)
    identifiers=[];instances=set();selected=None
    for row in value:
        exact(row,{'runId','handoffId','instance','retired','timerActive','readActive','complete'})
        need(all(nonce(row[key]) for key in ('runId','handoffId','instance'))
            and all(type(row[key]) is bool for key in ('retired','timerActive','readActive','complete'))
            and row['instance'] not in instances and not row['readActive'])
        identifiers.append(row['handoffId']);instances.add(row['instance'])
        if row['handoffId']==owner['handoffId']:
            need(row['runId']==owner['runId'] and row['instance']==owner['sourceInstance']);selected=row
        else:need(row['retired'] and not row['timerActive'] and row['complete'])
    need(identifiers==sorted(set(identifiers)) and selected is not None
        and all(selected[key]==source[key] for key in ('retired','timerActive','readActive','complete')))


def original(value,owner,epoch,*,pins_path=None):
    binding(owner)
    exact(value,{'snapshotHandoffVersion','instance','runId','handoffId','processId','sequence','startedEpochMs','deadlineEpochMs',
        'capturedEpochMs','complete','error','retired','timerActive','readActive','source'})
    need(type(value['snapshotHandoffVersion']) is int and value['snapshotHandoffVersion']==1
        and value['instance']==owner['sourceInstance'] and all(value[key]==owner[key] for key in ('runId','handoffId','processId','startedEpochMs','deadlineEpochMs'))
        and integer(value['sequence'],1,1000000000) and value['complete'] is True and value['error']==''
        and type(value['retired']) is bool and type(value['timerActive']) is bool and value['readActive'] is False
        and value['timerActive']==(not value['retired']) and integer(value['capturedEpochMs'],value['startedEpochMs']))
    fresh(value['capturedEpochMs'],epoch)
    if not value['retired']:need(epoch<owner['deadlineEpochMs'] and value['capturedEpochMs']<owner['deadlineEpochMs'])
    batch=value['source'];exact(batch,{'context','group','readbacks','captureFiles','upload'})
    need(len(json.dumps(batch,separators=(',',':')).encode())<=MAX_BYTES)
    context=batch['context'];exact(context,{'snapshotHandoffContextVersion','requestedEpochMs','capturedEpochMs','lifecycle','account'})
    need(type(context['snapshotHandoffContextVersion']) is int and context['snapshotHandoffContextVersion']==1
        and integer(context['requestedEpochMs'],value['startedEpochMs']) and integer(context['capturedEpochMs'],context['requestedEpochMs'],value['capturedEpochMs']))
    fresh(context['requestedEpochMs'],epoch);fresh(context['capturedEpochMs'],epoch)
    exact(context['lifecycle'],{'backgrounds','activations','launches'})
    need(all(integer(count,0,1000000) for count in context['lifecycle'].values()) and context['lifecycle']['launches']>=1)
    account_packet(context['account'],context['capturedEpochMs'],context['requestedEpochMs'])
    run,pid=owner['runId'],owner['processId'];selected=measurements(batch['group'],run=run,pid=pid,epoch=epoch,pins_path=pins_path)
    packets=[batch['group'][key] for key in ('rootsBefore','script','snapshot','rootsAfter')]
    for key,validator,action,extra in (
        ('readbacks',readbacks_packet,'phone-snapshot-readback',dict(operation='observe',exportRequest='',resourceId='')),
        ('captureFiles',files_packet,'phone-snapshot-files-observe',{}),
        ('upload',upload_packet,'phone-snapshot-upload-observe',{})):
        packet=batch[key]
        validator(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action=action,runId=run,**extra),pid,epoch)
        packets.append(packet)
    previous=context['capturedEpochMs'];identifiers=set()
    for packet in packets:
        need(len(json.dumps(packet,separators=(',',':')).encode())<=262144)
        identity=packet.get('requestId',packet.get('commandId'))
        need(packet['instance']==owner['instance'] and nonce(identity) and identity not in identifiers
            and integer(packet['requestedEpochMs'],previous) and packet['capturedEpochMs']<=value['capturedEpochMs'])
        identifiers.add(identity);previous=packet['capturedEpochMs']
    need(value['capturedEpochMs']-context['requestedEpochMs']<1500)
    return selected


def continuity(before,after):
    a,b=before['source'],after['source']
    need(all(b[key]==a[key] for key in ('instance','runId','handoffId','processId','startedEpochMs','deadlineEpochMs'))
        and b['sequence']>a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs']
        and (not a['retired'] or b['retired']))
    old,new=a['source'],b['source']
    need(all(new['context']['lifecycle'][key]>=count for key,count in old['context']['lifecycle'].items()))
    account_continuity(old['context']['account']['observation'],new['context']['account'])
    for key,check in (('readbacks',readbacks_continuity),('captureFiles',files_continuity),('upload',upload_continuity)):
        check(old[key],new[key])
    snapshot_continuity(old['group']['snapshot'],new['group']['snapshot'])
    for key in ('rootsBefore','script','rootsAfter'):
        x,y=old['group'][key],new['group'][key]
        need(y['instance']==x['instance'] and y['sequence']>x['sequence'] and y['capturedEpochMs']>=x['capturedEpochMs'])
    old_jobs={row['handoffId']:row for row in before['jobs']};new_jobs={row['handoffId']:row for row in after['jobs']}
    need(set(old_jobs)<=set(new_jobs))
    for id,row in old_jobs.items():
        new=new_jobs[id];need(all(new[key]==row[key] for key in ('instance','runId','handoffId')) and (not row['retired'] or new==row))


def control(value,request,pid,epoch,*,pins_path=None):
    command(request)
    exact(value,{'snapshotHandoffControlVersion','requestId','runId','handoffId','instance','processId','sequence','capturedEpochMs','source','jobs'})
    need(type(value['snapshotHandoffControlVersion']) is int and value['snapshotHandoffControlVersion']==1
        and value['requestId']==request['commandId'] and all(value[key]==request[key] for key in ('runId','handoffId'))
        and nonce(value['instance']) and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1000000000))
    fresh(value['capturedEpochMs'],epoch);owner=bound(value)
    original(value['source'],owner,epoch,pins_path=pins_path);jobs(value['jobs'],owner,value['source'])
    need(value['capturedEpochMs']>=value['source']['capturedEpochMs'])
    if request['operation']=='start':need(not value['source']['retired'])
    if request['operation']=='retire':need(value['source']['retired'])
    return value


class PhoneSnapshotHandoffControl:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.read,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
    def request(self,run,operation,handoff_id):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-handoff',runId=run,handoffId=handoff_id,operation=operation))
            need(self.guard() is not False);start=previous=self.monotonic();requested=self.clock_ms();self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.read();need(type(raw) is str and len(raw.encode())<=MAX_BYTES+16384)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-start<5);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    control(value,request,self.pid,self.clock_ms());need(value['capturedEpochMs']>=requested)
                    if self.last is not None:
                        need(value['instance']==self.last['instance'] and value['sequence']>self.last['sequence'])
                        if value['handoffId']==self.last['handoffId']:
                            # Observe may read the same native sample; it is never
                            # relabeled a new acquisition or used as such.
                            if value['source']['sequence']==self.last['source']['sequence']:need(value['source']==self.last['source'])
                            else:continuity(self.last,value)
                    need(self.guard() is not False);fresh(value['capturedEpochMs'],self.clock_ms())
                    need(self.monotonic()-start<5);self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Snapshot handoff control is unavailable or invalid') from None
        raise NativeUIError('Original Snapshot handoff control did not produce this request')


class PhoneSnapshotHandoff:
    def __init__(self,read,clock_ms,guard,owner,*,monotonic=time.monotonic,sleep=time.sleep,pins_path=None):
        binding(owner);need(all(callable(fn) for fn in (read,clock_ms,guard,monotonic,sleep)))
        self.original,self.clock_ms,self.guard,self.owner=read,clock_ms,guard,deepcopy(owner)
        self.monotonic,self.sleep,self.pins_path,self.last=monotonic,sleep,pins_path,None
        self.last_clock=None
    def read(self):
        try:
            need(self.guard() is not False);start=previous=self.monotonic()
            need(number(start,0,1e15) and (self.last_clock is None or start>=self.last_clock))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=MAX_BYTES+16384)
                value=decode(raw)
                exact(value,{'snapshotHandoffSourceVersion','instance','processId','publishedEpochMs','source','jobs'})
                need(type(value['snapshotHandoffSourceVersion']) is int and value['snapshotHandoffSourceVersion']==1
                    and value['instance']==self.owner['instance'] and type(value['processId']) is int and value['processId']==self.owner['processId'])
                epoch=self.clock_ms();fresh(value['publishedEpochMs'],epoch)
                original(value['source'],self.owner,epoch,pins_path=self.pins_path);jobs(value['jobs'],self.owner,value['source'])
                need(integer(value['publishedEpochMs'],value['source']['capturedEpochMs'],epoch))
                need(self.guard() is not False);now=self.monotonic();need(number(now,previous,1e15) and now-start<5);previous=now
                if self.last is None or value['source']['sequence']>self.last['source']['sequence']:
                    if self.last is not None:continuity(self.last,value)
                    final=self.clock_ms();fresh(value['source']['capturedEpochMs'],final)
                    need(value['source']['retired'] or final<self.owner['deadlineEpochMs'])
                    need(self.guard() is not False and self.monotonic()-start<5)
                    self.last_clock=self.monotonic();need(number(self.last_clock,now,1e15) and self.last_clock-start<5)
                    self.last=deepcopy(value);return deepcopy(value['source']['source'])
                need(value==self.last and not value['source']['retired'] and attempt<50)
                self.sleep(.1)
        except Exception:raise NativeUIError('Original passive Snapshot handoff source is unavailable, stale or invalid') from None
        raise NativeUIError('Original passive Snapshot handoff source produced no new acquisition')
