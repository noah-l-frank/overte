"""Original OS share-chooser resolution for a bounded Snapshot handoff.

This reads package-manager results only. It does not launch or select anything,
verify a grant, or claim that the later native Intent used this component.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import re
import shlex
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_system_ui import component,PACKAGE_NAME,PRIMARY,RECEIVER

RESOLVE=('cmd','package','resolve-activity','--brief','--user','0','-a','android.intent.action.CHOOSER')


def resolved(raw):
    need(type(raw) is str and 0<len(raw.encode())<=4096)
    lines=raw.strip().splitlines();need(1<=len(lines)<=2)
    if len(lines)==2:
        # Android's brief resolver may retain its original match metadata.
        need(re.fullmatch(r'priority=-?[0-9]+ preferredOrder=-?[0-9]+ match=0x[0-9a-fA-F]+ specificIndex=-?[0-9]+ isDefault=(true|false)',lines[0]) is not None)
    value=lines[-1];need(value.count('/')==1)
    package,activity=value.split('/');actual=component(package,activity)
    need(package not in (PRIMARY,RECEIVER));return actual


def package_uid(raw,package):
    need(type(raw) is str and 0<len(raw.encode())<=16384 and PACKAGE_NAME.fullmatch(package))
    found=[]
    for line in raw.strip().splitlines():
        row=re.fullmatch(r'package:([A-Za-z][A-Za-z0-9_.]+) uid:([1-9][0-9]{0,9})',line);need(row is not None)
        if row[1]==package:found.append(int(row[2]))
    need(len(found)==1);return found[0]


def original(value):
    exact(value,{'snapshotChooserResolutionVersion','component','uid','requestedEpochMs','capturedEpochMs','resolutionSha256','uidSha256'})
    need(type(value['snapshotChooserResolutionVersion']) is int and value['snapshotChooserResolutionVersion']==1
        and type(value['component']) is str and resolved(value['component'])==value['component']
        and integer(value['uid'],1) and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<=1500
        and all(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]) for key in ('resolutionSha256','uidSha256')))
    return value


class SnapshotChooserResolution:
    def __init__(self,adb,selector,guard,clock_ms,*,monotonic=time.monotonic):
        need(type(selector) is str and bool(selector) and all(callable(fn) for fn in (guard,clock_ms,monotonic)))
        self.adb,self.selector,self.guard,self.clock_ms,self.monotonic=adb,selector,guard,clock_ms,monotonic
        self.last=None

    def _read(self,*args):
        need(self.guard() is not False)
        value=self.adb.execute(['shell',shlex.join(args)],target=self.selector,timeout=5)
        need(self.guard() is not False);return value

    def read(self):
        try:
            need(self.guard() is not False);start=self.monotonic();need(number(start,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            raw=self._read(*RESOLVE);actual=resolved(raw);package=actual.split('/')[0]
            uid_raw=self._read('cmd','package','list','packages','-U','--user','0',package);uid=package_uid(uid_raw,package)
            # Resolve again after package identity acquisition. No automatic
            # adoption of a changed chooser is permitted within this owner.
            again=self._read(*RESOLVE);need(resolved(again)==actual)
            captured=self.clock_ms();now=self.monotonic()
            need(integer(captured,requested) and captured-requested<=1500 and number(now,start,1e15) and now-start<=1.5)
            value=original(dict(snapshotChooserResolutionVersion=1,component=actual,uid=uid,requestedEpochMs=requested,
                capturedEpochMs=captured,resolutionSha256=hashlib.sha256(raw.encode()).hexdigest(),uidSha256=hashlib.sha256(uid_raw.encode()).hexdigest()))
            if self.last is not None:need(value['component']==self.last['component'] and value['uid']==self.last['uid'])
            need(self.guard() is not False);self.last=dict(value);return dict(value)
        except Exception:raise NativeUIError('Original Snapshot chooser OS resolution is unavailable or changed') from None


def join_grant(resolution,grant):
    """Original native Intent must independently resolve to the same OS owner."""
    original(resolution)
    need(type(grant) is dict and type(grant.get('chooserComponent')) is str and grant['chooserComponent'].count('/')==1)
    package,activity=grant['chooserComponent'].split('/')
    need(component(package,activity)==resolution['component'] and type(grant.get('chooserUid')) is int and grant['chooserUid']==resolution['uid'])
    return dict(resolution)
