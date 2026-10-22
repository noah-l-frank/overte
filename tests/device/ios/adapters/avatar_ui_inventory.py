"""Actual retained Avatar/People roots, independently of visible input rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from ios.adapters.avatar_controls import nonce,component

VERSION=1


def validate(value):
    exact(value,{'iosAvatarUiInventoryVersion','complete','roots'})
    need(type(value['iosAvatarUiInventoryVersion']) is int and value['iosAvatarUiInventoryVersion']==VERSION
        and type(value['complete']) is bool and type(value['roots']) is list and len(value['roots'])<=16
        and (value['complete'] or not value['roots']))
    seen=set()
    for row in value['roots']:
        exact(row,{'rootId','qmlSource','role','visible','enabled','attached','windowPresent','panels'})
        need(nonce(row['rootId']) and row['rootId'] not in seen and row['role'] in ('avatar','people'));seen.add(row['rootId'])
        component(row['qmlSource']);need(row['qmlSource'].endswith('/Pal.qml')==(row['role']=='people'))
        for name in ('visible','enabled','attached','windowPresent'):need(type(row[name]) is bool)
        exact(row['panels'],{'connection'} if row['role']=='people' else {'popup','favorite','settings','wearables'})
        need(all(type(flag) is bool for flag in row['panels'].values()))
    return value


def absent(widgets):
    need(type(widgets.get('avatarControlsVersion')) is int and widgets['avatarControlsVersion']==1
        and 'avatarInventory' in widgets)
    inventory=validate(widgets['avatarInventory']);need(inventory['complete']);return not inventory['roots']
