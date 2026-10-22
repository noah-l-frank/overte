"""Positive current native Qt/UIKit disposition, not a teardown entry or ACK.

Detached, cached and weakly dead objects remain separate actual facts. This
source never authorizes a Stop, claims OS absence, or repairs a native object.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters import tablet_web_source as native,uikit_input

VERSION=1
ACTION='feature-ios-tablet-web-state'
FILE=ACTION+'.json'
LIMIT=2097152
FLAGS={'active','viewPresent','presentationPresent','presentationAttached','windowPresent','cleanupFailed','imagePresent','inputActive',
    'loading','openTimerActive','deadlineActive','resumeOnForeground','sourceCurrent'}


def command(value):
    need(type(value) is dict and value.get('action')==ACTION);native.command(dict(value,action=native.ACTION));return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosTabletWebStateVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','uikitInstance','otherLiveTablets','owners','targets'})
    need(type(value['iosTabletWebStateVersion']) is int and value['iosTabletWebStateVersion']==VERSION
        and all(value[key]==query[key] for key in ('commandId','runId','fixtureUrl')) and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-tablet-web-state' and type(value['complete']) is bool
        and integer(value['otherLiveTablets'],0,128) and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    for key in ('instance','uikitInstance'):native.sources.identifier(value[key])
    a,b=value['clockBefore'],value['clockAfter'];native.sources.stamp(a);native.sources.stamp(b,floor=a)
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    need(type(value['owners']) is list and len(value['owners'])<=1024 and type(value['targets']) is list and len(value['targets'])<=1024)
    ids=set();handles=set()
    for row in value['owners']:
        exact(row,{'id','handle','source','firstObserved','expired','alive','current'});native.sources.identifier(row['id'])
        need(row['id'] not in ids and type(row['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',row['handle'])
            and row['handle'] not in handles and type(row['alive']) is bool);ids.add(row['id']);handles.add(row['handle'])
        native.source_reference(row['source'],dict(query,action=native.ACTION));native.sources.stamp(row['firstObserved'],b)
        if row['expired'] is not None:native.sources.stamp(row['expired'],b,row['firstObserved']);need(not row['alive'])
        else:need(row['alive'])
        current=row['current']
        if current is None:need(not row['alive'] or not value['complete'])
        else:
            need(row['alive']);exact(current,FLAGS|{'generation'});need(integer(current['generation']) and all(type(current[key]) is bool for key in FLAGS))
            if current['cleanupFailed']:need(not value['complete'])
    ids=set()
    for row in value['targets']:
        exact(row,{'source','kind','alive','windowAttached','superviewPresent','subtreeResponder'})
        need(row['kind'] in ('wk','qt-control') and all(type(row[key]) is bool for key in ('alive','windowAttached','superviewPresent','subtreeResponder')))
        target=row['source'];exact(target,{'view','bound','qtControl' if row['kind']=='qt-control' else 'identity'})
        native.sources.identifier(target['view']);need(target['view'] not in ids);ids.add(target['view']);native.sources.stamp(target['bound'])
        need(target['bound']['epochMs']<=a['epochMs'])  # The native timers have distinct actual origins.
        if row['kind']=='wk':uikit_input._identity(target['identity']);need(target['identity']['source']['fixtureUrl']==query['fixtureUrl'])
        else:uikit_input.qt_control(target['qtControl']);need(target['qtControl']['fixtureUrl']==query['fixtureUrl'] and target['qtControl']['featureRun']==query['runId'])
        if not row['alive']:need(not any(row[key] for key in ('windowAttached','superviewPresent','subtreeResponder')))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(all(value[key]==previous[key] for key in ('instance','uikitInstance','processId')) and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and (previous['complete'] or not value['complete']))
        native.sources.stamp(a,floor=previous['clockAfter'])
        for collection in ('owners','targets'):
            need(len(value[collection])>=len(previous[collection]))
            for old,new in zip(previous[collection],value[collection]):
                immutable={'id','handle','source','firstObserved'} if collection=='owners' else {'source','kind'}
                need(all(new[key]==old[key] for key in immutable) and (old['alive'] or not new['alive']))
                if collection=='owners':
                    if old['expired'] is not None:need(new['expired']==old['expired'])
                    elif new['expired'] is not None:native.sources.stamp(new['expired'],floor=previous['clockAfter'])
            if collection=='owners':
                for row in value[collection][len(previous[collection]):]:native.sources.stamp(row['firstObserved'],floor=previous['clockAfter'])
            else:
                for row in value[collection][len(previous[collection]):]:need(row['source']['bound']['epochMs']>=previous['clockAfter']['epochMs'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def join(value,sources,transcript,inputs):
    original(value);native.join_sources(transcript,sources);uikit_input.original(inputs)
    need(value['complete'] and inputs['complete'] and value['uikitInstance']==inputs['instance']
        and all(value[key]==sources[key]==transcript[key]==inputs[key] for key in ('processId','runId','fixtureUrl')))
    for row in value['owners']:
        need(any(event['identity']['handle']==row['handle'] and event['identity']['source']==row['source'] for event in transcript['events']))
    owned=[row for row in inputs['targets'] if uikit_input._owned(row,inputs)]
    need([row['source'] for row in value['targets']]==owned)
    return deepcopy(value)


def closed(value,sources,transcript,inputs,*,require_observed=True):
    """Actual page absence while a detached UIKit cache may still be alive."""
    join(value,sources,transcript,inputs);need(type(require_observed) is bool and value['otherLiveTablets']==0)
    if require_observed:need(value['owners'] and any(row['kind']=='wk' for row in value['targets']))
    for row in value['owners']:
        current=row['current']
        if row['alive']:
            need(current is not None and current['generation']==0 and not any(current[key] for key in FLAGS))
        else:need(row['expired'] is not None)
    for row in value['targets']:
        if row['kind']=='wk':need(not row['windowAttached'] and not row['subtreeResponder'])
    # Physical target alive, detached superviews and native QObject/cache
    # lifetimes are preserved. No generic weak-retirement receipt is minted.
    return deepcopy(value)


class IOSTabletWebState(native.IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
