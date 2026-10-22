"""Original retained Emote QML roots, independently of visible input rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import unquote,urlsplit
import uuid
from adapters.native_feature_observation import exact,need
from adapters.token_emote_ui import NAMES

VERSION=1


def validate(value):
    exact(value,{'iosEmoteUiInventoryVersion','complete','roots'})
    need(type(value['iosEmoteUiInventoryVersion']) is int and value['iosEmoteUiInventoryVersion']==VERSION
        and type(value['complete']) is bool and type(value['roots']) is list and len(value['roots'])<=16)
    need(value['complete'] or not value['roots']);ids=set()
    for row in value['roots']:
        exact(row,{'rootId','qmlSource','activeName','visible','enabled','attached','windowPresent'})
        need(type(row['rootId']) is str)
        try:need(str(uuid.UUID(row['rootId']))==row['rootId'] and uuid.UUID(row['rootId']).int!=0)
        except ValueError:need(False)
        need(row['rootId'] not in ids);ids.add(row['rootId'])
        need(type(row['qmlSource']) is str and len(row['qmlSource'])<=4096 and not any(ord(c)<32 for c in row['qmlSource']))
        source=urlsplit(row['qmlSource']);path=unquote(source.path,errors='strict')
        need(source.scheme in ('file','qrc') and not source.netloc and not source.query and not source.fragment
            and path==source.path and path.endswith('/system/+android_phoneInterface/PhoneEmote.qml')
            and not any(part in ('.','..') for part in path.split('/')) and '\\' not in path)
        need(type(row['activeName']) is str and row['activeName'] in ('',*NAMES))
        for field in ('visible','enabled','attached','windowPresent'):need(type(row[field]) is bool)
    return value


def absent(original):
    need(original.get('emoteControlsVersion')==2 and type(original.get('emoteControlsVersion')) is int)
    inventory=validate(original['emoteInventory']);need(inventory['complete'])
    return not inventory['roots']
