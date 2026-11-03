"""The original Create CLI with existing volume and permission source actors.

Owned loopback Settings endpoints are test producers, never a live Domain.
Normal permission writes occur only through the real outer fixture runner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.request import ProxyHandler,build_opener
from unittest.mock import patch

sys.path[:0]=[str(Path(__file__).resolve().parents[5]/'tests/device'),str(Path(__file__).resolve().parent)]
import create_operation_voxel_cli_host as volume
import test_create_recovery_owner as recovery
import test_create_journey as original
from test_create_models import ModelBackend
from adapters.feature_fixture_access import AdapterFixtureClient
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.phase_fixture import PhaseFixtureReader


class SettingsView:
    def __init__(self,url,publish):self.url=url;self.publish=publish;self.opener=build_opener(ProxyHandler({}))
    @property
    def security(self):
        self.publish()
        with self.opener.open(self.url+'/settings.json',timeout=2) as response:
            raw=response.read(1048577)
            assert response.status==200 and len(raw)<=1048576
        return json.loads(raw)['values']['security']


class FullFixture(volume.VoxelFixture):
    def _before_prepare(self):
        super()._before_prepare()
        self.configuration=PrivateFeatureState(volume.host.area/'permission-model.json').read()
        self.clock_store=PrivateFeatureState(volume.host.area/'permission-source-clock.json')
        self.clock_previous=self.clock_store.read()
        def publish():
            value=dict(epochMs=self.b.epoch())
            self.clock_store.write(value,self.clock_previous);self.clock_previous=value
        self.publish_clock=publish
        self.actor=SimpleNamespace(server=SettingsView(self.configuration['settingsUrl'],publish))
        recovery.CreateRecoveryTests._before_prepare(self)
        reader=ModelBackend.reader
        def native(b,kind):
            observer=reader(b,kind);send=observer.send
            def deliver(command):
                send(command)
                if kind=='entities':
                    # Independent actual Settings GET; no provider ACK or
                    # requested boolean is copied into a source observation.
                    actual=self.actor.server.security['standard_permissions']
                    baseline=self.configuration['originalStandard']
                    rights=(True,False) if actual==baseline else (actual[0]['id_can_rez'],actual[0]['id_can_rez_tmp'])
                    packet=json.loads(b.frames[kind]);packet['source']['canRez'],packet['source']['canRezTmp']=rights
                    b.frames[kind]=json.dumps(packet,indent=2)+'\n'
            observer.send=deliver;return observer
        boundary=patch.object(ModelBackend,'reader',native);boundary.start();self.addCleanup(boundary.stop)

    def setUp(self):
        super().setUp()
        local=original.PhaseClient(self.journal)
        endpoint=AdapterFixtureClient(self.configuration['fixtureUrl'],'a'*64)
        class Source(original.PhaseClient):
            def request(_source,path,value=None,method=None,**options):
                if path.endswith('/create-permissions'):
                    self.publish_clock();return endpoint.request(path,value,method,**options)
                return local.request(path,value,method,**options)
        self.source=lambda:PhaseFixtureReader(Source(self.journal),original.RUN,'create',
            epoch_ms=self.b.epoch,monotonic=self.b.now)


if __name__=='__main__':
    volume.host.make_fixture=FullFixture
    volume.host.android.cli=lambda argv=None:(volume.host.args,volume.Binding)
    try:raise SystemExit(volume.host.android.main([]))
    except Exception as error:
        import traceback
        seen=set()
        while error is not None and id(error) not in seen:
            seen.add(id(error));traceback.print_exception(error,chain=False)
            error=error.__context__
        raise SystemExit(2)
