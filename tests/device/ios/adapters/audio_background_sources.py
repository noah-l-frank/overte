"""Original foreground Audio cuts for an owned OS interruption child."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_clock_source_history import restore
from adapters.native_feature_observation import exact,need,validate as native_packet
from adapters.normal_feature_state import context
from adapters.token_audio_ui import TokenAudioUI
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters.graphics_history import follow_native
from ios.adapters.normal_input import observation as ui_packet
from ios.adapters.normal_audio import IOSAudioIO
from adapters.normal_ui import NativeUI
from types import SimpleNamespace


def validate(value,binding,run,ticket):
    exact(value,{'iosAudioBackgroundObservationVersion','binding','runId','ticket',
        'phaseBefore','phaseAfter','originals','clockJoin'})
    need(type(value['iosAudioBackgroundObservationVersion']) is int and value['iosAudioBackgroundObservationVersion']==1
        and same(context(value['binding']),context(binding)) and value['runId']==identifier(run) and value['ticket']==identifier(ticket))
    for current,previous in ((value['phaseBefore'],None),(value['phaseAfter'],value['phaseBefore'])):
        phase_packet(current,run=run,area='audio',request=current['requestId'],epoch=current['capturedEpochMs'],previous=previous)
        need(current['active'] and current['activations'] and current['activations'][-1]['ticket']==ticket
            and current['activations'][-1]['stimulus']==dict(verb='background-resume',inputs={}))
    need(same(value['phaseBefore']['activations'],value['phaseAfter']['activations']))
    raw=value['originals'];exact(raw,{'native','ui'});join=validate_join(value['clockJoin'],raw)
    first,current,last=join['nativeBefore'],raw['native'],join['nativeAfter']
    native_packet(current,current['requestId'],int(binding['processIdentity']),last['capturedEpochMs'],require_recorded_history=True)
    follow_native(first,current);follow_native(current,last)
    need(str(first['processId'])==binding['processIdentity'] and same(first['lifecycle'],last['lifecycle']))
    ui=ui_packet(raw['ui'],int(binding['processIdentity']),last['capturedEpochMs'])
    class Frozen:
        def capture(self):return deepcopy(ui)
    controls=TokenAudioUI(Frozen(),lambda *_args:need(False)).capture()
    page=TokenAudioUI.row(controls,'audio.page');record=TokenAudioUI.row(controls,'audio.record')
    voice=current['audio']['recordedVoice']
    need(page is not None and record is not None and page['cycle']==record['cycle']==voice['cycle']
        and record['phase']==voice['event']['phase'] and record['nativeActive']==record['uiActive']==voice['active'])
    return value


class AudioBackgroundSources:
    def __init__(self,source,run,client,intent,previous,*,epoch_ms,monotonic):
        self.source,self.run=source,identifier(run);self.binding=deepcopy(context(source['binding']))
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.phase=PhaseFixtureReader(client,run,'audio',epoch_ms=epoch_ms,monotonic=monotonic)
        self.native=source['clock_source'];restore(self.native,previous)
        send=self.native.send
        def observed(command):intent(command);return send(command)
        self.native.send=observed;source['native'].observe_intent=intent
        self.io=IOSAudioIO(SimpleNamespace(capture=source['native'].capture,native=source['native'],
            ui=NativeUI(source['client'],source['session'],source['check'])))

    def sample(self,ticket):
        self.source['check']();status=self.phase.read()
        need(status['ticket']==ticket and status['verb']=='background-resume' and status['inputs']=={})
        clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        clock.begin(self.epoch_ms());native=self.native.read(self.native.sequence,require_recorded_history=True)
        ui=self.io.capture();raw=dict(native=native,ui=ui)
        joined=clock.finish(raw,[('native','capturedEpochMs'),('ui','sampleEpochMs')])
        after=self.phase.status(status['status']);self.source['check']()
        return dict(iosAudioBackgroundObservationVersion=1,binding=self.binding,runId=self.run,ticket=ticket,
            phaseBefore=status['status'],phaseAfter=after,originals=raw,clockJoin=joined)
