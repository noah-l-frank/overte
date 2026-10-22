"""Closed metadata for the existing path-specific Pico Snapshot QML buttons."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import re
from adapters.native_feature_observation import exact,need
from urllib.parse import unquote,urlsplit

def path(value):
    from adapters.pico4.snapshot_capture_source import path as original_path
    return original_path(value)

def component(value):
    if type(value) is not str or len(value)>4096 or '\0' in unquote(value):return False
    url=urlsplit(value);parts=unquote(url.path).split('/')
    return (url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and unquote(url.path).endswith('/system/snapshot/NativeSnapshotReview.qml')
        and not any(part in ('.','..') for part in parts))

VERSION=1
CANCELS=('snapshot.cancel-export','snapshot.cancel-upload')


def control(value):
    return type(value) is str and (value in CANCELS or re.fullmatch(r'snapshot\.(save|share|upload)\.[0-9a-f]{64}',value) is not None)


def metadata(value):
    need(type(value) is dict and control(value.get('id')))
    field='exportTicket' if value['id']==CANCELS[0] else 'uploadPath' if value['id']==CANCELS[1] else 'path'
    exact(value,{'id','token','enabled','focused','profile','componentUrl','inputReady',field})
    need(value['profile']=='native-pico-snapshot-export-v1' and component(value['componentUrl'])
        and type(value['inputReady']) is bool and (not value['inputReady'] or value['enabled']))
    if field=='exportTicket':need(type(value[field]) is str and re.fullmatch('[1-9][0-9]{0,18}',value[field]) is not None and int(value[field])<=2**63-1)
    else:
        need(path(value[field]))
        if field=='path':need(value['id'].rsplit('.',1)[1]==hashlib.sha256(value[field].encode()).hexdigest())
    return value
