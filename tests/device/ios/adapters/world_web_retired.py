"""Whole native Web retirement joins, separate from restored pixels/peer release."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import world_web_source,world_web_work,world_web_keys,pointer_state,create_entities
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_file_receipts import receipt as file_receipt
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
from ios.adapters.world_web_history import current_view
from ios.adapters import world_web_surface_lease
from ios.adapters.world_web_resource_disposition import disposition


def native_retired(lease,baseline,current,files):
    need(isinstance(lease,WorldWebLease));lease.source.lock.assert_held();owned=lease.packet();scope=lease.scope
    archived=lease.scope_state()
    need(archived['phase']=='released' and archived['stopBarrier'] is not None and archived['quiet'])
    before,after=lease.source.frame(baseline),lease.source.frame(current);a,b=before['originals'],after['originals']
    need(before['index']<=owned['before']['index']<owned['after']['index']<after['index'] and a['document'] is b['document'] is None)
    body_preserved(a['world'],b['world']);view_preserved(a['world'],b['world'])
    need(same(a['world']['source']['tree']['entities'],b['world']['source']['tree']['entities']))
    barrier=archived['stopBarrier']['epoch'];dead=create_entities.retired(b['entities'],owned['returned'],after_epoch=barrier)
    need(dead is not None)
    worker=world_web_work.owned_worker(b['work'],owned['files'],owned['directory'],dead['id']);need(worker['ended'] and worker['calls']==[])
    if lease.source.version>=5:
        from ios.adapters.world_web_emission_retirement import drained
        drained(b['emissions'],dead['id'],worker['manager'],worker['code'])
    script=b['world']['source']['scriptOriginal']['source'];need(script.get('membershipSourceVersion')==1 and script['membership']['complete']
        and all(row['instance']!=worker['manager']['instance'] for row in script['membership']['managers'])
        and all(row['required']['instance']!=worker['manager']['instance'] for row in script['engines']))
    ledger=b['ledgerAfter'];need(ledger['iosWorldWebVersion']>=2 and current_view(ledger) is None and world_web_source.pending(ledger)==[])
    prior=len(a['ledgerAfter']['events']);events=ledger['events'][prior:];owner='web-entity:'+dead['id'];views={};owners={}
    for row in events:
        item=row['identity'];need(item['sourceIdentity']==owner and item['sourceUrl']==owned['admission']['marker']['sourceUrl'])
        key=(item['handle'],item['creation'])
        if row['kind']=='view-created':need(key not in views);views[key]=dict(created=row,teardown=None)
        elif row['kind']=='view-teardown':need(key in views and views[key]['teardown'] is None);views[key]['teardown']=row
        elif row['kind']=='owner-destroyed':need(item['handle'] not in owners);owners[item['handle']]=row
    need(views and all(value['teardown'] is not None for value in views.values()) and set(owners)<={key[0] for key in views})
    for key,value in views.items():
        need(value['created']['sequence']<value['teardown']['sequence'])
        if key[0] in owners:need(value['teardown']['sequence']<owners[key[0]]['sequence'])
    surface=resources=None
    if owned['iosWorldWebLeaseVersion']==2:
        surface=world_web_surface_lease.retired(owned['surfaceLease'],b['surfaces'],after_epoch=barrier)
        resources=disposition(b['closures'],lease.source.frame(owned['after'])['originals']['closures'])
    else:need(set(owners)=={key[0] for key in views})
    world_web_keys.drained(b['keys']);pointer=pointer_state.drained(a['pointer'],b['pointer'],after_epoch=barrier)
    ui=b['uikit']['observation']['nativeUi'];need(ui['valid'] and ui['keyboardVisible'] is False and ui['imeInsetBottom']==0 and b['widgets']['tabletShown'] is False)
    file_receipt(files,root=scope.root,binding=lease.binding,run=lease.run,role='primary')
    need(files['kind']=='absent' and same(files['ownership'],owned['files']) and files['packet']['requestedEpochMs']>=barrier)
    native_epoch=max(dead['destructionObservedEpochMs'],max(row['teardown']['clock']['epochMs'] for row in views.values()),b['keys']['clockAfter']['epochMs'],
        b['pointer']['clockAfter']['epochMs'],files['clockJoin']['nativeAfter']['capturedEpochMs'])
    if owners:native_epoch=max(native_epoch,max(row['clock']['epochMs'] for row in owners.values()))
    if surface is not None:native_epoch=max(native_epoch,surface['weakAbsenceObservedEpochMs'],b['closures']['capturedEpochMs'])
    value=dict(iosWorldWebNativeRetirementVersion=2 if surface is not None else 1,runId=lease.run,binding=deepcopy(lease.binding),source=deepcopy(current),entity=dead,
        worker=deepcopy(worker['manager']),webViews=sorted([list(key) for key in views]),pointer=pointer,afterNativeEpochMs=native_epoch)
    if surface is not None:value.update(surface=surface,resources=resources,ownersDestroyed=sorted(owners))
    return value


def activity(frame):
    """Original event/lifecycle floors; a changed floor starts a new window."""
    original=frame['originals'];native=frame['clockJoin']['nativeAfter']
    return dict(processId=native['processId'],instance=native['instance'],lifecycle=deepcopy(native['lifecycle']),
        keys=[original['keys']['source']['instance'],original['keys']['source']['eventSequence']],
        pointer=[original['pointer']['source']['instance'],original['pointer']['source']['eventSequence']],
        web=original['ledgerAfter']['eventSequence'],
        cache=None if 'surfaces' not in original else deepcopy(original['surfaces']['source']['events']),
        holders=None if 'closures' not in original else deepcopy(original['closures']['contexts']))


def quiet(first,last):
    a,b=first['clockJoin'],last['clockJoin'];need(first['index']<last['index'] and first['ticket']==last['ticket']
        and b['hostBeforeMonotonic']-a['hostAfterMonotonic']>=3 and b['hostBeforeEpochMs']-a['hostAfterEpochMs']>=3000
        and a['nativeAfter']['processId']==b['nativeBefore']['processId'] and a['nativeAfter']['instance']==b['nativeBefore']['instance']
        and b['nativeBefore']['capturedEpochMs']-a['nativeAfter']['capturedEpochMs']>=3000 and same(a['nativeAfter']['lifecycle'],b['nativeBefore']['lifecycle']))
    need(same(activity(first),activity(last)))
    for group in ('keys','pointer'):
        x,y=first['originals'][group]['source'],last['originals'][group]['source'];need(x['instance']==y['instance'] and x['eventSequence']==y['eventSequence'])
    need(first['originals']['ledgerAfter']['eventSequence']==last['originals']['ledgerAfter']['eventSequence'])
    return True


def quiet_summary(first,last):
    quiet(first,last);a,b=first['clockJoin'],last['clockJoin']
    start=first['originals']['world']['clockAfter']['monotonicMs'];end=last['originals']['world']['clockBefore']['monotonicMs'];need(end-start>=3000)
    return dict(hostAfterFirstEpochMs=a['hostAfterEpochMs'],hostBeforeLastEpochMs=b['hostBeforeEpochMs'],hostAfterFirstMonotonic=a['hostAfterMonotonic'],hostBeforeLastMonotonic=b['hostBeforeMonotonic'],
        nativeAfterFirstEpochMs=a['nativeAfter']['capturedEpochMs'],nativeBeforeLastEpochMs=b['nativeBefore']['capturedEpochMs'],nativeAfterFirstMonotonicMs=start,nativeBeforeLastMonotonicMs=end,
        nativeInstance=a['nativeAfter']['instance'],processId=a['nativeAfter']['processId'])
