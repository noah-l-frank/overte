"""Candidate-qualified iOS Authentication on the existing native input sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import Locator,NativeUI
from adapters.token_login_ui import TokenLoginUI
from adapters.native_account_probe import AccountProbeOwner
from adapters.private_login_input import PrivateLoginInput
from adapters.restart_inputs import RestartInputs
from feature_journeys.contract import arguments,identifier
from ios.adapters.account_preferences import require_owned,validate_basis,validate_intent,CONTROL_ID,control_metadata
from ios.adapters.account_menu import IOSAccountMenu
from ios.adapters.login_source import IOSLoginSource
from ios.adapters.normal_scripts import IOSScriptIO
from ios.adapters.private_login_transport import IOSPrivateLoginTransport
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.authentication_origin import origin as fixture_origin
from ios.adapters.authentication_actions import IOSAuthenticationActions
from ios.adapters.authentication_feature import IOSAuthenticationFeature,AuthenticationFixtureReader


class IOSLoginControls(TokenLoginUI):
    """Open the real tablet before using its ordinary Login entry.

    Original startup dialogs can already exist on the HUD and use their actual
    dismiss control. Opening the tablet is journalled before pointer delivery;
    neither a normal open nor a failed receipt is automatically replayed.
    """
    def __init__(self,*args,native_source,**kwargs):
        super().__init__(*args,**kwargs);self.native_source=native_source

    def open(self):
        raw=self.io.original.capture()
        if not any(row['id']=='login.page' for row in raw['controls']) and not raw['tabletShown']:
            packet=self.native_source.read(self.native_source.sequence,require_account=True)
            self.intent('account-menu-open-tablet',packet,'open-tablet')
            self.io.original.ui.click(Locator('accessibility id','OverteTabletOpen'))
            started=self.now()
            for _attempt in range(101):
                current=self.io.original.capture()
                if current['tabletShown']:break
                need(self.now()-started<10);self.sleep(.1)
            else:need(False)
        return super().open()


class IOSAuthenticationRuntime(IOSScriptRuntime):
    def __init__(self,adapter,client,run):
        super().__init__(adapter);identifier(run)
        self.client,self.run=client,run;self.origin=fixture_origin(client.url)

    def _sources(self,selector):
        target=self.adapter._target(selector)
        need(target.get('testBuild',{}).get('launchEnvironment',{}).get('HIFI_METAVERSE_URL')==self.origin)
        source=super()._sources(selector)
        raw=source['native'].capture()
        need(raw.get('loginClearInputVersion')==1)
        source['preferences']=require_owned(raw.get('accountPreferences'),self.origin,run=self.run)
        source['preferenceReceipt']=deepcopy(source['native'].last_receipt)
        return source

    def _preference_admission(self,selector,*,initial=False,baseline=None):
        s=self._sources(selector)
        return require_owned(s['preferences'],self.origin,run=self.run,initial=initial,baseline=baseline)

    def _preference_basis(self,selector):
        s=self._sources(selector)
        actual=require_owned(s['preferences'],self.origin,initial=True)
        return validate_basis(dict(binding=deepcopy(s['binding']),receipt=deepcopy(s['preferenceReceipt']),preferences=actual),self.origin)

    def _restore_account_preferences(self,selector,basis,intent):
        original=validate_basis(basis,self.origin)['preferences']
        current=self._preference_admission(selector)
        if current==original:return current
        controls=self._login_controls(selector,lambda stage,packet,control:intent('restore-'+stage,packet,control),self.run,self.origin)
        controls.open()
        s=self._sources(selector);io=controls.io.original;source=s['observer'].native_observer()
        def send(stage,identifier,deliver,*,expected_checked=None):
            raw=io.capture();receipt=deepcopy(io.native.last_receipt)
            packet=source.read(source.sequence,require_account=True)
            need(not packet['account']['loggedIn'] and not any(packet['account']['observation'][key]
                for key in ('tokenPresent','refreshPresent','loginPending','refreshPending')))
            proof=validate_intent(dict(native=packet,receipt=receipt),self.origin,self.run)
            rows=[row for row in raw['controls'] if row['id']==identifier and row['enabled']]
            need(len(rows)==1)
            if expected_checked is not None:
                control_metadata(rows[0]);need(rows[0]['checked'] is expected_checked)
            intent('account-preference-'+stage,proof,identifier)
            deliver(rows[0])
        send('focus-username','login.username',lambda row:io.ui.click_with_token(
            Locator('accessibility id','OverteNavigation.login.username'),row['token']))
        send('clear-username','login.username',lambda row:io.native.clear_login_username(token=row['token']))
        raw=io.capture();rows=[row for row in raw['controls'] if row['id']==CONTROL_ID];need(len(rows)==1);control_metadata(rows[0])
        if rows[0]['checked']:
            send('remember-off',CONTROL_ID,lambda row:io.ui.click_with_token(
                Locator('accessibility id','OverteNavigation.'+CONTROL_ID),row['token']),expected_checked=True)
        if original['rememberValue']:
            raw=io.capture();rows=[row for row in raw['controls'] if row['id']==CONTROL_ID];need(len(rows)==1)
            control_metadata(rows[0]);need(rows[0]['checked'] is False)
            send('remember-on',CONTROL_ID,lambda row:io.ui.click_with_token(
                Locator('accessibility id','OverteNavigation.'+CONTROL_ID),row['token']),expected_checked=False)
        self._preference_admission(selector,baseline=original)
        controls.cancel()
        return self._preference_admission(selector,baseline=original)

    def _native_feature_observer(self,selector,*,read_only=False):
        need(type(read_only) is bool)
        return self._sources(selector)['observer'].native_observer()

    def account_origin_store(self,selector):return self.adapter.account_origin_store(selector)
    def account_probe_store(self,selector,*,role='primary'):
        need(role in ('primary','actor'))
        if role=='primary':return self.adapter.account_probe_store(selector)
        return PrivateFeatureState(self.state_path(selector).with_name('account-actor-probe-owner.json'))
    def private_login_input_store(self,selector):return self.adapter.private_login_input_store(selector)

    def _account_origin(self,selector,*,read_only=False):
        need(type(read_only) is bool);s=self._sources(selector)
        return s['observer'].account_origin(self.account_origin_store(selector),s['binding'],component_only=False)

    def _account_probe(self,selector,*,role='primary',read_only=False):
        need(type(read_only) is bool);s=self._sources(selector)
        owner=AccountProbeOwner(self.account_probe_store(selector,role=role),s['binding'],s['check'],ios=True)
        return s['observer'].account_probe(owner)

    def _private_login_input(self,selector,run):
        need(run==self.run);s=self._sources(selector)
        return PrivateLoginInput(IOSPrivateLoginTransport(s['observer']),self.private_login_input_store(selector),
            s['binding'],run,component_only=False)

    def _login_controls(self,selector,intent,run,origin,*,read_only=False):
        need(run==self.run and origin==self.origin and type(read_only) is bool);s=self._sources(selector)
        original=IOSScriptIO(NativeUI(s['client'],s['session'],s['check']),s['native'])
        private=None if read_only else self._private_login_input(selector,run)
        io=IOSLoginSource(original,s['native_clock'],s['check'],int(s['binding']['processIdentity']),
            private_input=private,read_only=read_only,origin=origin,run=run)
        return IOSLoginControls(io,intent,run,origin,native_source=s['observer'].native_observer())

    def _account_menu(self,selector,intent,run,origin):
        need(run==self.run and origin==self.origin);s=self._sources(selector)
        io=IOSScriptIO(NativeUI(s['client'],s['session'],s['check']),s['native'])
        return IOSAccountMenu(io,s['observer'].native_observer(),intent,run,origin)

    def _account_tablet(self,selector):return self.normal_feature_runtime(selector,read_only=True)[0]

    def authentication_samples_store(self,selector,role,stage):
        need(role in ('primary','actor') and type(stage) is int and 0<=stage<=3)
        return PrivateFeatureState(self.state_path(selector).with_name('ios-authentication-'+role+'-'+str(stage)+'-samples.json'))
    def authentication_actions_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('ios-authentication-actions.json'))
    def authentication_feature_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('ios-authentication-feature.json'))
    def authentication_retirement_store(self,selector):return PrivateFeatureState(self.state_path(selector).with_name('ios-authentication-retirement.json'))
    def authentication_restart_store(self,selector,stage):
        need(type(stage) is int and 1<=stage<=3)
        return PrivateFeatureState(self.state_path(selector).with_name('ios-authentication-restart-'+str(stage)+'.json'))

    def _authentication_actions(self,selector,client,run):
        need(client is self.client and run==self.run)
        return IOSAuthenticationActions(self,selector,client,run)

    def _authentication_feature(self,selector,run,*,role='primary',client=None):
        need(run==self.run and role in ('primary','actor') and client in (None,self.client))
        return IOSAuthenticationFeature(self,selector,AuthenticationFixtureReader(self.client,run),role=role)

    def _restart_inputs(self,selector,stage):
        return RestartInputs(self.authentication_restart_store(selector,stage),[self.account_origin_store(selector),
            self.account_probe_store(selector),self.account_probe_store(selector,role='actor')])

    def _authentication_recover_launch(self,selector,inputs):
        need(isinstance(inputs,RestartInputs) and not inputs.component_only)
        owned=self.adapter._binding_store(selector).read()
        if owned is not None and owned['phase']=='preparing':
            need(inputs.read()['phase']=='launch-issued')
            self.adapter._recover_script_restart_launch(selector,inputs=inputs)

    def invoke(self,selector,operation,values):
        need(operation in ('app.stop','app.launch') and values=={})
        actions=IOSAuthenticationActions(self,selector,self.client,self.run);state=actions.load()
        need(state['phase']=='issued' and state['current']['arguments']['verb']=='restart-app')
        stage=state['stage']+1;inputs=self._restart_inputs(selector,stage);plan=inputs.read()
        need(plan['phase']==('stop-issued' if operation=='app.stop' else 'launch-issued')
             and plan['oldBinding']==state['current']['binding'])
        base=self.adapter;outer=base._operation;need(outer in (None,'feature.authentication.act'))
        base._operation=None
        try:return base.invoke(selector,operation,{})
        finally:base._operation=outer

    def _authentication_restart_stopped(self,selector,old_binding):
        state=IOSAuthenticationActions(self,selector,self.client,self.run).load()
        need(state['phase']=='issued' and state['current']['binding']==old_binding)
        inputs=self._restart_inputs(selector,state['stage']+1)
        need(inputs.read()['oldBinding']==old_binding)
        base=self.adapter;client,session_state,target=base._script_restart_session(selector,inputs=inputs)
        gate=base._binding(selector,client,session_state['sessionId'],session_state,target);record=gate.record()
        if record is not None and record['phase']=='retiring':gate.finish_retirement()
        gate.retired_absence();base.reset_launch_state(selector,session_state)
        return {'running':False,'identity':None}
