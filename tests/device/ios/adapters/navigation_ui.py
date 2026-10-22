"""Actual retained Go To roots, independently of hit-test/input eligibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit,unquote

from adapters.native_feature_observation import exact,need
from ios.adapters.places_controls import identity

VERSION=1


def component(value):
    need(type(value) is str and len(value)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in value))
    parsed=urlsplit(value);path=unquote(parsed.path,encoding='utf-8',errors='strict')
    need(parsed.scheme in ('qrc','file') and not parsed.netloc and not parsed.query and not parsed.fragment
         and path.endswith('/+android_phoneInterface/AddressBarDialog.qml')
         and not any(part in ('.','..') for part in path.split('/')))
    return value


def validate(value):
    exact(value,{'iosNavigationUiInventoryVersion','complete','roots'})
    need(type(value['iosNavigationUiInventoryVersion']) is int and value['iosNavigationUiInventoryVersion']==VERSION
         and type(value['complete']) is bool and type(value['roots']) is list and len(value['roots'])<=16)
    need(value['complete'] or not value['roots'])
    ids=set()
    for root in value['roots']:
        exact(root,{'rootId','qmlSource','shown','visible','windowPresent','field'})
        identity(root['rootId']);component(root['qmlSource']);need(root['rootId'] not in ids);ids.add(root['rootId'])
        for key in ('shown','visible','windowPresent'):need(type(root[key]) is bool)
        need(not root['visible'] or root['shown'])
        field=root['field'];exact(field,{'text','visible','focused'})
        need(type(field['text']) is str and len(field['text'])<=4096
             and type(field['visible']) is bool and type(field['focused']) is bool)
        field['text'].encode('utf-8')
        need(not field['visible'] or root['visible'])
    return value


def project(ui):
    """A historical projection keeps the original native input packet clocks."""
    from ios.adapters.normal_input import observation
    need(type(ui) is dict and 'navigationInventory' in ui)
    observation(ui,ui.get('processId'),ui.get('sampleEpochMs'))
    inventory=validate(ui['navigationInventory']);need(inventory['complete'] is True)
    # A shown detached root is uncertain, not evidence that Go To was closed.
    need(all(not root['shown'] or root['windowPresent'] for root in inventory['roots']))
    visible=[root for root in inventory['roots'] if root['visible']];need(len(visible)<=1)
    return dict(addressDialog=bool(visible),roots=deepcopy(inventory['roots']))
