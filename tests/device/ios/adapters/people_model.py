"""Actual Pal materialized rows, retained prompts and QML request/timer state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re

from adapters.native_feature_observation import exact, fresh, integer, need
from ios.adapters.avatar_state import identity, session, text
from ios.adapters.places_model import IOSPlacesModel, tree
from ios.adapters.places_http import installed

VERSION = 1
ACTION = 'feature-ios-people-model'
FILE = ACTION+'.json'
LIMIT = 262144
PHASES = {'idle','outgoing','incoming','accepted','submitting','polling','success','declined','cancelled','error'}
TIMERS = {'selectionTimer','connectionsTimeoutTimer','connectionsRefreshScrollTimer'}
PANELS = {'connectionPrompt','letterboxMessage','comboDialog'}


def command(value):
    exact(value, {'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}', value['commandId']))
    identity(value['runId']);return value


def root(value, shown):
    exact(value, {'rootId','qmlSource','windowPresent','visible','active','connectionState','activeTab','myData',
        'ignored','nearbyUserModelData','timers','panels','nearbyRows','connectionRows','pagination','httpCallbacks','httpCounter'})
    session(value['rootId']);installed(value['qmlSource'],'/hifi/Pal.qml')
    for key in ('windowPresent','visible','active'):need(type(value[key]) is bool)
    need((not value['visible'] or value['windowPresent']) and value['active']==(shown and value['visible'])
         and value['activeTab'] in ('nearbyTab','connectionsTab'))
    state=value['connectionState'];need(type(state) is dict and set(state) in
        ({'phase','message','peerName'},{'phase','message','peerName','peer','requestId'}) and state['phase'] in PHASES)
    for key in set(state)-{'phase'}:text(state[key],4096)
    for key in ('myData','ignored'):need(type(value[key]) is dict);tree(value[key])
    for key in ('nearbyUserModelData','nearbyRows','connectionRows'):
        need(type(value[key]) is list and len(value[key])<=1000);tree(value[key])
        for row in value[key]:need(type(row) is dict and len(row)<=64)
    for row in value['connectionRows']:
        exact(row, {'userName','connection','profileUrl','placeName'})
        for item in row.values():text(item,4096)
    for key, names in (('timers',TIMERS),('panels',PANELS)):
        exact(value[key],names)
        for flag in value[key].values():need(type(flag) is bool)
    pagination=value['pagination'];exact(pagination, {'endpoint','initialized','requestPending','additionalFirstPageRequested',
        'delayedClear','retrievedAtLeastOnePage','currentPageToRetrieve','totalPages','totalEntries','itemsPerPage','sortKey','searchFilter'})
    need(pagination['endpoint']=='/api/v1/users/connections')
    for key in ('initialized','requestPending','additionalFirstPageRequested','delayedClear','retrievedAtLeastOnePage'):
        need(type(pagination[key]) is bool)
    need(integer(pagination['currentPageToRetrieve'],-1,1000000) and integer(pagination['totalPages'],0,1000000)
         and integer(pagination['totalEntries'],0,1000000) and integer(pagination['itemsPerPage'],1,1000))
    text(pagination['sortKey'],128);text(pagination['searchFilter'],4096)
    callbacks=value['httpCallbacks'];need(integer(value['httpCounter'],0,9007199254740991)
        and type(callbacks) is list and len(callbacks)<=256 and callbacks==sorted(set(callbacks)))
    for callback in callbacks:
        need(type(callback) is str and re.fullmatch('0|[1-9][0-9]{0,15}',callback)
             and int(callback)<value['httpCounter'])
    return value


def validate(value, query, pid, epoch=None, previous=None):
    command(query)
    exact(value, {'iosPeopleModelVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosPeopleModelVersion']) is int and value['iosPeopleModelVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and identity(value['instance'])
         and integer(value['sequence'],1,1000000000) and integer(pid,1) and type(value['processId']) is int
         and value['processId']==pid and value['clockDomain']=='native-main-people-model')
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock, {'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    before,after=value['clockBefore'],value['clockAfter'];utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source, {'complete','tabletShown','roots'})
    need(type(source['complete']) is bool and type(source['tabletShown']) is bool
         and type(source['roots']) is list and len(source['roots'])<=32)
    ids=[];active=0
    for entry in source['roots']:root(entry,source['tabletShown']);ids.append(entry['rootId']);active+=entry['active']
    need(active<=1 and ids==sorted(set(ids)) and len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
             and value['requestId']!=previous['requestId'] and value['runId']==previous['runId']
             and all(before[key]>=previous['clockAfter'][key] for key in before))
        old={entry['rootId']:entry for entry in previous['source']['roots']}
        for entry in source['roots']:
            if entry['rootId'] in old:
                prior=old[entry['rootId']]
                need(entry['qmlSource']==prior['qmlSource'] and entry['httpCounter']>=prior['httpCounter'])
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def current(value):
    original(value);need(value['source']['complete'])
    active=[entry for entry in value['source']['roots'] if entry['active']];need(len(active)==1)
    return deepcopy(active[0])


def relationship(value, username, *, present, after_epoch):
    """Actual completed Pal table only, independent of backend response success."""
    entry=current(value);text(username,4096);need(username and type(present) is bool and integer(after_epoch,1)
        and value['clockBefore']['epochMs']>=after_epoch and entry['activeTab']=='connectionsTab')
    page=entry['pagination']
    need(page['initialized'] and page['retrievedAtLeastOnePage'] and not page['requestPending']
         and not page['additionalFirstPageRequested'] and not page['delayedClear'] and page['currentPageToRetrieve']==-1
         and page['totalEntries']==len(entry['connectionRows']))
    rows=[row for row in entry['connectionRows'] if row['userName']==username];need(len(rows)<=1)
    if present:need(len(rows)==1 and rows[0]['connection']=='connection')
    else:need(not rows)
    return deepcopy(rows)


def drained(value):
    """QML originals only; native HTTP and protocol timers need separate proof."""
    original(value);need(value['source']['complete'])
    return all(not entry['active'] and entry['connectionState']['phase']=='idle' and not entry['httpCallbacks']
        and not any(entry['timers'].values()) and not any(entry['panels'].values())
        and not entry['pagination']['requestPending'] and not entry['pagination']['additionalFirstPageRequested']
        for entry in value['source']['roots'])


class IOSPeopleModel(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosPeopleModelAcquisitionVersion'
