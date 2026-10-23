"""Original observed Qt root identity and weak expiry; no allocation-time claim.

The enclosing native UI receipt owns nonce/PID/candidate and clock provenance.
Weak expiry alone supplies no callback, pixels, process or SDK retirement fact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need,fresh

VERSION=1
LIMIT=16384
HEX=r'[0-9a-f]{32}'


def validate(value,*,pid=None,epoch=None,previous=None,profile="scripts"):
    need(type(profile) is str and profile in ("scripts","login"))
    schema="iosScriptUiRootOwnershipVersion" if profile=="scripts" else "iosLoginUiRootOwnershipVersion"
    domain="native-main-ios-script-ui-roots" if profile=="scripts" else "native-main-ios-login-ui-roots"
    suffixes=({"manager":"/hifi/dialogs/TabletRunningScripts.qml","picker":"/dialogs/NativeFileBrowser.qml"} if profile=="scripts"
        else {"tablet":"/dialogs/TabletLoginDialog.qml","overlay":"/OverlayLoginDialog.qml","dialog":"/LoginDialog.qml"})
    need(type(value) is dict and len(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())<=LIMIT)
    need(type(value.get(schema)) is int and value[schema]==1 and type(value.get('available')) is bool)
    if not value['available']:
        exact(value,{schema,'available'});return value
    exact(value,{schema,'available','instance','sequence','processId','capturedEpochMs','monotonicMs','clockDomain',
        'complete','wholeTreeReady','observationSequence','roots'})
    need(value['clockDomain']==domain and type(value['instance']) is str and re.fullmatch(HEX,value['instance']) and integer(value['sequence'],1,9007199254740991)
        and integer(value['processId'],1,2147483647) and (pid is None or type(pid) is int and value['processId']==pid)
        and integer(value['capturedEpochMs'],1) and integer(value['monotonicMs']) and type(value['complete']) is bool
        and type(value['wholeTreeReady']) is bool and integer(value['observationSequence'],0,64)
        and type(value['roots']) is list and len(value['roots'])<=64)
    if epoch is not None:fresh(value['capturedEpochMs'],epoch)
    ids=set()
    for index,row in enumerate(value['roots'],1):
        exact(row,{'observedIdentity','kind','componentSource','firstObservedSequence','firstObservedEpochMs','firstObservedMonotonicMs',
            'weakAlive','weakExpiredObservedEpochMs','weakExpiredObservedMonotonicMs'})
        need(type(row['observedIdentity']) is str and re.fullmatch(HEX,row['observedIdentity']) and row['observedIdentity'] not in ids
            and row['kind'] in suffixes and type(row['componentSource']) is str and len(row['componentSource'])<=4096
            and not any(ord(c)<32 for c in row['componentSource']) and '?' not in row['componentSource'] and '#' not in row['componentSource'])
        ids.add(row['observedIdentity']);url=urlsplit(row['componentSource'])
        suffix=suffixes[row['kind']]
        need(url.scheme in ('qrc','file') and not url.netloc and url.path.endswith(suffix)
            and type(row['firstObservedSequence']) is int and row['firstObservedSequence']==index
            and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs']) and integer(row['firstObservedMonotonicMs'],0,value['monotonicMs'])
            and type(row['weakAlive']) is bool and integer(row['weakExpiredObservedEpochMs']) and integer(row['weakExpiredObservedMonotonicMs']))
        if row['weakAlive']:need(row['weakExpiredObservedEpochMs']==row['weakExpiredObservedMonotonicMs']==0)
        else:need(row['firstObservedEpochMs']<=row['weakExpiredObservedEpochMs']<=value['capturedEpochMs']
            and row['firstObservedMonotonicMs']<=row['weakExpiredObservedMonotonicMs']<=value['monotonicMs'])
    need(len(value['roots'])==value['observationSequence'] if value['complete'] else len(value['roots'])<=value['observationSequence'])
    if previous is not None:
        validate(previous,pid=pid,profile=profile);need(previous['available'] and value['instance']==previous['instance'] and value['processId']==previous['processId']
            and value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs'] and value['monotonicMs']>=previous['monotonicMs']
            and (previous['complete'] or not value['complete']) and value['observationSequence']>=previous['observationSequence'])
        if value['complete']:
            need(len(value['roots'])>=len(previous['roots']))
            for before,after in zip(previous['roots'],value['roots']):
                need(all(after[key]==before[key] for key in before if key not in ('weakAlive','weakExpiredObservedEpochMs','weakExpiredObservedMonotonicMs'))
                    and (before['weakAlive'] or not after['weakAlive']))
                if not before['weakAlive']:need(after==before)
    return value


def membership(inventory,*,pid=None,epoch=None):
    value=validate(inventory['rootOwnership'],pid=pid,epoch=epoch)
    members=inventory['rootMembership'];exact(members,{'managers','pickers'})
    need(all(type(rows) is list and len(rows)<=16 and all(type(key) is str and re.fullmatch(HEX,key) for key in rows) for rows in members.values()))
    if not inventory['complete']:
        need(members==dict(managers=[],pickers=[]));return value
    need(value['available'] and value['complete'] and value['wholeTreeReady'])
    by_id={row['observedIdentity']:row for row in value['roots']};selected=[]
    for group,kind in (('managers','manager'),('pickers','picker')):
        need(len(members[group])==len(inventory[group]))
        for identity,row in zip(members[group],inventory[group]):
            need(identity in by_id);root=by_id[identity]
            need(root['weakAlive'] and root['kind']==kind and root['componentSource']==row['componentSource']);selected.append(identity)
    need(len(set(selected))==len(selected) and set(selected)=={key for key,row in by_id.items() if row['weakAlive']})
    return value
