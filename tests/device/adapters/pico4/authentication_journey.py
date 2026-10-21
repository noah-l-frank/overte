"""Pico composition of shared Authentication through ordinary VR input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shlex
from types import SimpleNamespace

from adapters.android_process_query import AndroidProcessQuery
from adapters.authentication_journey.actions import AuthenticationActions
from adapters.authentication_journey.feature import AuthenticationFeature,AuthenticationFixtureReader
from adapters.authentication_journey.fixture import origin as fixture_origin,EXTRA
from adapters.authentication_journey.login_source import LoginObservationSource,FILE as LOGIN_FILE
from adapters.native_account_origin import NativeAccountOrigin,OwnedAccountOrigin,FILE as ORIGIN_FILE
from adapters.native_account_probe import NativeAccountProbe,AccountProbeOwner,OwnedAccountProbe,FILE as PROBE_FILE
from adapters.native_feature_observation import exact,fresh,need,validate as validate_native
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.normal_account_menu import PicoAccountMenu
from adapters.pico4.normal_login import PicoLoginIO
from adapters.pico4.tablet_home import bind_home,validate_input as validate_home_input
from adapters.pico4.normal_scripts import configuration as normal_configuration
from adapters.pico4.navigation import validate_snapshot
from adapters.pico4.script_journey import PicoScriptJourney
from adapters.token_login_ui import TokenLoginUI

VERSION=1
OPERATIONS=frozenset('feature.authentication.'+verb for verb in ('act','observe','cleanup'))
COMMAND_FILE='files/overte-e2e/login-ui-command.json'


def account_fixture(environment):
    enabled=environment.get('OVERTE_PICO_ACCOUNT_FIXTURE','0');need(enabled in ('0','1'))
    if enabled=='0':return None
    need(normal_configuration(environment) is not None)
    return fixture_origin(environment.get('OVERTE_E2E_FEATURE_FIXTURE_URL',''))


def configured(environment):
    enabled=environment.get('OVERTE_PICO_FEATURE_AUTHENTICATION','0');need(enabled in ('0','1'))
    if enabled=='0':return False
    need(account_fixture(environment) is not None and 'OVERTE_E2E_FEATURE_READER_TOKEN' not in environment)
    from adapters.feature_fixture_access import client
    client(Path(environment.get('OVERTE_PICO_FEATURE_FIXTURE_CONFIG','')),
        configured_url=environment.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
    return True


def launcher_arguments(environment):
    origin=account_fixture(environment)
    return () if origin is None else ('--es',EXTRA,shlex.quote(origin))


class PicoLoginSource(LoginObservationSource):
    def __init__(self,adapter,target,native):
        def send(envelope):
            exact(envelope,{'schemaVersion','commandId','action','request'})
            request=envelope['request'];exact(request,{'schemaVersion','commandId','action'})
            need(envelope['schemaVersion']==request['schemaVersion']==1 and envelope['action']==self.wire_action
                 and request['action']=='observe' and request['commandId']==envelope['commandId'])
            native.guard()
            adapter.adb.write_debug_app_file(target,'org.overte.pico',COMMAND_FILE,
                json.dumps(request,sort_keys=True,separators=(',',':'))+'\n')
            native.guard()
        super().__init__(send,lambda:adapter.adb.read_debug_app_file(target,'org.overte.pico',
            'files/overte-e2e/'+LOGIN_FILE,attempts=1),native.clock_ms,native.guard,native.pid,
            monotonic=native.monotonic,sleep=native.sleep)


class PicoLoginRecipe:
    def __init__(self,ui,intent,run,origin,passive,home):
        self.ui,self.intent=ui,intent
        self.passive=passive;self.home=home
        self.controls=TokenLoginUI(PicoLoginIO(ui.io,lambda:home.ensure(intent)),intent,run,origin)
        self.io=self.controls.io

    def open(self):
        value=self.ui.capture()
        if not value['open']:
            self.intent('login-tablet-open',value,'tablet.open');self.ui.open_tablet()
        # Reopening a retained pending page must not first destroy it or submit.
        value=self.ui.capture()
        if not any(row['id']=='login.page' for row in value['controls']):
            self.home.ensure(self.intent)
        return self.controls.open()

    def fill(self,credentials):
        # The process-only fixture origin must already supply the normal QML
        # server target. Do not rewrite an unrelated saved server preference.
        page=self.controls.row(self.controls.capture(),'login.page')
        need(page is not None and page['submitEndpointSha256'] in self.controls.endpoints)
        return self.controls.fill(credentials)

    def submit(self):return self.controls.submit()
    def cancel(self):
        value=self.ui.capture()
        if not value['open']:
            original=self.passive.capture()
            if not any(row['id']=='login.page' for row in original['controls']):return original
            self.intent('login-tablet-open',value,'tablet.open');self.ui.open_tablet()
        return self.controls.cancel()


class PicoAuthenticationJourney(PicoScriptJourney):
    state_area='authentication'

    def account_origin_store(self,target):return self._store(target,'account-origin-owner.json')
    def account_probe_store(self,target,*,role='primary'):
        need(role in ('primary','actor'))
        return self._store(target,'account-'+role+'-probe-owner.json')
    def authentication_actions_store(self,target):return self._store(target,'authentication-actions.json')
    def authentication_feature_store(self,target):return self._store(target,'authentication-feature.json')
    def authentication_retirement_store(self,target):return self._store(target,'authentication-retirement.json')
    def authentication_restart_store(self,target,stage):
        need(type(stage) is int and 1<=stage<=3)
        return self._store(target,'authentication-restart-'+str(stage)+'.json')
    def authentication_samples_store(self,target,role,stage):
        need(role in ('primary','actor') and type(stage) is int and 0<=stage<=3)
        return self._store(target,'authentication-'+role+'-'+str(stage)+'-samples.json')

    def _account_origin(self,target,*,read_only=False):
        need(type(read_only) is bool)
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        native=self._native_feature_observer(target,read_only=True);actual=native.read(0,require_account=True)
        source=NativeAccountOrigin(native.send,lambda:self.original.adb.read_debug_app_file(target,'org.overte.pico',
            'files/overte-e2e/'+ORIGIN_FILE,attempts=1),native.clock_ms,native.guard,native.pid,actual['instance'],
            monotonic=native.monotonic,sleep=native.sleep)
        result=OwnedAccountOrigin(source,self.account_origin_store(target),binding)
        result.native_admission=deepcopy(actual);guard();return result

    def _account_probe(self,target,*,read_only=False,role='primary'):
        need(type(read_only) is bool)
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        native=self._native_feature_observer(target,read_only=True)
        owner=AccountProbeOwner(self.account_probe_store(target,role=role),binding,native.guard)
        probe=NativeAccountProbe(native.send,lambda:self.original.adb.read_debug_app_file(target,'org.overte.pico',
            'files/overte-e2e/'+PROBE_FILE,attempts=1),native.clock_ms,native.guard,native.pid,intent=owner.intent,
            monotonic=native.monotonic,sleep=native.sleep)
        guard();return OwnedAccountProbe(probe,owner)

    def _script_file_io(self,target,*,read_only=False):
        need(type(read_only) is bool);return super()._script_file_io(target)

    def _login_controls(self,target,intent,run,origin,*,read_only=False):
        need(type(read_only) is bool)
        if read_only:return SimpleNamespace(io=PicoLoginSource(self.original,target,self._native_feature_observer(target,read_only=True)))
        ui,_observe,_binding,guard,_installed=self.normal_feature_runtime(target)
        passive=PicoLoginSource(self.original,target,self._native_feature_observer(target,read_only=True))
        guard();return PicoLoginRecipe(ui,intent,run,origin,passive,self._tablet_home(target))

    def _account_menu(self,target,intent,run,origin):
        ui,_observe,_binding,guard,_installed=self.normal_feature_runtime(target)
        native=self._native_feature_observer(target,read_only=True);guard()
        return PicoAccountMenu(ui,native,intent,run,origin,self._tablet_home(target))

    @staticmethod
    def _authentication_login_input_epoch(original):return original['updatedEpochMs']

    @staticmethod
    def _authentication_cleanup_input_key(stage,identifier):
        return 'tablet.home' if (stage=='login-close' and identifier=='login.page') or identifier=='tablet.home-ray' else identifier

    @staticmethod
    def _validate_authentication_login_input(original,pid,epoch):
        validate_snapshot(original,pid,epoch);fresh(original['updatedEpochMs'],epoch)
        need(original.get('loginControlsVersion')==2)

    @staticmethod
    def _validate_authentication_menu_input(original,native,control):
        exact(original,{'menuInputVersion','native','ui'})
        need(type(original['menuInputVersion']) is int and original['menuInputVersion']==1)
        before=original['native'];ui=original['ui']
        validate_native(before,before.get('requestId'),native['processId'],native['capturedEpochMs'],require_account=True)
        validate_snapshot(ui,native['processId'],native['capturedEpochMs']);fresh(ui['updatedEpochMs'],native['capturedEpochMs'])
        need(before['instance']==native['instance'] and before['sequence']<=native['sequence'])
        if control=='tablet.open':need(ui['open'] is False)
        else:
            rows=[row for row in ui['controls'] if row['id']==control]
            need(len(rows)==1 and rows[0]['enabled'])
            if control.startswith('account-menu.'):
                row=rows[0];account=native['account'];observed=account['observation']
                need(row['inputReady'] and row['accountInstance']==observed['instance']
                     and row['credentialGeneration']==observed['credentialGeneration']
                     and row['endpointSha256']==observed['endpointSha256'] and row['principalSha256']==account['principalSha256'])
            else:need(control in ('tablet.home','scripts.menu') or control.startswith('tablet.page.'))

    def _tablet_home(self,target):
        return bind_home(self.original,target,self._native_feature_observer(target,read_only=True))

    @staticmethod
    def _validate_authentication_home_input(original,native,control):
        validate_home_input(original,native['processId'],native['capturedEpochMs'],control)

    def _close_authentication_tablet(self,target,intent):
        ui,_observe,_binding,guard,_installed=self.normal_feature_runtime(target)
        value=ui.capture()
        if value['open']:
            self._tablet_home(target).ensure(intent)
            value=ui.capture()
            intent('tablet-close',value,'tablet.close');ui.close_tablet()
        ui.wait_tablet_absent();guard()

    def _authentication_actions(self,target,client,run):return AuthenticationActions(self,target,client,run)

    def _authentication_feature(self,target,run,*,role='primary',client=None):
        if client is None:
            need(role=='primary' and configured(os.environ))
            from adapters.feature_fixture_access import client as access_client
            client=access_client(Path(os.environ['OVERTE_PICO_FEATURE_FIXTURE_CONFIG']),
                configured_url=os.environ.get('OVERTE_E2E_FEATURE_FIXTURE_URL'))
        return AuthenticationFeature(self,target,AuthenticationFixtureReader(client,run),role=role)

    def _authentication_restart_stopped(self,target,old):
        def guard():
            need(hashlib.sha256((target+'\0'+str(self.original.pico_configuration)).encode()).hexdigest()==old['targetFingerprint'])
            installed=self.original._installation(target)
            need(all(installed[key]==old[key] for key in ('sourceRevision','artifactSha256')))
        packet=AndroidProcessQuery(self.original.adb,'org.overte.pico',guard).read(target,int(old['processIdentity'].split(':')[0]))
        return dict(running=bool(packet['processIds']),identity=old['processIdentity'] if packet['processIds'] else None)

    def _authentication_restart_source(self,target,inputs,actions):
        need(isinstance(actions,AuthenticationActions) and actions.adapter is self and actions.selector==target)
        def owner_check():
            state=actions.load();need(state is not None)
            stage=state['stage']+1
            feature=AuthenticationFeature(self,target,AuthenticationFixtureReader(actions.client,actions.run))
            control=feature.control()
            need(inputs.store.path==self.authentication_restart_store(target,stage).path
                 and state['phase']=='issued' and state['current']['arguments']['verb']=='restart-app'
                 and control is not None and control['phase']=='acting'
                 and control['arguments']==state['current']['arguments']
                 and inputs.read()['oldBinding']==state['current']['binding'])
            return dict(actions=self.authentication_actions_store(target).read(),
                feature=self.authentication_feature_store(target).read())
        owner_check()
        if inputs.read()['phase']=='launch-issued':
            self.original._script_restart_recover_binding(target,restart_inputs=inputs,owner_check=owner_check)
        _ui,_observe,binding,guard,_installed=self.normal_feature_runtime(target,read_only=True)
        return binding,self._native_feature_observer(target,read_only=True),guard

    def invoke(self,target,operation,values):
        need(operation in ('app.stop','app.launch') and values=={})
        return self.original.invoke(target,operation,values)
