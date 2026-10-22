"""Normal Pico VR View-menu pointers; camera effects are independently read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_feature_observation import exact,integer,need,number
from adapters.pico4.navigation import validate_snapshot,VIEW_MENU_IDS
from adapters.token_create_ui import scope

VERSION=1


def project(original):
    need(type(original) is dict)
    validate_snapshot(original,original.get('processId'),original.get('updatedEpochMs'))
    need(type(original.get('viewMenuControlsVersion')) is int and original['viewMenuControlsVersion']==VERSION)
    return dict(viewMenuControlsVersion=VERSION,open=original['open'],ready=original['ready'],
        scope=dict(instance=original['bridgeId'],generation=original['generation'],processId=original['processId'],
            sequence=original['lastCommandSequence'],elapsedMs=original['elapsedMs']),
        controls=[deepcopy(row) for row in original['controls'] if row['id'] in VIEW_MENU_IDS])


class PicoViewMenu:
    """Caller retains each intent before input; this helper never retries it.

    An action acknowledgement/checked bit is not a camera, stereo or Emote
    verdict. A whole parent supplies original avatar/render reads and cleanup.
    """
    def __init__(self,original,intent,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (original.capture,intent,monotonic,sleep)))
        self.original,self.intent,self.monotonic,self.sleep=original,intent,monotonic,sleep
        self.previous=None;self.clock=None

    def capture(self):
        value=project(self.original.capture());now=self.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock))
        if self.previous is not None:
            a,b=self.previous['scope'],value['scope']
            need(a['instance']==b['instance'] and a['processId']==b['processId'] and b['sequence']>=a['sequence'] and b['elapsedMs']>=a['elapsedMs'])
        self.previous=deepcopy(value);self.clock=now;return value

    def activate(self,identifier,reference):
        need(identifier in VIEW_MENU_IDS);exact(reference,{'viewMenuControlsVersion','open','ready','scope','controls'});scope(reference['scope'])
        current=self.capture();need(current['open'] and current['ready']
            and type(reference['viewMenuControlsVersion']) is int and reference['viewMenuControlsVersion']==VERSION
            and type(reference['open']) is bool and type(reference['ready']) is bool and type(reference['controls']) is list)
        a,b=reference['scope'],current['scope'];need(all(a[key]==b[key] for key in ('instance','generation','processId','sequence'))
            and integer(a['elapsedMs']) and 0<=b['elapsedMs']-a['elapsedMs']<=5000)
        old=[row for row in reference['controls'] if row['id']==identifier]
        rows=[row for row in current['controls'] if row['id']==identifier]
        need(len(old)==len(rows)==1 and old==rows and rows[0]['enabled'] and rows[0]['inputReady'])
        request=dict(viewMenuInputVersion=VERSION,action='activate',controlId=identifier,controlToken=rows[0]['token'],
            menuInstance=rows[0]['menuInstance'],checkedBefore=rows[0]['checked'],scope=deepcopy(b))
        need(self.intent(deepcopy(request)) is not False)
        # Existing PicoNavigation rebinds the candidate and compares this exact
        # original token before its one normal native pointer dispatch.
        return self.original.navigation.input(identifier,token=rows[0]['token'])

    def wait(self,identifier):
        need(identifier in VIEW_MENU_IDS);started=self.monotonic();need(number(started,0,1e15))
        for index in range(51):
            value=self.capture();now=self.monotonic();need(number(now,started,started+5))
            if value['open'] and value['ready'] and any(row['id']==identifier and row['inputReady'] for row in value['controls']):return value
            if index<50:self.sleep(.1)
        need(False)
