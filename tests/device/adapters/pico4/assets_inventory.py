"""Original weak picker/file-model lifetime; hidden state never means death."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_avatar_render import nonce
from adapters.native_feature_observation import exact,integer,need
from urllib.parse import urlsplit


def inventory(value):
    exact(value,{'assetsUiInventoryVersion','instance','sequence','elapsedMs','capturedEpochMs','complete','browsers'})
    need(type(value['assetsUiInventoryVersion']) is int and value['assetsUiInventoryVersion']==1 and nonce(value['instance'])
        and integer(value['sequence'],1,9007199254740991) and integer(value['elapsedMs'],0) and integer(value['capturedEpochMs'],1)
        and type(value['complete']) is bool and type(value['browsers']) is list and len(value['browsers'])<=16)
    ids=[];models=set()
    for row in value['browsers']:
        exact(row,{'id','modelId','contextId','windowId','componentSource','bornEpochMs','rootAlive','modelAlive','contextAlive',
            'windowAlive','inCurrentTree','visible','pendingDocuments','closing'})
        need(all(nonce(row[key]) for key in ('id','modelId','contextId','windowId')) and row['modelId'] not in models
            and integer(row['bornEpochMs'],1,value['capturedEpochMs'])
            and all(type(row[key]) is bool for key in ('rootAlive','modelAlive','contextAlive','windowAlive','inCurrentTree','visible','pendingDocuments','closing')))
        need(not row['visible'] or row['rootAlive']);need(not row['inCurrentTree'] or row['rootAlive'])
        need(type(row['componentSource']) is str and 1<=len(row['componentSource'])<=4096
            and not any(ord(ch)<32 for ch in row['componentSource']))
        source=urlsplit(row['componentSource']);need(source.scheme in ('file','qrc') and not source.netloc and not source.query
            and not source.fragment and source.path.endswith('/dialogs/NativeFileBrowser.qml'))
        ids.append(row['id']);models.add(row['modelId'])
    need(ids==sorted(set(ids)) and (value['complete'] or not ids));return value


def original(value):
    need(type(value.get('assetsUiInventoryVersion')) is int and value['assetsUiInventoryVersion']==1)
    return deepcopy(inventory(value['assetsUiInventory']))
