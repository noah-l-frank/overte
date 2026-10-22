"""Actual restored appearance and owned UI/HTTP/timer endpoints, without SDK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import integer,need
from adapters.script_feature.history import same
from ios.adapters import avatar_observation,avatar_scripts,avatar_social_http,avatar_ui_work,avatar_ui_inventory,people_model
from ios.adapters.avatar_sources import IOSAvatarSources

VERSION=1


def wearable_lifetimes(sources,baseline_index,current_index,before_entities,after_entities,*,fixture_url,expected_code):
    """Join Avatar API returns to original generic Tree births and weak death.

    Loading a bookmark can remove an avatar entity through native Avatar
    setters, so this join does not invent an Entities.deleteEntity return.
    Actual Tree removal and actual EntityItem weak expiry remain mandatory.
    """
    from ios.adapters import create_entities
    need(isinstance(sources,IOSAvatarSources) and sources.historical);sources.lock.assert_held()
    appearance=avatar_observation.appearance(sources,baseline_index,current_index,fixture_url=fixture_url,expected_code=expected_code)
    baseline=avatar_observation.frame(sources,baseline_index);current=avatar_observation.frame(sources,current_index)
    a,b=before_entities,after_entities;create_entities.original(a)
    create_entities.validate(b,dict(schemaVersion=1,commandId=b['requestId'],action=create_entities.ACTION,runId=sources.run),
        int(sources.binding['processIdentity']),previous=a)
    need(a['runId']==b['runId']==sources.run and all(packet['source'][key]['complete'] for packet in (a,b) for key in ('calls','tree')))
    tree=b['source']['tree'];need(a['source']['tree']['treeInstance']==tree['treeInstance']
        ==baseline['originals']['renderers']['source']['tree']['treeInstance']
        ==current['originals']['renderers']['source']['tree']['treeInstance'])
    prior={row['birth'] for row in a['source']['tree']['entities']};old_calls=len(a['source']['calls']['events'])
    result={};endpoint=0
    for identity,owned in appearance['ownedWearables'].items():
        need(not owned['present']);original=owned['original'];who=original['caller']
        caller={key:deepcopy(who[key]) for key in ('callerVersion','method','sequence','invokedEpochMs','manager','code')}
        need(a['clockAfter']['epochMs']<=who['invokedEpochMs'])
        events=[event for event in b['source']['calls']['events'][old_calls:] if event['kind']=='add-returned'
            and event['entityId']==identity and same(event['caller'],caller)]
        need(len(events)==1 and events[0]['localTreeAvailable'] and events[0]['clock']['epochMs']>=original['clock']['epochMs'])
        rows=[row for row in tree['entities'] if row['id']==identity and row['birth'] not in prior
            and who['invokedEpochMs']<=row['bornEpochMs']<=original['clock']['epochMs']]
        need(len(rows)==1);row=rows[0]
        need(row['removedSequence']>0 and row['destroyed'] and row['destructionObservedEpochMs']>=row['removedEpochMs']
            and not any(other['id']==identity and (not other['removedSequence'] or not other['destroyed']) for other in tree['entities']))
        endpoint=max(endpoint,row['destructionObservedEpochMs'])
        result[identity]=dict(avatarReturn=deepcopy(original),genericReturn=deepcopy(events[0]),lifetime=deepcopy(row))
    return dict(avatarWearableLifetimesVersion=VERSION,baselineIndex=baseline_index,sourceIndex=current_index,
        beforeEntitySha256=digest(a),afterEntitySha256=digest(b),owned=result,endpointEpochMs=endpoint)


def restored(sources,baseline_index,current_index,*,fixture_url,expected_code):
    """Select only new original lifetimes; this is one cleanup proof component.

    It needs the independent entity weak-lifetime, input dispatch, account,
    marker/file/GPU, paired retirement and native-plus-host quiet joins before
    a whole feature can publish cleanup. Empty optional-source inventories are
    never substituted for unavailable original components.
    """
    need(isinstance(sources,IOSAvatarSources) and sources.historical);sources.lock.assert_held()
    need(integer(baseline_index,1,current_index))
    before=avatar_observation.frame(sources,baseline_index);after=avatar_observation.frame(sources,current_index)
    baseline,current=before['originals'],after['originals']
    appearance=avatar_observation.appearance(sources,baseline_index,current_index,fixture_url=fixture_url,expected_code=expected_code)
    state=appearance['state'];need(state['requestedAvatar']==state['avatar']=='original' and state['modelLoaded']
        and not state['loadFailed'] and not state['wearable'] and not state['bookmarked'] and abs(state['scale']-1.)<.0001)
    need(not after['ui']['open'] and not after['ui']['controls'] and avatar_ui_inventory.absent(current['widgets'])
        and people_model.drained(current['people']))
    relevant={worker['membership']['instance'] for worker in baseline['scripts']['source']['workers'] if worker['avatar']['code']}
    timers=avatar_ui_work.drained_since(baseline['scripts'],current['scripts'],relevant,expected_code)
    need(avatar_scripts.drained(current['scripts'],relevant))
    # Existing default periodic timers remain unowned, but an actual dispatch
    # already executing at this cut must not disappear behind the birth filter.
    for worker in current['scripts']['source']['workers']:
        if worker['membership']['instance'] in relevant:
            need(all(row['depth']==row['pendingDispatch']==0 for row in worker['uiWork']['timers']))
    old=avatar_social_http.events(baseline['http']);now=avatar_social_http.events(current['http'])
    owned={identity for identity in now if identity not in old}
    if owned:need(avatar_social_http.drained(current['http'],sorted(owned)))
    # Every source has already passed strict append-only history validation
    # during historical archive reconstruction. Preserve actual endpoint clocks.
    terminal={'callbacks-released','timer-destroyed','xhr-destroyed','reply-destroyed','callback-leave'}
    endpoints=[event['clock']['epochMs'] for event in current['http']['events'] if event['xhrId'] in owned and event['kind'] in terminal]
    endpoint=max([timers['endpointEpochMs'],*endpoints])
    need(endpoint<=after['clockJoin']['nativeAfter']['capturedEpochMs'])
    return dict(avatarCleanupSourcesVersion=VERSION,baselineIndex=baseline_index,sourceIndex=current_index,
        baselineSha256=digest(before),sourceSha256=digest(after),appearance=deepcopy(appearance),
        ownedHttp=sorted(owned),timers=timers,endpointEpochMs=endpoint)
