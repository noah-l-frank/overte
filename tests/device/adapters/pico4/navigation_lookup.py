"""Original Go To/page/address sources and ordinary scoped Pico input.

The enclosing owner persists intent before each input and separately proves
lookup/modal/world effects. This component never infers those from an ACK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.native_navigation_panels import validate as panels_packet,continuation as panels_advance
from adapters.token_create_ui import nonce,scope
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.contract import identifier

VERSION=1


def control_id(value):
    return type(value) is str and (value in ('navigation.goto','navigation.address')
        or re.fullmatch(r'tablet\.page\.([1-9]|[12][0-9]|3[0-2])',value) is not None)


def packet(value,run):
    identifier(run);exact(value,{'navigationLookupControlsVersion','open','ready','observedEpochMs','scope','controls','native'})
    need(type(value['navigationLookupControlsVersion']) is int and value['navigationLookupControlsVersion']==VERSION
         and type(value['open']) is bool and type(value['ready']) is bool and (value['open'] or not value['ready'])
         and integer(value['observedEpochMs'],1) and type(value['controls']) is list and len(value['controls'])<=34)
    scope(value['scope']);native=value['native'];panels_packet(native,dict(schemaVersion=1,commandId=native.get('commandId'),
        action='feature-navigation-panels',runId=run),value['scope']['processId'],native.get('capturedEpochMs'))
    need(native['navigationPanelsVersion']==2 and all(native['ui'][k]==value['scope'][k2]
        for k,k2 in (('bridgeId','instance'),('generation','generation'),('sequence','sequence'))))
    need(native['ui']['open']==value['open'] and native['ui']['ready']==value['ready']
         and value['scope']['elapsedMs']<=native['ui']['elapsedMs']
         and 0<=native['capturedEpochMs']-value['observedEpochMs']<=1500
         and value['observedEpochMs']<=native['ui']['observedEpochMs'])
    ids=set();tokens=set();source=native['lookup']
    for row in value['controls']:
        fields={'id','token','enabled','focused'};need(type(row) is dict and control_id(row.get('id')))
        if row['id']=='navigation.address':fields|={'textSha256','textLength','inputReady'}
        exact(row,fields)
        need(row['id'] not in ids and nonce(row['token']) and row['token'] not in tokens
             and type(row['enabled']) is bool and type(row['focused']) is bool)
        if row['id']=='navigation.address':
            address=source['address'];need(address is not None and address['visible']
                 and all(row[k]==address[k] for k in ('textSha256','textLength','focused','inputReady'))
                 and type(row['inputReady']) is bool and integer(row['textLength'],0,2048))
        else:
            home=source['home'];need(home is not None and home['visible'])
            if row['id'].startswith('tablet.page.'):need(int(row['id'][12:])<=home['pageCount'])
        ids.add(row['id']);tokens.add(row['token'])
    need(value['ready'] or not value['controls']);return value


def same_reference(before,after,run,control):
    packet(before,run);packet(after,run)
    need(all(before['scope'][k]==after['scope'][k] for k in ('instance','generation','sequence','processId'))
         and 0<=after['observedEpochMs']-before['observedEpochMs']<=1500
         and 0<=after['scope']['elapsedMs']-before['scope']['elapsedMs']<=1500
         and before['controls']==after['controls'] and before['native']['lookup']==after['native']['lookup']
         and before['native']['roots']==after['native']['roots'])
    rows=[r for r in before['controls'] if r['id']==control];need(len(rows)==1);return rows[0]


class PicoNavigationLookup:
    def __init__(self,normal,panels,intent,run):
        need(isinstance(normal,TokenScriptUI) and isinstance(normal.io,PicoScriptIO) and callable(intent))
        identifier(run);self.normal,self.panels,self.intent,self.run=normal,panels,intent,run;self.last=None
    @staticmethod
    def row(value,control):
        rows=[r for r in value['controls'] if r['id']==control];need(len(rows)<=1);return rows[0] if rows else None
    def capture(self):
        raw=self.normal.capture();need(type(raw.get('navigationLookupControlsVersion')) is int and raw['navigationLookupControlsVersion']==VERSION)
        need(type(raw.get('navigationAddressVersion')) is int and raw['navigationAddressVersion']==1)
        native=self.panels.read(self.run)
        value=dict(navigationLookupControlsVersion=VERSION,open=raw['open'],ready=raw['ready'],observedEpochMs=raw['updatedEpochMs'],
            scope=dict(instance=raw['bridgeId'],generation=raw['generation'],sequence=raw['lastCommandSequence'],
                elapsedMs=raw['elapsedMs'],processId=raw['processId']),
            controls=deepcopy([row for row in raw['controls'] if control_id(row['id'])]),native=native)
        packet(value,self.run)
        if self.last is not None:
            panels_advance(self.last['native'],native)
            need(value['scope']['instance']==self.last['scope']['instance'] and value['scope']['processId']==self.last['scope']['processId'])
        self.last=deepcopy(value);return value
    def input(self,control,action='activate',*,original,text=None):
        need(control_id(control) and action in ('activate','replace','submit'))
        current=self.capture();row=same_reference(original,current,self.run,control)
        need(current['open'] and current['ready'] and current['native']['lookup']['complete'] and row['enabled'])
        if action in ('replace','submit'):
            need(control=='navigation.address' and row['focused'] and row['inputReady'])
        if action=='replace':need(text=='hifi://hidden-'+self.run)
        else:need(text is None)
        need(control=='navigation.address' or action=='activate')
        value=dict(navigationLookupInputVersion=VERSION,controlId=control,action=action,controlToken=row['token'],
            scope=deepcopy(current['scope']),native=deepcopy(current['native']))
        if text is not None:value['text']=text
        self.intent(value)
        # The actual backend captures again and validates this original token,
        # generation/counter and native source fingerprint before pointer/IME.
        self.normal.io.navigation.input(control,action,text,token=row['token'],expected_scope=current['scope'],
            expected_address='hifi://hidden-'+self.run if action=='submit' else None)
        after=self.capture();need(after['scope']['sequence']==current['scope']['sequence']+1);return after
