"""Cold authenticated Audio fixture reusing the current normal recipe owners.

Native, OS and media primitives are declared models; HTTP and kernel/file
originals are actual. The separate clock changes only on a modeled Launch.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from copy import deepcopy
import tempfile,uuid,hashlib
from self_tests.test_pico_audio_recipe import AudioRecipeFixture as BaseFixture
from self_tests.test_pico_audio_page_owner import Boundary
from self_tests.test_audio_preview import BINDING as BASE_CANONICAL_BINDING
from self_tests.test_pico_audio_pages import BRIDGE as CANONICAL_BRIDGE
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Journal,Client
TARGET='explicit-audio-boundary'
def canonical_binding(root):
    return dict(BASE_CANONICAL_BINDING,sessionId=CANONICAL_BRIDGE,
        targetFingerprint=hashlib.sha256((TARGET+'\x00'+str(('declared-pico-audio-layer',root))).encode()).hexdigest())

"""Cold declared fixture clock, switched ONLY by an actual model Launch effect.

Old Native/phase records retain their original times. No received packet, query
anchor, deadline or product fact is rewritten; this is not an Android clock.
"""
import time,math
class ProcessPhaseClock:
    def __init__(self,native):
        self.native=native;self.started=None;self.epoch_base=self.mono_base=None;self.starts=0
    def launched(self):
        if self.started is not None:raise ValueError('Modeled process clock cannot be launched twice')
        self.epoch_base=self.native.epoch();self.mono_base=self.native.clock
        self.started=time.monotonic();self.starts+=1
    def monotonic(self):
        return self.native.clock if self.started is None else self.mono_base+time.monotonic()-self.started
    def epoch(self):
        return self.native.epoch() if self.started is None else self.epoch_base+round((time.monotonic()-self.started)*1000)


class AuthenticatedAudioRecipeFixture(BaseFixture):
    process_phase_clock=True
    authenticated_loopback=True

    def setUp(self):
            self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.path=Path(self.temp.name)
            self.native=Boundary(self.path,lifetime=True,binding=canonical_binding(self.path))
            self.native.phase_clock=ProcessPhaseClock(self.native) if self.process_phase_clock else None
            phase_epoch=self.native.epoch if self.native.phase_clock is None else self.native.phase_clock.epoch
            phase_mono=(lambda:self.native.clock) if self.native.phase_clock is None else self.native.phase_clock.monotonic
            self.journal=Journal(clock=phase_epoch)
            self.run=self.native.preview.run;generated=self.journal.register('audio');self.journal.runs[self.run]=self.journal.runs.pop(generated)
            test=self
            class PhaseClient(Client):
                def request(self,path,*args,phase_nonce=None,**kwargs):return test.journal.phase(test.run,phase_nonce)
            self.fixture_server=self.fixture_thread=None;self.fixture_closed=False
            client_type=PhaseClient;fixture_url='http://127.0.0.1:9876/feature-fixture/v1'
            if self.authenticated_loopback:
                from feature_journeys.server import make_server
                import threading
                # Both clients/real listener are selected before any PhaseReader,
                # Recipe or Actor exists. No previously emitted packet is changed.
                self.fixture_server=make_server('a'*64,'b'*64)
                self.fixture_server.journal=self.journal
                self.addCleanup(self.close_loopback)
                self.fixture_thread=threading.Thread(target=self.fixture_server.serve_forever,
                    kwargs=dict(poll_interval=.01),name='owned-audio-fixture')
                self.fixture_thread.start()
                fixture_url='http://127.0.0.1:'+str(self.fixture_server.server_address[1])+'/feature-fixture/v1'
                client_type=Client
            self.source=PhaseFixtureReader(client_type(fixture_url,'a'*64),self.run,'audio',
                monotonic=phase_mono,epoch_ms=phase_epoch)
            self.activate('baseline');self.parents=[];self.foreground=True;self.os_inputs=[];self.os_fault=''
            self.counts=deepcopy(self.native.native_reader.lifecycle);original=self.native.native.mutate
            def metadata(packet):
                original(packet)
                if self.counts is None:self.counts=deepcopy(packet['lifecycle'])
                packet['lifecycle']=deepcopy(self.counts)
            self.native.native.mutate=metadata
            original_stage=self.native.transport.stage
            def stage(envelope,profile,*,before_publish=None):
                if before_publish is not None:before_publish(deepcopy(envelope))
                return original_stage(envelope,profile)
            self.native.transport.stage=stage
            self.owner=self.recipe()

    def close_loopback(self):
            if self.fixture_server is not None:
                if self.fixture_thread is not None and self.fixture_thread.is_alive():self.fixture_server.shutdown()
                self.fixture_server.server_close()
            if self.fixture_thread is not None:
                self.fixture_thread.join(timeout=2)
                self.assertFalse(self.fixture_thread.is_alive())
            self.fixture_closed=True
