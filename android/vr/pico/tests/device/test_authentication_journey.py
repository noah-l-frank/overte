"""Full Pico Authentication at explicit synthetic Qt/native/OS/HTTPS seams.

The common Journey, wrapper, owners, source validators, private original files
and fixture journal execute. Native client, SDK, HTTPS provider, process and
OpenXR behavior are simulated. No build, device or remote request is performed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from inspect import getclosurevars
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid

import test_normal_scripts as components
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.android import adapter as android
from adapters.authentication_journey.feature import AuthenticationFeature,AuthenticationFixtureReader,AuthenticationPhasePending
from adapters.authentication_journey.login_source import FILE as LOGIN_FILE
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.native_process_presence import NativeProcessPresence
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import authentication_journey as pico
from adapters.pico4 import normal_scripts,tablet_home
from adapters.script_journey.history import unpack
from adapters.token_login_ui import TokenLoginUI
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.engine import Journey
from feature_journeys.scenarios import VERSION
from feature_journeys.witness import Client,Journal
from self_tests.test_authentication_journey_samples import Sources,RUN,ORIGIN,PROVIDER
from self_tests.test_native_account_observation import account,event,append
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_process_presence import Boundary as Presence
from self_tests.test_script_ui_inventory import inventory
from self_tests.test_token_login_ui import Boundary as LoginWidgets
from self_tests.test_login_ui_inventory import loads,component

URL=ORIGIN+'/feature-fixture/v1'


class AuthenticationBoundary:
    def setUp(self):
        self.f=components.PicoNormalScriptsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.original,self.native=self.f.instance,self.f.native;self.target=self.native.target
        self.clock=0.;self.stage=0;self.lifecycle=dict(launches=1,activations=1,backgrounds=0)
        self.birth='a'*32;self.binding=self.native.identity;self.sequence=0;self.menu=None
        self.fault='';self.raw_command='{}\n';self.started_dialog=False;self.inputs=[];self.os_inputs=[]
        self.s=Sources(self.f.fixture.state_root)
        self.login=LoginWidgets(generic=True);self.native.opened=False
        self.s.epoch_ms=self.epoch;self.s.provider_epoch_ms=self.epoch
        self.remote_tokens=self.remote_refresh=0;self.grants_enabled=self.account_exists=True
        self.provider_rows=[];self.ticket=None;self.provider_calls=[];self.control_count=0
        self.passive_login=None;self.login_sequence=0;self.source_nonces=set()
        self.home_packet=None;self.home_sequence=0;self.qml_components=[];self.keyboard_raised=False
        self.login_root=self.menu_root=None;self.retired_roots=set();self.retained_roots=[]
        self.facade=pico.PicoAuthenticationJourney(self.original)
        self.journal=Journal(self.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('authentication')
        self.journal.activate(RUN,'b'*32)
        self.primary_client=Client(URL,'x'*64);self.primary_client.run=RUN;self.primary_client.area='authentication'
        self.primary_client.request=lambda *args,**kwargs:self.request('primary',*args,**kwargs)
        self.primary_client.monotonic=lambda:self.clock;self.primary_client.sleep=self.sleep
        self.actor_client=Client(URL,'y'*64);self.actor_client.request=lambda *args,**kwargs:self.request('actor',*args,**kwargs)
        self.primary=AuthenticationFeature(self.facade,self.target,AuthenticationFixtureReader(self.primary_client,RUN,epoch_ms=self.epoch),
            monotonic=lambda:self.clock,sleep=self.sleep)
        self.actor=AuthenticationFeature(self.facade,self.target,AuthenticationFixtureReader(self.actor_client,RUN,epoch_ms=self.epoch),
            role='actor',monotonic=lambda:self.clock,sleep=self.sleep)
        config=self.f.fixture.state_root/'authentication-access.json'
        PrivateFeatureState(config).write(dict(fixtureAdapterAccessVersion=1,fixtureUrl=URL,adapterToken='d'*64),None)
        original_read=self.native.read_debug_app_file;original_write=self.native.write_debug_app_file
        original_snapshot=self.f.original_snapshot;original_shell=self.native.shell;real_run=subprocess.run
        verified=self.original._candidate()
        def snapshot():
            value=original_snapshot();widgets=self.widgets()
            value.update(processId=self.pid(),updatedEpochMs=self.epoch(),loginControlsVersion=2,
                accountMenuControlsVersion=1,controls=widgets,open=self.native.opened,ready=self.native.opened,
                featureControlsVersion=1)
            return value
        self.snapshot=snapshot
        def read(target,package,path,**kwargs):
            if path==android.ANDROID_CONTROL_MARKER:return json.dumps(android.ANDROID_CONTROL_CONTRACT|dict(processId=self.pid()))
            if path=='files/overte-e2e/feature-native-observation.json':return self.s.native.original()
            if path=='files/overte-e2e/feature-account-origin-result.json':return self.s.origin.read()
            if path=='files/overte-e2e/feature-account-probe.json':return self.s.probe.read()
            if path=='files/overte-e2e/'+LOGIN_FILE:return json.dumps(self.passive_login)
            if path=='files/overte-e2e/'+tablet_home.FILE:return json.dumps(self.home_packet)
            if path=='files/overte-e2e/script-file-ui.json':return json.dumps(self.s.tablet.value)
            if path=='files/overte-e2e/navigation-ui-command.json':return self.raw_command
            if path=='files/overte-e2e/feature-process-presence.json':return self.presence.original()
            return original_read(target,package,path,**kwargs)
        def write(target,package,path,raw):
            command=json.loads(raw);action=command.get('action')
            if action=='feature-native-observe':return self.s.native.send(command)
            if action=='feature-account-origin':return self.s.origin.send(command)
            if action=='feature-account-probe':return self.s.probe.send(command)
            if action=='feature-process-presence':return self.presence.send(command)
            if path==tablet_home.COMMAND:
                self.assertEqual({'schemaVersion','commandId','action'},set(command));self.assertEqual('observe',action)
                self.assertNotIn(command['commandId'],self.source_nonces);self.source_nonces.add(command['commandId'])
                self.home_sequence+=1
                self.home_packet=dict(schemaVersion=1,commandId=command['commandId'],action='observe',
                    instance=self.birth,generation=self.birth,sourceSequence=self.home_sequence,lastCommandSequence=0,
                    elapsedMs=round(self.clock*1000),capturedEpochMs=self.epoch(),processId=self.pid(),homeObservationVersion=1,
                    tabletShown=self.native.opened,onHomeScreen=not self.menu and not self.login.dialog,
                    tabletId='1'*32,homeId='2'*32,parentId='1'*32,entityType='Gizmo',entityName='homeButton',
                    visible=self.native.opened,ignorePickIntersection=False,hostType='local',
                    sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],headPosition=[0,1.6,0],position=[.2,1.1,-.6])
                return
            if path==pico.COMMAND_FILE:
                self.assertEqual({'schemaVersion','commandId','action'},set(command));self.assertEqual('observe',action)
                if command['commandId'] in self.source_nonces:return
                self.source_nonces.add(command['commandId']);self.login_sequence+=1
                value=self.login.capture()
                self.passive_login=dict(value,schemaVersion=1,commandId=command['commandId'],action='observe',
                    sourceSequence=self.login_sequence,lastCommandSequence=0,elapsedMs=round(self.clock*1000),
                    capturedEpochMs=self.epoch(),processId=self.pid(),loginObservationVersion=1,
                    startupDialogPresent=self.started_dialog,loginInventory=self.login_inventory())
                if not self.native.opened or self.menu:self.passive_login['controls']=[]
                return
            if path=='files/overte-e2e/script-file-ui-command.json':
                return self.s.tablet.send(dict(schemaVersion=1,commandId=command['commandId'],action='script-file-ui',request=command))
            if path=='files/overte-e2e/navigation-ui-command.json':
                if command=={}:
                    if self.fault!='ignore-private-clear':self.raw_command=raw
                    return
                self.raw_command=raw;current=self.snapshot()
                row=next(row for row in current['controls'] if row['id']==command['controlId'])
                self.assertEqual(row['token'],command['controlToken']);self.assertEqual(self.native.sequence+1,command['sequence'])
                self.native.sequence+=1;safe=deepcopy(command);safe.pop('text',None);self.inputs.append(safe)
                if self.fault!='ignore-input':self.apply_input(command)
                self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                    sequence=command['sequence'],performed=True,error='',processId=self.pid(),updatedEpochMs=self.epoch())
                if self.fault=='lost-submit' and command['action']=='submit':self.native.status['commandId']=str(uuid.uuid4())
                return
            return original_write(target,package,path,raw)
        def shell(target,*args,**kwargs):
            if args==('am','force-stop','org.overte.pico'):
                self.os_inputs.append('stop');self.native.running=False;self.lifecycle['backgrounds']+=1;return ''
            if args[:4]==('am','start','-W','-n'):
                self.os_inputs.append('launch');self.assertEqual(pico.launcher_arguments(os.environ),args[5:])
                self.restart()
                if self.fault=='lost-launch':raise RuntimeError('Synthetic lost launch receipt')
                return ''
            return original_shell(target,*args,**kwargs)
        def controller(identity,operation,values):
            self.assertEqual(self.native.identity,identity)
            if operation=='input.primary':
                expected=tablet_home.observed_grip_pose(self.home_packet['sensorToWorld'],self.home_packet['headPosition'],self.home_packet['position'])
                self.assertEqual(expected,values);self.os_inputs.append(operation)
                state=unpack(self.facade.authentication_actions_store(self.target).read()['payload'])[0]
                intents=state['current']['intents'] if state['phase']=='issued' else self.primary.control()['cleanupIntents']
                self.assertEqual('tablet.home-ray',intents[-1]['control'])
                if self.fault!='ignore-home':self.apply_home()
                if self.fault=='lost-home':raise RuntimeError('Synthetic lost Home input receipt')
                return {'performed':True}
            self.assertEqual({'holdMilliseconds':1000},values)
            self.assertIn(operation,('tablet.open','tablet.close'));self.os_inputs.append(operation)
            if self.fault=='ignore-tablet-close' and operation=='tablet.close':return {'performed':True}
            self.native.opened=operation=='tablet.open'
            if not self.native.opened:self.menu=None
            return {'performed':True}
        def query(argv,**kwargs):
            if argv[0]!='synthetic-adb':return real_run(argv,**kwargs)
            self.assertEqual(['synthetic-adb','-s',self.target,'exec-out','run-as','org.overte.pico',
                '/system/bin/ps','-p',str(self.pid()),'-o','PID'],argv)
            return subprocess.CompletedProcess(argv,0 if self.native.running else 1,
                ('PID\n'+str(self.pid())+'\n' if self.native.running else 'PID\n').encode(),b'')
        globals_=type(self.original)._script_restart_prepare.__wrapped__.__globals__
        pinned=getclosurevars(type(self.original)._candidate.__wrapped__).nonlocals
        candidate_arguments,candidate_inputs=pinned['args'],deepcopy(pinned['frozen'])
        def frozen_inputs(arguments):
            self.assertIs(candidate_arguments,arguments);return deepcopy(candidate_inputs)
        patches=[patch.dict(os.environ,dict(OVERTE_PICO_FEATURE_AUTHENTICATION='1',OVERTE_PICO_ACCOUNT_FIXTURE='1',
                    OVERTE_E2E_FEATURE_FIXTURE_URL=URL,OVERTE_PICO_FEATURE_FIXTURE_CONFIG=str(config))),
            patch('adapters.common.time.time',side_effect=lambda:self.epoch()/1000),
            patch.object(self.native,'snapshot',side_effect=snapshot),patch.object(self.native,'read_debug_app_file',side_effect=read),
            patch.object(self.native,'write_debug_app_file',side_effect=write),patch.object(self.native,'shell',side_effect=shell),
            patch.object(self.native,'epoch_milliseconds',side_effect=lambda *_:self.epoch()),
            patch.object(self.native,'require_process_identity',side_effect=lambda identity:self.assertEqual(self.binding,identity)),
            patch.object(self.native,'is_unbound',side_effect=lambda:self.binding is None,create=True),
            patch.object(self.native,'begin',side_effect=lambda identity:setattr(self,'binding',identity),create=True),
            patch.object(self.native,'discard_local_state',side_effect=lambda:setattr(self,'binding',None)),
            patch.object(self.native,'stage',side_effect=controller),patch.object(self.native,'command',['synthetic-adb'],create=True),
            patch('adapters.android_process_query.subprocess.run',side_effect=query),
            patch.object(globals_['verifier'],'verify_candidate',return_value=verified),
            # Candidate tools and source-file hashing are a frozen synthetic
            # boundary here. The owning candidate suites test their real guards;
            # this full flow keeps actual installed-byte/PID/OpenXR checks.
            patch.dict(globals_,_inputs=frozen_inputs),
            patch.object(self.original,'_authentication_journey',return_value=self.facade),
            patch.object(self.facade,'_authentication_feature',side_effect=lambda target,run,**kwargs:self.primary),
            patch.object(normal_scripts,'TokenScriptUI',partial(TokenScriptUI,monotonic=lambda:self.clock,sleep=self.sleep)),
            patch.object(pico,'TokenLoginUI',partial(TokenLoginUI,monotonic=lambda:self.clock,sleep=self.sleep)),
            patch.dict(globals_,NativeFeatureObservation=partial(NativeFeatureObservation,monotonic=lambda:self.clock,sleep=self.sleep),
                NativeProcessPresence=partial(NativeProcessPresence,monotonic=lambda:self.clock,sleep=self.sleep))]
        for change in patches:change.start();self.addCleanup(change.stop)
        self.bind_sources()

    def epoch(self):return 20000+round(self.clock*1000)
    def sleep(self,value):self.clock+=value;self.login.clock=self.clock
    def pid(self):return int(self.native.identity.split(':')[0])
    def bind_sources(self):
        self.s.pid=self.pid();self.s.origin.instance=self.birth;self.s.origin.sequence=0
        self.s.probe.instance=self.s.fact['observation']['instance'];self.s.probe.sequence=0
        def native(packet):
            self.s.fact['observation']['capturedEpochMs']=self.epoch()
            packet.update(processId=self.pid(),instance=self.birth,lifecycle=deepcopy(self.lifecycle),account=deepcopy(self.s.fact),
                requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
            packet['animationFence']['requestedEpochMs']=self.epoch()
        self.s.native.mutate=native
        self.s.origin.mutate=lambda packet:packet.update(processId=self.pid(),requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
        def response(packet):
            packet.update(processId=self.pid(),requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
            if packet['operation']=='read':
                self.s.provider_sequence+=1;valid=self.s.fact['loggedIn'] and self.grants_enabled
                packet['source'].update(httpStatus=200 if valid else 401,networkError=0 if valid else 204,
                    endpointSha256=self.s.fact['observation']['endpointSha256'],
                    credentialGeneration=self.s.fact['observation']['credentialGeneration'],
                    sentEpochMs=self.epoch(),completedEpochMs=self.epoch(),tokenAttached=self.s.fact['observation']['tokenValid'],
                    principalSha256=hashlib.sha256(('e2e-'+RUN).encode() if valid else b'').hexdigest())
        self.s.probe.mutate=response
        self.s.tablet.mutate=lambda packet:packet.update(processId=self.pid(),capturedEpochMs=self.epoch(),controls=[],
            scriptInventory=inventory(tabletShown=self.native.opened))
        self.presence=Presence(pid=self.pid(),epoch_ms=self.epoch);self.presence.presence='absent'
        self.presence.edit=lambda packet:packet.update(instance=self.birth)

    def widgets(self):
        fact=self.s.fact['observation'];self.login.account=fact['instance'];self.login.account_generation=fact['credentialGeneration']
        self.login.endpoint=fact['endpointSha256'];self.login.pending=fact['loginPending'];self.login.token=fact['tokenPresent']
        if not self.native.opened:return []
        if self.menu:
            control='account-menu.file' if self.menu=='root' else 'account-menu.logout'
            rows=[dict(id=control,token=str(uuid.uuid5(uuid.NAMESPACE_URL,control+str(fact['credentialGeneration']))),
                enabled=True,focused=False,inputReady=True,accountInstance=fact['instance'],credentialGeneration=fact['credentialGeneration'],
                endpointSha256=fact['endpointSha256'],principalSha256=self.s.fact['principalSha256'])]
            if self.menu=='file' and not self.s.fact['loggedIn']:rows=[]
        else:
            rows=deepcopy(self.login.capture()['controls'])
            for row in rows:row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
            if not self.login.dialog:rows.append(dict(id='scripts.menu',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'MENU')),enabled=True,focused=False))
        return rows

    def login_inventory(self):
        rows=deepcopy(self.retained_roots)
        if self.login.dialog:rows.append(dict(id=self.login_root,profile='qml-login-v1',visible=True,inCurrentTree=True,
            callbackRunning=False,callbackItemPresent=False))
        if self.menu_root is not None:rows.append(dict(id=self.menu_root,profile='tablet-menu-v1',visible=True,inCurrentTree=True,
            callbackRunning=False,callbackItemPresent=False))
        return dict(inventoryVersion=1,complete=True,retiredRoots=sorted(self.retired_roots),roots=rows,
            qmlLoads=loads(self.qml_components),keyboard3D=dict(raised=self.keyboard_raised,enabled=True))

    def apply_input(self,command):
        control,action=command['controlId'],command['action']
        actions=self.facade.authentication_actions_store(self.target).read()
        state=unpack(actions['payload'])[0]
        if state['phase']=='issued':intents=state['current']['intents']
        else:intents=self.primary.control()['cleanupIntents']
        self.assertTrue(intents)
        self.assertIn(intents[-1]['control'],(control,'login.page') if control=='tablet.home' else (control,))
        if control=='scripts.menu':self.menu='root';self.menu_root=uuid.uuid4().hex;return
        if control=='account-menu.file':self.menu='file';return
        if control=='account-menu.logout':
            if self.fault=='ignore-logout':return
            observed=self.s.fact['observation'];generation=observed['credentialGeneration']+1
            self.s.fact.update(loggedIn=False,principalSha256=hashlib.sha256(b'').hexdigest())
            observed.update(credentialGeneration=generation,tokenPresent=False,tokenValid=False,refreshPresent=False,loginPending=False,refreshPending=False)
            append(self.s.fact,event(sequence=observed['eventSequence']+1,kind='logout-complete',generation=generation,epoch=self.epoch()));return
        row=next(row for row in self.login.capture()['controls'] if row['id']==control)
        self.login.intent('login-'+action,self.snapshot(),control)
        if control=='login.entry' and action=='activate':self.login_root=uuid.uuid4().hex
        self.login.input(control,action,token=row['token'],text=command.get('text'))
        if action=='submit':self.grant(self.login.fields.get('login.password'))

    def apply_home(self):
        self.menu=None
        if self.menu_root is not None:self.retired_roots.add(self.menu_root);self.menu_root=None
        if self.login.dialog:
            self.login.intent('login-close',self.snapshot(),'login.page');self.login.close_view()
            if self.fault=='retain-login-root':
                self.retained_roots.append(dict(id=self.login_root,profile='qml-login-v1',visible=False,inCurrentTree=False,
                    callbackRunning=False,callbackItemPresent=False))
            else:self.retired_roots.add(self.login_root)
            self.login_root=None

    def grant(self,password):
        if self.fault=='ignore-grant':self.login.waiting=False;return
        observed=self.s.fact['observation'];observed['credentialGeneration']+=1;self.s.provider_sequence+=1
        if password=='synthetic-private-delayed':
            observed['loginPending']=True
            self.provider_rows.append(dict(requestId='f'*32,requestTicket=self.ticket,startedEpochMs=self.epoch(),
                releasedEpochMs=0,issuedEpochMs=0,status=0,state='held',accessValid=False,refreshValid=False))
            return
        success=password=='synthetic-private-owned'
        reply=event(sequence=observed['eventSequence']+1,generation=observed['credentialGeneration'],
            status=200 if success else 401,epoch=self.epoch())
        reply['networkError']=0 if success else 203;append(self.s.fact,reply)
        if success:
            self.s.fact.update(loggedIn=True,principalSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest())
            observed.update(tokenPresent=True,tokenValid=True,refreshPresent=True)
            self.remote_tokens+=1;self.remote_refresh+=1;self.login.dialog=False
            self.retired_roots.add(self.login_root);self.login_root=None
        else:self.login.error='invalid-credentials'
        self.login.waiting=False;observed['loginPending']=False

    def restart(self):
        old=self.s.fact;self.stage+=1;self.native.identity=str(123+self.stage)+':synthetic-restart-'+str(self.stage)
        self.native.bridge_id=str(uuid.uuid4());self.native.sequence=0;self.native.running=True;self.native.opened=False
        self.lifecycle['launches']+=1;self.lifecycle['activations']+=1;self.birth=format(10+self.stage,'032x')
        self.s.fact=account();self.s.fact['observation'].update(instance=format(30+self.stage,'032x'),endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest())
        if old['loggedIn']:
            self.s.fact.update(loggedIn=True,principalSha256=old['principalSha256'])
            self.s.fact['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
        self.s.native=NativeBoundary();self.login=LoginWidgets(generic=True);self.login.clock=self.clock;self.menu=None
        self.login_root=self.menu_root=None;self.retired_roots=set();self.retained_roots=[]
        self.s.origin.retired=set();self.source_nonces=set();self.login_sequence=0;self.bind_sources()

    def request(self,role,path,value=None,method=None,**kwargs):
        self.assertEqual({},kwargs);self.provider_calls.append((role,path))
        if path=='/account-provider':return dict(providerVersion=2,instance=PROVIDER,transport='https',tlsVersion='TLSv1.3',internalErrors=0)
        if path=='/runs/'+RUN+'/account/status':
            return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=self.epoch(),eventSequence=self.s.provider_sequence,
                accountExists=self.account_exists,heldRequests=sum(row['state']=='held' for row in self.provider_rows),armedHold=False,inflightRequests=0,
                accessTokens=self.remote_tokens,refreshTokens=self.remote_refresh,grantsEnabled=self.grants_enabled)
        if path.startswith('/runs/'+RUN+'/account/credentials/'):
            self.assertEqual('primary',role);return dict(username='e2e-'+RUN,password='synthetic-private-'+path.rsplit('/',1)[1])
        if path=='/runs/'+RUN+'/account/control':
            self.assertEqual('primary',role);self.account_exists=self.grants_enabled=False;self.remote_tokens=self.remote_refresh=0
            self.revoke();return {}
        if path=='/runs/'+RUN+'/active':
            if value is None:return self.journal.active(RUN)
            self.assertEqual('primary',role);self.journal.activate(RUN,**value);self.ticket=value['ticket']
            if value['verb']=='cleanup':self.grants_enabled=False;self.remote_tokens=self.remote_refresh=0;self.revoke()
            if value['verb']=='release-stale-response':
                for row in self.provider_rows:
                    if row['state']=='held':
                        row.update(releasedEpochMs=self.epoch(),issuedEpochMs=self.epoch(),status=200,state='issued',accessValid=True,refreshValid=True)
                        self.remote_tokens+=1;self.remote_refresh+=1
            return {}
        if path=='/runs/'+RUN:
            if method=='DELETE':self.assertFalse(self.account_exists);self.journal.close(RUN);return {}
            return self.journal.snapshot(RUN)
        if path=='/runs/'+RUN+'/samples':self.assertEqual('actor',role);self.journal.publish(RUN,value);return {}
        if '/account/proof/' in path:
            self.assertEqual('actor',role);self.assertEqual(self.journal.active(RUN)['ticket'],path.rsplit('/',2)[1])
            valid=self.s.probe.value['source']['httpStatus']==200
            return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=self.epoch(),eventSequence=self.s.provider_sequence,
                kind='profile-request',ticket=path.rsplit('/',2)[1],requestId=path.rsplit('/',1)[1],status=200 if valid else 401,
                principal='owned' if valid else 'anonymous',protectedAccess=valid)
        if path=='/runs/'+RUN+'/account/delayed':
            return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=self.epoch(),eventSequence=self.s.provider_sequence,
                grantsEnabled=self.grants_enabled,requests=deepcopy(self.provider_rows),
                delayedGrantOutstanding=any(row['accessValid'] or row['refreshValid'] for row in self.provider_rows))
        self.fail('Unexpected synthetic provider route: '+path)

    def revoke(self):
        for row in self.provider_rows:
            row.update(accessValid=False,refreshValid=False)
            if row['state']=='held':row.update(state='cancelled',status=503)

    def observe(self,flow=None):return (flow or self.primary).observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
    def act(self,verb,inputs=None):
        self.control_count+=1;ticket=format(self.control_count,'032x');inputs={} if inputs is None else inputs
        self.primary_client.activate(ticket,verb,inputs)
        call=dict(contractVersion=VERSION,runId=RUN,fixtureUrl=URL+'/runs/'+RUN+'/',ticket=ticket,verb=verb,inputs=inputs)
        return self.original.invoke(self.target,'feature.authentication.act',call)

class PicoAuthenticationTests(AuthenticationBoundary,unittest.TestCase):
    def test_both_baseline_readers_use_original_sources_and_separate_probe_ownership_without_input(self):
        with self.assertRaises(AuthenticationPhasePending):self.observe(self.actor)
        first=self.observe();second=self.observe(self.actor)
        self.assertEqual(first['state'],second['state']);self.assertEqual([],first['resources']);self.assertEqual([],self.inputs)
        a=self.primary.role_state()['last']['frame'];b=self.actor.role_state()['last']['frame']
        self.assertNotEqual(a['probe']['requestId'],b['probe']['requestId']);self.assertIsNone(a['proof']);self.assertIsNotNone(b['proof'])

    def test_normal_vr_invalid_pending_close_reopen_and_owned_login_have_independent_effects(self):
        self.observe();self.actor.publish()
        for verb,inputs in (('login-open',{}),('login-submit',{'account':'invalid'}),('login-cancel',{}),
                ('login-open',{}),('login-submit',{'account':'owned'}),('logout',{})):
            self.act(verb,inputs);actual=self.observe();self.actor.publish()
            self.assertEqual(actual['state'],self.journal.snapshot(RUN)['entries'][-1]['facts'])
        self.assertEqual('anonymous',actual['state']['principal']);self.assertEqual(2,sum(row['action']=='submit' for row in self.inputs))
        self.assertNotIn('text',json.loads(self.raw_command));self.assertIn('account-menu.logout',[row['controlId'] for row in self.inputs])
        self.assertNotIn('synthetic-private-',repr(self.inputs)+repr(self.primary.store.read()))

    def test_source_cannot_hide_an_actual_startup_dialog_behind_the_test_launcher_argument(self):
        self.started_dialog=True
        with self.assertRaises(RuntimeError):self.observe()
        self.assertEqual([],self.inputs);self.assertIsNotNone(self.primary.store.read())

    def test_ignored_grant_or_uncertain_submit_retains_intent_and_never_replays_input(self):
        self.observe();self.act('login-open');self.fault='lost-submit'
        with self.assertRaises((RuntimeError,ValueError)):self.act('login-submit',{'account':'owned'})
        before=len(self.inputs);state=unpack(self.facade.authentication_actions_store(self.target).read()['payload'])[0]
        call=state['current']['arguments']
        with self.assertRaises((RuntimeError,ValueError)):self.original.invoke(self.target,'feature.authentication.act',call)
        self.assertEqual(before,len(self.inputs));self.assertEqual(1,sum(row['action']=='submit' for row in self.inputs))
        self.assertNotIn('text',json.loads(self.raw_command));self.assertEqual('issued',state['phase'])

    def test_fresh_control_ack_without_a_native_login_reply_cannot_be_feature_success(self):
        self.observe();self.act('login-open');self.fault='ignore-grant'
        with self.assertRaises((RuntimeError,ValueError)):self.act('login-submit',{'account':'owned'})
        self.assertFalse(self.s.fact['loggedIn']);self.assertEqual(0,self.s.fact['observation']['eventSequence'])
        state=unpack(self.facade.authentication_actions_store(self.target).read()['payload'])[0]
        self.assertEqual('issued',state['phase']);self.assertTrue(state['current']['delivered'])
        self.assertEqual(1,sum(row['action']=='submit' for row in self.inputs))

    def test_lost_launch_is_rebound_from_new_native_birth_and_old_pid_exit_without_resending(self):
        self.observe();self.actor.publish();self.fault='lost-launch'
        with self.assertRaises((RuntimeError,ValueError)):self.act('restart-app')
        self.assertIsNone(self.binding)
        state=unpack(self.facade.authentication_actions_store(self.target).read()['payload'])[0]
        call=state['current']['arguments'];self.fault=''
        self.assertEqual({'performed':True},self.original.invoke(self.target,'feature.authentication.act',call))
        self.observe();self.actor.publish()
        self.assertEqual(['stop','launch'],self.os_inputs);self.assertEqual(self.native.identity,self.binding)
        self.assertEqual('observed',self.facade.authentication_restart_store(self.target,1).read()['phase'])

    def test_a_foreign_generic_server_target_cannot_change_saved_preferences_or_receive_credentials(self):
        self.observe();self.act('login-open');self.login.server='https://foreign.invalid';before=len(self.inputs)
        with self.assertRaises((RuntimeError,ValueError)):self.act('login-submit',{'account':'owned'})
        self.assertEqual(before,len(self.inputs));self.assertEqual({},self.login.fields)
        self.assertEqual('https://foreign.invalid',self.login.server)

    def test_hidden_detached_login_object_prevents_cleanup_and_journal_retirement(self):
        self.observe();self.act('login-open');self.observe();self.fault='retain-login-root';self.act('login-cancel')
        actual=self.observe();self.assertFalse(actual['state']['dialog'])
        self.assertIn('panel:account-dialog-retained',actual['resources'])
        self.primary_client.activate('e'*32,'cleanup',{})
        with self.assertRaises(RuntimeError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual('cleaning',self.primary.control()['phase']);self.assertTrue(self.retained_roots)
        self.assertIsNotNone(self.primary.store.read());self.assertIsNone(self.primary.retirement_store.read())

    def test_lost_home_result_never_replays_the_ray_during_retry_or_cleanup(self):
        self.observe();self.act('login-open');self.fault='lost-home'
        with self.assertRaises((RuntimeError,ValueError)):self.act('login-cancel')
        state=unpack(self.facade.authentication_actions_store(self.target).read()['payload'])[0]
        self.assertEqual('tablet-home-ray',state['current']['intents'][-1]['stage'])
        original=list(self.os_inputs);self.fault=''
        with self.assertRaises((RuntimeError,ValueError)):self.original.invoke(self.target,'feature.authentication.act',state['current']['arguments'])
        self.assertEqual(original,self.os_inputs)
        self.primary_client.activate('e'*32,'cleanup',{})
        self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(1,self.os_inputs.count('input.primary'))
        self.assertFalse(self.primary.control()['cleanupIntents'][0]['control']=='tablet.home-ray')

    def test_ignored_home_ack_cannot_close_a_page_or_be_retried_in_cleanup(self):
        self.observe();self.act('login-open');self.fault='ignore-home'
        with self.assertRaises((RuntimeError,ValueError)):self.act('login-cancel')
        self.assertTrue(self.login.dialog);self.assertEqual(1,self.os_inputs.count('input.primary'))
        self.primary_client.activate('e'*32,'cleanup',{})
        with self.assertRaises(RuntimeError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(1,self.os_inputs.count('input.primary'));self.assertIsNotNone(self.primary.store.read())
        self.assertIsNone(self.primary.retirement_store.read())

    def test_uncertain_ignored_logout_is_not_sent_again_during_cleanup(self):
        self.observe();self.act('login-open');self.act('login-submit',{'account':'owned'});self.fault='ignore-logout'
        with self.assertRaises((RuntimeError,ValueError)):self.act('logout')
        self.primary_client.activate('e'*32,'cleanup',{})
        with self.assertRaises(RuntimeError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertEqual(1,sum(row['controlId']=='account-menu.logout' for row in self.inputs))
        self.assertTrue(self.s.fact['observation']['tokenPresent']);self.assertIsNotNone(self.primary.store.read())
        self.assertIsNone(self.primary.retirement_store.read())

    def test_hidden_menu_and_retained_callback_remain_resources(self):
        self.observe();self.act('login-open');self.act('login-submit',{'account':'owned'})
        self.retained_roots.append(dict(id='c'*32,profile='tablet-menu-v1',visible=False,inCurrentTree=False,
            callbackRunning=True,callbackItemPresent=True))
        actual=self.observe()
        self.assertIn('panel:account-menu',actual['resources']);self.assertIn('connection:account-menu-callback',actual['resources'])
        self.primary_client.activate('e'*32,'cleanup',{})
        with self.assertRaises(RuntimeError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertIsNotNone(self.primary.store.read());self.assertIsNone(self.primary.retirement_store.read())

    def test_retained_native_qml_callback_cannot_be_hidden_by_an_empty_login_tree(self):
        self.observe();self.qml_components=[component()]
        actual=self.observe();self.assertFalse(actual['state']['dialog'])
        self.assertIn('connection:account-qml-load',actual['resources'])
        self.primary_client.activate('e'*32,'cleanup',{})
        with self.assertRaises(RuntimeError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertIsNotNone(self.primary.store.read());self.assertIsNone(self.primary.retirement_store.read())

    def test_actual_raised_vr_keyboard_blocks_cleanup_even_after_login_roots_are_gone(self):
        self.observe();self.keyboard_raised=True
        actual=self.observe();self.assertFalse(actual['state']['dialog'])
        self.assertIn('input:account-keyboard',actual['resources'])
        self.primary_client.activate('e'*32,'cleanup',{})
        with self.assertRaises(RuntimeError):self.primary.cleanup(dict(contractVersion=VERSION,runId=RUN))
        self.assertIsNotNone(self.primary.store.read());self.assertIsNone(self.primary.retirement_store.read())

    def test_changed_installed_candidate_stops_before_any_authentication_input_or_source_dispatch(self):
        self.observe();self.native.digest='f'*64;before=list(self.provider_calls);commands=len(self.source_nonces)
        with self.assertRaises((RuntimeError,ValueError)):self.act('login-open')
        self.assertEqual([],self.inputs);self.assertEqual([],self.os_inputs)
        self.assertEqual(commands,len(self.source_nonces));self.assertIsNotNone(self.primary.store.read())
        # Only the explicitly requested fixture phase activation may precede
        # adapter admission. No credential/native/UI source request follows it.
        self.assertEqual(before+[('primary','/runs/'+RUN+'/active')],self.provider_calls)

    def test_configuration_requires_owned_https_launch_and_adapter_only_read_authority(self):
        self.assertTrue(pico.configured(os.environ))
        self.assertTrue(all(operation in self.original.capabilities(self.target) for operation in pico.OPERATIONS))
        for change in (dict(OVERTE_PICO_ACCOUNT_FIXTURE='0'),dict(OVERTE_E2E_FEATURE_FIXTURE_URL='http://owned.invalid/feature-fixture/v1'),
                dict(OVERTE_PICO_FEATURE_FIXTURE_CONFIG=''),dict(OVERTE_E2E_FEATURE_READER_TOKEN='x'*64)):
            with patch.dict(os.environ,change),self.assertRaises(RuntimeError):pico.configured(os.environ)
        with patch.dict(os.environ,{'OVERTE_PICO_FEATURE_AUTHENTICATION':'0'}):
            self.assertFalse(pico.configured(os.environ));self.assertFalse(set(pico.OPERATIONS)&set(self.original.capabilities(self.target)))


class PicoAuthenticationEngineTests(AuthenticationBoundary,unittest.TestCase):
    # Keep the complete common-engine flow independently selectable under the
    # existing catalog timeout, without rerunning the component class methods.
    def test_entire_common_journey_uses_three_actual_restart_boundaries_and_verified_retirement(self):
        reports=[]
        def invoke(operation,fields):return self.original.invoke(self.target,operation,fields)
        def witness():self.actor.publish();return self.primary_client.observe()
        journey=Journey('authentication',RUN,URL+'/runs/'+RUN+'/',invoke=invoke,witness=witness,
            activate=self.primary_client.activate,read_artifact=lambda _name:self.fail('Authentication has no synthetic artifact proof'),
            image_policy={},continuity=lambda *_args:None,monotonic=lambda:self.clock,epoch_ms=self.epoch,sleep=self.sleep,report=reports.append)
        journey.execute()
        self.assertTrue(reports[-1]['sequenceCompleted']);self.assertTrue(reports[-1]['cleanupSucceeded'])
        self.assertEqual(17,len(reports[-1]['phases'])-2)
        self.assertEqual(['stop','launch']*3,[verb for verb in self.os_inputs if verb in ('stop','launch')])
        self.assertEqual(3,self.stage);self.primary_client.close()
        self.assertEqual({'performed':True},self.primary.finalize())
        self.assertTrue(all(store.read() is None for store in self.primary._retirement_paths()))
        self.assertIsNone(self.facade.account_probe_store(self.target,role='actor').read())
        self.assertFalse(self.s.origin.path.exists())


if __name__=='__main__':unittest.main()
