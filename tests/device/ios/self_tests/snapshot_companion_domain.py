"""Explicit UIKit/NSBundle/OS models with real ZIP/AFC/CAS/private files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import plistlib
import tempfile
import zipfile
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import W3C_ELEMENT,NativeUIError
from feature_journeys.witness import Client
from ios.adapters.bundle_identity import EMPTY,root_digest
from ios.adapters.installed_code import SDK
from ios.adapters.snapshot_companion_runtime import IOSSnapshotCompanionRuntime

RUN='a'*32
BASE=1700000000000
BUNDLE='org.example.snapshot.photos'


class SnapshotCompanionDomain:
    def __init__(self,case):
        temporary=tempfile.TemporaryDirectory(prefix='snapshot-companion-');case.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.installed=self.root/'InstalledPhotos.app';self.installed.mkdir();self.documents=self.root/'Documents';self.documents.mkdir()
        self.tick=1;self.pid=42;self.driver_bundle=BUNDLE;self.source='e'*32;self.instance='f'*32;self.sequence=0
        self.nonce='';self.requests=[];self.sdk=[];self.clicks=[];self.nonces=set();self.loss=None;self.ignore=False;self.pending=False;self.stale=False
        self.foreign=False;self.corrupt_clock=False;self.replace_birth=False;self.phase_sequence=0
        info=dict(CFBundleIdentifier=BUNDLE,CFBundleExecutable='photos-test',CFBundlePackageType='APPL',
            OVTSnapshotCompanionContractVersion=1,OVTSnapshotCompanionRole='photos',UIFileSharingEnabled=True)
        self.files={'Info.plist':plistlib.dumps(info),'photos-test':b'Structural Mach-O model, not signed Apple code',
            '_CodeSignature/CodeResources':b'Structural signature model','embedded.mobileprovision':b'PRIVATE-PROVISIONING-ACCOUNT-MODEL'}
        self.ipa=self.root/'selected.ipa';self.write_archive(self.files)
        for name,body in self.files.items():
            path=self.installed/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
        self.target=dict(platform='ios',physical=True,appId=BUNDLE,serverUrl='http://already-bound.invalid')
        self.scope=dict(sourceRevision='c'*40,artifactSha256=hashlib.sha256(self.ipa.read_bytes()).hexdigest(),sessionId='companion-session',generation=1,targetFingerprint=digest(self.target))
        self.session=PrivateFeatureState(self.root/'session.json');self.session.write({key:self.scope[key] for key in ('sessionId','generation','targetFingerprint')},None)

    def write_archive(self,files):
        with zipfile.ZipFile(self.ipa,'w') as archive:
            for name,body in files.items():archive.writestr('Payload/PhotosTest.app/'+name,body)

    def epoch(self):return BASE+self.tick
    def mono(self):return 100+self.tick/1000
    def clock(self,offset=0):return dict(epochMs=BASE+self.tick+offset,monotonicMs=900000+self.tick+offset)
    def installed_identity(self):
        entries={}
        for path in self.installed.rglob('*'):
            name=path.relative_to(self.installed).as_posix()
            entries[name]=('D',0,EMPTY) if path.is_dir() else ('F',path.stat().st_size,hashlib.sha256(path.read_bytes()).digest())
        return dict(bundleContractVersion=1,bundleId=BUNDLE,executableSha256=entries['photos-test'][2].hex(),**root_digest(entries))

    def observe(self,action):
        need(self.nonce not in self.nonces);self.nonces.add(self.nonce);self.sequence+=1;self.tick+=2
        before=self.clock();self.tick+=1;after=self.clock()
        value=dict(snapshotCompanionObservationVersion=1,action=action,nonce=self.nonce,role='photos',instance=self.instance,
            processId=self.pid,bundleId=BUNDLE,sequence=self.sequence,sourceBirthClock=dict(epochMs=BASE-100,monotonicMs=899900),
            clockBefore=before,clockAfter=after,status='pending' if action=='identity' and self.pending else 'ready')
        if action=='identity':value.update(preparedClock=None if self.pending else dict(epochMs=BASE-90,monotonicMs=899910),bundle={} if self.pending else self.installed_identity())
        if self.foreign:value['processId']+=1
        if self.replace_birth and action=='identity':value['instance']='1'*32
        if self.corrupt_clock:value['clockAfter']['monotonicMs']+=500
        return value

    def call(self,method,path,body=None):
        self.requests.append((method,path,deepcopy(body)))
        if method=='GET' and path=='/session/companion-session':return dict(capabilities={'appium:bundleId':self.driver_bundle})
        need(path.startswith('/session/companion-session/'));suffix=path[len('/session/companion-session'):]
        if suffix=='/elements':
            identifier=body['value'];need(identifier in ('snapshot.companion.nonce','snapshot.companion.identity','snapshot.companion.clock'))
            return [{W3C_ELEMENT:identifier}]
        if suffix.endswith(('/displayed','/enabled')):return True
        if suffix.endswith('/text'):return self.nonce
        if suffix.endswith('/clear'):
            self.nonce=''
            if self.loss=='clear':raise NativeUIError('Explicit lost ordinary field clear return')
            return None
        if suffix.endswith('/value'):
            self.nonce=body['text']
            if self.loss=='value':raise NativeUIError('Explicit lost ordinary nonce value return')
            return None
        need(method=='POST' and suffix.endswith('/click'));action=suffix.split('/')[2].rsplit('.',1)[1];self.clicks.append(action)
        if not self.ignore:
            value=self.observe(action)
            if not self.stale:
                path=self.documents/('snapshot-companion-'+action+'.json');path.write_text(json.dumps(value,indent=1)+'\n');path.chmod(0o600)
        if self.loss==action:raise NativeUIError('Explicit lost native inspection return after delivery')
        return None

    def execute(self,session,operation,query):
        self.sdk.append((session,operation,deepcopy(query)));need(session=='companion-session')
        if operation in ('mobile: overteProcessSourceInfo','mobile: overteProcessInfo'):
            need(query==dict(bundleId=self.driver_bundle) and self.driver_bundle==BUNDLE)
            if operation=='mobile: overteProcessSourceInfo':return dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance=self.source,available=True,cleanupPending=False,sdk=deepcopy(SDK))
            return dict(bundleId=self.driver_bundle,pid=self.pid,foreground=True)
        need(operation=='mobile: pullFile' and set(query)=={'remotePath'})
        prefix='@'+BUNDLE+':documents/';need(query['remotePath'].startswith(prefix));filename=query['remotePath'][len(prefix):]
        need(filename in ('snapshot-companion-identity.json','snapshot-companion-clock.json'))
        return base64.b64encode((self.documents/filename).read_bytes()).decode()

    def runtime(self):
        return IOSSnapshotCompanionRuntime(self,self.session,self.target,self.scope,self.ipa,lambda:True,epoch_ms=self.epoch,monotonic=self.mono,sleep=lambda _:None)

    def client(self):
        domain=self
        class Phase(Client):
            def request(self,path,value=None,method=None,*,phase_nonce=None,**_kwargs):
                need(path=='/runs/'+RUN+'/phase');domain.phase_sequence+=1
                return dict(fixturePhaseVersion=1,instance='b'*32,sequence=domain.phase_sequence,requestId=phase_nonce,runId=RUN,area='snapshots',
                    capturedEpochMs=domain.epoch(),active=True,createdEpochMs=BASE-200,retiredEpochMs=None,
                    activations=[dict(sequence=1,ticket='d'*32,activatedEpochMs=BASE-150,stimulus=dict(verb='capture',inputs=dict(mode='still',format='png')))])
        return Phase('https://controlled.invalid/feature-fixture/v1','r'*64,monotonic=self.mono,sleep=lambda _:None)

    def owner(self):return self.runtime().owner(RUN,self.client())
