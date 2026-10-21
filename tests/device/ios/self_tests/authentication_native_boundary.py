"""Explicit synthetic iOS SDK/Qt boundary for the real loopback OAuth fixture.

No application, simulator, device, compiler or WebDriver server is started.
Native source packets are synthesized here; their host parsers and journals are
real. OAuth/profile replies, server proof, private files and file descriptors
are original local test data, never requested checkpoint values.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request
import uuid

from adapters.normal_ui import W3C_ELEMENT,NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.account_provider import TOKEN_PATH,PROFILE_PATH,REQUEST_HEADER,RUN_HEADER,TICKET_HEADER
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_account_observation import account,event,append
from self_tests.test_native_account_origin import Boundary as OriginBoundary
from self_tests.test_private_login_input import Boundary as PrivateBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_token_login_ui import Boundary as LoginBoundary
from ios.adapters import normal_scripts


class Native:
    def __init__(self,root,origin,opener):
        self.root,self.origin,self.opener=Path(root),origin,opener
        self.clock=0.;self.pid=42;self.running=True;self.launches=0;self.phase='bound'
        self.birth='b'*32;self.instance=str(uuid.uuid4());self.generation=str(uuid.uuid4())
        self.lifecycle=dict(backgrounds=0,activations=1,launches=1);self.lifecycle_inputs=[];self.dead=set()
        self.target=dict(platform='ios',physical=True,appId='org.example.overte',serverUrl='http://sdk.invalid:4723',
            nativeUiObservation=dict(kind='uikit-documents',version=1),probe=dict(kind='ios-documents'),
            testBuild=dict(fixtureOrigin='http://transport.invalid:49121',resultsDirectory='owned-results',scenePath='/scene.json',
                launchEnvironment={'HIFI_METAVERSE_URL':origin}),normalScripts=dict(contractVersion=1,profile=normal_scripts.PROFILE))
        self.state=dict(sessionId='owned-session',generation=1,processIdentity='42',targetFingerprint=self.fingerprint())
        self.login=LoginBoundary(generic=True);self.login.server=origin;self.login.endpoint=hashlib.sha256(origin.encode()).hexdigest()
        self.login.transform=self.login_packet
        self.shown=False;self.menu='home';self.sequence=0;self.ui_sequence=0;self.service_sequence=0
        self.remember=False;self.saved='';self.input_log=[];self.commands=[];self.references={}
        self.account=account();self.account['observation'].update(endpointSha256=hashlib.sha256(origin.encode()).hexdigest())
        self.token=self.refresh=None;self.cache=None;self.success_at=None;self.tasks=[]
        self.executor=ThreadPoolExecutor(max_workers=4)
        self.feature=FeatureBoundary();self.feature.mutate=self.feature_packet
        self.origins=OriginBoundary(self.root/'native-origin');self.origins.mutate=self.origin_packet
        private_root=self.root/'native-private';private_root.mkdir(mode=0o700)
        self.private=PrivateBoundary(private_root,PrivateFeatureState(self.root/'private-login-input-owner.json'))
        self.probe_sequence=0;self.probe_slot=None;self.probe_used=set();self.probe_value=None;self.presence=None
        self.ignored_clear=self.ignored_stop=self.ignored_submit=False

    def login_packet(self,value):
        # The shared small SDK fixture has a fixed example HTTPS origin. This
        # iOS boundary models the actual dynamic loopback endpoint instead.
        if self.login.dialog:
            ready=not any((self.login.waiting,self.login.pending,self.login.token,self.login.domain,self.login.closing))
            for row in value['controls']:
                if row['id']=='login.server':row['inputReady']=ready
                elif row['id'] in ('login.username','login.password','login.submit'):
                    row['inputReady']=ready and self.login.server==self.origin
        return value

    def fingerprint(self):return hashlib.sha256(json.dumps(self.target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def host_epoch(self):return 1700000000000+round(self.clock*1000)
    def epoch(self):return self.host_epoch()+86400000
    def scope(self):return dict(sourceRevision='a'*40,artifactSha256='e'*64,sessionId='owned-session',generation=1,targetFingerprint=self.fingerprint())
    def process(self):return dict(bundleId=self.target['appId'],pid=self.pid,foreground=True) if self.running else None
    def sleep(self,seconds):
        import time
        self.clock+=seconds;self.login.clock=self.clock;self.poll();time.sleep(.005)

    def http(self,path,*,data=None,headers=None,timeout=5):
        request=Request(self.origin+path,data=data,headers=headers or {})
        try:response=self.opener.open(request,timeout=timeout)
        except HTTPError as error:response=error
        with response:return response.code,response.read(8193)

    def poll(self):
        remaining=[]
        for future,birth,generation in self.tasks:
            if not future.done():remaining.append((future,birth,generation));continue
            if birth!=self.birth or not self.running or generation!=self.account['observation']['credentialGeneration']:continue
            # The host's original HTTPS future may fail after its simulated
            # native consumer died. That failure belongs to the retired
            # consumer too; never evaluate it in the replacement process.
            status,raw=future.result()
            self.account['observation']['loginPending']=False
            reply=event(sequence=self.account['observation']['eventSequence']+1,kind='login-reply',
                epoch=self.epoch(),generation=generation,status=status)
            reply['networkError']=0 if status==200 else 203;append(self.account,reply)
            if status==200:
                grant=json.loads(raw);self.token=grant['access_token'];self.refresh=grant['refresh_token']
                code,body=self.http(PROFILE_PATH,headers={'Authorization':'Bearer '+self.token})
                if code!=200:raise NativeUIError('Synthetic native account profile failed')
                username=json.loads(body)['data']['user']['username']
                self.account.update(loggedIn=True,principalSha256=hashlib.sha256(username.encode()).hexdigest())
                self.account['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
                self.cache=(self.token,self.refresh,username);self.success_at=self.clock+1
                self.login.waiting=False;self.login.pending=False;self.saved=self.login.fields.get('login.username','') if self.remember else self.saved
            else:
                self.login.waiting=False;self.login.pending=False;self.login.error='invalid-credentials'
        self.tasks=remaining
        if self.success_at is not None and self.clock>=self.success_at:
            self.login.dialog=False;self.login.focused=None;self.success_at=None
        self.sync_login()

    def sync_login(self):
        current=self.account['observation'];self.login.account=current['instance'];self.login.account_generation=current['credentialGeneration']
        self.login.endpoint=current['endpointSha256'];self.login.pending=current['loginPending'];self.login.token=current['tokenPresent']

    def preferences(self):
        digest=hashlib.sha256(self.origin.encode()).hexdigest()
        return dict(accountPreferenceVersion=2,present=True,valueType='string',valueSha256=digest,canonicalOrigin=True,
            processOverridePresent=True,processOverrideSha256=digest,processOverrideCanonical=True,
            rememberPresent=True,rememberType='bool',rememberValue=self.remember,savedUsernamePresent=True,
            savedUsernameType='string',savedUsernameSha256=hashlib.sha256(self.saved.encode()).hexdigest())

    def observed(self):
        self.poll();self.ui_sequence+=1
        rows=deepcopy(self.login.capture()['controls']) if self.shown or self.login.dialog else []
        for row in rows:row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
        if self.shown:
            if self.login.dialog:
                rows.append(dict(id='tablet.home',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'tablet.home')),enabled=True,focused=False))
                if not self.login.waiting and not self.account['loggedIn']:
                    rows.append(dict(id='account.remember',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'remember-'+str(self.remember))),
                        enabled=True,focused=False,preferenceControlVersion=1,checked=self.remember))
            else:
                rows.append(dict(id='scripts.menu',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'menu')),enabled=True,focused=False))
                if self.menu=='root':
                    rows.append(dict(id='account.menu-file',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'file')),enabled=True,focused=False,
                        menuSourceVersion=1,sourceType=2,labelSha256=hashlib.sha256(b'File').hexdigest()))
                if self.menu=='file' and self.account['loggedIn']:
                    rows.append(dict(id='account.logout',token=str(uuid.uuid5(uuid.NAMESPACE_URL,'logout')),enabled=True,focused=False,
                        menuSourceVersion=1,sourceType=1,labelSha256=hashlib.sha256(('Directory Service: Logout '+(self.cache[2] if self.cache else '')).encode()).hexdigest()))
        for row in rows:row['frame']=dict(x=10,y=20,width=100,height=48)
        return dict(schemaVersion=1,instance=self.instance,generation=self.generation,frameSpace='qt-window-logical',
            processId=self.pid,sampleEpochMs=self.epoch(),elapsedMs=round(self.clock*1000),lastSequence=self.sequence,
            tabletShown=self.shown,ready=True,controls=rows,featureControlsVersion=1,fileControlsVersion=1,loginControlsVersion=2,
            accountMenuControlsVersion=1,loginClearInputVersion=1,accountPreferences=self.preferences(),
            scriptObservationVersion=1,scriptSourceSequence=self.ui_sequence,
            scriptInventory=dict(inventoryVersion=1,complete=True,managers=[],pickers=[],tabletPresent=True,tabletShown=self.shown))

    def feature_packet(self,value):
        self.poll();value.update(instance=self.birth,processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),
            lifecycle=deepcopy(self.lifecycle),account=deepcopy(self.account))
        value['account']['observation']['capturedEpochMs']=self.epoch();value['animationFence']['requestedEpochMs']=self.epoch()

    def origin_packet(self,value):value.update(processId=self.pid,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())

    def probe(self,request):
        self.poll();self.probe_sequence+=1;op=request['operation'];key=tuple(request[k] for k in ('runId','ticket','requestId'))
        if op=='read' and request['requestId'] not in self.probe_used:
            self.probe_slot=key;self.probe_used.add(request['requestId'])
        elif op=='release' and request['requestId'] not in self.probe_used:
            self.probe_slot=key;self.probe_used.add(request['requestId'])
        if key!=self.probe_slot:
            self.probe_value=dict(commandId=request['commandId'],available=False);return
        if op=='read':
            sent=self.epoch();headers={RUN_HEADER:request['runId'],TICKET_HEADER:request['ticket'],REQUEST_HEADER:request['requestId']}
            if self.token:headers['Authorization']='Bearer '+self.token
            status,body=self.http(PROFILE_PATH,headers=headers);value=json.loads(body)
            username=value.get('data',{}).get('user',{}).get('username','')
            source=dict(httpStatus=status,networkError=0 if status==200 else 204,parsed=True,
                principalSha256=hashlib.sha256(username.encode()).hexdigest(),responseSha256=hashlib.sha256(body).hexdigest(),
                responseBytes=len(body),tokenAttached=bool(self.token),credentialGeneration=self.account['observation']['credentialGeneration'],
                endpointSha256=hashlib.sha256(self.origin.encode()).hexdigest(),sentEpochMs=sent,completedEpochMs=self.epoch())
        elif op=='release':source=dict(performed=True)
        else:source=dict(inflight=False,responseBytes=0,credentialBytes=0,released=True)
        self.probe_value=dict(probeVersion=1,**{key:request[key] for key in ('commandId','requestId','runId','ticket','operation')},
            instance=self.account['observation']['instance'],sequence=self.probe_sequence,processId=self.pid,
            requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=source)

    def post(self,request,timeout):
        command=json.loads(request.data);self.commands.append(deepcopy(command));self.echo=json.dumps(command).encode();action=command['action']
        if action=='feature-native-observe':self.feature.send(command)
        elif action=='feature-account-origin':self.origins.send(command)
        elif action=='feature-account-probe':self.probe(command)
        elif action=='feature-process-presence':
            if self.presence is None or self.presence.pid!=self.pid:
                self.presence=PresenceBoundary(pid=self.pid,epoch_ms=self.epoch)
                self.presence.edit=lambda value:value.update(instance=self.birth)
            self.presence.presence='absent' if command['queryProcessId'] in self.dead else 'present';self.presence.send(command)
        elif action=='feature-private-login-input':
            payload=None
            if command['operation']=='deliver' and self.private.path(command).exists():payload=json.loads(self.private.path(command).read_bytes())['input']
            self.private.pid=self.pid;self.private.send(command);self.private.value.update(capturedEpochMs=self.epoch(),elapsedMs=round(self.clock*1000))
            if payload is not None and 'inputStatus' in self.private.value['source']:
                rows=[row for row in self.observed()['controls'] if row['id'] in ('login.username','login.password') and row['token']==payload['fieldToken']]
                valid=len(rows)==1 and rows[0]['focused'] and rows[0]['inputReady'] and payload['instance']==self.instance and payload['sequence']==self.sequence+1
                if valid:self.sequence+=1;self.login.fields[rows[0]['id']]=payload['text']
                status=self.private.rows[command['inputId']]['inputStatus'];status.update(performed=valid,processId=self.pid,sampleEpochMs=self.epoch())
                self.private.value['source']['inputStatus']=deepcopy(status)
        elif action=='normal-ui-input':
            if command['operation']=='observe':self.ui_receipt=dict(schemaVersion=1,commandId=command['commandId'],observation=self.observed())
            else:
                native=command['input'];assert native['operation']=='clear-login-username' and 'text' not in native
                assert native['sequence']==self.sequence+1;self.sequence+=1;self.input_log.append('clear-username')
                if not self.ignored_clear:self.login.fields['login.username']=''
                self.ui_receipt=dict(schemaVersion=1,commandId=command['commandId'],status=dict(schemaVersion=1,commandId=native['commandId'],
                    instance=self.instance,sequence=self.sequence,performed=True,processId=self.pid,sampleEpochMs=self.epoch()))
        elif action=='normal-feature-observe':
            self.service_sequence+=1;self.diagnostic=dict(schemaVersion=1,requestId=command['commandId'],instance=self.birth,
                sampleSequence=self.service_sequence,sampleEpochMs=self.epoch(),complete=True,scripts=[])
        else:raise AssertionError('Unreviewed synthetic native request')
        return self

    status=200
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,limit):return self.echo[:limit]

    def execute(self,session,operation,values):
        assert session=='owned-session'
        if operation=='mobile: overteProcessInfo':return self.process()
        if operation=='mobile: pushFile':self.private.write(values['remotePath'].rsplit('/',1)[-1],base64.b64decode(values['payload'],validate=True));return None
        assert operation=='mobile: pullFile'
        name=values['remotePath'].rsplit('/',1)[-1]
        if name=='feature-native-observation.json':raw=self.feature.original().encode()
        elif name=='feature-account-origin-result.json':raw=self.origins.read().encode()
        elif name=='feature-account-probe.json':raw=json.dumps(self.probe_value).encode()
        elif name=='feature-process-presence.json':raw=self.presence.original().encode()
        elif name=='ios-normal-ui-request-result.json':raw=json.dumps(self.ui_receipt).encode()
        elif name=='normal-feature-observation.json':raw=json.dumps(self.diagnostic).encode()
        elif name=='feature-private-login-input.json':raw=self.private.read().encode()
        elif name.startswith('feature-login-input-'):raw=self.private.original(name)
        else:raise AssertionError('Unreviewed synthetic AFC file')
        return base64.b64encode(raw).decode()

    def call(self,method,path,body=None):
        self.poll()
        if method=='GET' and path=='/session/owned-session':return {}
        if path.endswith('/actions') and method=='DELETE':return None
        if path.endswith('/elements'):
            identifier=body['value'];name=identifier.removeprefix('OverteNavigation.')
            rows=self.observed()['controls']
            special=identifier=='OverteTabletOpen' and not self.shown or identifier=='OverteTabletClose' and self.shown and not self.login.dialog
            row=next((row for row in rows if row['id']==name),None)
            if not special and row is None:return []
            key='node-'+str(len(self.references));self.references[key]=(identifier,row['token'] if row else 'special')
            return [{W3C_ELEMENT:key}]
        identifier,token=self.references[path.split('/element/')[1].split('/')[0]];name=identifier.removeprefix('OverteNavigation.')
        row=next((row for row in self.observed()['controls'] if row['id']==name),None)
        if path.endswith('/displayed') or path.endswith('/enabled'):return row is not None or identifier in ('OverteTabletOpen','OverteTabletClose')
        if path.endswith('/attribute/value'):return row['token'] if row else 'special'
        assert path.endswith('/click') and method=='POST'
        if row is not None and row['token']!=token:raise NativeUIError('Synthetic current iOS token retired')
        self.input_log.append(name)
        if identifier=='OverteTabletOpen':self.shown=True;self.generation=str(uuid.uuid4())
        elif identifier=='OverteTabletClose':self.shown=False;self.menu='home';self.generation=str(uuid.uuid4())
        elif name=='login.entry':self.login.dialog=True;self.remember=True;self.menu='home'
        elif name in ('login.username','login.password'):self.login.focused=name
        elif name=='tablet.home':self.login.dialog=False;self.login.waiting=False;self.login.error='none';self.login.focused=None;self.menu='home'
        elif name=='login.submit':
            if not self.ignored_submit:
                self.account['observation']['credentialGeneration']+=1;self.account['observation']['loginPending']=True
                self.login.waiting=True;self.login.pending=True;self.login.error='none'
                if self.remember:self.saved=self.login.fields.get('login.username','')
                data=urlencode(dict(grant_type='password',scope='owner',username=self.login.fields.get('login.username',''),
                    password=self.login.fields.get('login.password',''))).encode()
                future=self.executor.submit(self.http,TOKEN_PATH,data=data,headers={'Content-Type':'application/x-www-form-urlencoded'},timeout=30)
                self.tasks.append((future,self.birth,self.account['observation']['credentialGeneration']))
        elif name=='scripts.menu':self.menu='root'
        elif name=='account.menu-file':self.menu='file'
        elif name=='account.logout':
            self.token=self.refresh=self.cache=None;self.account.update(loggedIn=False,principalSha256=hashlib.sha256(b'').hexdigest())
            obs=self.account['observation'];obs.update(tokenPresent=False,tokenValid=False,refreshPresent=False,loginPending=False,refreshPending=False)
            append(self.account,event(sequence=obs['eventSequence']+1,kind='logout-complete',epoch=self.epoch(),generation=obs['credentialGeneration']+1))
            self.menu='home'
        elif name=='account.remember':self.remember=not self.remember;self.saved=self.login.fields.get('login.username','') if self.remember else ''
        else:raise AssertionError('Unreviewed synthetic ordinary input')
        self.sync_login();return None

    def lifecycle_input(self,operation):
        self.lifecycle_inputs.append(operation)
        if operation=='app.stop':
            if not self.ignored_stop:self.dead.add(self.pid);self.running=False;self.phase='retired';self.lifecycle['backgrounds']+=1
            return {'stopped':not self.running}
        assert operation=='app.launch' and not self.running
        self.pid+=1;self.running=True;self.phase='bound';self.launches+=1
        self.birth=format(11+self.launches,'032x');self.instance=str(uuid.uuid4());self.generation=str(uuid.uuid4())
        self.lifecycle['launches']+=1;self.lifecycle['activations']+=1;self.state['processIdentity']=str(self.pid)
        self.shown=False;self.menu='home';self.login.dialog=False;self.login.waiting=False;self.success_at=None
        self.account=account();self.account['observation'].update(instance=format(31+self.launches,'032x'),
            endpointSha256=hashlib.sha256(self.origin.encode()).hexdigest())
        self.token=self.refresh=None
        if self.cache:
            self.token,self.refresh,username=self.cache
            code,body=self.http(PROFILE_PATH,headers={'Authorization':'Bearer '+self.token})
            if code==200:
                actual=json.loads(body)['data']['user']['username'];self.account.update(loggedIn=True,principalSha256=hashlib.sha256(actual.encode()).hexdigest())
                self.account['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
        self.probe_slot=None;self.probe_used.clear();self.private.instance=format(51+self.launches,'032x')
        self.sync_login();return {'launched':True}

    def base(self):
        owner=self
        class Gate:
            def verify(self):
                if not owner.running:raise NativeUIError('Synthetic native process absent')
                return dict(schemaVersion=1,sourceRevision='a'*40,artifactSha256='e'*64,installedCandidateVerified=True)
            def continuity(self):
                if not owner.running:raise NativeUIError('Synthetic native process absent')
                return owner.process()
            def record(self):return dict(phase=owner.phase)
            def retired_absence(self):
                if owner.running:raise NativeUIError('Synthetic old process remains live')
            def finish_retirement(self):self.retired_absence()
        base=SimpleNamespace(_operation=None,_session_recreation_forbidden=False,_candidate_guard=lambda **_:None,
            _target=lambda _:self.target,_scope=lambda *_:self.scope(),_binding=lambda *_:Gate(),
            _binding_store=lambda _:SimpleNamespace(read=lambda:dict(phase=self.phase)),read_session=lambda _:deepcopy(self.state),
            state_path=lambda _:self.root/'session.json',invoke=lambda _selector,operation,_values:self.lifecycle_input(operation),
            reset_launch_state=lambda *_:None,_script_restart_session=lambda *_a,**_kw:(self,self.state,self.target))
        for name,file in (('account_origin_store','account-origin-owner.json'),('account_probe_store','account-probe-owner.json'),
                          ('private_login_input_store','private-login-input-owner.json'),('script_store','normal-scripts.json'),
                          ('script_files_store','normal-script-files.json'),('script_restart_store','normal-script-restart.json'),
                          ('script_restart_inputs_store','normal-script-restart-inputs.json')):
            setattr(base,name,lambda _selector,name=file:PrivateFeatureState(self.root/name))
        return base

    def close(self):self.private.close();self.executor.shutdown(wait=True,cancel_futures=True)
