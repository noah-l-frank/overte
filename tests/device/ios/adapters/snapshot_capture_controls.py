"""Original SNAP capture targeting/settings; no capture outcome is inferred."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from ios.adapters.snapshot_export_controls import identity,BASE

VERSION=1
IDS=frozenset(('snapshot.name','snapshot.mode','snapshot.format','snapshot.capture','snapshot.cancel'))
FIELDS={'snapshotCaptureControlVersion','snapshotRootId','snapshotQmlSource','snapshotNameSha256','snapshotName','snapshotNameOwned',
    'snapshotMode','snapshotFormat','snapshotCapturing','snapshotProcessing','snapshotSettingsLoaded','snapshotStatusError',
    'snapshotImageCount','snapshotSystemBlocked','inputReady'}
PREFIX=re.compile(r'parity-[0-9a-f]{16}-(still-png|still-jpg|animated|panorama|cubemap)\Z')
EMPTY=hashlib.sha256(b'').hexdigest()


def metadata(row):
    need(type(row) is dict and row.get('id') in IDS and FIELDS<=set(row))
    need(type(row['snapshotCaptureControlVersion']) is int and row['snapshotCaptureControlVersion']==VERSION)
    identity(row['snapshotRootId']);identity(row['token']);source=row['snapshotQmlSource']
    need(type(source) is str and len(source)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in source))
    url=urlsplit(source);need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and url.path.endswith('/system/snapshot/NativeSnapshotReview.qml'))
    for key in ('enabled','focused','snapshotNameOwned','snapshotCapturing','snapshotProcessing','snapshotSettingsLoaded',
        'snapshotStatusError','snapshotSystemBlocked','inputReady'):need(type(row[key]) is bool)
    need(type(row['snapshotNameSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['snapshotNameSha256'])
        and type(row['snapshotName']) is str and integer(row['snapshotMode'],0,3) and row['snapshotFormat'] in ('png','jpg','webp')
        and integer(row['snapshotImageCount'],0,8))
    if row['snapshotNameOwned']:need(PREFIX.fullmatch(row['snapshotName']) and hashlib.sha256(row['snapshotName'].encode()).hexdigest()==row['snapshotNameSha256'])
    else:need(row['snapshotName']=='')
    if row['inputReady']:need(row['enabled'] and not row['snapshotSystemBlocked'])
    return row


def project(value):
    need(type(value) is dict and type(value.get('snapshotCaptureControlsVersion')) is int and value['snapshotCaptureControlsVersion']==VERSION
        and type(value.get('tabletShown')) is bool and type(value.get('controls')) is list)
    scope=dict(processId=value['processId'],instance=value['instance'],sampleEpochMs=value['sampleEpochMs'],elapsedMs=value['elapsedMs'],sequence=value['lastSequence'])
    identity(scope['instance']);need(integer(scope['processId'],1) and integer(scope['sampleEpochMs'],1) and integer(scope['elapsedMs']) and integer(scope['sequence']))
    rows=[];seen=set();tokens=set();root=None
    for row in value['controls']:
        need(type(row) is dict)
        if row.get('id') not in IDS:continue
        exact(row,BASE|FIELDS);metadata(row);need(row['id'] not in seen and row['token'] not in tokens)
        current={key:row[key] for key in FIELDS-{'inputReady'}}
        if root is None:root=current
        else:need(same(root,current))
        exact(row['frame'],{'x','y','width','height'});need(all(number(v,0,10000) for v in row['frame'].values())
            and row['frame']['width']>0 and row['frame']['height']>0)
        seen.add(row['id']);tokens.add(row['token']);rows.append(deepcopy(row))
    return dict(iosSnapshotCaptureControlsVersion=VERSION,scope=scope,open=value['tabletShown'],controls=rows)


def same_reference(reference,current,identifier):
    exact(reference,{'iosSnapshotCaptureControlsVersion','scope','open','controls'});exact(current,set(reference))
    need(type(reference['iosSnapshotCaptureControlsVersion']) is int and reference['iosSnapshotCaptureControlsVersion']==VERSION
        and type(current['iosSnapshotCaptureControlsVersion']) is int and current['iosSnapshotCaptureControlsVersion']==VERSION
        and identifier in IDS and reference['open'] and current['open'])
    a,b=reference['scope'],current['scope'];exact(a,{'processId','instance','sampleEpochMs','elapsedMs','sequence'});exact(b,set(a))
    need(all(a[k]==b[k] for k in ('processId','instance','sequence')) and 0<=b['sampleEpochMs']-a['sampleEpochMs']<=3000
        and 0<=b['elapsedMs']-a['elapsedMs']<=3000)
    old=[row for row in reference['controls'] if row['id']==identifier];new=[row for row in current['controls'] if row['id']==identifier]
    need(len(old)==len(new)==1);metadata(old[0]);metadata(new[0]);need(same(old[0],new[0]));return deepcopy(new[0])
