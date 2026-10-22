"""Actual Pico fixture-app tiles on original normal navigation references.

Button identity is original UI evidence. It does not establish the owning script
or loaded WebView; the whole owner must join its independent original sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,need
from adapters.token_create_ui import nonce,navigation,scope

VERSION=1
IDS={'browser-app.web','browser-app.inline'}
CAPTIONS={'browser-app.web':'WEB TEST','browser-app.inline':'INLINE TEST'}


def control_id(identifier):return type(identifier) is str and (identifier in IDS or navigation(identifier))


def metadata(row):
    need(type(row) is dict and type(row.get('id')) is str and row['id'] in IDS)
    exact(row,{'id','token','enabled','focused','inputReady','buttonId','caption','componentSourceSha256'})
    need(nonce(row['token']) and nonce(row['buttonId']) and '-' in row['buttonId']
        and row['caption']==CAPTIONS[row['id']] and all(type(row[k]) is bool for k in ('enabled','focused','inputReady'))
        and (not row['inputReady'] or row['enabled']) and type(row['componentSourceSha256']) is str
        and re.fullmatch('[0-9a-f]{64}',row['componentSourceSha256']))
    return row


def snapshot(value):
    exact(value,{'picoBrowserAppControlsVersion','open','ready','scope','controls'})
    need(type(value['picoBrowserAppControlsVersion']) is int and value['picoBrowserAppControlsVersion']==VERSION
        and all(type(value[k]) is bool for k in ('open','ready')) and (not value['ready'] or value['open'])
        and type(value['controls']) is list and len(value['controls'])<=35)
    scope(value['scope']);ids=set();tokens=set();buttons=set()
    for row in value['controls']:
        need(type(row) is dict and type(row.get('id')) is str)
        if row.get('id') in IDS:
            metadata(row);need(row['buttonId'] not in buttons);buttons.add(row['buttonId'])
        else:
            exact(row,{'id','token','enabled','focused'})
            need(navigation(row['id']) and nonce(row['token']) and all(type(row[k]) is bool for k in ('enabled','focused')))
        need(row['id'] not in ids and row['token'] not in tokens);ids.add(row['id']);tokens.add(row['token'])
    need(value['open'] or not value['controls']);return value


def project(original):
    return snapshot(dict(picoBrowserAppControlsVersion=original['picoBrowserAppControlsVersion'],open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],sequence=original['lastCommandSequence'],
            elapsedMs=original['elapsedMs'],processId=original['processId']),controls=deepcopy([r for r in original['controls'] if control_id(r['id'])])))


def same_reference(original,current,identifier):
    snapshot(original);snapshot(current);need(control_id(identifier))
    need(all(original['scope'][key]==current['scope'][key] for key in ('instance','generation','sequence','processId'))
        and 0<=current['scope']['elapsedMs']-original['scope']['elapsedMs']<=5000
        and original['open'] and original['ready'] and current['open'] and current['ready'])
    before=[r for r in original['controls'] if r['id']==identifier];after=[r for r in current['controls'] if r['id']==identifier]
    need(len(before)==len(after)==1 and before[0]==after[0]);return before[0]


class PicoBrowserAppsIO:
    def __init__(self,original,*,source_lock,read_only=True):
        from adapters.script_journey.lock import ScriptSourceLock
        need(isinstance(source_lock,ScriptSourceLock) and type(read_only) is bool)
        self.original,self.lock,self.read_only,self.fence=original,source_lock,read_only,None
        original.navigation.io.bind_before_send(self.before_send)
    def before_send(self,command):
        self.lock.assert_held();need(not self.read_only)
        if self.fence is not None:self.fence.before_send(command)
        self.lock.assert_held()
    def capture(self):
        self.lock.assert_held();value=project(self.original.capture());self.lock.assert_held();return value
    def activate(self,identifier,*,reference):
        self.lock.assert_held();need(not self.read_only)
        self.original.navigation.input(identifier,reference=reference)
    def bind_input_fence(self,fence):
        need(self.fence is None or self.fence is fence);self.fence=fence
        self.original.navigation.io.bind_controller_admission(fence.before_controller,intent=fence.stage_intent,before_publish=fence.before_publish)
