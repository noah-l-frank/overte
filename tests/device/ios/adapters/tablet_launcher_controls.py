"""Passive actual launcher selection bound to ordinary source-control tokens."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_export_controls import identity,BASE

VERSION=1
FIELDS={'tabletLauncherControlVersion','launcherRootId','launcherQmlSource','launcherCurrentIndex','launcherPageCount','launcherControlIndex','inputReady'}


def control_id(value):
    return type(value) is str and (value=='snapshot.entry' or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',value) is not None)


def metadata(row):
    need(type(row) is dict and control_id(row.get('id')) and FIELDS<=set(row))
    need(type(row['tabletLauncherControlVersion']) is int and row['tabletLauncherControlVersion']==VERSION)
    identity(row['launcherRootId']);identity(row['token']);source=row['launcherQmlSource']
    need(type(source) is str and 1<=len(source)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in source))
    url=urlsplit(source);need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and url.path.endswith('/hifi/tablet/TabletHome.qml'))
    need(integer(row['launcherPageCount'],1,32) and integer(row['launcherCurrentIndex'],0,row['launcherPageCount']-1)
        and type(row['launcherControlIndex']) is int and row['launcherControlIndex']==(-1 if row['id']=='snapshot.entry' else int(row['id'].rsplit('.',1)[1])-1)
        and row['launcherControlIndex']<row['launcherPageCount'])
    for key in ('inputReady','enabled','focused'):need(type(row[key]) is bool)
    if row['inputReady']:need(row['enabled'])
    return row


def selection(value):
    """Require one coherent observed root and every actual page indicator."""
    need(type(value) is dict and type(value.get('tabletLauncherControlsVersion')) is int and value['tabletLauncherControlsVersion']==VERSION
        and value.get('tabletShown') is True and type(value.get('controls')) is list)
    rows=[row for row in value['controls'] if 'tabletLauncherControlVersion' in row]
    need(rows);root=None;pages=set();entry=False
    for row in rows:
        exact(row,BASE|FIELDS);metadata(row)
        actual={key:row[key] for key in ('launcherRootId','launcherQmlSource','launcherCurrentIndex','launcherPageCount')}
        if root is None:root=actual
        else:need(same(root,actual))
        if row['id']=='snapshot.entry':need(not entry);entry=True
        else:need(row['launcherControlIndex'] not in pages);pages.add(row['launcherControlIndex'])
    count=root['launcherPageCount'];need(pages==set(range(count)) if count>1 else not pages)
    return deepcopy(root)
