"""Validate one original Pico Audio bundle; admission and durable storage are caller-owned.

No source is retimed to the envelope. The caller must retain the original wire
and prebook native/parser/retained work in its existing Audio family before IO.
This module neither performs IO nor creates an admission or completion token.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import decode, exact, fresh, integer, need, validate as native_validate
from adapters.recorded_preview_history import accept_history, measured_state
from adapters.pico4 import audio_pages, audio_settings_source
from adapters.pico4.lifecycle_source import nonce
from adapters.pico4.navigation import identifier, validate_snapshot
from feature_journeys.contract import json_document

VERSION=1
LIMIT=1048576
FILE='feature-pico-audio-observation-bundle.json'
ACTION='feature-pico-audio-observation-bundle'
NATIVE_DECLARATION=4*1024*1024


def request(value):
    exact(value,{'schemaVersion','action','commandId','runId','nativeNonce','settingsNonce'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and all(nonce(value[key]) for key in ('commandId','runId','nativeNonce','settingsNonce'))
        and len({value[key] for key in ('commandId','nativeNonce','settingsNonce')})==3)
    return value


def validate(raw,command,pid,bridge,epoch):
    request(command)
    need(integer(pid,1) and identifier(bridge) and type(raw) is str and 0<len(raw.encode('utf-8'))<=LIMIT)
    value=json_document(raw)
    exact(value,{'picoAudioObservationBundleVersion','commandId','runId','processId','requestedEpochMs',
        'capturedEpochMs','status','nativeNonce','settingsNonce','nativeRaw','settingsRaw','pagesRaw',
        'originalPageKnownClosed','nativeAdmissionJoined'})
    need(type(value['picoAudioObservationBundleVersion']) is int and value['picoAudioObservationBundleVersion']==VERSION
        and all(value[key]==command[key] for key in ('commandId','runId','nativeNonce','settingsNonce'))
        and integer(value['processId'],1) and value['processId']==pid and value['status']=='ready'
        and value['originalPageKnownClosed'] is True and value['nativeAdmissionJoined'] is False)
    requested,captured=value['requestedEpochMs'],value['capturedEpochMs']
    need(integer(requested,1) and integer(captured,requested) and captured-requested<1500)
    fresh(requested,epoch);fresh(captured,epoch)
    native=decode(value['nativeRaw'])
    native_validate(native,command['nativeNonce'],pid,epoch,require_recorded_history=True)
    need(integer(native.get('requestedEpochMs'),requested,captured)
        and native['requestedEpochMs']<=native['capturedEpochMs']<=captured)
    settings=decode(value['settingsRaw'])
    audio_settings_source.validate(settings,dict(commandId=command['settingsNonce'],runId=command['runId']),pid,epoch)
    need(requested<=settings['capturedEpochMs']<=captured
        and all(requested<=settings['source'][key]<=captured for key in audio_settings_source.CLOCKS))
    need(type(value['pagesRaw']) is str and 0<len(value['pagesRaw'].encode('utf-8'))<=audio_pages.LIMIT)
    pages=decode(value['pagesRaw']);validate_snapshot(pages,pid,epoch)
    need(pages['bridgeId']==bridge and type(pages.get('picoAudioPageVersion')) is int
        and pages['picoAudioPageVersion']==audio_pages.VERSION)
    audio_pages.validate(pages['picoAudioPages'],epoch)
    need(pages['picoAudioPages']['capturedEpochMs']<=pages['updatedEpochMs']<=captured
        and (pages['open'] or not pages['picoAudioPages']['current']))
    need(settings['source']['native']['muted']==native['audio']['muted']
        and settings['source']['native']['previewCycle']==native['audio']['recordedVoice']['cycle'])
    actual=measured_state(native);actual['open']=bool(pages['picoAudioPages']['current'])
    return dict(envelope=value,native=native,settings=settings,pages=pages,actual=actual)


def accept(previous,current):
    """Check progress without mutating either retained original or issuing IO."""
    if previous is not None:
        old,new=previous['envelope'],current['envelope']
        need(all(old[key]==new[key] for key in ('runId','processId'))
            and new['commandId']!=old['commandId'] and new['requestedEpochMs']>=old['requestedEpochMs']
            and not {old['nativeNonce'],old['settingsNonce']} & {new['nativeNonce'],new['settingsNonce']})
        old,new=previous['native'],current['native']
        need(new['instance']==old['instance'] and new['sequence']>old['sequence']
            and new['capturedEpochMs']>=old['capturedEpochMs']
            and all(new['lifecycle'][key]>=old['lifecycle'][key] for key in old['lifecycle']))
        old_event=old['audio']['recordedVoice']['event'];new_event=new['audio']['recordedVoice']['event']
        need(new_event.get('eventSequence',0)>=old_event.get('eventSequence',0))
        accept_history(old['audio']['recordedVoice'],new['audio']['recordedVoice'])
        for part in ('account','animation'):
            old_part,new_part=old[part],new[part]
            history='observation' if part=='account' else 'history'
            if history in old_part or history in new_part:
                need(history in old_part and history in new_part)
                if part=='account':
                    from adapters.native_account_observation import accept as accept_account
                    accept_account(old_part['observation'],new_part)
                else:
                    from adapters.native_animation_history import accept as accept_animation
                    accept_animation(accept_animation(None,old_part['rigId'],old_part['history']),new_part['rigId'],new_part['history'])
        audio_settings_source.accept(previous['settings'],current['settings'])
        need(current['pages']['bridgeId']==previous['pages']['bridgeId']
            and current['pages']['generation']==previous['pages']['generation']
            and current['pages']['elapsedMs']>=previous['pages']['elapsedMs'])
        audio_pages.accept(previous['pages']['picoAudioPages'],current['pages']['picoAudioPages'])
    return current
