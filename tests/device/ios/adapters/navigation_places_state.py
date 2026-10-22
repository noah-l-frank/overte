"""Join actual Places/bookmark/Go To fields; arrival and error remain separate.

All retained HTTP/model originals keep their original timestamps. No input,
search implementation, expected checkpoint or desired bookmark enters this
projection. It is not a whole Worlds observation or an independent publisher.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context as run_context
from feature_journeys.navigation_fixture import configuration
from navigation_observation import same_viewpoint
from ios.adapters import location_bookmarks as bookmarks,places_model as models,places_http as http
from ios.adapters import places_controls as controls,navigation_ui

VERSION=1
DIRECTORY_VERSION=1
FIELDS=frozenset(('bookmark','bookmarkName','searchQuery','searchResults','panel','addressDialog'))
ORIGINALS=frozenset(('bookmarks','model','ui','http'))
ADMISSION=frozenset(('runId','ticket','inputs','origin','nativeAfterEpochMs','providerAfterEpochMs','afterEvent'))


def pid(binding):
    context(binding);value=int(binding['processIdentity']);need(value>0 and str(value)==binding['processIdentity']);return value


def bookmark_entries(packet,run,process):
    query=dict(schemaVersion=1,commandId=packet.get('requestId'),action='feature-ios-location-bookmarks',runId=run)
    bookmarks.validate(packet,query,process)
    need(packet['loaded']['loadError'] is False)
    loaded=bookmarks.string_entries(packet['loaded']['entries']);saved=bookmarks.saved(packet['file'])
    need(saved['status'] in ('ready','absent'))
    persisted={} if saved['status']=='absent' else bookmarks.string_entries(saved['entries'])
    need(same(loaded,persisted));return loaded


def bookmark_baseline(binding,run,packet):
    """Freeze actual loaded/disk admission, including physical-file distinction."""
    identifier(run);actual=bookmark_entries(packet,run,pid(binding));ctx=run_context(run)
    need(not any(name in actual for name in (ctx['name'],ctx['renamed'])))
    return dict(binding=deepcopy(binding),runId=run,original=deepcopy(packet),originalSha256=digest(packet))


def baseline_entries(value,run,binding):
    exact(value,{'binding','runId','original','originalSha256'})
    need(value['runId']==run and value['originalSha256']==digest(value['original']))
    baseline=bookmark_baseline(value['binding'],run,value['original']);need(same(baseline,value))
    # Original process/session may have been replaced by the separately owned
    # restart; installed candidate and target admission cannot be replaced.
    need(all(value['binding'][key]==binding[key] for key in ('sourceRevision','artifactSha256','targetFingerprint')))
    return bookmark_entries(value['original'],run,pid(value['binding']))


def directory_proof(binding,observations,admission):
    """A genuine original first-refresh join, reusable without retiming it."""
    process=pid(binding);exact(observations,{'http','model','provider'});exact(admission,ADMISSION)
    run=identifier(admission['runId']);identifier(admission['ticket'])
    inputs,_urls=configuration(admission['inputs'])
    need(inputs['sourceRevision']==binding['sourceRevision'] and observations['http']['processId']==process
         and observations['model']['processId']==process)
    result=http.consumed(observations['http'],observations['model'],provider_status=observations['provider'],
        provider_instance=observations['provider']['instance'],inputs=inputs,owned_origin=admission['origin'],run=run,
        ticket=admission['ticket'],after_epoch=admission['nativeAfterEpochMs'],
        provider_after_epoch=admission['providerAfterEpochMs'],after_event=admission['afterEvent'])
    return dict(iosNavigationDirectoryProofVersion=DIRECTORY_VERSION,binding=deepcopy(binding),
        admission=deepcopy(admission),originals=deepcopy(observations),originalsSha256=digest(observations),materialized=result)


def validate_directory_proof(value,binding,run):
    exact(value,{'iosNavigationDirectoryProofVersion','binding','admission','originals','originalsSha256','materialized'})
    need(type(value['iosNavigationDirectoryProofVersion']) is int and value['iosNavigationDirectoryProofVersion']==DIRECTORY_VERSION
         and same(value['binding'],binding) and value['admission']['runId']==run
         and value['originalsSha256']==digest(value['originals']))
    expected=directory_proof(binding,value['originals'],value['admission']);need(same(expected,value))
    return deepcopy(expected['materialized'])


def compose(run,binding,originals,clock_join,*,baseline,provider_inputs,directory=None):
    """Six original fields only; neither location nor error is fabricated here."""
    identifier(run);process=pid(binding);exact(originals,ORIGINALS)
    inputs,urls=configuration(provider_inputs);need(inputs['sourceRevision']==binding['sourceRevision'])
    clock=validate_join(clock_join,originals);first,last=clock['nativeBefore'],clock['nativeAfter']
    need(first['processId']==last['processId']==process and same(first['lifecycle'],last['lifecycle']))
    for key,module in (('model',models),('http',http)):
        packet=originals[key]
        module.validate(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action=module.ACTION,runId=run),
                        process,last['capturedEpochMs'])
    saved=originals['bookmarks'];actual=bookmark_entries(saved,run,process)
    for key in ('model','bookmarks','http'):
        packet=originals[key]
        need(first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
    ui=originals['ui'];need(ui['processId']==process)
    address=navigation_ui.project(ui)
    need(first['capturedEpochMs']<=ui['sampleEpochMs']<=last['capturedEpochMs'])
    model=originals['model'];need(model['iosPlacesModelVersion']==2 and model['complete'] is True
        and ui['tabletShown']==model['tabletShown'])
    # Hidden retained queues/popup work cannot be concealed by a closed tablet.
    need(all(not root['loading'] and not root['pendingCommands'] and not root['timerRunning']
             and not root['dialog']['visible'] and root['popup']=='none' for root in model['roots']))
    before=baseline_entries(baseline,run,binding);ctx=run_context(run);names=(ctx['name'],ctx['renamed'])
    if same(baseline['binding'],binding):
        bookmarks.validate(saved,dict(schemaVersion=1,commandId=saved['requestId'],action='feature-ios-location-bookmarks',runId=run),
                           process,last['capturedEpochMs'],baseline['original'])
    owned=[name for name in names if name in actual];need(len(owned)<=1)
    need(same({name:value for name,value in actual.items() if name not in names},before))
    if owned:
        need(same_viewpoint(actual[owned[0]],urls['A']))
    fields=dict(bookmark=bool(owned),bookmarkName=owned[0] if owned else '',searchQuery='',searchResults=[],
                panel=model['tabletShown'],addressDialog=address['addressDialog'])
    if directory is not None:
        materialized=validate_directory_proof(directory,binding,run)
        need(same(directory['admission']['inputs'],inputs))
        prior_model=directory['originals']['model']
        if model['sequence']==prior_model['sequence']:need(same(model,prior_model))
        else:models.validate(model,dict(schemaVersion=1,commandId=model['requestId'],action=models.ACTION,runId=run),
                             process,last['capturedEpochMs'],prior_model)
        prior=directory['originals']['http'];current=originals['http']
        need(current['instance']==prior['instance'] and current['sequence']>=prior['sequence']
             and len(current['events'])>=len(prior['events']) and same(current['events'][:len(prior['events'])],prior['events']))
        if current['sequence']==prior['sequence']:need(same(current,prior))
        else:http.validate(current,dict(schemaVersion=1,commandId=current['requestId'],action=http.ACTION,runId=run),
                           process,last['capturedEpochMs'],prior)
        prefs=model['preferences'];need(prefs['metaverseOrigin']==directory['admission']['origin']
             and prefs['protocolSignature']==directory['admission']['inputs']['protocolSignature'])
    else:materialized=None
    selected=controls.project(ui)
    if fields['panel']:
        need(materialized is not None)
        page=models.join_controls(model,selected)
        need(page['tab']==0 and page['lists']['places']['visible'] and 'everyone' in page['maturityFilter']
             and same(page['bookmarkAddresses'],actual))
        editors=[row for row in selected['controls'] if row['id']=='places.search']
        need(len(editors)==1 and editors[0]['rootId']==page['rootId'] and editors[0]['qmlSource']==page['qmlSource']
             and editors[0]['value']==page['search'] and page['search'] in ('',ctx['name'],ctx['hidden']))
        # A retained genuine response may populate a fresh page. Its original
        # text-read time stays old; current native model/field observations must
        # independently retain that response's exact materialized record.
        records=[row for row in page['records'] if row.get('id')==ctx['destination']]
        need(len(records)==1 and same(records[0],materialized['record']))
        rows=[row for row in page['lists']['places']['rows'] if row['placeId']==ctx['destination']]
        need(len(rows)<=1 and (not rows or same(rows[0],materialized['row'])))
        fields.update(searchQuery=page['search'],searchResults=[row['placeId'] for row in rows])
    else:
        need(not any(root['active'] for root in model['roots']) and not selected['controls'])
    need(set(fields)==FIELDS)
    return dict(iosNavigationPlacesStateVersion=VERSION,runId=run,binding=deepcopy(binding),fields=fields,
        originalsSha256=digest(originals),baselineSha256=digest(baseline),
        directoryProofSha256=None if directory is None else digest(directory),
        nativeBeforeEpochMs=first['capturedEpochMs'],nativeAfterEpochMs=last['capturedEpochMs'],
        acquiredHostEpochMs=clock['hostBeforeEpochMs'])
