"""Actual SNAP export-row tokens; input readiness never proves an outcome."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same

VERSION=1
IDS=frozenset({'snapshot.export-cancel','snapshot.upload-cancel'}|{f'snapshot.{kind}.{index}' for kind in ('save','share','upload') for index in range(8)})
FIELDS={'snapshotExportControlVersion','snapshotRootId','snapshotQmlSource','snapshotRow','snapshotFileName','snapshotFileOwned',
        'snapshotExportTicket','snapshotCapturing','snapshotProcessing','snapshotSystemBlocked','inputReady'}
BASE={'id','token','enabled','focused','frame'}
FILE=re.compile(r'parity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)-snap_[0-9]{1,20}_[0-9]{1,10}\.(png|jpg|jpeg|webp|gif)\Z')


def identity(value):
    need(type(value) is str)
    try:parsed=uuid.UUID(value)
    except ValueError:need(False)
    need(str(parsed)==value and parsed.int>0);return value


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS and FIELDS<=set(row));identifier=row['id']
    need(type(row['snapshotExportControlVersion']) is int and row['snapshotExportControlVersion']==VERSION)
    identity(row['snapshotRootId']);identity(row['token'])
    need(type(row['snapshotQmlSource']) is str and len(row['snapshotQmlSource'])<=4096)
    source=urlsplit(row['snapshotQmlSource']);need(source.scheme in ('file','qrc') and not source.netloc and not source.query and not source.fragment
        and source.path.endswith('/system/snapshot/NativeSnapshotReview.qml') and all(ord(c)>=32 and ord(c)!=127 for c in row['snapshotQmlSource']))
    for key in ('enabled','focused','snapshotFileOwned','snapshotCapturing','snapshotProcessing','snapshotSystemBlocked','inputReady'):
        need(type(row[key]) is bool)
    need(type(row['snapshotFileName']) is str and (bool(FILE.fullmatch(row['snapshotFileName'])) if row['snapshotFileOwned'] else row['snapshotFileName']==''))
    need(type(row['snapshotExportTicket']) is str)
    if row['snapshotExportTicket']:identity(row['snapshotExportTicket'])
    if identifier in ('snapshot.export-cancel','snapshot.upload-cancel'):need(type(row['snapshotRow']) is int and row['snapshotRow']==-1)
    else:need(integer(row['snapshotRow'],0,7) and row['snapshotRow']==int(identifier.rsplit('.',1)[1]))
    if row['inputReady']:need(row['enabled'] and not row['snapshotSystemBlocked'] and (identifier=='snapshot.export-cancel' or row['snapshotFileOwned']))
    return row


def project(value):
    need(type(value) is dict and type(value.get('snapshotExportControlsVersion')) is int and value['snapshotExportControlsVersion']==VERSION
         and type(value.get('tabletShown')) is bool and type(value.get('controls')) is list)
    scope=dict(processId=value['processId'],instance=value['instance'],sampleEpochMs=value['sampleEpochMs'],elapsedMs=value['elapsedMs'],sequence=value['lastSequence'])
    identity(scope['instance']);need(integer(scope['processId'],1) and integer(scope['sampleEpochMs'],1) and integer(scope['elapsedMs']) and integer(scope['sequence']))
    controls=[];ids=set();tokens=set()
    for row in value['controls']:
        need(type(row) is dict)
        if row.get('id') not in IDS:continue
        exact(row,BASE|FIELDS);metadata(row);need(row['id'] not in ids and row['token'] not in tokens)
        frame=row['frame'];exact(frame,{'x','y','width','height'})
        need(all(number(frame[key],0,10000) for key in frame) and frame['width']>0 and frame['height']>0)
        ids.add(row['id']);tokens.add(row['token']);controls.append(deepcopy(row))
    return dict(iosSnapshotExportControlsVersion=VERSION,scope=scope,open=value['tabletShown'],controls=controls)


def same_reference(reference,current,identifier):
    exact(reference,{'iosSnapshotExportControlsVersion','scope','open','controls'});exact(current,set(reference))
    need(type(reference['iosSnapshotExportControlsVersion']) is int and reference['iosSnapshotExportControlsVersion']==VERSION
         and type(current['iosSnapshotExportControlsVersion']) is int and current['iosSnapshotExportControlsVersion']==VERSION
         and identifier in IDS and reference['open'] and current['open'])
    a,b=reference['scope'],current['scope'];exact(a,{'processId','instance','sampleEpochMs','elapsedMs','sequence'});exact(b,set(a))
    need(all(a[key]==b[key] for key in ('processId','instance','sequence')) and 0<=b['sampleEpochMs']-a['sampleEpochMs']<=3000
         and 0<=b['elapsedMs']-a['elapsedMs']<=3000)
    rows=[row for row in reference['controls'] if row['id']==identifier];fresh=[row for row in current['controls'] if row['id']==identifier]
    need(len(rows)==len(fresh)==1);metadata(rows[0]);metadata(fresh[0]);need(same(rows[0],fresh[0]));return deepcopy(fresh[0])
