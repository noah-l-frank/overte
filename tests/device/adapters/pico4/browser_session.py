"""Runner-side Browser scope using the existing session and original CLI.

Comparison policy and Reader credentials remain in the actual shared Journey
process. Only private execution/Actor/consumption coordination crosses stdio.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import uuid
from urllib.parse import urlsplit

from adapter_operation_host import PinnedFile, pico_command
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact, need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_common_export import JourneyConsumptionExport
from adapters.pico4.browser_execution_budget import BrowserExecutionBudget
from adapters.pico4.browser_source import fixture

VERSION = 1
UNRESOLVED = []


class PicoBrowserSession:
    def __init__(self, session, artifacts, run, fixture_url, configuration, whole_budget):
        self.session = session; self.artifacts = Path(artifacts); self.run = run; self.url = fixture_url
        self.whole = self._whole = BrowserExecutionBudget(whole_budget)
        self.configuration = Path(configuration)
        self.context = self._context = None
        self.owner = self._owner = self.export = self._export = None
        self.fixture_close_started = False; self.finalize_started = False; self.result = None
        self.pin_complete=False;self.entered=False;self.failed=False
        self.nonce = uuid.uuid4().hex
        self.config_pin = self._config_pin = object.__new__(PinnedFile)
        self.scope = self._scope = (session, self.artifacts, run, fixture_url,
            self.configuration, self.whole, self.nonce)
        try:
            PinnedFile.__init__(self.config_pin,self.configuration,65536);self.pin_complete=True
            self.configure()
        except BaseException:
            self.close_local();raise

    def configure(self):
        self.config = PrivateFeatureState(self.configuration).read()
        exact(self.config, {'picoBrowserRunConfigVersion', 'foreignFixtureUrl', 'actorToken'})
        need(type(self.config['picoBrowserRunConfigVersion']) is int and self.config['picoBrowserRunConfigVersion'] == VERSION
            and type(self.config['actorToken']) is str and 32 <= len(self.config['actorToken']) <= 256
            and self.config['actorToken'].isascii() and all(33 <= ord(c) <= 126 for c in self.config['actorToken']))
        fixture(self.run, self.url)
        fixture(self.run, self.config['foreignFixtureUrl'] + '/runs/' + self.run + '/')
        a, b = urlsplit(self.url), urlsplit(self.config['foreignFixtureUrl'])
        need((a.scheme, a.netloc) != (b.scheme, b.netloc))
        self.config_sha = self._config_sha = json_digest(self.config)
        self.bound()

    def bound(self):
        try:
            need(not self.failed and self.scope is self._scope and self.config_pin is self._config_pin
                and self.whole is self._whole and self.context is self._context
                and self.owner is self._owner and self.export is self._export
                and self.session is self.scope[0] and self.whole is self.scope[5]
                and (self.artifacts, self.run, self.url, self.configuration, self.nonce)
                    == (self.scope[1], self.scope[2], self.scope[3], self.scope[4], self.scope[6])
                and self.config_sha is self._config_sha and json_digest(self.config) == self.config_sha)
            self.whole.check(); self.config_pin.check()
            if self.owner is not None: self.owner.guard()
        except BaseException:
            self.failed = True
            raise

    def call(self, operation, arguments=None):
        self.bound()
        result = self.owner.browser_component(self.run, self.url, operation, arguments, whole_budget=self.whole.value)
        self.bound(); return result

    def __enter__(self):
        self.bound()
        self.context = self._context = self.session.operation_host(self.artifacts)
        try:
            self.owner = self._owner = self.context.__enter__();self.entered=True
            self.call('begin', dict(artifactRoot=str(self.artifacts),
                foreignFixtureUrl=self.config['foreignFixtureUrl'], nonce=self.nonce))
            self.export = self._export = object.__new__(JourneyConsumptionExport)
            JourneyConsumptionExport.__init__(self.export, self.artifacts, 'tablet-web', self.run, self.url,
                self.nonce, lambda request:self.call('consume', request), self.bound)
            return self
        except BaseException:
            import sys
            try:
                if self.entered:self.context.__exit__(*sys.exc_info())
            finally:self.close_local()
            raise

    def start_actor(self):
        self.bound(); prefix = pico_command(self.owner.manifest)
        arguments = list(prefix[2:]); index = arguments.index('--kind')
        need(arguments[index+1] == 'pico'); del arguments[index:index+2]
        arguments.remove('--native-binding')
        return self.call('actor.start', dict(target=self.owner.target, candidateArguments=arguments,
            fixtureUrl=self.url.rsplit('/runs/', 1)[0], actorToken=self.config['actorToken'],
            durationSeconds=120, artifactRoot=str(self.artifacts)))

    def input_context(self,operation,arguments):
        self.bound()
        return self.owner.browser_input_context(self.run,self.url,operation,arguments,
            whole_budget=self.whole.value)

    def close_fixture(self, client):
        need(not self.fixture_close_started and client.run == self.run and client.url + '/runs/' + self.run + '/' == self.url)
        self.fixture_close_started = True
        client.close()  # Task-owned fixture cleanup remains one-shot after failure too.

    def finalize(self, client):
        self.bound(); need(not self.finalize_started and self.export.complete and not self.export.failed)
        self.finalize_started = True
        self.close_fixture(client); self.bound()
        self.call('actor.return')
        result = self.call('finalize')
        need(result['runId'] == self.run and result['sequenceCompleted'] is True and result['hostReleased'] is True
            and result['deviceAcceptance'] is False)
        self.result = deepcopy(result)
        need(self.export.close_host()); self.whole.check()
        return deepcopy(result)

    def __exit__(self, kind, value, traceback):
        attempted=False
        try:
            if kind is None: need(self.result is not None)
            attempted=True
            self.context.__exit__(kind, value, traceback)
            if kind is None: self.whole.check()
        except BaseException:
            import sys
            if not attempted:self.context.__exit__(*sys.exc_info())
            raise
        finally:
            complete=self.close_local()
            if kind is None:need(complete)
        return False

    def close_local(self):
        if (self.config_pin is not self._config_pin or self.export is not self._export):
            self.failed = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            return False
        results=[]
        if self.export is not None:
            try:results.append(self.export.close_host())
            except Exception:results.append(False)
        try:
            if self.pin_complete:results.append(self.config_pin.close())
            elif hasattr(self.config_pin,'owner'):results.append(self.config_pin.owner.close())
        except Exception:results.append(False)
        complete=all(results)
        if not complete and not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)
        return complete
