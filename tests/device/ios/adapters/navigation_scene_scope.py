"""Pure original owned-world gate shared by normal return and process transfer.

A new-process source group has no same-process history floor. Its caller must
independently prove the native restart before using floor=False. This validates
only present scene ownership and settled native pose, never restart or success.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters import navigation_state,scene_inventory,navigation_ui
from ios.adapters.navigation_challenge import marker
from ios.adapters.graphics_history import follow_native
from feature_journeys.navigation_scene import scene,marker_id
from navigation_observation import viewpoint_urls,same_viewpoint

def owned(proof,originals,clock,provider,fixture_url,*,floor=True):
    """Necessary ownership before replacing a scene, not restored-world proof."""
    need(type(floor) is bool);exact(originals,{'inventory','navigation','ui'});validate_join(clock,originals)
    binding,run=proof['binding'],proof['runId'];process=int(binding['processIdentity'])
    first,last=clock['nativeBefore'],clock['nativeAfter']
    if floor:follow_native(proof['clockJoin']['nativeAfter'],first)
    need(first['processId']==last['processId']==process and same(first['lifecycle'],last['lifecycle']))
    inventory,navigation,ui=(originals[name] for name in ('inventory','navigation','ui'))
    for name,module in (('inventory',scene_inventory),('navigation',navigation_state)):
        packet=originals[name]
        module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=module.ACTION,runId=run),
            process,last['capturedEpochMs'],proof['originals'][name] if floor else None)
        need(first['capturedEpochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=last['capturedEpochMs'])
    if floor:need(ui['instance']==proof['originals']['ui']['instance']
         and ui['lastSequence']>=proof['originals']['ui']['lastSequence'])
    need(ui['processId']==process and first['capturedEpochMs']<=ui['sampleEpochMs']<=last['capturedEpochMs']
         and not ui['tabletShown'] and not navigation_ui.project(ui)['addressDialog']
         and not any(row['id'].startswith('navigation.error.') for row in ui['controls']))
    source=navigation['source'];url=source['sceneUrl'];urls=viewpoint_urls(proof['providerInputs']['sceneUrl'])
    labels=[label for label,wanted in urls.items() if same_viewpoint(url,wanted)];need(len(labels)==1)
    navigation_state.pose_ready(navigation,url,labels[0])
    actual,scene_ticket=marker(dict(frame=dict(navigationAfter=navigation),fixtureUrl=fixture_url,url=url,
        provider=provider,providerInstance=proof['providerInstance'],ticket=provider['ticket']),run)
    anchor=scene_inventory.unchanged_since_commit(inventory,url)
    raw=json.dumps(scene(run,scene_ticket,fixture_url),separators=(',',':'),ensure_ascii=False).encode()
    need(anchor['bodyBytes']==len(raw) and anchor['bodySha256']==hashlib.sha256(raw).hexdigest()
         and set(scene_inventory.semantics(inventory))==set(navigation_state.MARKER_IDS)|{marker_id(run)}
         and inventory['clockAfter']['epochMs']<=navigation['clockBefore']['epochMs'])
    before,after=inventory['source']['sceneLoads'],source['sceneLoads']
    need(all(same(before[key],after[key]) for key in
         ('instance','processId','runId','currentGeneration','pendingLeases','complete','requests'))
         and before['sequence']<after['sequence'] and before['capturedEpochMs']<=after['capturedEpochMs'])
    return dict(originalsSha256=digest(originals),commit=anchor,sceneTicket=scene_ticket,marker=actual)

