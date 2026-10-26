"""Actual original Share extension PID anchor and separate retired-PID reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from ios.adapters.snapshot_photos_context import PhotosCompanionContext
from ios.adapters.snapshot_share_admission import IOSSnapshotShareAdmissionOwner,IOSSnapshotShareAdmissionRuntime
from ios.adapters import snapshot_share_original as share
from ios.adapters.installed_code import source as process_source
from adapters.native_feature_observation import decode


def stamp(value,previous=None):
    exact(value,{'epochMs','monotonicMs'});need(number(value['epochMs'],1,1e15) and number(value['monotonicMs'],0,1e15))
    if previous is not None:need(value['epochMs']>=previous['epochMs'] and value['monotonicMs']>=previous['monotonicMs']
        and abs(value['epochMs']-previous['epochMs']-(value['monotonicMs']-previous['monotonicMs']))<=250)
    return value


def samples(value):
    need(type(value['appStates']) is list and len(value['appStates'])==2 and all(integer(item,0,4) for item in value['appStates'])
        and type(value['bundlePids']) is list and len(value['bundlePids'])==2 and all(integer(item,0,2147483647) for item in value['bundlePids'])
        and type(value['pidChecks']) is list and len(value['pidChecks']) in (0,2))
    for check in value['pidChecks']:
        exact(check,{'pid','running'});need(integer(check['pid'],1,2147483647) and type(check['running']) is bool)


def original(value,nonce,artifact,os_source,previous=None):
    process_source(os_source)
    exact(value,{'iosSnapshotShareExtensionProcessVersion','kind','commandId','instance','sequence','archiveBundleId','receiverBundleId','source','clockDomain',
        'clockBefore','clockAfter','connectionClosed','anchor','appStates','bundlePids','pidChecks'})
    need(artifact['role']=='share-archive' and artifact['extension']['bundle']['bundleId']==artifact['bundle']['bundleId']+'.receiver'
        and type(value['iosSnapshotShareExtensionProcessVersion']) is int and value['iosSnapshotShareExtensionProcessVersion']==1
        and value['kind'] in ('live','retired') and value['commandId']==nonce and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce)
        and value['archiveBundleId']==artifact['bundle']['bundleId'] and value['receiverBundleId']==artifact['extension']['bundle']['bundleId']
        and value['instance']==os_source['instance'] and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
        and integer(value['sequence'],1) and value['source']=='dvt-owned-share-extension-pid-and-bundle-state'
        and value['clockDomain']=='appium-node-host' and value['connectionClosed'] is True)
    stamp(value['clockBefore']);stamp(value['clockAfter'],value['clockBefore']);samples(value)
    need(value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<5000)
    anchor=value['anchor']
    if anchor is None:need(value['kind']=='live' and value['bundlePids']==[0,0] and all(state<2 for state in value['appStates']) and value['pidChecks']==[])
    else:
        exact(anchor,{'sequence','pid','appStates','bundlePids','pidChecks','clockBefore','clockAfter'});samples(anchor)
        need(integer(anchor['sequence'],1,value['sequence']) and integer(anchor['pid'],1,2147483647)
            and anchor['bundlePids']==[anchor['pid']]*2 and all(state>=2 for state in anchor['appStates'])
            and (anchor['appStates'][0]==4)==(anchor['appStates'][1]==4)
            and anchor['pidChecks']==[dict(pid=anchor['pid'],running=True)]*2)
        stamp(anchor['clockBefore']);stamp(anchor['clockAfter'],anchor['clockBefore']);stamp(value['clockAfter'],anchor['clockAfter'])
        need(anchor['clockAfter']['monotonicMs']-anchor['clockBefore']['monotonicMs']<5000
            and len(value['pidChecks'])==2 and all(check['pid']==anchor['pid'] for check in value['pidChecks']))
        if value['kind']=='live':need(value['bundlePids']==anchor['bundlePids'] and all(state>=2 for state in value['appStates'])
            and (value['appStates'][0]==4)==(value['appStates'][1]==4) and value['pidChecks']==anchor['pidChecks'])
        if anchor['sequence']==value['sequence']:need(value['kind']=='live' and same(anchor['clockBefore'],value['clockBefore'])
            and all(same(anchor[key],value[key]) for key in ('appStates','bundlePids','pidChecks')))
        else:stamp(value['clockBefore'],anchor['clockAfter'])
    if previous is not None:
        original(previous,previous['commandId'],artifact,os_source)
        need(value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']);stamp(value['clockBefore'],previous['clockAfter'])
        if previous['anchor'] is not None:need(same(value['anchor'],previous['anchor']))
    return value


def receiver_anchor(value,receiver,artifact,os_source):
    original(value,value['commandId'],artifact,os_source);share.original(receiver)
    need(value['anchor'] is not None and receiver['receiverBundleId']==value['receiverBundleId']
        and receiver['processId']==value['anchor']['pid']);return deepcopy(value['anchor'])


def absent(value,receiver,artifact,os_source):
    anchor=receiver_anchor(value,receiver,artifact,os_source)
    need(value['kind']=='retired' and value['bundlePids']==[0,0] and all(state<2 for state in value['appStates'])
        and value['pidChecks']==[dict(pid=anchor['pid'],running=False)]*2)
    return dict(snapshotShareExtensionAbsenceVersion=1,originalPid=anchor['pid'],instance=value['instance'],sequence=value['sequence'],
        sourceClock=deepcopy(value['clockAfter']),connectionClosed=True,quietWindowRequired=True,wholeFeatureRequired=True)


def stored_original(value,nonce,artifact,os_source,previous=None):
    exact(value,{'snapshotShareExtensionOriginalVersion','commandId','instance','status','raw'})
    need(type(value['snapshotShareExtensionOriginalVersion']) is int and value['snapshotShareExtensionOriginalVersion']==1
        and value['commandId']==nonce and value['instance']==os_source['instance'] and value['status'] in ('issued','complete','failed'))
    if value['status']!='complete':need(value['raw'] is None);return None
    need(type(value['raw']) is str and 1<=len(value['raw'].encode('utf-8'))<=65536)
    return original(decode(value['raw'],limit=65536),nonce,artifact,os_source,previous)


class SnapshotShareArchiveContext(PhotosCompanionContext):
    _admission_owner=IOSSnapshotShareAdmissionOwner
    _runtime=IOSSnapshotShareAdmissionRuntime
    def extension_query(self,nonce,*,retired=False,previous=None):
        need(type(retired) is bool and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce))
        need(self.artifact['extension']['bundle']['bundleId']==self.artifact['bundle']['bundleId']+'.receiver')
        self.admission.bound();before=self.probe()
        command='mobile: overteRetiredSnapshotShareExtensionInfo' if retired else 'mobile: overteSnapshotShareExtensionInfo'
        value=self.client.execute(self.session,command,dict(bundleId=self.target['appId'],commandId=nonce))
        after=self.probe();need(same(before['binding'],after['binding']) and same(before['source'],after['source']))
        original(value,nonce,self.artifact,self.os_scope['source'],previous);return deepcopy(value)
    def extension_original(self,nonce,*,previous=None):
        need(type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce));self.admission.bound();self.probe()
        value=self.client.execute(self.session,'mobile: overteSnapshotShareExtensionOriginal',dict(bundleId=self.target['appId'],commandId=nonce))
        self.probe();stored_original(value,nonce,self.artifact,self.os_scope['source'],previous);return deepcopy(value)
