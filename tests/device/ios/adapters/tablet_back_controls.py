"""Original semantic Back source tokens; input delivery is no editor verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_export_controls import identity,BASE

VERSION=1
FIELDS={'tabletBackControlVersion','navigationRootId','navigationQmlSource','screenIdSha256',
    'sourceHistorySha256','sourceHistoryLength','backTargetPending','inputReady'}


def metadata(row):
    need(type(row) is dict and row.get('id')=='tablet.back' and FIELDS<=set(row)
        and type(row['tabletBackControlVersion']) is int and row['tabletBackControlVersion']==VERSION)
    identity(row['navigationRootId']);identity(row['token']);source=row['navigationQmlSource']
    need(type(source) is str and 1<=len(source)<=4096 and all(ord(char)>=32 and ord(char)!=127 for char in source))
    url=urlsplit(source);need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and url.path.endswith('/hifi/tablet/WindowRoot.qml'))
    for key in ('screenIdSha256','sourceHistorySha256'):
        need(type(row[key]) is str and re.fullmatch('[a-f0-9]{64}',row[key]) is not None)
    need(integer(row['sourceHistoryLength'],0,128))
    for key in ('backTargetPending','inputReady','enabled','focused'):need(type(row[key]) is bool)
    if row['inputReady']:need(row['enabled'] and not row['backTargetPending'])
    return row


def reference(value):
    need(type(value) is dict and type(value.get('tabletBackControlsVersion')) is int
        and value['tabletBackControlsVersion']==VERSION and value.get('tabletShown') is True and value.get('ready') is True
        and type(value.get('controls')) is list)
    rows=[row for row in value['controls'] if row.get('id')=='tablet.back'];need(len(rows)==1)
    row=rows[0];exact(row,BASE|FIELDS);metadata(row);need(row['inputReady'])
    return dict(scope={key:deepcopy(value[key]) for key in ('instance','processId','lastSequence','elapsedMs')},control=deepcopy(row))


def current(original,value):
    exact(original,{'scope','control'});exact(original['scope'],{'instance','processId','lastSequence','elapsedMs'})
    identity(original['scope']['instance']);exact(original['control'],BASE|FIELDS);metadata(original['control'])
    for key in ('processId','lastSequence','elapsedMs'):need(integer(original['scope'][key],1 if key=='processId' else 0))
    actual=reference(value)
    need(same(original['control'],actual['control']) and all(same(original['scope'][key],actual['scope'][key])
        for key in ('instance','processId','lastSequence')) and actual['scope']['elapsedMs']>=original['scope']['elapsedMs'])
    return actual
