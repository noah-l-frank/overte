"""Original Places, storage, grounded arrival and current HTTP/modal join."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit
from adapters.native_feature_observation import need,integer,fresh
from feature_journeys.contract import state as public_state
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import configuration,validate_status
from navigation_observation import FreshNavigation,arrived,viewpoint_urls,same_viewpoint
from overte_phone_navigation_native import validate,VIEW_ACTION
from overte_phone_script_history import same


def request(value):return dict(schemaVersion=1,commandId=value['commandId'],action=VIEW_ACTION,runId=value['runId'])


def measurement(run,frame,baseline,inputs,fixture_origin,*,pid,epoch,after_epoch,previous=None,retired=False):
    """No action/expected state is accepted by this projection."""
    configuration(inputs);before,after=frame['before'],frame['after']
    validate(before,request(before),pid,epoch)
    validate(after,request(after),pid,epoch,previous=before)
    need(before['runId']==after['runId']==run and before['requestedEpochMs']>=after_epoch)
    left,right=before['source'],after['source']
    if not same(left,right):
        from feature_journeys.phase_fixture import PhasePending
        raise PhasePending('Original navigation state changed inside its acquisition bracket')
    need(left['endpoint'].rstrip('/')==fixture_origin and left['protocolSignature']==inputs['protocolSignature'])
    status=frame['navigation'];validate_status(status,instance=frame['providerInstance'],run=run,inputs=inputs)
    fresh(status['capturedEpochMs'],epoch);need(type(retired) is bool and status['active'] is (not retired) and status['ticket']==(None if retired else frame['ticket']))
    if retired:need(not frame['phase']['active'] and frame['phase']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
    probe=frame['probe'];fresh(probe['sampleEpochMs'],epoch)
    need(before['capturedEpochMs']<=probe['sampleEpochMs']<=after['capturedEpochMs'])
    selector=FreshNavigation()
    if previous is not None:selector.previous=previous['probe']
    _,advanced=selector.accept(probe);need(advanced)
    urls=viewpoint_urls(inputs['sceneUrl']);labels=[label for label in ('A','B') if arrived(probe,urls[label],label)]
    need(len(labels)==1)
    owned=context(run);bookmarks=left['storage']['bookmarks'];names={owned['name'],owned['renamed']}
    selected=[name for name in names if name in bookmarks];need(len(selected)<=1)
    need(all(same_viewpoint(bookmarks[name],urls['A']) for name in selected))
    unowned={key:value for key,value in bookmarks.items() if key not in names}
    if baseline is not None:
        need(same(unowned,baseline['source']['storage']['bookmarks']) and same(left['preferences'],baseline['source']['preferences'])
            and left['endpoint']==baseline['source']['endpoint'])
    else:need(not selected)
    ui=left['ui'];query='';results=[];need(not ui['bookmarkDialog'])
    if not ui['present'] and not ui['addressDialog']:need(not left['keyboard']['visible'])
    if ui['present']:
        need(not ui['loading'] and ui['pendingCommands']==0 and ui['activeTimers']==0 and 'everyone' in ui['maturity'])
        query=ui['query'];need(query in ('',owned['hidden'],owned['name']))
        original=[row for row in ui['records'] if row.get('id',row.get('placeID'))==owned['destination']]
        need(len(original)==1 and original[0].get('name')==owned['name'] and same_viewpoint(original[0].get('address'),urls['B'])
            and original[0].get('maturity')=='everyone')
        model=[row for row in ui['model'] if row['placeId']==owned['destination']]
        need(len(model)<=1 and all(row['placeName']==owned['name'] and same_viewpoint(row['placeAddress'],urls['B']) for row in model))
        results=[row['placeId'] for row in model]
        need(any(row['kind']=='directory' for row in status['responses']))
        servers=[row for row in ui['servers'] if row['serverUrl'].rstrip('/')==fixture_origin]
        need(len(servers)==1 and servers[0]['fetched'] and not servers[0]['failed'])
    error='none'
    if ui['notFoundModal']:
        pair=frame['missing'];need(type(pair) is dict)
        native,http=pair['native'],pair['http']
        need(same(ui['notFound']['nativeEvent'],native) and native['callbackEpochMs']<=ui['notFound']['createdEpochMs']<=before['capturedEpochMs'])
        need(native['runId']==run and native['origin']==fixture_origin and native['httpStatus']==404 and native['contentNotFound']
            and native['current'] and native['responseId']==http['responseId'] and http in status['responses']
            and http['ticket']==frame['ticket'] and http['kind']=='missing-name' and http['status']==404
            and native['callbackEpochMs']>=after_epoch and http['completedEpochMs']>=after_epoch)
        error='not-found'
    actual=dict(location=labels[0],bookmark=bool(selected),bookmarkName=selected[0] if selected else '',
        searchQuery=query,searchResults=results,error=error,panel=ui['present'],addressDialog=ui['addressDialog'])
    return deepcopy(public_state('world-navigation',actual,run))
