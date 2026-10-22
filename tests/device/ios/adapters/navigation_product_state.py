"""Eight original Worlds fields in one bounded acquisition, without publication.

This pure join does not own inputs, cross-sample cursors, restart or cleanup.
The caller must retain all original source packets and the owned image archive.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.graphics_subject_geometry import near
from adapters.script_feature.history import same
from feature_journeys.contract import identifier,state as public_state
from feature_journeys.navigation_fixture import configuration
from navigation_observation import same_viewpoint
from ios.adapters import navigation_places_state as places,navigation_error_state as errors
from ios.adapters.navigation_challenge import evaluate as challenge
from ios.adapters.navigation_state import validate as navigation_packet,pose_ready,ACTION
from ios.adapters.navigation_world_measurements import originals as image_originals

VERSION=1
PLACES=frozenset(('bookmarks','model','ui','http'))
ERROR=frozenset(('dialogs','replies','ui'))
IMAGE=frozenset(('navigationBefore','capture','retirement','navigationAfter'))
ORIGINALS=PLACES|ERROR|IMAGE|{'currentNavigation'}


def validation_view(clock,originals,names):
    """Derive a subset validation view; retain every original clock unchanged."""
    validate_join(clock,originals);need(set(names)<=set(originals))
    subset={name:originals[name] for name in names};view=deepcopy(clock)
    view['originalsSha256']=digest(subset)
    view['sourceTimes']=[deepcopy(row) for row in clock['sourceTimes'] if row['source'] in names]
    validate_join(view,subset)
    return subset,view


def compose(run,binding,originals,clock_join,image,*,baseline,provider_inputs,fixture_url,provider_instance,
            directory=None,missing=None):
    identifier(run);identifier(provider_instance);process=places.pid(binding);exact(originals,ORIGINALS)
    clock=validate_join(clock_join,originals);first,last=clock['nativeBefore'],clock['nativeAfter']
    need(first['processId']==last['processId']==process and same(first['lifecycle'],last['lifecycle']))
    inputs,urls=configuration(provider_inputs)
    need(image['label'] in ('A','B') and same_viewpoint(image['url'],urls[image['label']])
         and image['fixtureUrl']==fixture_url and image['providerInstance']==provider_instance
         and same(image_originals(image['frame']),{name:originals[name] for name in IMAGE}))
    if directory is not None:need(directory['originals']['provider']['instance']==provider_instance)
    if missing is not None:need(missing['provider']['instance']==provider_instance)
    inner=image['frame']['clockJoin']
    need(first['instance']==inner['nativeBefore']['instance']==inner['nativeAfter']['instance']==last['instance']
         and first['sequence']<inner['nativeBefore']['sequence']<inner['nativeAfter']['sequence']<last['sequence']
         and first['capturedEpochMs']<=inner['nativeBefore']['capturedEpochMs']
         and inner['nativeAfter']['capturedEpochMs']<=last['capturedEpochMs']
         and same(first['lifecycle'],inner['nativeBefore']['lifecycle']) and same(first['lifecycle'],inner['nativeAfter']['lifecycle'])
         and clock['hostBeforeMonotonic']<=inner['hostBeforeMonotonic']<=inner['hostAfterMonotonic']<=clock['hostAfterMonotonic']
         and clock['hostBeforeEpochMs']<=inner['hostBeforeEpochMs']<=inner['hostAfterEpochMs']<=clock['hostAfterEpochMs'])
    current=originals['currentNavigation'];before=image['frame']['navigationAfter']
    navigation_packet(current,dict(schemaVersion=1,commandId=current.get('requestId'),action=ACTION,runId=run),
                      process,last['capturedEpochMs'],before)
    pose_ready(current,image['url'],image['label'])
    latest=max(packet['clockAfter']['epochMs'] if 'clockAfter' in packet else packet.get('capturedEpochMs',packet.get('sampleEpochMs',0))
               for name,packet in originals.items() if name!='currentNavigation')
    source=current['source'];previous=before['source']
    need(latest<=current['clockBefore']['epochMs']<=current['clockAfter']['epochMs']<=last['capturedEpochMs']
         and same(source['domain'],previous['domain']) and same(source['markers'],previous['markers'])
         and same(source['challengeMarker'],previous['challengeMarker'])
         and source['sceneLoads']['currentGeneration']==previous['sceneLoads']['currentGeneration']
         and same(source['sceneLoads']['requests'],previous['sceneLoads']['requests'])
         and near(source['avatar']['feetPosition'],previous['avatar']['feetPosition'],.025)
         and near(source['avatar']['orientation'],previous['avatar']['orientation'],.0001)
         and near(source['avatar']['modelScale'],previous['avatar']['modelScale'],.0001)
         and source['view']['mode']==previous['view']['mode']
         and near(source['view']['position'],previous['view']['position'],.001)
         and near(source['view']['rotation'],previous['view']['rotation'],.0001)
         and source['view']['perspective']==previous['view']['perspective']
         and near(source['view']['fieldOfViewDegrees'],previous['view']['fieldOfViewDegrees'],.001)
         and near(source['view']['aspectRatio'],previous['view']['aspectRatio'],.0001))
    # Both projections consume the SAME original UI packet and global native
    # interval. These are deterministic hash/time-list views, not new reads.
    place_sources,place_clock=validation_view(clock,originals,PLACES)
    error_sources,error_clock=validation_view(clock,originals,ERROR)
    place=places.compose(run,binding,place_sources,place_clock,baseline=baseline,provider_inputs=inputs,directory=directory)
    error=errors.compose(run,binding,error_sources,error_clock,missing=missing)
    need(place['fields']['addressDialog']==error['fields']['addressDialog'])
    rendered,_subject=challenge(run,binding,image)
    actual=dict(place['fields'],location=rendered['rendered']['location'],error=error['fields']['error'])
    public_state('world-navigation',actual,run)
    return dict(iosNavigationProductStateVersion=VERSION,runId=run,ticket=image['ticket'],binding=deepcopy(binding),state=actual,
        originalsSha256=digest(originals),clockJoinSha256=digest(clock),image=rendered,places=place,error=error,
        nativeBeforeEpochMs=first['capturedEpochMs'],nativeAfterEpochMs=last['capturedEpochMs'],
        acquiredHostEpochMs=clock['hostBeforeEpochMs'])
