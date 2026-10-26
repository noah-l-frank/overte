"""Declared Share archive UIKit/OS sources over actual ZIP/installed forests."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import plistlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_ui import W3C_ELEMENT,NativeUIError
from ios.adapters.installed_code import SDK
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionRuntime
from ios.self_tests.snapshot_companion_domain import SnapshotCompanionDomain,BASE


BUNDLE='org.example.snapshot.sharearchive'
EXTENSION='PlugIns/OriginalReceiver.appex/'


class ShareAdmissionDomain(SnapshotCompanionDomain):
    def __init__(self,case):
        super().__init__(case);info=plistlib.loads(self.files['Info.plist'])
        info.update(CFBundleIdentifier=BUNDLE,OVTSnapshotCompanionRole='share-archive',OVTSnapshotShareGroup='group.org.example.snapshot.share')
        self.files['Info.plist']=plistlib.dumps(info)
        extension=dict(CFBundleIdentifier=BUNDLE+'.receiver',CFBundleExecutable='share-receiver',CFBundlePackageType='XPC!',
            OVTSnapshotShareGroup=info['OVTSnapshotShareGroup'],NSExtension=dict(NSExtensionPointIdentifier='com.apple.share-services',NSExtensionPrincipalClass='OVTShareReceiver'))
        self.files.update({EXTENSION+'Info.plist':plistlib.dumps(extension),EXTENSION+'share-receiver':b'Explicit structural share executable model',
            EXTENSION+'_CodeSignature/CodeResources':b'Actual selected extension signature bytes',EXTENSION+'embedded.mobileprovision':b'PRIVATE-EXTENSION-PROVISION-MODEL'})
        self.write_archive(self.files)
        for name,raw in self.files.items():
            path=self.installed/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.target['appId']=BUNDLE;self.driver_bundle=BUNDLE
        self.scope.update(artifactSha256=hashlib.sha256(self.ipa.read_bytes()).hexdigest(),targetFingerprint=digest(self.target))
        old=self.session.read();self.session.write(dict(old,targetFingerprint=self.scope['targetFingerprint']),old)
    def installed_identity(self):
        value=super().installed_identity();value['bundleId']=BUNDLE;return value
    def observe(self,action):
        need(action in ('identity','clock') and self.nonce not in self.nonces);self.nonces.add(self.nonce);self.sequence+=1;self.tick+=2
        before=self.clock();self.tick+=1;after=self.clock()
        value=dict(snapshotShareCompanionObservationVersion=1,action=action,nonce=self.nonce,role='share-archive',instance=self.instance,
            processId=self.pid+(1 if self.foreign else 0),bundleId=BUNDLE,sequence=self.sequence,sourceBirthClock=dict(epochMs=BASE-100,monotonicMs=899900),
            clockBefore=before,clockAfter=after,status='pending' if action=='identity' and self.pending else 'ready')
        if action=='identity':value.update(preparedClock=None if self.pending else dict(epochMs=BASE-90,monotonicMs=899910),bundle={} if self.pending else self.installed_identity())
        return value
    def call(self,method,path,body=None):
        self.requests.append((method,path,deepcopy(body)))
        if method=='GET' and path=='/session/companion-session':return dict(capabilities={'appium:bundleId':self.driver_bundle})
        need(path.startswith('/session/companion-session/'));suffix=path[len('/session/companion-session'):]
        if suffix=='/elements':
            identifier=body['value'];need(identifier in ('snapshot.share.companion.nonce','snapshot.share.companion.identity','snapshot.share.companion.clock'))
            return [{W3C_ELEMENT:identifier}]
        if suffix.endswith(('/displayed','/enabled')):return True
        if suffix.endswith('/text'):return self.nonce
        if suffix.endswith('/clear'):self.nonce='';return None
        if suffix.endswith('/value'):self.nonce=body['text'];return None
        need(method=='POST' and suffix.endswith('/click'));action=suffix.split('/')[2].rsplit('.',1)[1];self.clicks.append(action)
        if not self.ignore:
            value=self.observe(action)
            if not self.stale:
                output=self.documents/('snapshot-share-companion-'+action+'.json');output.write_text(json.dumps(value,indent=1)+'\n');output.chmod(0o600)
        if self.loss==action:raise NativeUIError('Declared lost Share archive inspection return after delivery')
        return None
    def execute(self,session,operation,query):
        self.sdk.append((session,operation,deepcopy(query)));need(session=='companion-session')
        if operation in ('mobile: overteProcessSourceInfo','mobile: overteProcessInfo'):
            need(query==dict(bundleId=BUNDLE) and self.driver_bundle==BUNDLE)
            if operation=='mobile: overteProcessSourceInfo':return dict(processSourceVersion=1,source='dvt-bundle-pid-xcuitest-state',instance=self.source,available=True,cleanupPending=False,sdk=deepcopy(SDK))
            return dict(bundleId=BUNDLE,pid=self.pid,foreground=True)
        need(operation=='mobile: pullFile' and set(query)=={'remotePath'});prefix='@'+BUNDLE+':documents/'
        need(query['remotePath'].startswith(prefix));filename=query['remotePath'][len(prefix):]
        need(filename in ('snapshot-share-companion-identity.json','snapshot-share-companion-clock.json'))
        return base64.b64encode((self.documents/filename).read_bytes()).decode()
    def runtime(self):return IOSSnapshotShareAdmissionRuntime(self,self.session,self.target,self.scope,self.ipa,lambda:True,epoch_ms=self.epoch,monotonic=self.mono,sleep=lambda _:None)
