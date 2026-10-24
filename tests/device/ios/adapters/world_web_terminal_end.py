"""Decode genuine once-Stop, independent OS quiet and SDK deletion originals.

This contains no native/UI/GPU query and no process operation. It projects the
already verified typed final owners for the common terminal protocol only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.retirement_receipts import binding_from_context
from feature_journeys.terminal import os_quiet
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.world_web_process_end import WorldWebProcessEnd
from ios.adapters.world_web_session_end import WorldWebSessionEnd
from ios.adapters.world_web_final_archive import WorldWebFinalArchive
from ios.adapters.world_web_archived import rebuild


def role_end(flow,held_original_sha):
    from ios.adapters.world_web_feature import IOSWorldWebFeature
    need(type(flow) is IOSWorldWebFeature and flow.state['phase']=='retired')
    flow.lock.assert_held();flow.primary_lock.assert_held()
    owner=rebuild(flow);parts=dict(source=owner.source,peer=None if flow.role=='primary' else owner.peer,retirement=owner,
        lease=owner.lease if flow.role=='primary' else owner.observer.lease)
    process=WorldWebProcessEnd(flow);process.verify(parts)
    sdk=WorldWebSessionEnd(flow);sdk.historical();need(sdk.state['phase']=='complete')
    archive=WorldWebFinalArchive(flow.runtime._world_web_store(flow.selector,'ios-world-web-'+flow.role+'-'+flow.run+'-final.json'),
        flow.root,flow.state['binding'],flow.run,flow.role,flow.lock);archive.verify()
    need(sdk.state['processSha256']==digest(process.previous) and sdk.state['sceneSha256']==digest(archive.previous))
    store=PrivateFeatureState(process.store.path.with_name(filename('worldweb',flow.role,0)));raw=store.read()
    need(raw is not None and digest(raw)==process.state['processSha256'])
    state=IOSProcessRetirement.archive(raw,path=store.path,binding=flow.state['binding'],source=process.state['source'],
        bundle=process.state['bundleId'],run=flow.run,role=flow.role,stage=0,profile='worldweb')
    # This pure reader has no runtime/SDK callback. Each selected actual record
    # is reopened and hashed by the existing closed original decoder.
    reader=object.__new__(IOSProcessRetirement);reader.profile='worldweb';reader.store=store;reader.binding=deepcopy(flow.state['binding'])
    reader.pid=int(flow.state['binding']['processIdentity'])
    reader.source=deepcopy(process.state['source']);reader.bundle=process.state['bundleId'];reader.run=flow.run;reader.role=flow.role;reader.stage=0
    need(state['pending'] is None and state['windows'] and state['windows'][-1]['complete'])
    window=state['windows'][-1];rows=[reader.load(state['records'][n-1]) for n in window['samples'][window['start']:]]
    need(len(rows)>=3 and all(row['mode']=='observed' for row in rows));a,b=rows[0],rows[-1]
    quiet=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance=process.state['source']['instance'],
        processId=int(flow.state['binding']['processIdentity']),samples=len(rows),originalSha256=digest(dict(owner=raw,records=rows)),
        hostAfterFirstEpochMs=a['acquisition']['hostAfterEpochMs'],hostBeforeLastEpochMs=b['acquisition']['hostBeforeEpochMs'],
        hostAfterFirstMonotonic=a['acquisition']['hostAfterMonotonic'],hostBeforeLastMonotonic=b['acquisition']['hostBeforeMonotonic'],
        osAfterFirstEpochMs=a['original']['clockAfter']['epochMs'],osBeforeLastEpochMs=b['original']['clockBefore']['epochMs'],
        osAfterFirstMonotonicMs=a['original']['clockAfter']['monotonicMs'],osBeforeLastMonotonicMs=b['original']['clockBefore']['monotonicMs'])
    os_quiet(quiet,flow.state['binding']['processIdentity'])
    return dict(binding=binding_from_context(flow.state['binding']),heldOriginalSha256=held_original_sha,
        stopOriginalSha256=digest(process.previous),osAbsence=quiet,sdkDeletionOriginalSha256=digest(sdk.previous),archiveSha256=digest(archive.previous))
