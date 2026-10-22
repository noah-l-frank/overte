"""Complete Phone tablet-browser journey on normal fixture-app controls.

The common browser owner supplies phase/candidate binding, original acquisition,
independent actors, original PNG ownership and verified durable retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from overte_phone_world_web_feature import PhoneWorldWebFeature


class PhoneTabletWebFeature(PhoneWorldWebFeature):
    area='tablet-web'
    surface='tablet'
    action='phone-tablet-web'
    version_field='tabletWebFeatureVersion'

    def source_control(self,owner,operation):
        return self.io(owner,read_only=False).request(self.run,self.fixture_url,owner['ownerToken'],operation)

    def deliver(self,owner,call):
        verb=call['verb']
        if verb=='open':
            super().deliver(owner,call)
            self.adapter._tablet_web_entry(self.selector,'WEB TEST',initial=True)
        elif verb in ('open-inline-app','return-from-inline'):
            need(bool(self.sample_native(owner)['source']['current']))
            self.adapter._tablet_web_entry(self.selector,'INLINE TEST' if verb=='open-inline-app' else 'WEB TEST',initial=False)
        elif verb=='hold-inline-message':
            self.source_control(owner,'arm-held');self.input(owner,'bridge')
        elif verb=='deliver-retired-inline-message':self.source_control(owner,'deliver-held')
        else:super().deliver(owner,call)

    def close_source(self,owner):
        if owner['scriptUrl'] is not None:self.adapter._tablet_web_close(self.selector)
        super().close_source(owner)
        # Stop/Home must retire the original carrier before a held callback may
        # traverse its unchanged document/grant gate. This also resolves a lost
        # pointer return without repeating the original input.
        source=self.sample_native(owner)['source']['deferred']
        if source['armed']:self.source_control(owner,'cancel-held')
        if source['pending']:self.source_control(owner,'deliver-held')

    def check_released(self,runtime):
        super().check_released(runtime)
        handles={row['handle'] for row in runtime['source']['nativeAfter']['knownHandles']}
        need(not any(row['handle'] in handles for key in ('nativeBefore','nativeAfter') for row in runtime['source'][key]['views'])
            and not any(row['handle'] in handles for row in runtime['source']['java']['views'])
            and not any(row['handle'] in handles for row in runtime['source']['java']['creations']))
        return runtime['source']
