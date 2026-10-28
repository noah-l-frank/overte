"""Original typed, twice-read Audio settings; no setter or global restoration."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from ios.adapters import audio_session_source as common
from ios.adapters.keyboard_source import clock,identifier
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-audio-settings';FILE=ACTION+'.json';LIMIT=32768
SCRIPT_BOOLS={'settingsLoaded','hmdContext','mutedDesktop','mutedHmd','pttDesktop','pttHmd','pushingToTalk',
    'noiseReduction','noiseReductionAutomatic','warnWhenMuted','acousticEchoCancellation'}
SCRIPT_NUMBERS={'inputVolume','noiseReductionThreshold','localInjectorGain','systemInjectorGain','pttOutputGainDesktop'}
PERSISTED_BOOLS={'mutedDesktop','mutedHmd','pttDesktop','pttHmd','noiseReduction','noiseReductionAutomatic','warnWhenMuted','acousticEchoCancellation'}
PERSISTED_NUMBERS={'avatarGain','serverInjectorGain','localInjectorGain','systemInjectorGain','noiseReductionThreshold'}
CLIENT_BOOLS={'muted','localEcho','serverEcho','stereoInput','recording','voiceActive'}
MIXER_NUMBERS={'avatarGain','serverInjectorGain'}
UNAVAILABLE={'wholeSettingsRestorationAvailable','independentAcousticsAvailable','processSdkRetirementAvailable'}


def command(value):
    common.command(dict(value,action=common.ACTION));need(value['action']==ACTION);return value


def typed(value,booleans,numbers):
    exact(value,set(booleans)|set(numbers));need(all(type(value[key]) is bool for key in booleans)
        and all(number(value[key],-1e9,1e9) for key in numbers));return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAudioSettingsVersion','requestId','runId','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','lifecycle','source'}|UNAVAILABLE)
    need(type(value['iosAudioSettingsVersion']) is int and value['iosAudioSettingsVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-audio-settings' and all(value[key] is False for key in UNAVAILABLE))
    identifier(value['instance']);clock(value['clockBefore']);clock(value['clockAfter'],floor=value['clockBefore'])
    a,b=value['clockBefore'],value['clockAfter'];need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500)
    if epoch is not None:
        from adapters.native_feature_observation import fresh
        fresh(b['epochMs'],epoch)
    exact(value['lifecycle'],{'backgrounds','activations','launches'})
    need(all(integer(v,0,1000000) for v in value['lifecycle'].values()) and value['lifecycle']['launches']>=1)
    source=value['source'];exact(source,{'iosAudioSettingsReadVersion','nativeHmd','scriptBefore','scriptAfter','clientBefore','clientAfter','mixerBefore','mixerAfter'})
    need(type(source['iosAudioSettingsReadVersion']) is int and source['iosAudioSettingsReadVersion']==1 and type(source['nativeHmd']) is bool)
    for suffix in ('Before','After'):
        script=source['script'+suffix];exact(script,SCRIPT_BOOLS|SCRIPT_NUMBERS|{'persisted'})
        typed({key:script[key] for key in SCRIPT_BOOLS|SCRIPT_NUMBERS},SCRIPT_BOOLS,SCRIPT_NUMBERS)
        typed(script['persisted'],PERSISTED_BOOLS,PERSISTED_NUMBERS)
        typed(source['client'+suffix],CLIENT_BOOLS,());typed(source['mixer'+suffix],(),MIXER_NUMBERS)
    need(all(same(source[key+'Before'],source[key+'After']) for key in ('script','client','mixer')))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and value['lifecycle']==previous['lifecycle']);clock(a,floor=previous['clockAfter'])
    return value


def original(value):return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def settings(value):
    original(value);source=value['source'];return dict(nativeHmd=source['nativeHmd'],script=deepcopy(source['scriptAfter']),
        client=deepcopy(source['clientAfter']),mixer=deepcopy(source['mixerAfter']))


def admissible(value):
    result=settings(value);script,client=result['script'],result['client'];key='mutedHmd' if result['nativeHmd'] else 'mutedDesktop'
    # iOS hides the normal PTT control. Refuse before mutation rather than
    # silently disabling PTT through Audio::setMuted(false) or a hidden setter.
    need(script['settingsLoaded'] and script['hmdContext']==result['nativeHmd'] and not script['pttDesktop'] and not script['pttHmd']
        and not script['pushingToTalk'] and not client['recording'] and not client['voiceActive'] and client['muted']==script[key])
    return result


def guards(value):
    result=admissible(value);key='mutedHmd' if result['nativeHmd'] else 'mutedDesktop'
    del result['script'][key];del result['client']['muted'];del result['client']['localEcho'];return result


def selected(value):
    result=admissible(value);return dict(muted=result['client']['muted'],localEcho=result['client']['localEcho'])


class IOSAudioSettings(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosAudioSettingsAcquisitionVersion'
