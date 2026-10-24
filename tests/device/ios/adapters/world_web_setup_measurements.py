"""Original failure-setup restoration; unknown resources never become absence.

The full rendered lease has a separate decoder. This path admits only actual
released Scope originals and original native create-return/weak/tree operands,
including a real null addEntity return. It cannot manufacture an admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from adapters.script_ui_root_ownership import membership,validate as roots_validate
from ios.adapters import create_entities,pointer_state,world_web_keys,world_web_source,world_web_work
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_sources import WorldWebSources
from ios.adapters.world_web_scope_archive import archived
from ios.adapters.world_web_resource_disposition import disposition
from ios.adapters.world_web_trace import current_view


def original(scope,source,baseline,current):
    need(type(scope) is IOSWorldWebScope and type(source) is WorldWebSources and source.version==5
        and scope.lock is source.lock and same(scope.binding,source.binding) and scope.run==source.run)
    source.lock.assert_held();retained=archived(scope,source);state=retained.state
    need(state['phase']=='released' and state['baseline'] is not None and state['quiet'] and state['pending'] is None)
    first,last=source.frame(baseline),source.frame(current);a,b=first['originals'],last['originals']
    need(first['index']<last['index'] and a['document'] is b['document'] is None and current_view(b['ledgerAfter']) is None
        and not world_web_source.pending(b['ledgerAfter']))
    body_preserved(a['world'],b['world']);view_preserved(a['world'],b['world'])
    need(same(a['world']['source']['tree']['entities'],b['world']['source']['tree']['entities']))
    need(a['work']['source']['complete'] and b['work']['source']['complete'])
    world_web_keys.drained(b['keys']);barrier=retained.frames[state['baseline']-1]['clockJoin']['nativeAfter']['capturedEpochMs']
    if state['stopBarrier'] is not None:barrier=state['stopBarrier']['epoch']
    pointer=pointer_state.drained(a['pointer'],b['pointer'],after_epoch=barrier)
    ui=b['uikit']['observation']['nativeUi'];need(ui['valid'] and not ui['keyboardVisible'] and ui['imeInsetBottom']==0
        and b['widgets']['tabletShown'] is False)
    before_roots=membership(a['widgets']['scriptInventory'],pid=source.pid);after_roots=membership(b['widgets']['scriptInventory'],pid=source.pid)
    need(a['widgets']['scriptInventory']['inventoryVersion']==b['widgets']['scriptInventory']['inventoryVersion']==2)
    roots_validate(after_roots,pid=source.pid,previous=before_roots)
    need(after_roots['available'] and after_roots['complete'] and after_roots['wholeTreeReady'])
    admission=state['admission'];returned=None;worker=None;entity=None
    if admission is None:
        need(state['cleanupMode']=='unloaded' and same(a['entities']['source']['calls']['events'],b['entities']['source']['calls']['events'])
            and same(a['work']['source']['workers'],b['work']['source']['workers']))
    else:
        need(state['loadBarrier'] is not None and state['fileOwnership'] is not None and state['directory'] is not None)
        returned=create_entities.returned(b['entities'],a['entities'],admission['manager'],admission['code'],after_epoch=state['loadBarrier'])
        entity=returned['returned']['entityId'];create_entities.retired(b['entities'],returned,after_epoch=barrier)
        rows=[row for row in b['work']['source']['workers'] if row['nonce']==state['fileOwnership']['nonce']]
        if rows:
            worker=world_web_work.owned_worker(b['work'],state['fileOwnership'],state['directory'],entity)
            need(worker['ended'] and worker['calls']==[])
        # The Scope archive separately validates actual VM/code/thread terminal
        # originals even when failure occurred before the JS loaded event.
        script=b['world']['source']['scriptOriginal']['source'];need(script['membershipSourceVersion']==1 and script['membership']['complete']
            and not any(row['instance']==admission['manager']['instance'] for row in script['membership']['managers'])
            and not any(row['required']['instance']==admission['manager']['instance'] for row in script['engines']))
        from ios.adapters.world_web_emission_retirement import drained
        drained(b['emissions'],entity,admission['manager'],admission['code'])
    for packet in (a['entities'],b['entities']):need(packet['source']['calls']['complete'] and packet['source']['tree']['complete'])
    resources=disposition(b['closures'],a['closures'],partial=True)
    old_leases={row['birth'] for row in a['surfaces']['source']['leases']};leases=[];roots=[]
    for lease in b['surfaces']['source']['leases']:
        if lease['birth'] in old_leases:continue
        need(entity is not None and lease['entityId']==entity and not lease['alive'])
        surface=[row for row in b['surfaces']['source']['surfaces'] if row['birth']==lease['surfaceBirth']];need(len(surface)==1)
        surface=surface[0];need(surface['cached'] or not surface['surfaceAlive'])
        events=b['surfaces']['source']['events'];acquired=[row for row in events if row['kind']=='renderer-acquired' and row['leaseBirth']==lease['birth']]
        released=[row for row in events if row['kind']=='released' and row['surfaceBirth']==lease['surfaceBirth'] and row['epochMs']>=barrier]
        need(len(acquired)==1 and acquired[0]['epochMs']>=state['loadBarrier']
            and any(row['sequence']>acquired[0]['sequence'] for row in released))
        leases.append(deepcopy(lease))
        if not any(row['birth']==surface['birth'] for row in roots):roots.append(deepcopy(surface))
    prior_surfaces={row['birth'] for row in a['surfaces']['source']['surfaces']}
    need({row['birth'] for row in b['surfaces']['source']['surfaces'] if row['birth'] not in prior_surfaces}
        <={row['birth'] for row in roots})
    own_identity=None if entity is None else hashlib.sha256(('web-entity:'+entity).encode()).hexdigest()
    old_contexts={row['id']:row for row in a['closures']['contexts']};owned_contexts=[]
    for context in resources['contexts']:
        if context['id'] not in old_contexts:
            need(own_identity is not None and context['descriptor']['identitySha256']==own_identity)
            owned_contexts.append(context['id'])
    return dict(iosWorldWebSetupRestorationVersion=1,binding=deepcopy(source.binding),runId=source.run,
        scopeSha256=digest(scope.previous),baseline=deepcopy(baseline),current=deepcopy(current),cleanupMode=state['cleanupMode'],
        returned=returned,worker=worker,surfaces=roots,leases=leases,
        surfaceSource=dict(instance=b['surfaces']['source']['instance'],processId=source.pid),
        resources=resources,ownedContexts=owned_contexts,pointer=pointer,
        scriptRoots=dict(instance=after_roots['instance'],processId=after_roots['processId'],roots=[deepcopy(row) for row in after_roots['roots']
            if row['observedIdentity'] not in {old['observedIdentity'] for old in before_roots['roots']}]),
        afterNativeEpochMs=max(barrier,b['closures']['capturedEpochMs'],b['surfaces']['source']['capturedEpochMs'],after_roots['capturedEpochMs'],
            b['keys']['clockAfter']['epochMs'],b['pointer']['clockAfter']['epochMs']))
