"""Join original Snapshot VM calls to reviewed code and fresh native readers.

This proves source provenance only. Capture success still requires actual
normal input, native lifetime, original file/pixels and independent witnesses.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.emote_admission import catalog,KEYS,relative,same_pin
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_observation import validate as scripts_packet
from adapters.native_script_roots import validate as roots_packet,root_url
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_source import validate as snapshot_packet
from overte_phone_snapshot_script_history import validate as history_packet

PATH='system/snapshot.js'


def executable(script,root,*,pins_path=None):
    """Select the unique running, actually assigned Snapshot manager."""
    pins=catalog() if pins_path is None else catalog(pins_path)
    expected=next(row for row in pins['files'] if row['runtimePath']==PATH)
    source=script['source']
    need(source.get('sourceIdentityVersion')==1 and source.get('membershipSourceVersion')==1
        and source.get('compiledSourceVersion')==1 and source['membership']['complete'])
    members=source['membership']['managers'];candidates=[]
    for engine in source['engines']:
        matches=[row for row in members if row['instance']==engine['required']['instance']]
        need(len(matches)==1)
        manager=matches[0]
        if manager['url']!=root+PATH:continue
        need(manager['assigned'] and relative(engine['url'],root)==PATH
            and engine['running'] and not engine['stopping'] and not engine['finished']
            and engine['code']['submitted'] and manager['assignedEpochMs']<=engine['code']['submittedEpochMs']
            and engine['compiled']['complete'])
        same_pin(engine['code'],expected)
        originals=[row for row in engine['compiled']['compilations'] if row['resourceName'] in (manager['url'],engine['url'])
            and all(row[key]==engine['code'][key] for key in KEYS)
            and row['compiledEpochMs']>=engine['code']['submittedEpochMs']]
        need(len(originals)==1)
        candidates.append(dict(manager=deepcopy(manager),code=deepcopy(engine['code']),compilation=deepcopy(originals[0])))
    need(len(candidates)==1)
    # A second assigned but not yet represented manager is not an idle source.
    need([row['instance'] for row in members if row['assigned'] and row['url']==root+PATH]
        ==[candidates[0]['manager']['instance']])
    return candidates[0]


def callers(history,selected,epoch):
    """Every retained VM event keeps its actual manager/code/compilation."""
    history_packet(history,epoch)
    for event in history['events']:
        origin=event['caller']
        need(all(origin[key]==selected[key] for key in ('manager','code','compilation')))
    return deepcopy(history)


def validate(group,*,run,pid,epoch,pins_path=None):
    exact(group,{'rootsBefore','script','snapshot','rootsAfter'})
    before,script,snapshot,after=(group[key] for key in ('rootsBefore','script','snapshot','rootsAfter'))
    for packet in (before,after):
        roots_packet(packet,dict(schemaVersion=1,commandId=packet.get('commandId'),action='feature-script-roots-observe'),pid,epoch)
    roots_packet(after,dict(schemaVersion=1,commandId=after['commandId'],action='feature-script-roots-observe'),pid,epoch,previous=before)
    scripts_packet(script,script.get('requestId'),pid,epoch)
    snapshot_packet(snapshot,dict(schemaVersion=1,commandId=snapshot.get('requestId'),action='phone-snapshot-observe',runId=run),pid,epoch)
    need(before['instance']==script['instance']==snapshot['instance']==after['instance']
        and before['capturedEpochMs']<=script['requestedEpochMs']<=script['capturedEpochMs']
        <=snapshot['requestedEpochMs']<=snapshot['capturedEpochMs']<=after['requestedEpochMs']
        and after['capturedEpochMs']-before['requestedEpochMs']<=1500)
    fresh(before['requestedEpochMs'],epoch)
    selected=executable(script,root_url(before['source']['defaultScriptsUrl']),pins_path=pins_path)
    callers(snapshot['source']['scriptHistory'],selected,snapshot['capturedEpochMs'])
    return selected


class PhoneSnapshotMeasurements:
    """Acquire original sources in order without native input or source hints."""
    def __init__(self,roots,scripts,snapshot,guard,clock_ms,pid,*,monotonic=time.monotonic):
        need(all(callable(fn) for fn in (guard,clock_ms,monotonic)) and integer(pid,1)
            and roots.pid==scripts.pid==snapshot.pid==pid)
        self.roots,self.scripts,self.snapshot=roots,scripts,snapshot
        self.guard,self.clock_ms,self.pid,self.monotonic=guard,clock_ms,pid,monotonic

    def read(self,run):
        try:
            need(self.guard() is not False);start=self.monotonic();need(number(start,0,1e15))
            before=self.roots.read(0 if self.roots.last is None else self.roots.last['sequence'])
            script=self.scripts.read(self.scripts.sequence,require_code_identity=True,require_membership=True)
            snapshot=self.snapshot.read(run)
            after=self.roots.read(before['sequence'])
            need(self.guard() is not False);now=self.monotonic();need(number(now,start,1e15) and now-start<=1.5)
            group=dict(rootsBefore=before,script=script,snapshot=snapshot,rootsAfter=after)
            selected=validate(group,run=run,pid=self.pid,epoch=self.clock_ms())
            final=self.monotonic();need(self.guard() is not False and number(final,now,1e15) and final-start<=1.5)
            return deepcopy(group),selected
        except Exception:
            raise NativeUIError('Original Snapshot VM/source measurement is unavailable or inconsistent') from None
