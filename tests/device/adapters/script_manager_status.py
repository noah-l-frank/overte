"""Original manager status and separately displayed Label; no desired verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit

from adapters.normal_feature_state import need
from adapters.normal_script_manager import missing_script_url

VERSION = 2
FIELDS = {'managerSourceVersion', 'available', 'componentSource', 'statusText',
          'labelText', 'rootVisible', 'labelVisible', 'errorUrl', 'errorEpochMs'}


def validate(value):
    need(type(value) is dict and type(value.get('managerSourceVersion')) is int
         and value['managerSourceVersion'] == VERSION and type(value.get('available')) is bool)
    if not value['available']:
        need(set(value) == {'managerSourceVersion', 'available'})
        return value
    need(set(value) == FIELDS and all(type(value[key]) is bool for key in ('rootVisible', 'labelVisible'))
         and type(value['componentSource']) is str and len(value['componentSource']) <= 4096
         and not any(ord(char) < 32 for char in value['componentSource'])
         and '?' not in value['componentSource'] and '#' not in value['componentSource'])
    try: source = urlsplit(value['componentSource'])
    except ValueError: need(False)
    need(source.scheme in {'file', 'qrc'} and not source.netloc
         and source.path.endswith('/hifi/dialogs/TabletRunningScripts.qml'))
    for key in ('statusText', 'labelText'):
        need(type(value[key]) is str and len(value[key]) <= 8192
             and all(ord(char) >= 32 or char in '\r\n\t' for char in value[key]))
    need(type(value['errorUrl']) is str and len(value['errorUrl'])<=8192
         and all(ord(char)>=32 for char in value['errorUrl'])
         and type(value['errorEpochMs']) is int and 0<=value['errorEpochMs']<=2**53-1
         and (value['errorEpochMs']==0 if not value['errorUrl'] else value['errorEpochMs']>=1))
    return value


def manager_status(snapshot):
    # Freshness, nonce, PID/birth, candidate and inventory completeness belong
    # to the original owning IO.capture(); this never retimes their snapshot.
    need(type(snapshot) is dict and type(snapshot.get('fileControlsVersion')) is int
         and snapshot['fileControlsVersion'] == 1 and snapshot.get('ready') is True
         and type(snapshot.get('controls')) is list and len(snapshot['controls']) <= 384)
    rows = [row for row in snapshot['controls'] if type(row) is dict and row.get('id') == 'scripts.from-file']
    need(len(rows) == 1 and 'manager' in rows[0])
    value = validate(rows[0]['manager']); need(value['available'])
    return deepcopy(value)


def missing_status(value, url, *, after_epoch=0):
    missing_script_url(url)
    value=validate(value);need(value['available'])
    need(value['rootVisible'] and value['labelVisible'] and value['labelText'] == value['statusText'])
    need(type(after_epoch) is int and after_epoch>=0 and value['errorUrl']==url
         and value['errorEpochMs']>=after_epoch)
    # The label may be compact, but an actual independently recorded full URL
    # and signal epoch remain mandatory. A basename alone is never identity.
    prefixes=('Failed to load '+url,'Failed to load '+urlsplit(url).path.rsplit('/',1)[-1])
    need(any(value['labelText']==prefix or value['labelText'].startswith(prefix+': ') for prefix in prefixes))
    return value  # Original text, not a claimed NotFound callback or peer result.


def missing_error(snapshot, url, *, after_epoch=0):
    return deepcopy(missing_status(manager_status(snapshot),url,after_epoch=after_epoch))
