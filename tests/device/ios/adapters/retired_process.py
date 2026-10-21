"""Original OS/DVT numeric-PID observations after the native app has stopped.

Appium's Node-host clocks remain separate from controller and native clocks.
This reader cannot stop/launch an app or select an arbitrary PID/device.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError
from ios.adapters.installed_code import source as process_source
from ios.adapters.login_source import nonce

VERSION=1
ACQUISITION_VERSION=1
LIMIT=16384


def command(value):
    exact(value,{'bundleId','commandId'});nonce(value['commandId'])
    need(type(value['bundleId']) is str and len(value['bundleId'])<=255 and
         re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9][A-Za-z0-9-]*)+',value['bundleId']))
    return value


def clocks(before,after,limit):
    for row in (before,after):
        exact(row,{'epochMs','monotonicMs'})
        need(integer(row['epochMs'],1,10**15) and number(row['monotonicMs'],0,10**15))
    elapsed=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=elapsed<limit and 0<=mono<limit and abs(elapsed-mono)<=250)


def validate(value,query,pid,source,previous=None):
    """Pure original validation; historical validation does not create freshness."""
    command(query);process_source(source);need(integer(pid,1,2147483647) and type(value) is dict
        and len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    exact(value,{'iosRetiredProcessVersion','commandId','instance','sequence','source','clockDomain',
                 'clockBefore','clockAfter','anchor','appStates','bundlePids','pidChecks'})
    need(type(value['iosRetiredProcessVersion']) is int and value['iosRetiredProcessVersion']==VERSION
         and value['commandId']==query['commandId'] and value['instance']==source['instance']
         and integer(value['sequence'],1,10**9) and value['source']=='dvt-owned-pid-and-bundle-state'
         and value['clockDomain']=='appium-node-host')
    clocks(value['clockBefore'],value['clockAfter'],1500)
    anchor=value['anchor'];exact(anchor,{'sequence','pid','appStates','bundlePids','clockBefore','clockAfter'})
    need(integer(anchor['sequence'],1,value['sequence']-1) and type(anchor['pid']) is int and anchor['pid']==pid
         and type(anchor['appStates']) is list and len(anchor['appStates'])==2
         and all(integer(v,2,4) for v in anchor['appStates'])
         and (anchor['appStates'][0]==4)==(anchor['appStates'][1]==4)
         and type(anchor['bundlePids']) is list and len(anchor['bundlePids'])==2
         and all(type(v) is int and v==pid for v in anchor['bundlePids']))
    clocks(anchor['clockBefore'],anchor['clockAfter'],5000)
    need(value['clockBefore']['epochMs']>=anchor['clockAfter']['epochMs']
         and value['clockBefore']['monotonicMs']>=anchor['clockAfter']['monotonicMs'])
    need(type(value['appStates']) is list and len(value['appStates'])==2 and all(integer(v,0,4) for v in value['appStates'])
         and type(value['bundlePids']) is list and len(value['bundlePids'])==2
         and all(integer(v,0,2147483647) for v in value['bundlePids'])
         and type(value['pidChecks']) is list and len(value['pidChecks'])==2)
    for row in value['pidChecks']:
        exact(row,{'pid','running'});need(type(row['pid']) is int and row['pid']==pid and type(row['running']) is bool)
    if previous is not None:
        old_query=dict(query,commandId=nonce(previous['commandId']));validate(previous,old_query,pid,source)
        need(value['commandId']!=previous['commandId'] and value['sequence']>previous['sequence']
             and digest(anchor)==digest(previous['anchor'])
             and value['clockBefore']['epochMs']>=previous['clockAfter']['epochMs']
             and value['clockBefore']['monotonicMs']>=previous['clockAfter']['monotonicMs'])
    return value


def absent(value):
    """Only use after complete original validation; bundle absence is insufficient."""
    return (all(v in (0,1) for v in value['appStates']) and value['bundlePids']==[0,0]
            and all(row['running'] is False for row in value['pidChecks']))


class IOSRetiredProcess:
    def __init__(self,send,guard,bundle,pid,source,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(all(callable(v) for v in (send,guard,epoch_ms,monotonic)) and integer(pid,1,2147483647))
        command(dict(bundleId=bundle,commandId='ios-'+'a'*32));process_source(source)
        self.send,self.guard,self.bundle,self.pid,self.source=send,guard,bundle,pid,deepcopy(source)
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.last=self.acquisition=None

    def read(self):
        try:
            before=self.epoch_ms();started=self.monotonic();need(number(before,1,10**15) and number(started,0,10**15))
            need(self.guard() is not False)
            query=command(dict(bundleId=self.bundle,commandId='ios-'+uuid.uuid4().hex))
            value=deepcopy(self.send(deepcopy(query)));validate(value,query,self.pid,self.source,self.last)
            need(self.guard() is not False);after=self.epoch_ms();ended=self.monotonic()
            need(number(after,before,before+1500) and number(ended,started,started+1.5)
                 and after-before<1500 and ended-started<1.5 and abs(after-before-(ended-started)*1000)<=250)
            acquisition=dict(iosRetiredProcessAcquisitionVersion=ACQUISITION_VERSION,
                hostBeforeEpochMs=before,hostAfterEpochMs=after,hostBeforeMonotonic=started,hostAfterMonotonic=ended,
                originalSha256=digest(value))
            # The raw Node-host clocks and original anchor remain untouched.
            self.last,self.acquisition=deepcopy(value),acquisition;return deepcopy(value)
        except Exception:raise NativeUIError('Original iOS retired process observation is unavailable') from None
