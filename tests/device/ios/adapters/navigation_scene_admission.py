"""Original static-scene admission prerequisites, without input or publication."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit

from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.graphics_subject_geometry import near
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.navigation_base_scene import validate_status as base_status
from feature_journeys.navigation_fixture import configuration
from ios.adapters import scene_inventory,navigation_state,places_model,places_http,navigation_dialogs,places_preferences
from ios.adapters import navigation_product_state as product,navigation_error_state as errors
from ios.adapters.navigation_places_state import bookmark_baseline,pid

VERSION=1
ORIGINALS=frozenset(('inventory','navigation','bookmarks','model','http','dialogs','replies','ui'))


def admit(run,binding,originals,clock_join,base,*,provider_instance,provider_inputs):
    """A bounded, initially quiet and replayable static base, not feature success.

    The whole owner must retain this exact proof and meet the original freshness
    deadline again before its first durable ordinary input. This pure function
    performs no read and cannot make a historical proof current.
    """
    identifier(run);identifier(provider_instance);process=pid(binding);exact(originals,ORIGINALS)
    inputs,_urls=configuration(provider_inputs);need(inputs['sourceRevision']==binding['sourceRevision'])
    base_status(base,instance=provider_instance,scene_url=inputs['sceneUrl'],source_revision=inputs['sourceRevision'])
    need(base['available'] and bool(base['responses']))
    clock=validate_join(clock_join,originals);first,last=clock['nativeBefore'],clock['nativeAfter']
    need(first['processId']==last['processId']==process and same(first['lifecycle'],last['lifecycle']))
    for name,module in (('inventory',scene_inventory),('navigation',navigation_state),('model',places_model),
                        ('http',places_http),('dialogs',navigation_dialogs)):
        packet=originals[name]
        module.validate(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),action=module.ACTION,runId=run),
                        process,last['capturedEpochMs'])
        need(first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
    bookmarks=originals['bookmarks'];baseline=bookmark_baseline(binding,run,bookmarks)
    # Ordinary add/delete cannot restore physical nonexistence. Admit a real
    # existing persistence file before any mutation instead of deleting a
    # product file behind its loaded LocationBookmarks object during cleanup.
    need(bookmarks['file']['status']=='ready'
         and first['capturedEpochMs']<=bookmarks['clockBefore']['epochMs']<=bookmarks['clockAfter']['epochMs']<=last['capturedEpochMs'])
    subset,view=product.validation_view(clock,originals,errors.ORIGINALS)
    current_error=errors.compose(run,binding,subset,view)
    need(current_error['fields']==dict(error='none',addressDialog=False)
         and not originals['ui']['tabletShown'] and not originals['ui']['navigationInventory']['roots']
         and type(originals['ui'].get('placesControlsVersion')) is int and originals['ui']['placesControlsVersion']==2)
    need(not originals['dialogs']['dialogs'] and not originals['http']['events'])
    model=originals['model'];need(model['iosPlacesModelVersion']==2 and model['complete'] and not model['roots'] and not model['tabletShown'])
    preferences=model['preferences'];origin=urlsplit(inputs['sceneUrl']);expected_origin=origin.scheme+'://'+origin.netloc
    need(preferences['metaverseOrigin'].rstrip('/')==expected_origin and preferences['protocolSignature']==inputs['protocolSignature']
         and places_preferences.ordinary_maturity_plan(preferences)['change'] is False)
    for key in (places_preferences.PINNED,places_preferences.FETCHED):
        value=preferences['values'][key]
        need(value['kind']=='absent' or value['kind'] in ('list','string-list') and value['value']==[])
    inventory=originals['inventory'];navigation=originals['navigation'];source=navigation['source'];url=source['sceneUrl']
    need(navigation['iosNavigationStateVersion']==2 and not source['challengeMarker']['present'])
    anchor=scene_inventory.unchanged_since_commit(inventory,url)
    need(anchor['bodyBytes']==base['bytes'] and anchor['bodySha256']==base['sha256']
         and set(scene_inventory.semantics(inventory))==set(navigation_state.MARKER_IDS))
    navigation_state.pose_ready(navigation,url,'A')
    # The URL is the actual native scene, constrained to the independently
    # attached original static resource. The fixed root viewpoint is an
    # explicit reversible profile, not an inferred current location.
    from adapters.native_scene_loads import resource_hash
    need(resource_hash(url)==resource_hash(base['url']) and source['view']['mode']=='first person'
         and near(source['avatar']['feetPosition'],[0,0,4],.01) and near(source['avatar']['orientation'],[0,0,0,1],.0001)
         and near(source['avatar']['modelScale'],1,.0001) and near(source['view']['rotation'],source['avatar']['orientation'],.0001)
         and inventory['clockAfter']['epochMs']<=navigation['clockBefore']['epochMs'])
    before,after=inventory['source']['sceneLoads'],source['sceneLoads']
    need(all(same(before[key],after[key]) for key in ('instance','processId','runId','currentGeneration','pendingLeases','complete','requests'))
         and before['sequence']<after['sequence'] and before['capturedEpochMs']<=after['capturedEpochMs'])
    return dict(iosNavigationSceneAdmissionVersion=VERSION,runId=run,binding=deepcopy(binding),providerInstance=provider_instance,
        providerInputs=inputs,base=deepcopy(base),originals=deepcopy(originals),clockJoin=deepcopy(clock),
        originalsSha256=digest(originals),bookmarkBaseline=baseline,commit=anchor)


def validate(value):
    exact(value,{'iosNavigationSceneAdmissionVersion','runId','binding','providerInstance','providerInputs','base',
        'originals','clockJoin','originalsSha256','bookmarkBaseline','commit'})
    need(type(value['iosNavigationSceneAdmissionVersion']) is int and value['iosNavigationSceneAdmissionVersion']==VERSION
         and value['originalsSha256']==digest(value['originals']))
    expected=admit(value['runId'],value['binding'],value['originals'],value['clockJoin'],value['base'],
        provider_instance=value['providerInstance'],provider_inputs=value['providerInputs'])
    need(same(expected,value));return deepcopy(expected)
