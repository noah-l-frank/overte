"""Join an actual returned Web Entity to cache/root/renderer lifetime originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters import world_web_surfaces as surfaces


def original(packet):
    return surfaces.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=surfaces.ACTION,runId=packet['runId']),packet['processId'])


def admitted(before,after,entity,source_url,*,after_epoch):
    original(before);original(after);need(integer(after_epoch,1) and before['runId']==after['runId'] and before['processId']==after['processId'])
    surfaces.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=surfaces.ACTION,runId=after['runId']),after['processId'],previous=before)
    a,b=before['source'],after['source'];old={row['birth'] for row in a['leases']}
    rows=[row for row in b['leases'] if row['birth'] not in old and row['entityId']==entity and row['sourceUrl']==source_url]
    need(len(rows)==1 and rows[0]['alive']);lease=rows[0]
    roots=[row for row in b['surfaces'] if row['birth']==lease['surfaceBirth']]
    need(len(roots)==1 and roots[0]['rootBirth'] and roots[0]['surfaceAlive'] and roots[0]['rootAlive'] and not roots[0]['cached'])
    events=[row for row in b['events'][a['eventSequence']:] if row['kind']=='renderer-acquired' and row['leaseBirth']==lease['birth']]
    need(len(events)==1 and events[0]['surfaceBirth']==roots[0]['birth'] and events[0]['epochMs']>=after_epoch)
    return dict(iosWorldWebSurfaceLeaseVersion=1,instance=b['instance'],processId=after['processId'],runId=after['runId'],
        lease=deepcopy({key:lease[key] for key in ('birth','surfaceBirth','entityId','sourceUrl')}),
        rootBirth=roots[0]['rootBirth'],rootSource=roots[0]['rootSource'],acquired=deepcopy(events[0]))


def current(owned,packet,*,live):
    exact(owned,{'iosWorldWebSurfaceLeaseVersion','instance','processId','runId','lease','rootBirth','rootSource','acquired'})
    need(type(owned['iosWorldWebSurfaceLeaseVersion']) is int and owned['iosWorldWebSurfaceLeaseVersion']==1 and type(live) is bool)
    original(packet);source=packet['source'];need(source['instance']==owned['instance'] and packet['processId']==owned['processId'] and packet['runId']==owned['runId'])
    rows=[row for row in source['leases'] if row['birth']==owned['lease']['birth']]
    need(len(rows)==1 and same({key:rows[0][key] for key in owned['lease']},owned['lease'])
        and owned['acquired'] in source['events'])
    roots=[row for row in source['surfaces'] if row['birth']==owned['lease']['surfaceBirth']]
    need(len(roots)==1 and roots[0]['rootBirth']==owned['rootBirth'] and roots[0]['rootSource']==owned['rootSource'])
    if live:need(rows[0]['alive'] and roots[0]['surfaceAlive'] and roots[0]['rootAlive'] and not roots[0]['cached'])
    return rows[0],roots[0]


def retired(owned,packet,*,after_epoch):
    lease,root=current(owned,packet,live=False);need(integer(after_epoch,1) and not lease['alive'])
    events=[row for row in packet['source']['events'] if row['kind']=='released' and row['surfaceBirth']==root['birth']
        and row['sequence']>owned['acquired']['sequence'] and row['epochMs']>=after_epoch]
    need(events and (root['cached'] or not root['surfaceAlive']))
    return dict(iosWorldWebSurfaceReleaseVersion=1,instance=owned['instance'],lease=deepcopy(owned['lease']),
        surface=deepcopy(root),release=deepcopy(events[0]),weakAbsenceObservedEpochMs=packet['source']['capturedEpochMs'])
