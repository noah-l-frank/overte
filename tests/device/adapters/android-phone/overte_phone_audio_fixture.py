"""Current original Audio phase and independently serialized HTTP input log."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
from adapters.native_feature_observation import fresh,need
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending,PhaseRetired
from feature_journeys.audio_resources import fixture_url,validate_status


class AudioFixtureReader(PhaseFixtureReader):
    def __init__(self,client,run,**kwargs):
        super().__init__(client,run,'audio',**kwargs);fixture_url(client.url)
        self.http_previous=None;self.http_instance=None

    def provider(self,previous=None):
        request=secrets.token_hex(16);value=self.client.request('/runs/'+self.run+'/audio',audio_nonce=request)
        instance=self.http_instance or (previous['instance'] if previous else value.get('instance'))
        validate_status(value,instance=instance,run=self.run,url=self.client.url,request=request,previous=self.http_previous)
        if previous is not None:validate_status(value,instance=instance,run=self.run,url=self.client.url,request=request,previous=previous)
        fresh(value['capturedEpochMs'],int(self.epoch_ms()));self.http_instance=instance;self.http_previous=deepcopy(value);return value

    def read(self,previous=None):
        first=super().read(previous);provider=self.provider();last=super().read()
        if first['ticket']!=last['ticket'] or provider['ticket']!=last['ticket'] or not provider['active']:
            raise PhasePending('Original Audio HTTP input/phase changed during acquisition')
        return dict(last,http=provider)
