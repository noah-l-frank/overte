"""Six frozen original source files joined to actual Share/admission bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import re
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_destination import stamp
from ios.adapters.snapshot_share_seal import admitted_outputs

NAMES=('snapshot-share-companion-identity.json','snapshot-share-companion-clock.json','snapshot-share-chunk.json',
    'snapshot-share-retire-intent.json','snapshot-share-retire.json','snapshot-share-retirement-observation.json')


def original(value,nonce,share,seal):
    exact(value,{'snapshotShareSourceInventoryVersion','requestId','processId','bundleId','instance','sourceBirthClock','sourceInstance','admissionSealSha256',
        'clockBefore','clockAfter','parentIdentity','outputs','frozen','current','readersClosed'})
    sealed,sealed_raw=seal.original();seal.proof();share.cleanup_proof();_last,_identity,admission_raw=admitted_outputs(seal.admission)
    last=share.state['cleanup']['after'][-1];need(last['qualified'] is True);observation_raw=share.archive_source(last['source']);observation=decode(observation_raw.decode('utf-8'))
    expected={NAMES[0]:admission_raw['identity'],NAMES[1]:admission_raw['clock'],NAMES[2]:share.archive_source(share.state['chunks'][-1]),NAMES[5]:observation_raw}
    need(type(value['snapshotShareSourceInventoryVersion']) is int and value['snapshotShareSourceInventoryVersion']==1
        and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce) and value['requestId']==nonce and nonce!=sealed['requestId']
        and integer(value['processId'],1,2147483647) and value['processId']==sealed['processId'] and value['bundleId']==sealed['bundleId']
        and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance']) and value['sourceInstance']==sealed['instance']
        and value['admissionSealSha256']==hashlib.sha256(sealed_raw).hexdigest() and type(value['parentIdentity']) is str
        and value['parentIdentity']==sealed['outputs'][0]['parentIdentity'] and all(type(value[key]) is bool for key in ('frozen','current','readersClosed')))
    stamp(value['sourceBirthClock']);stamp(value['clockBefore'],value['sourceBirthClock']);stamp(value['clockBefore'],sealed['clockAfter'])
    stamp(value['clockBefore'],observation['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<1500 and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<1500
        and type(value['outputs']) is list and len(value['outputs'])==6)
    for name,pin in zip(NAMES,value['outputs']):
        embedded=name in NAMES[3:5];exact(pin,{'name','revision','sha256','byteCount','parentIdentity'}|({'data'} if embedded else set()))
        need(pin['name']==name and type(pin['revision']) is str and re.fullmatch('[a-f0-9]{64}',pin['revision'])
            and pin['parentIdentity']==value['parentIdentity'] and integer(pin['byteCount'],1,720896))
        if embedded:
            need(type(pin['data']) is str and len(pin['data'])<=349528);raw=base64.b64decode(pin['data'],validate=True)
            need(1<=len(raw)<=262144 and base64.b64encode(raw).decode()==pin['data']);expected[name]=raw
        raw=expected[name];need(pin['sha256']==hashlib.sha256(raw).hexdigest() and pin['byteCount']==len(raw))
    need(all(same(value['outputs'][index],sealed['outputs'][index]) for index in range(2)))
    retired=decode(expected[NAMES[4]].decode('utf-8'));intent=decode(expected[NAMES[3]].decode('utf-8'))
    need(same(retired,observation['retirement']) and same(intent,dict(retired,clockAfter=None,steps=[],complete=False,readersClosed=False)))
    return value


def qualified(value):need(value['frozen'] is True and value['current'] is True and value['readersClosed'] is True);return value
