"""Opt-in iOS process-end retirement, separate from live feature observations.

These codecs bind originals; feature decoders must establish actual native
restoration, held resources, process death and canonical SDK deletion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import re

from .contract import exact, identifier, number, result as observation, typed_equal
from .retirement_receipts import binding, digest, sha
from .scenarios import SCENARIOS
from .witness import projection

VERSION=1
PROFILE='ios-native-process-end-v1'
ROLES=('primary','actor')
KINDS=('qt-root','qsg-root','qimage','wk-view','native-holder')


def need(value):
    if not value:raise ValueError('Original terminal retirement is unavailable or invalid')


def bounded(value):
    need(len(json.dumps(value,allow_nan=False).encode())<=1048576)


def held(value):
    need(type(value) is list and len(value)<=64);names=[]
    for row in value:
        exact(row,{'resource','kind','originalSha256'},'held native resource')
        need(type(row['resource']) is str and re.fullmatch(r'panel:[a-z0-9-]{1,64}',row['resource'])
            and row['kind'] in KINDS and sha(row['originalSha256']))
        names.append(row['resource'])
    need(names==sorted(set(names)));return names


def description(value,*,area=None,run=None,ticket=None):
    exact(value,{'featureTerminalVersion','profile','area','runId','ticket','roles'},'terminal description')
    need(type(value['featureTerminalVersion']) is int and value['featureTerminalVersion']==VERSION
        and value['profile']==PROFILE and value['area'] in SCENARIOS
        and (area is None or value['area']==area) and (run is None or value['runId']==run)
        and (ticket is None or value['ticket']==ticket))
    identifier(value['runId']);identifier(value['ticket']);exact(value['roles'],ROLES,'terminal roles')
    for role in ROLES:
        row=value['roles'][role];exact(row,{'binding','heldResources','originalSha256'},'terminal role description')
        binding(row['binding']);held(row['heldResources']);need(sha(row['originalSha256']))
    # Both observations concern this candidate. Separate physical observers
    # may have different target/session/PID bindings; logical observers may not.
    a,b=(value['roles'][role]['binding'] for role in ROLES)
    need(all(a[k]==b[k] for k in ('sourceRevision','artifactSha256')))
    need(value['roles']['primary']['originalSha256']!=value['roles']['actor']['originalSha256'])
    if a['sessionSha256']==b['sessionSha256']:need(typed_equal(a,b))
    return value


def window(rows,descriptor):
    description(descriptor);need(type(rows) is list and 3<=len(rows)<=81)
    first=None;previous=None;actor_previous=0
    for row in rows:
        exact(row,{'primary','actor'},'terminal live pair');primary,actor=row['primary'],row['actor']
        observation('feature.'+descriptor['area']+'.observe',primary)
        exact(actor,{'ticket','actor','actorSequence','capturedEpochMs','facts','sequence','receivedEpochMs'},'terminal actor original')
        need(primary['runId']==descriptor['runId'] and actor['ticket']==descriptor['ticket']
            and actor['actor']=='owned-observer' and type(actor['actorSequence']) is int
            and actor['actorSequence']>actor_previous and type(actor['sequence']) is int and actor['sequence']>0
            and typed_equal(actor['facts'],projection(descriptor['area'],primary['state'])))
        number(actor['capturedEpochMs'],1);number(actor['receivedEpochMs'],actor['capturedEpochMs']-250,actor['capturedEpochMs']+1500)
        need(primary['resources']==held(descriptor['roles']['primary']['heldResources']))
        if first is None:first=row
        else:
            need(primary['sequence']>previous['primary']['sequence']
                and primary['capturedEpochMs']>=previous['primary']['capturedEpochMs']
                and actor['capturedEpochMs']>=previous['actor']['capturedEpochMs']
                and actor['sequence']>previous['actor']['sequence']
                and typed_equal(primary['state'],first['primary']['state'])
                and typed_equal(primary['lifecycle'],first['primary']['lifecycle']))
        previous=row;actor_previous=actor['actorSequence']
    for role in ROLES:
        need(3000<=rows[-1][role]['capturedEpochMs']-rows[0][role]['capturedEpochMs']<60000)
    return rows


def sealed(value,descriptor=None,rows=None):
    exact(value,{'featureTerminalSealVersion','description','windowSha256','liveOriginalSha256'},'terminal live seal')
    need(type(value['featureTerminalSealVersion']) is int and value['featureTerminalSealVersion']==VERSION
        and sha(value['windowSha256']) and sha(value['liveOriginalSha256']))
    description(value['description'])
    if descriptor is not None:need(typed_equal(value['description'],descriptor))
    if rows is not None:window(rows,value['description']);need(value['windowSha256']==digest(rows))
    return value


def os_quiet(value,pid):
    exact(value,{'source','clockDomain','instance','processId','samples','originalSha256',
        'hostAfterFirstEpochMs','hostBeforeLastEpochMs','hostAfterFirstMonotonic','hostBeforeLastMonotonic',
        'osAfterFirstEpochMs','osBeforeLastEpochMs','osAfterFirstMonotonicMs','osBeforeLastMonotonicMs'},'terminal OS quiet')
    need(value['source']=='dvt-owned-pid-and-bundle-state' and value['clockDomain']=='appium-node-host'
        and type(value['processId']) is int and str(value['processId'])==pid
        and type(value['samples']) is int and 3<=value['samples']<=128 and sha(value['originalSha256']))
    identifier(value['instance']);intervals=[]
    for a,b,scale in (('hostAfterFirstEpochMs','hostBeforeLastEpochMs',1),
        ('hostAfterFirstMonotonic','hostBeforeLastMonotonic',1000),('osAfterFirstEpochMs','osBeforeLastEpochMs',1),
        ('osAfterFirstMonotonicMs','osBeforeLastMonotonicMs',1)):
        duration=(number(value[b])-number(value[a]))*scale;need(3000<=duration<60000);intervals.append(duration)
    need(max(intervals)-min(intervals)<=500)


def ended(value,seal=None):
    exact(value,{'featureTerminalEndVersion','seal','roles'},'terminal process-end result')
    need(type(value['featureTerminalEndVersion']) is int and value['featureTerminalEndVersion']==VERSION)
    sealed(value['seal']);exact(value['roles'],ROLES,'terminal ended roles')
    if seal is not None:need(typed_equal(value['seal'],seal))
    for role in ROLES:
        row=value['roles'][role];prior=value['seal']['description']['roles'][role]
        exact(row,{'binding','heldOriginalSha256','stopOriginalSha256','osAbsence','sdkDeletionOriginalSha256','archiveSha256'},'terminal ended role')
        need(typed_equal(row['binding'],prior['binding']) and row['heldOriginalSha256']==prior['originalSha256']
            and all(sha(row[k]) for k in ('stopOriginalSha256','sdkDeletionOriginalSha256','archiveSha256')))
        os_quiet(row['osAbsence'],row['binding']['processIdentity'])
    a,b=(value['roles'][role] for role in ROLES)
    need(a['osAbsence']['originalSha256']!=b['osAbsence']['originalSha256'])
    if a['binding']['sessionSha256']==b['binding']['sessionSha256']:
        need(a['stopOriginalSha256']==b['stopOriginalSha256']
            and a['sdkDeletionOriginalSha256']==b['sdkDeletionOriginalSha256'])
    return value


def arguments(area,value):
    bounded(value)
    need(area in SCENARIOS and type(value) is dict and value.get('stage') in ('inspect','seal','finish'))
    fields={'contractVersion','runId','stage'}
    if value['stage']=='seal':fields|={'description','samples'}
    if value['stage']=='finish':fields|={'seal'}
    exact(value,fields,'terminal request');identifier(value['runId'])
    need(type(value['contractVersion']) is int and value['contractVersion']==VERSION)
    if value['stage']=='seal':description(value['description'],area=area,run=value['runId']);window(value['samples'],value['description'])
    if value['stage']=='finish':sealed(value['seal']);description(value['seal']['description'],area=area,run=value['runId'])
    return value


def result(area,value):
    bounded(value)
    need(type(value) is dict and value.get('stage') in ('inspect','seal','finish'))
    stage=value['stage'];key={'inspect':'description','seal':'seal','finish':'end'}[stage]
    exact(value,{'stage',key},'terminal response')
    if stage=='inspect':description(value[key],area=area)
    elif stage=='seal':sealed(value[key]);description(value[key]['description'],area=area)
    else:ended(value[key]);description(value[key]['seal']['description'],area=area)
    return value
