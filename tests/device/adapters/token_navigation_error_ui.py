"""Ordinary Pico OK input to the exact originally presented lookup modal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re

from adapters.native_feature_observation import exact, integer, need
from adapters.native_navigation_modals import MESSAGE_SHA256, presented, validate as native_modal
from adapters.token_create_ui import nonce, scope

VERSION = 1
HEX = r'[0-9a-f]{32}'


def control_id(value):
    return type(value) is str and re.fullmatch(r'navigation\.error\.ok\.' + HEX, value) is not None


def metadata(value):
    exact(value, {'id', 'token', 'enabled', 'focused', 'inputReady', 'modalId', 'eventId', 'runId',
                  'lookupGeneration', 'createdEpochMs', 'messageSha256'})
    need(control_id(value['id']) and nonce(value['token']) and type(value['modalId']) is str
         and re.fullmatch(HEX, value['modalId']) and value['id'] == 'navigation.error.ok.' + value['modalId']
         and all(type(value[k]) is bool for k in ('enabled', 'focused', 'inputReady'))
         and all(type(value[k]) is str and re.fullmatch(HEX, value[k]) for k in ('eventId', 'runId'))
         and integer(value['lookupGeneration'], 1) and integer(value['createdEpochMs'], 1)
         and type(value['messageSha256']) is str and re.fullmatch('[0-9a-f]{64}', value['messageSha256']))
    need(not value['inputReady'] or value['enabled'] and value['messageSha256'] == MESSAGE_SHA256)
    return value


def snapshot(value):
    exact(value, {'navigationErrorControlsVersion', 'open', 'ready', 'observedEpochMs', 'scope', 'controls'})
    need(type(value['navigationErrorControlsVersion']) is int and value['navigationErrorControlsVersion'] == VERSION
         and type(value['open']) is bool and type(value['ready']) is bool and (not value['ready'] or value['open'])
         and integer(value['observedEpochMs'], 1) and type(value['controls']) is list and len(value['controls']) <= 128)
    scope(value['scope']);ids = set();tokens = set()
    for row in value['controls']:
        metadata(row)
        need(row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls'])
    return value


def same_reference(original, current, identifier):
    snapshot(original);snapshot(current)
    need(all(original['scope'][k] == current['scope'][k] for k in ('instance', 'generation', 'sequence', 'processId'))
         and 0 <= current['scope']['elapsedMs'] - original['scope']['elapsedMs'] <= 5000
         and 0 <= current['observedEpochMs'] - original['observedEpochMs'] <= 5000
         and original['controls'] == current['controls'])
    rows = [row for row in original['controls'] if row['id'] == identifier]
    need(len(rows) == 1)
    return rows[0]


class TokenNavigationErrorUI:
    def __init__(self, io, intent, run):
        need(callable(intent) and type(run) is str and re.fullmatch(HEX, run))
        self.io, self.intent, self.run = io, intent, run
        self.last = None

    def capture(self):
        value = deepcopy(snapshot(self.io.capture()))
        if self.last is not None:
            need(all(value['scope'][k] == self.last['scope'][k] for k in ('instance', 'processId'))
                 and value['scope']['sequence'] >= self.last['scope']['sequence']
                 and value['scope']['elapsedMs'] >= self.last['scope']['elapsedMs']
                 and value['observedEpochMs'] >= self.last['observedEpochMs'])
        self.last = deepcopy(value)
        return value

    def dismiss(self, original, event):
        need(type(original) is dict and original.get('runId') == self.run)
        before = self.capture()
        native_modal(original, dict(schemaVersion=1, commandId=original.get('commandId'),
            action='feature-navigation-modals', runId=self.run), before['scope']['processId'], before['observedEpochMs'])
        modal = presented(original, event)
        need(before['open'] and before['ready']
             and before['scope']['instance'] == original['uiBridgeId']
             and before['scope']['generation'] == original['uiGeneration']
             and before['scope']['processId'] == original['processId']
             and before['scope']['sequence'] == original['uiInputSequence']
             and 0 <= before['observedEpochMs'] - original['uiEpochMs'] <= 1500)
        identifier = 'navigation.error.ok.' + modal['modalId']
        rows = [row for row in before['controls'] if row['id'] == identifier]
        need(len(rows) == 1)
        row = rows[0]
        need(row['enabled'] and row['inputReady'] and row['runId'] == self.run
             and row['eventId'] == event['eventId'] and row['lookupGeneration'] == event['lookupGeneration']
             and row['createdEpochMs'] == modal['createdEpochMs'] and row['messageSha256'] == MESSAGE_SHA256)
        self.intent(dict(navigationErrorInputVersion=VERSION, action='activate', controlId=identifier,
                         controlToken=row['token'], scope=deepcopy(before['scope']), modalId=modal['modalId'], eventId=event['eventId']))
        self.io.activate(identifier, reference=before)
        after = self.capture()
        need(after['scope']['sequence'] == before['scope']['sequence'] + 1)
        # This consumed input is not proof of response, QObject destruction or
        # quiet cleanup. Those require fresh independent native modal reads.
        return after
