"""Passive complete source-owned manager/picker inventory, independent of input rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit

from adapters.normal_feature_state import need
from adapters.script_manager_status import validate as validate_manager

VERSION = 1


def text(value, limit):
    need(type(value) is str and len(value) <= limit
         and all(ord(char) >= 32 or char in '\r\n\t' for char in value))


def validate(value):
    need(type(value) is dict and set(value) == {'inventoryVersion', 'complete', 'managers', 'pickers', 'tabletPresent', 'tabletShown'}
         and type(value['inventoryVersion']) is int and value['inventoryVersion'] == VERSION
         and type(value['complete']) is bool
         and type(value['tabletPresent']) is bool and type(value['tabletShown']) is bool
         and (not value['tabletShown'] or value['tabletPresent'])
         and all(type(value[key]) is list and len(value[key]) <= 16 for key in ('managers', 'pickers')))
    if not value['complete']:
        need(value['managers'] == [] and value['pickers'] == [])
        return value
    for manager in value['managers']:
        validate_manager(manager); need(manager['available'])
        need(not manager['labelVisible'] or manager['rootVisible'])
    for picker in value['pickers']:
        need(type(picker) is dict and set(picker) == {'componentSource', 'visible', 'closing', 'requestId', 'errorText'}
             and type(picker['visible']) is bool and type(picker['closing']) is bool)
        text(picker['componentSource'], 4096)
        need(not any(ord(char) < 32 for char in picker['componentSource'])
             and '?' not in picker['componentSource'] and '#' not in picker['componentSource'])
        try: source = urlsplit(picker['componentSource'])
        except ValueError: need(False)
        need(source.scheme in {'file', 'qrc'} and not source.netloc
             and source.path.endswith('/dialogs/NativeFileBrowser.qml'))
        text(picker['requestId'], 4096); text(picker['errorText'], 8192)
    return value


def ui_state(snapshot):
    # The owning IO.capture supplies the original nonce, source cursor, clocks,
    # candidate and process guards. This helper does not reacquire or retime it.
    need(type(snapshot) is dict and type(snapshot.get('fileControlsVersion')) is int
         and snapshot['fileControlsVersion'] == 1 and snapshot.get('ready') is True
         and 'scriptInventory' in snapshot)
    inventory = validate(snapshot['scriptInventory']); need(inventory['complete'])
    managers = [row for row in inventory['managers'] if row['rootVisible']]
    pickers = [row for row in inventory['pickers'] if row['visible']]
    need(len(managers) <= 1 and len(pickers) <= 1 and (not pickers or managers))
    need(inventory['tabletPresent'] or not managers and not pickers)
    if not inventory['tabletShown']: managers, pickers = [], []
    return deepcopy(dict(open=bool(managers), picker=bool(pickers),
        manager=managers[0] if managers else None,
        pickerSource=pickers[0] if pickers else None,
        systemPending=any(row['requestId'] != '' for row in inventory['pickers'])))
