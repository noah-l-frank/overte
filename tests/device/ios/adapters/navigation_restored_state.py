"""Actual static restoration after restart, retaining historical live roots.

This is a source-only condition before final rendered comparison and Stop.
Hidden QML roots remain explicit lifetime responsibility until independently
observed OS-process absence. No history is erased to imitate initial admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.native_scene_loads import resource_hash
from adapters.graphics_subject_geometry import near
from adapters.script_feature.history import same
from feature_journeys.navigation_base_scene import validate_status as base_status
from ios.adapters import navigation_scene_admission as admission,scene_inventory,navigation_state
from ios.adapters import navigation_product_state as product,navigation_error_state as errors
from ios.adapters import navigation_places_state as places,places_model,places_http
from ios.adapters import navigation_source_prefix as prefix
from ios.adapters.graphics_history import follow_native
from ios.adapters.navigation_address_inputs import transfer_original
from ios.adapters.navigation_process_context import validate as process_original,source_basis
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions

VERSION=1


def compose(initial,process_context,owner_files,originals,clock_join,base,*,address_owner,surface_owner,directory,prior):
    """Validate original current product state, never an input acknowledgment."""
    initial=admission.validate(initial);process_context=process_original(process_context,owner_files)
    need(same(process_context['initialAdmission'],initial))
    basis=source_basis(process_context,owner_files);binding=basis['binding'];run=basis['runId'];pid=int(binding['processIdentity'])
    exact(originals,admission.ORIGINALS);clock=validate_join(clock_join,originals)
    first,last=clock['nativeBefore'],clock['nativeAfter'];follow_native(basis['clockJoin']['nativeAfter'],first)
    need(first['processId']==last['processId']==pid and same(first['lifecycle'],last['lifecycle']))
    base_status(base,instance=initial['providerInstance'],scene_url=initial['providerInputs']['sceneUrl'],
        source_revision=binding['sourceRevision'],previous=initial['base'])
    need(base['available'] and base['responses'])
    for name,module in (('inventory',scene_inventory),('navigation',navigation_state)):
        packet=originals[name]
        module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=module.ACTION,runId=run),
            pid,last['capturedEpochMs'],basis['originals'][name])
        need(first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
    previous=deepcopy(basis['originals']);previous['currentNavigation']=previous.pop('navigation')
    current=deepcopy(originals);current['navigationBefore']=current.pop('navigation')
    prefix.follow(previous,current,run,pid)
    exact(prior,{'originals','nativeAfter'});follow_native(prior['nativeAfter'],first)
    prefix.follow(prior['originals'],current,run,pid)
    navigation=originals['navigation'];source=navigation['source'];url=source['sceneUrl']
    need(navigation['iosNavigationStateVersion']==2 and not source['challengeMarker']['present']
        and resource_hash(url)==resource_hash(base['url']))
    navigation_state.pose_ready(navigation,url,'A')
    old=initial['originals']['navigation']['source']
    for field in ('avatar','view'):
        need(set(source[field])==set(old[field]))
        for key,value in old[field].items():
            actual=source[field][key]
            if type(value) in (int,float,list):need(near(actual,value,.0001))
            else:need(same(actual,value))
    inventory=originals['inventory'];anchor=scene_inventory.unchanged_since_commit(inventory,url)
    need(anchor['bodyBytes']==base['bytes'] and anchor['bodySha256']==base['sha256']
        and same(scene_inventory.semantics(inventory),scene_inventory.semantics(initial['originals']['inventory']))
        and inventory['clockAfter']['epochMs']<=navigation['clockBefore']['epochMs'])
    a,b=inventory['source']['sceneLoads'],source['sceneLoads']
    need(all(same(a[k],b[k]) for k in ('instance','processId','runId','currentGeneration','pendingLeases','complete','requests'))
        and a['sequence']<b['sequence'] and a['capturedEpochMs']<=b['capturedEpochMs'])
    subset,view=product.validation_view(clock,originals,places.ORIGINALS)
    state=places.compose(run,binding,subset,view,baseline=initial['bookmarkBaseline'],
        provider_inputs=initial['providerInputs'],directory=directory)
    need(state['fields']==dict(bookmark=False,bookmarkName='',searchQuery='',searchResults=[],panel=False,addressDialog=False))
    need(originals['bookmarks']['file']['status']=='ready'
        and same(places.bookmark_entries(originals['bookmarks'],run,pid),
            places.baseline_entries(initial['bookmarkBaseline'],run,binding)))
    model=originals['model'];need(places_model.drained(model)
        and same(model['preferences'],initial['originals']['model']['preferences']))
    roots=NavigationSurfaceActions.retained_process_roots(surface_owner,process_context,owner_files,model,originals['ui'])
    address=transfer_original(address_owner,binding,run,originals['ui'])
    subset,view=product.validation_view(clock,originals,errors.ORIGINALS)
    error=errors.compose(run,binding,subset,view)
    need(error['fields']==dict(error='none',addressDialog=False) and not originals['replies']['currentLookupActive'])
    # Every created XHR in this new process must finish real callback/timer/
    # reply/object lifetimes. Empty current UI cannot hide retained native work.
    xhrs=places_http.events(originals['http']);need(places_http.drained(originals['http'],sorted(xhrs)))
    need(directory is not None);places.validate_directory_proof(directory,binding,run)
    return dict(iosNavigationRestoredStateVersion=VERSION,runId=run,binding=deepcopy(binding),
        initialAdmissionSha256=digest(initial),processContextSha256=digest(process_context),
        originalsSha256=digest(originals),clockJoinSha256=digest(clock),priorSha256=digest(prior),base=deepcopy(base),commit=anchor,
        placesRoots=roots,addressRoot=address,lifetimeEndRequired=True)
