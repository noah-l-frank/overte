"""Pico Graphics fixture/configuration binding over existing normal VR owners."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path

from adapters.graphics_journey.feature import GraphicsFeature
from adapters.graphics_journey.fixture import GraphicsFixtureReader
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from adapters.pico4.normal_scripts import configuration as normal_configuration
from feature_journeys.contract import identifier
from feature_journeys.graphics_fixture import PICO_PROFILE
from feature_journeys.stereo_graphics_evidence import SURFACE_PROFILE

VERSION=1
OPERATIONS=frozenset('feature.graphics.'+kind for kind in ('act','observe','cleanup'))


def artifact_directory(value):
    need(type(value) is str and bool(value));root=Path(value)
    PrivateFeatureState(root/'graphics-artifact-boundary.json')._parent();return root


def configured(environment):
    enabled=environment.get('OVERTE_PICO_FEATURE_GRAPHICS','0');need(enabled in ('0','1'))
    if enabled=='0':return False
    need(normal_configuration(environment) is not None and 'OVERTE_E2E_FEATURE_READER_TOKEN' not in environment)
    artifact_directory(environment.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
    from adapters.feature_fixture_access import client as access_client
    access_client(Path(environment.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG','')),
        configured_url=environment.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
    return True


class PicoGraphicsJourney(PicoGraphicsBinding):
    def __init__(self,adapter,*,artifact_root=None):
        super().__init__(adapter,fixture_profile=PICO_PROFILE)
        self.artifact_root=None if artifact_root is None else artifact_directory(str(artifact_root))

    def graphics_feature_store(self,target):return self._store(target,'graphics-feature.json')
    def graphics_retirement_store(self,target):return self._store(target,'graphics-retirement.json')

    def _graphics_cleanup_feature(self,target,run):
        # Existing owned journals admit internal cleanup even when public
        # feature advertisement was disabled after an interruption. The same
        # actual candidate/native checks and adapter-only read authority apply.
        identifier(run)
        owner=self.graphics_feature_store(target).read() or self.graphics_retirement_store(target).read()
        need(type(owner) is dict and owner.get('runId')==run)
        from adapters.feature_fixture_access import client as access_client
        client=access_client(Path(os.environ.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG','')),
            configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
        return self._graphics_feature(target,run,client=client)

    def _graphics_feature(self,target,run,*,role='primary',client=None):
        identifier(run);need(role in ('primary','actor'))
        if client is None:
            need(role=='primary' and configured(os.environ))
            from adapters.feature_fixture_access import client as access_client
            client=access_client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
        root=self.artifact_root
        if root is None:root=artifact_directory(os.environ.get('OVERTE_DEVICE_ARTIFACT_DIR',''))
        source=GraphicsFixtureReader(client,run);status=source.status()
        need(status['graphicsProviderVersion']==2 and status['profile']==PICO_PROFILE)
        return GraphicsFeature(self,target,source,root,SURFACE_PROFILE,role=role)
