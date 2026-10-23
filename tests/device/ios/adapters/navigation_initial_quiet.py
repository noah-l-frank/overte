"""Original-process source, input and pixel quiet before lifetime retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.graphics_history import follow_native
from ios.adapters.navigation_initial_restored_image import NavigationInitialRestoredImage
from ios.adapters.navigation_initial_comparison import compare
from ios.adapters.navigation_quiet_period import account_state
from ios.adapters import navigation_source_prefix as prefix,world_web_keys as keys,pointer_state as pointer

VERSION=1


def compose(images,baseline,admission):
    need(type(images) is list and 3<=len(images)<=32 and all(type(owner) is NavigationInitialRestoredImage for owner in images))
    first=images[0];rows=[];requests=set();frames=set()
    for owner in images:
        need(owner.lock is first.lock and owner.run==first.run and owner.role==first.role and owner.root==first.root
            and same(owner.binding,first.binding) and owner.request not in requests);requests.add(owner.request)
        result,proof,_raw=owner.archive();parts=owner.originals();inputs=owner.input_owner().archive()
        frame=parts['capture']['source']['renderTrace']['frameId'];need(frame not in frames);frames.add(frame)
        comparison=compare(baseline,owner,admission)
        originals={key:parts[key] for key in ('bookmarks','model','http','dialogs','replies','ui','navigation')}
        originals['currentNavigation']=originals.pop('navigation')
        row=dict(ownerSha256=digest(owner.previous),proof=proof,originals=originals,native=parts['nativeEnd']['nativeAfter'],
            join=owner.join(parts,{key:parts[key] for key in ('bookmarks','model','http','dialogs','replies','ui','navigation','inventory')}),
            inputs=inputs,comparison=comparison)
        if rows:
            old=rows[-1];follow_native(old['native'],row['join']['nativeBefore'])
            current=deepcopy(originals);current['navigationBefore']=current.pop('currentNavigation')
            prefix.follow(old['originals'],current,owner.run,int(owner.binding['processIdentity']))
            for kind,module in (('keys',keys),('pointer',pointer)):
                before,after=old['inputs'][kind],inputs[kind]
                module.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=module.ACTION,runId=owner.run),
                    int(owner.binding['processIdentity']),previous=before)
                need(same(before['source']['events'],after['source']['events']))
            for name in ('http','dialogs','replies'):need(same(old['originals'][name]['events'],originals[name]['events']))
            need(same(old['native']['lifecycle'],row['native']['lifecycle']))
            if 'history' in old['native']['animation']:
                need(same(old['native']['animation']['history'],row['native']['animation'].get('history')))
            need(same(account_state(old['native']['account']),account_state(row['native']['account'])))
            need(row['join']['hostBeforeEpochMs']>=old['join']['hostAfterEpochMs']
                and row['join']['hostBeforeMonotonic']>=old['join']['hostAfterMonotonic'])
            a,b=old['inputs']['geometry']['observation'],inputs['geometry']['observation']
            need(b['sampleSequence']>a['sampleSequence'] and b['sampleEpochMs']>=a['sampleEpochMs'])
        rows.append(row)
    a,b=rows[0],rows[-1]
    need(3000<=b['join']['hostBeforeEpochMs']-a['join']['hostAfterEpochMs']<60000
        and 3<=b['join']['hostBeforeMonotonic']-a['join']['hostAfterMonotonic']<60
        and 3000<=b['join']['nativeBefore']['requestedEpochMs']-a['native']['capturedEpochMs']<60000)
    for kind in ('keys','pointer'):
        x,y=a['inputs'][kind]['clockAfter'],b['inputs'][kind]['clockBefore']
        need(3000<=y['epochMs']-x['epochMs']<60000 and 3000<=y['monotonicMs']-x['monotonicMs']<60000)
    return dict(iosNavigationInitialQuietPeriodVersion=VERSION,runId=first.run,role=first.role,binding=first.binding,
        originals=[row['ownerSha256'] for row in rows],comparisons=[row['comparison'] for row in rows],
        firstNativeAfter=deepcopy(a['native']),lastNativeBefore=deepcopy(b['join']['nativeBefore']),lifetimeEndRequired=True)
