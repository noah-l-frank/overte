"""Original native Snapshot request/worker weak lifetimes and callback history."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.script_feature.history import same
from ios.adapters.create_state import command as state_command, text
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-snapshot-captures'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    original=deepcopy(value);original['action']='feature-ios-create-state';state_command(original)
    need(value['action']==ACTION);return value


def identity(value):need(re.fullmatch('[a-f0-9]{32}',text(value,32)));return value


def activity(value):
    exact(value,{'requests','secondaryCapturePresent','secondaryTimerActive','secondaryTaking','secondaryFramePending','animated'})
    need(integer(value['requests'],0,8) and all(type(value[key]) is bool for key in
        ('secondaryCapturePresent','secondaryTimerActive','secondaryTaking','secondaryFramePending')))
    animated=value['animated'];exact(animated,{'capturePresent','encodingPresent','timerPresent','timerRunning','framePending','frames','delays'})
    need(all(type(animated[key]) is bool for key in ('capturePresent','encodingPresent','timerPresent','timerRunning','framePending'))
         and integer(animated['frames'],0,126) and integer(animated['delays'],0,126))
    return value


def ledger(value,epoch,previous=None):
    exact(value,{'complete','captures','resources','events','activity'})
    need(type(value['complete']) is bool and type(value['captures']) is list and len(value['captures'])<=64
         and type(value['resources']) is list and len(value['resources'])<=256
         and type(value['events']) is list and len(value['events'])<=1024)
    activity(value['activity']);ids=[];captures={}
    for row in value['captures']:
        exact(row,{'instance','requestId','bornEpochMs','alive','state','announced'})
        identity(row['instance']);ids.append(row['instance']);captures[row['instance']]=row
        need(type(row['requestId']) is str and (row['requestId']=='' or re.fullmatch('snap_[0-9]{1,16}_[0-9]{1,10}',row['requestId']))
             and integer(row['bornEpochMs'],1,epoch) and type(row['alive']) is bool)
        if row['alive']:need(type(row['state']) is int and row['state'] in (0,1,2) and type(row['announced']) is bool
                           and (row['state']!=2 or row['announced']))
        else:need(row['state'] is None and row['announced'] is None)
    need(ids==sorted(set(ids)))
    resources=[]
    for row in value['resources']:
        exact(row,{'instance','capture','kind','bornEpochMs','destroyedEpochMs','alive'})
        identity(row['instance']);resources.append(row['instance']);need(row['capture'] in captures
            and row['kind'] in ('animated-timer','animated-watcher','secondary-watcher')
            and integer(row['bornEpochMs'],captures[row['capture']]['bornEpochMs'],epoch) and type(row['alive']) is bool)
        if row['destroyedEpochMs'] is not None:need(integer(row['destroyedEpochMs'],row['bornEpochMs'],epoch) and not row['alive'])
        # QPointer may clear during destruction before destroyed is delivered.
        # The transient gap is readable, but cannot pass drained().
    need(resources==sorted(set(resources)))
    histories={id_:[] for id_ in ids};stamp=0
    for index,event in enumerate(value['events']):
        exact(event,{'sequence','capture','kind','capturedEpochMs','detail'})
        need(type(event['sequence']) is int and event['sequence']==index+1 and event['capture'] in histories
             and integer(event['capturedEpochMs'],max(1,stamp,captures[event['capture']]['bornEpochMs']),epoch))
        stamp=event['capturedEpochMs'];history=histories[event['capture']];kind=event['kind'];detail=event['detail']
        kinds=[row['kind'] for row in history];need(kind in ('begin','accepted','rejected','status-enqueued','status','cancel-requested','cancelled','cancel-delivered'))
        if kind=='begin':need(not history);exact(detail,set())
        else:
            need(kinds and kinds[0]=='begin')
            if kind in ('accepted','rejected'):need(kinds==['begin']);exact(detail,set())
            else:
                need('accepted' in kinds and 'rejected' not in kinds)
                if kind in ('status','status-enqueued'):
                    exact(detail,{'phase','hasPath','hasError'} if kind=='status' else {'phase'})
                    need(detail['phase'] in ('processing','complete','error'))
                    if kind=='status':
                        need(all(type(detail[key]) is bool for key in ('hasPath','hasError'))
                             and 'cancelled' not in kinds and not any(row['kind']=='status' and row['detail']['phase'] in ('complete','error') for row in history))
                else:
                    exact(detail,set())
                    if kind=='cancel-requested':need(kind not in kinds)
                    elif kind=='cancelled':need('cancel-requested' in kinds and kind not in kinds)
                    else:need('cancelled' in kinds and kind not in kinds)
        history.append(event)
    for id_,history in histories.items():
        need(history and history[0]['capturedEpochMs']>=captures[id_]['bornEpochMs'])
        row=captures[id_];kinds=[entry['kind'] for entry in history]
        terminal=any(entry['kind']=='status' and entry['detail']['phase'] in ('complete','error') for entry in history)
        if row['alive']:
            if 'cancelled' in kinds:need(row['state']==1)
            if terminal:need(row['state']==2)
            if row['state']==0:need(not terminal and 'cancelled' not in kinds)
            if 'cancel-delivered' in kinds:need(row['announced'])
    if previous is not None:
        ledger(previous,epoch);need(previous['complete'] or not value['complete'])
        need(same(value['events'][:len(previous['events'])],previous['events']))
        for category,immutable in (('captures',('instance','requestId','bornEpochMs')),('resources',('instance','capture','kind','bornEpochMs'))):
            current={row['instance']:row for row in value[category]}
            for old in previous[category]:
                need(old['instance'] in current);row=current[old['instance']]
                need(all(same(row[key],old[key]) for key in immutable) and (old['alive'] or not row['alive']))
                if category=='resources' and old['destroyedEpochMs'] is not None:need(row['destroyedEpochMs']==old['destroyedEpochMs'])
                if category=='captures' and old['alive'] and row['alive']:
                    need(old['state']==0 or row['state']==old['state']);need(not old['announced'] or row['announced'])
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosSnapshotCapturesVersion','requestId','runId','instance','sequence','processId',
                              'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotCapturesVersion']) is int and value['iosSnapshotCapturesVersion']==1 and value['requestId']==query['commandId']
         and value['runId']==query['runId'] and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and integer(value['sequence'],1,1000000000) and value['clockDomain']=='native-main-snapshot-captures');identity(value['instance'])
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    before,after=value['clockBefore'],value['clockAfter'];delta=after['epochMs']-before['epochMs'];elapsed=after['monotonicMs']-before['monotonicMs']
    need(0<=delta<1500 and 0<=elapsed<1500 and abs(delta-elapsed)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    ledger(value['source'],after['epochMs']);need(len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
             and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs'])
        ledger(value['source'],after['epochMs'],previous['source'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def drained(value):
    original(value);source=value['source'];need(source['complete'])
    need(all(not row['alive'] for row in source['captures']) and all(not row['alive'] and row['destroyedEpochMs'] is not None for row in source['resources']))
    active=source['activity'];need(all(not val for key,val in active.items() if key!='animated') and all(not val for val in active['animated'].values()))
    return deepcopy(source)


def pending_cancellation(native_before,pending_work,cancelled_work,native_after,scripts_root,*,_combined=False):
    """Prove the actual two-delay capture was cancelled before native begin.

    The result still requires independent owned-file absence and the normal
    input owner. It does not count a successful capture/export or finish a run.
    """
    need(type(_combined) is bool)
    from ios.adapters import snapshot_work,snapshot_combined_work
    work=snapshot_combined_work if _combined else snapshot_work
    drained(native_before);drained(native_after)
    validate(native_after,dict(schemaVersion=1,action=ACTION,commandId=native_after['requestId'],runId=native_after['runId']),
             native_before['processId'],previous=native_before)
    work.validate(cancelled_work,dict(schemaVersion=1,action=work.ACTION,commandId=cancelled_work['requestId'],runId=cancelled_work['runId']),
                  pending_work['processId'],previous=pending_work)
    need(len({value['processId'] for value in (native_before,pending_work,cancelled_work,native_after)})==1
         and len({value['runId'] for value in (native_before,pending_work,cancelled_work,native_after)})==1)
    pending=work.admit(pending_work,scripts_root);cancelled=work.admit(cancelled_work,scripts_root,quiet=True)
    need(pending['manager']==cancelled['manager'] and pending['state']['captureId'] and not pending['calls'])
    capture=pending['state']['captureId'];handles=pending['state']['timerHandles'];need(len(handles)==2 and pending['state']['overlaysHidden'])
    timer_sources=pending_work['source']['timerSources']['workers']
    native=next(row for row in timer_sources if row['membership']['instance']==pending['manager']['instance'])
    timers=[timer for timer in native['timerWork']['timers'] if timer['handle'] in handles and timer['destroyedEpochMs'] is None]
    need(len(timers)==2 and {row['intervalMs'] for row in timers}=={350,60000}
         and all(row['singleShot'] and row['activeAtBirth'] and row['fired']==row['pendingDispatch']==0 for row in timers))
    take=[row for row in pending['events'] if row['closure']=='takeSnapshot' and row['event']=='returned' and row['state']['captureId']==capture]
    need(len(take)==1 and native_before['clockAfter']['epochMs']<=take[0]['invokedEpochMs'])
    entries=[row for row in cancelled['events'] if row['closure']=='cancelNativeCapture' and row['event']=='entry'
             and row['state']['captureId']==capture and row['sequence']>pending['latest']['sequence']]
    need(len(entries)==1);entry=entries[0]
    finish=[row for row in cancelled['events'] if row['closure']==entry['closure'] and row['call']==entry['call']]
    need([row['event'] for row in finish]==['entry','returned','finally'] and all(not snapshot_work.pending(row['state']) for row in finish[1:])
         and native_after['clockBefore']['epochMs']>=finish[-1]['capturedEpochMs'])
    need(all(row['requestId']!=capture for row in native_after['source']['captures']))
    result=dict(iosSnapshotPendingCancellationVersion=2 if _combined else 1,captureId=capture,processId=native_after['processId'],
        runId=native_after['runId'],cancelCall=entry['call'],cancelledEpochMs=finish[-1]['capturedEpochMs'],
        nativeAfterSequence=native_after['sequence'],normalInputOwnerRequired=True,fileAbsenceRequired=True)
    if _combined:result['workProfile']='combined'
    return result


class IOSSnapshotCaptures(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotCapturesAcquisitionVersion'
