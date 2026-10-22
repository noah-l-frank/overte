"""Original AudioClient callback/timer/allocation facts; no process retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.pico4.lifecycle_source import nonce

VERSION=1
FIELDS={'audioPreviewLifetimeVersion','deferred','previewTimer','pendingLoopbackBytes','pendingLoopbackCapacityBytes',
    'loopbackDeviceAssigned','retainedPreviewBytes','previewBufferCapacityBytes','previewTapStateEmpty'}
REGISTRATION=('id','cycle','registeredEpochMs','scheduledDelayMs')
EVENTS=('enteredEpochMs','completedEpochMs','retiredEpochMs')


def validate(value,epoch,cycle):
    exact(value,FIELDS);need(type(value['audioPreviewLifetimeVersion']) is int and value['audioPreviewLifetimeVersion']==VERSION
        and integer(epoch,1) and integer(cycle,0,64))
    need(all(integer(value[key],0,64*1024*1024) for key in
        ('pendingLoopbackBytes','pendingLoopbackCapacityBytes','retainedPreviewBytes','previewBufferCapacityBytes'))
        and value['pendingLoopbackBytes']<=value['pendingLoopbackCapacityBytes'] and value['retainedPreviewBytes']<=value['previewBufferCapacityBytes']
        and type(value['loopbackDeviceAssigned']) is bool and type(value['previewTapStateEmpty']) is bool)
    deferred=value['deferred'];exact(deferred,{'complete','receiverId','callbacks'})
    need(deferred['complete'] is True and nonce(deferred['receiverId']) and type(deferred['callbacks']) is list
        and len(deferred['callbacks'])==cycle);ids=set()
    for index,row in enumerate(deferred['callbacks'],1):
        exact(row,{*REGISTRATION,*EVENTS,'receiverAlive','active','retired'})
        need(nonce(row['id']) and row['id'] not in ids and type(row['cycle']) is int and row['cycle']==index
            and integer(row['registeredEpochMs'],1,epoch) and type(row['scheduledDelayMs']) is int and row['scheduledDelayMs']==30000
            and all(type(row[key]) is bool for key in ('receiverAlive','active','retired'))
            and all(integer(row[key],0,epoch) for key in EVENTS));ids.add(row['id'])
        registered,entered,completed,retired=(row[key] for key in ('registeredEpochMs',*EVENTS))
        need((not entered or entered>=registered) and (not completed or entered and completed>=entered)
            and (not retired or retired>=registered and (not completed or retired>=completed)))
        if not entered:need(not completed and not row['active'])
        if row['active']:need(entered and not completed and not row['retired'])
        elif entered:need(completed>0)
        need(row['retired']==(retired>0) and (not row['retired'] or not row['active']))
    timer=value['previewTimer'];exact(timer,{'created','id','createdEpochMs','alive','active'})
    need(all(type(timer[key]) is bool for key in ('created','alive','active')))
    if timer['created']:need(nonce(timer['id']) and integer(timer['createdEpochMs'],1,epoch))
    else:need(timer['id']=='' and type(timer['createdEpochMs']) is int and timer['createdEpochMs']==0 and not timer['alive'] and not timer['active'])
    if timer['active']:need(timer['created'] and timer['alive'])
    return value


def accept(previous,current):
    if previous is not None:
        need(current['deferred']['receiverId']==previous['deferred']['receiverId']
            and len(current['deferred']['callbacks'])>=len(previous['deferred']['callbacks']))
        for old,new in zip(previous['deferred']['callbacks'],current['deferred']['callbacks']):
            need(all(old[key]==new[key] for key in REGISTRATION)
                and (old['receiverAlive'] or not new['receiverAlive']) and (not old['retired'] or new['retired']))
            for key in EVENTS:
                if old[key]:need(new[key]==old[key])
        old,new=previous['previewTimer'],current['previewTimer']
        if old['created']:need(new['created'] and all(new[key]==old[key] for key in ('id','createdEpochMs')) and (old['alive'] or not new['alive']))
    return deepcopy(current)


def deferred_retired(value):
    return all(row['retired'] and not row['active'] for row in value['deferred']['callbacks'])


def restored(value,original):
    # Only these actual retained resources are compared. Registry metadata,
    # Qt contexts and process scopes deliberately remain separate owners.
    return (deferred_retired(value) and value['previewTapStateEmpty']
        and all(value[key]==original[key] for key in ('pendingLoopbackBytes','pendingLoopbackCapacityBytes','loopbackDeviceAssigned',
            'retainedPreviewBytes','previewBufferCapacityBytes')) and value['previewTimer']==original['previewTimer'])
