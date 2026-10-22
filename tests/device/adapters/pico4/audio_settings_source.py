"""Original owner-bound audio settings and peak state; no acoustic verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import time
import uuid
from adapters.native_feature_observation import LIMIT,decode,exact,fresh,integer,need,number
from adapters.pico4.lifecycle_source import nonce

VERSION=2
READS=(1,2)
FILE='feature-audio-settings.json'
ACTION='feature-audio-settings-observe'
ROLES=('client','devices','input','nodes','script')
CLOCKS=('clientCapturedEpochMs','scriptCapturedEpochMs','inputCapturedEpochMs','nodesCapturedEpochMs')
BOOLEANS=('muted','mutedDesktop','mutedHMD','pushToTalkDesktop','pushToTalkHMD','noiseReduction',
    'noiseReductionAutomatic','warnWhenMuted','acousticEchoCancellation')
NUMBERS=('noiseReductionThreshold','inputVolume','localInjectorGain','systemInjectorGain','pushingToTalkOutputGainDesktop')


def validate(value,request,pid,epoch):
    exact(value,{'audioSettingsVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['audioSettingsVersion']) is int and value['audioSettingsVersion'] in READS
        and nonce(value['commandId']) and value['commandId']==request['commandId']
        and nonce(value['runId']) and value['runId']==request['runId'] and nonce(value['instance'])
        and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];fields={'complete','hmd','native','properties','mixerGains','inputPeakValuesEnabled',
        *CLOCKS,*(role+'Id' for role in ROLES)}
    if value['audioSettingsVersion']==2:fields.add('previewLifetime')
    exact(source,fields)
    need(source['complete'] is True and source['hmd'] is True and type(source['inputPeakValuesEnabled']) is bool
        and all(nonce(source[role+'Id']) for role in ROLES)
        and len({source[role+'Id'] for role in ROLES})==len(ROLES))
    previous=0
    for key in CLOCKS:
        stamp=source[key];need(integer(stamp,1,value['capturedEpochMs']) and stamp>=previous)
        fresh(stamp,epoch);previous=stamp
    properties=source['properties'];exact(properties,{*BOOLEANS,*NUMBERS,'context'})
    need(all(type(properties[key]) is bool for key in BOOLEANS)
        and all(number(properties[key],-1e6,1e6) for key in NUMBERS)
        and properties['context'] in ('VR','Desktop') and type(properties['context']) is str)
    native=source['native'];exact(native,{'recording','muted','localEcho','serverEcho','previewActive','previewCycle'})
    need(all(type(native[key]) is bool for key in ('recording','muted','localEcho','serverEcho','previewActive'))
        and integer(native['previewCycle']))
    if value['audioSettingsVersion']==2:
        from adapters.audio_preview_lifetime import validate as lifetime
        lifetime(source['previewLifetime'],source['clientCapturedEpochMs'],native['previewCycle'])
    exact(source['mixerGains'],{'avatarGain','injectorGain'})
    need(all(number(v,-1e6,1e6) for v in source['mixerGains'].values()))
    return value


def accept(previous,current):
    if previous is not None:
        need(all(current[key]==previous[key] for key in ('instance','processId','runId','audioSettingsVersion'))
            and current['sequence']>previous['sequence'] and current['capturedEpochMs']>=previous['capturedEpochMs']
            and current['commandId']!=previous['commandId']
            and all(current['source'][role+'Id']==previous['source'][role+'Id'] for role in ROLES)
            and all(current['source'][key]>=previous['source'][key] for key in CLOCKS)
            and current['source']['native']['previewCycle']>=previous['source']['native']['previewCycle'])
        if current['audioSettingsVersion']==2:
            from adapters.audio_preview_lifetime import accept as lifetime
            lifetime(previous['source']['previewLifetime'],current['source']['previewLifetime'])
    return deepcopy(current)


class PicoAudioSettings:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep,source_lock=None):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        from adapters.script_journey.lock import ScriptSourceLock
        need(source_lock is None or isinstance(source_lock,ScriptSourceLock))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.source_lock=monotonic,sleep,source_lock
        self.previous,self.last_raw,self.last_sha256=None,None,None
    def restore(self,value):
        validate(value,value,self.pid,value['capturedEpochMs']);need(self.guard() is not False)
        need(self.previous is None or self.previous==value);self.previous=deepcopy(value)
    def capture(self,run):
        if self.source_lock is not None:
            with self.source_lock.held():return self._capture(run)
        return self._capture(run)  # Explicit host/native boundary only.
    def _capture(self,run):
        need(nonce(run) and self.guard() is not False)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,runId=run)
        started=previous=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        self.send(request)
        for attempt in range(51):
            need(self.guard() is not False)
            raw=self.original();need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
            if type(value) is dict and value.get('commandId')==request['commandId']:
                epoch=self.clock_ms();validate(value,request,self.pid,epoch)
                need(all(value['source'][key]>=requested for key in CLOCKS))
                accepted=accept(self.previous,value);result=deepcopy(value);digest=hashlib.sha256(raw.encode()).hexdigest()
                # Include copy/hash/accept and final guard in both independent
                # clocks. No stale per-thread value borrows the envelope time.
                need(self.guard() is not False);final_epoch=self.clock_ms();fresh(value['capturedEpochMs'],final_epoch)
                completed=self.monotonic();earliest=min(value['source'][key] for key in CLOCKS)
                need(number(completed,0,1e15) and previous<=completed and completed-started<5
                    and max(final_epoch-earliest,requested-earliest+(completed-started)*1000)<=1500)
                self.previous,self.last_raw,self.last_sha256=accepted,raw,digest
                return result
            if attempt<50:self.sleep(.1)
        need(False)
