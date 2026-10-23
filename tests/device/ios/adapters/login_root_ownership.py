"""Actual observed Login Qt roots and token membership, never credential data.

This optional component preserves ordinary Login metadata version 2 unchanged.
Only original QPointer expiry or separately proven OS death ends an admitted
root's lifetime; hidden controls and successful login never supply that fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import exact,need
from adapters.script_ui_root_ownership import validate as roots
from adapters.token_login_ui import IDS

VERSION=1


def valid_uuid(value):
    try:return type(value) is str and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0
    except ValueError:return False


def validate(value,*,pid=None,epoch=None,previous=None):
    exact(value,{'iosLoginUiRootsVersion','complete','ownership','controls'})
    need(type(value['iosLoginUiRootsVersion']) is int and value['iosLoginUiRootsVersion']==VERSION
        and type(value['complete']) is bool and type(value['controls']) is list and len(value['controls'])<=16)
    if previous is not None:validate(previous,pid=pid)
    original=roots(value['ownership'],pid=pid,epoch=epoch,profile='login',previous=None if previous is None else previous['ownership'])
    if not value['complete']:need(not value['controls']);return value
    need(original['available'] and original['complete'] and original['wholeTreeReady'])
    by_id={row['observedIdentity']:row for row in original['roots']};identifiers=set();tokens=set()
    for row in value['controls']:
        exact(row,{'id','token','observedIdentity'})
        need(row['id'] in IDS and row['id']!='login.entry' and row['id'] not in identifiers and valid_uuid(row['token']) and row['token'] not in tokens
            and type(row['observedIdentity']) is str and re.fullmatch('[0-9a-f]{32}',row['observedIdentity'])
            and row['observedIdentity'] in by_id and by_id[row['observedIdentity']]['weakAlive'])
        identifiers.add(row['id']);tokens.add(row['token'])
    need([row['id'] for row in value['controls']]==sorted(identifiers));return value


def membership(observation,*,pid=None,epoch=None,previous=None):
    need(type(observation) is dict and type(observation.get('controls')) is list)
    value=validate(observation['loginRootOwnership'],pid=pid,epoch=epoch,previous=previous)
    if value['complete']:
        actual=[dict(id=row['id'],token=row['token']) for row in observation['controls'] if row['id'] in IDS and row['id']!='login.entry']
        need(actual==[{key:row[key] for key in ('id','token')} for row in value['controls']])
    return value


def admitted(observation,*,control_id,pid,epoch):
    value=membership(observation,pid=pid,epoch=epoch);need(value['complete'] and control_id in IDS and control_id!='login.entry')
    matches=[row for row in value['controls'] if row['id']==control_id];need(len(matches)==1)
    row=next(row for row in value['ownership']['roots'] if row['observedIdentity']==matches[0]['observedIdentity'])
    need(row['weakAlive']);return deepcopy(row)


def follow(admission,current,*,pid,epoch):
    value=validate(current,pid=pid,epoch=epoch);need(value['complete'])
    rows=[row for row in value['ownership']['roots'] if row['observedIdentity']==admission['observedIdentity']];need(len(rows)==1)
    row=rows[0];need(all(row[key]==admission[key] for key in admission if key not in ('weakAlive','weakExpiredObservedEpochMs','weakExpiredObservedMonotonicMs')))
    if not admission['weakAlive']:need(row==admission)
    return deepcopy(row)
