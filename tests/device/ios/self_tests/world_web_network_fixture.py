"""Actual authenticated localhost fixture with the ordinary host SDK model.

Only fixture authority/HTTP is real. Qt, WebKit, OS and GPU remain explicit
models; their originals are first produced after the real run is registered.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import threading
import uuid
from unittest.mock import patch

from feature_journeys.server import make_server
from feature_journeys.witness import Client
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class NetworkWorldWeb:
    def __init__(self,*,wall_clock=False,use_whole_snapshot=False):
        self.whole=None;self.server=make_server('r'*64,'a'*64,adapter_token='d'*64)
        self.thread=threading.Thread(target=self.server.serve_forever,kwargs={'poll_interval':.01},daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)+'/feature-fixture/v1'
        self.server.journal.clock=lambda:89000
        self.controller=Client(self.url,'r'*64);self.run,self.fixture_url=self.controller.register('world-web')
        self.ticket=uuid.uuid4().hex;self.controller.activate(self.ticket)
        self.adapter=Client(self.url,'d'*64);self.actor=Client(self.url,'a'*64)
        # The legacy host Domain producer has a closed test-run admission
        # constant. Configure it before producing any World/Scope original;
        # never relabel an earlier packet or amend a retained Source frame.
        from ios.self_tests import test_ios_emote_marker_owner as domain_fixture
        self.domain_run=patch.object(domain_fixture,'RUN',self.run);self.domain_run.start()
        def configure(whole):
            sdk=whole.sdk;sdk.controller=self.controller;sdk.phase_client=self.adapter
            whole.domain.world_template['runId']=self.run
            self.server.journal.clock=sdk.host_epoch
            self.server.browser_resources.clock_ms=sdk.tick;sdk.browser=self.server.browser_resources
        try:self.whole=ComposedWorldWeb(wall_clock=wall_clock,use_whole_snapshot=use_whole_snapshot,run=self.run,fixture_url=self.fixture_url,ticket=self.ticket,configure=configure)
        except BaseException:self.close();raise

    def close(self):
        if self.whole is not None:self.whole.close();self.whole=None
        if hasattr(self,'domain_run'):self.domain_run.stop()
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        assert not self.thread.is_alive()
