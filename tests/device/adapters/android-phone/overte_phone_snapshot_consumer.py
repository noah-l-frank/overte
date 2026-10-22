"""Independent separate-UID ACTION_SEND consumer. ACK is never consumption.

Its DUMP-protected provider accepts only existing IDs. Fresh observation and
binary nonces are generated here, not loaded from cached target output.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
import shlex
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_exports import uri
from overte_phone_snapshot_readbacks import nonce,share_grants
from snapshot_observation import MAX_BYTES

PACKAGE='org.overte.e2e.snapshotreceiver'
COMPONENT=PACKAGE+'/org.overte.snapshot.SnapshotConsumer'
AUTHORITY=PACKAGE+'.evidence'
ROOTS={'/data/'+base+'/'+PACKAGE+'/files/' for base in ('user/0','data')}


def source(value,run,arm,observation,identity,epoch):
    exact(value,{'snapshotConsumerVersion','runId','armId','observationId','instance','sequence','capturedEpochMs',
        'complete','phase','activityAlive','cancelled','identity','original','startedEpochMs','completedEpochMs',
        'grantPresent','originalClosed','files','removedCopies','retired','workersTerminated','processId','receiverUid','receiverPackage'})
    need(type(value['snapshotConsumerVersion']) is int and value['snapshotConsumerVersion']==1 and value['runId']==run and value['armId']==arm
        and value['observationId']==observation and nonce(value['instance']) and integer(value['sequence'],1)
        and value['complete'] is True and value['phase'] in ('armed','queued','reading','complete','failed')
        and all(type(value[key]) is bool for key in ('activityAlive','cancelled','grantPresent','originalClosed','retired','workersTerminated'))
        and value['receiverPackage']==PACKAGE and type(value['processId']) is int and value['processId']==identity['processId']
        and type(value['receiverUid']) is int and value['receiverUid']==identity['uid']
        and integer(value['startedEpochMs'],0,value['capturedEpochMs']) and integer(value['completedEpochMs'],0,value['capturedEpochMs']))
    fresh(value['capturedEpochMs'],epoch)
    if value['phase'] in ('armed','queued'):need(value['startedEpochMs']==value['completedEpochMs']==0 and value['original'] is None)
    elif value['phase']=='reading':need(value['startedEpochMs']>0 and value['completedEpochMs']==0 and value['original'] is None)
    else:need(value['startedEpochMs']>0 and value['completedEpochMs']>=value['startedEpochMs'])
    if value['identity'] is not None:
        row=value['identity'];exact(row,{'uri','providerPackage','providerUid','receiverUid','receiverPid','receiverPackage','component','readFlag','clipUri','permissionAtOpen'})
        parsed=uri(row['uri']);need(parsed.netloc=='io.github.noah_be.overte.phone.snapshot.files'
            and re.fullmatch('/snapshots/[^/]+',parsed.path) and row['clipUri']==row['uri'] and row['readFlag'] is True
            and row['providerPackage']=='io.github.noah_be.overte.phone' and integer(row['providerUid'],1)
            and row['providerUid']!=value['receiverUid'] and row['receiverUid']==value['receiverUid'] and row['receiverPid']==value['processId']
            and row['receiverPackage']==PACKAGE and row['component']==COMPONENT and type(row['permissionAtOpen']) is bool)
    need(type(value['files']) is list and len(value['files'])<=64 and type(value['removedCopies']) is list and len(value['removedCopies'])<=64)
    files={}
    for row in value['files']:
        receiver_original(row,value['capturedEpochMs'],arm);need(row['id'] not in files);files[row['id']]=row
    need(len(set(value['removedCopies']))==len(value['removedCopies']) and all(nonce(id) and id not in files for id in value['removedCopies']))
    if value['original'] is not None:
        row=value['original'];receiver_original(row,value['completedEpochMs'],arm)
        need(value['phase']=='complete' and row['phase']=='complete' and value['originalClosed'] and not value['cancelled']
            and value['identity'] is not None and value['identity']['permissionAtOpen'] is True
            and (files.get(row['id'])==row or row['id'] in value['removedCopies']))
    if value['phase']=='complete':need(value['original'] is not None)
    if value['retired']:need(not files and not value['activityAlive'] and not value['grantPresent'] and value['originalClosed'] and value['phase'] not in ('queued','reading'))
    if value['workersTerminated']:need(value['retired'])
    return value


def receiver_original(value,epoch,arm):
    # Reuse the original closed copy grammar with this independent APK root.
    exact(value,{'id','request','path','phase','bytes','sha256','capturedEpochMs'})
    need(nonce(value['id']) and value['request']==arm and type(value['path']) is str
        and any(re.fullmatch(re.escape(root)+r'overte-snapshot-e2e-[0-9a-f]{32}/'+value['id']+r'\.bin',value['path']) for root in ROOTS)
        and value['phase'] in ('planned','reading','failed','complete') and integer(value['bytes'],0,MAX_BYTES) and integer(value['capturedEpochMs'],0,epoch))
    if value['phase']=='complete' or value['bytes']:need(value['bytes']>0 and re.fullmatch('[0-9a-f]{64}',value['sha256']) and value['capturedEpochMs']>0)
    else:need(value['sha256']=='' and value['capturedEpochMs']==0)


def continuity(before,after):
    need(all(after[key]==before[key] for key in ('runId','armId','instance','processId','receiverUid','receiverPackage'))
        and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs']
        and after['removedCopies'][:len(before['removedCopies'])]==before['removedCopies']
        and (not before['retired'] or after['retired']) and (not before['cancelled'] or after['cancelled']))
    for key in ('identity','original'):
        if before[key] is not None:need(after[key]==before[key])
    if before['phase'] in ('complete','failed'):need(after['phase']==before['phase'] and after['startedEpochMs']==before['startedEpochMs'] and after['completedEpochMs']==before['completedEpochMs'])
    elif before['phase']=='queued':need(after['phase']!='armed')
    elif before['phase']=='reading':need(after['phase'] not in ('armed','queued') and after['startedEpochMs']==before['startedEpochMs'])


class PhoneSnapshotConsumer:
    def __init__(self,read,read_binary,control,identity,clock_ms,guard,run,arm,*,read_only=True,binding=None,monotonic=time.monotonic,sleep=time.sleep):
        need(nonce(run) and nonce(arm) and type(read_only) is bool and all(callable(fn) for fn in (read,read_binary,control,identity,clock_ms,guard,monotonic,sleep)))
        self.read,self.binary,self.send,self.identity,self.clock_ms,self.guard=read,read_binary,control,identity,clock_ms,guard
        self.run,self.arm,self.read_only,self.monotonic,self.sleep=run,arm,read_only,monotonic,sleep
        self.last,self.bound,self.source_instance=None,None,None
        if binding is not None:
            exact(binding,{'installed','instance'});need(nonce(binding['instance']))
            self.bound=deepcopy(binding['installed']);self.source_instance=binding['instance']

    def binding(self):
        need(self.bound is not None and self.source_instance is not None)
        return dict(installed=deepcopy(self.bound),instance=self.source_instance)

    def _identity(self):
        need(self.guard() is not False);value=self.identity()
        exact(value,{'package','apkSha256','uid','processId','processIdentity'})
        need(value['package']==PACKAGE and type(value['apkSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['apkSha256'])
            and integer(value['uid'],1) and integer(value['processId'],1) and type(value['processIdentity']) is str
            and re.fullmatch(str(value['processId'])+':[0-9]+',value['processIdentity']))
        if self.bound is None:self.bound=deepcopy(value)
        else:need(self.bound==value)
        return value

    def observe(self):
        try:
            start=self.monotonic();epoch=self.clock_ms();identity=self._identity();id=uuid.uuid4().hex
            raw=self.read(self.run,id);need(type(raw) is bytes and len(raw)<=262144)
            row=source(decode(raw.decode('utf-8')),self.run,self.arm,id,identity,self.clock_ms())
            need(row['capturedEpochMs']>=epoch and self._identity()==identity and number(self.monotonic(),start,1e15) and self.monotonic()-start<5)
            if self.source_instance is None:self.source_instance=row['instance']
            else:need(row['instance']==self.source_instance)
            if self.last is not None:continuity(self.last,row)
            self.last=deepcopy(row);return deepcopy(row)
        except Exception:raise NativeUIError('Original separate Snapshot consumer is unavailable or invalid') from None

    def control(self,operation,copy_id=''):
        try:
            need(not self.read_only and operation in ('arm','cancel','remove-copy','retire'))
            need(nonce(copy_id) if operation=='remove-copy' else copy_id=='');need(self.guard() is not False)
            # The return is an acknowledgement only. Consumers always observe.
            self.send(operation,self.run,self.arm if operation=='arm' else copy_id)
            need(self.guard() is not False)
        except Exception:raise NativeUIError('Snapshot consumer control is unavailable or unauthorized') from None

    def acquire(self,native_share,capture):
        try:
            before=self.observe();need(before['phase']=='complete' and before['original'] is not None and not before['retired'])
            original=before['original'];identity=before['identity'];need(type(native_share) is dict and type(capture) is dict
                and integer(capture.get('bytes'),1,MAX_BYTES) and type(capture.get('sha256')) is str and re.fullmatch('[0-9a-f]{64}',capture['sha256']))
            share_grants(dict(snapshotShareGrantsVersion=1,complete=True,checkId='',checkedEpochMs=0,rows=[native_share]),before['capturedEpochMs'])
            need(native_share['uri']==identity['uri'] and native_share['ownerUid']==identity['providerUid']
                and native_share['component']==identity['component'] and native_share['receiverUid']==identity['receiverUid'])
            content=self.binary(self.run,original['id'],uuid.uuid4().hex)
            need(type(content) is bytes and 0<len(content)<=MAX_BYTES and len(content)==original['bytes']
                and hashlib.sha256(content).hexdigest()==original['sha256'] and original['bytes']==capture['bytes'] and original['sha256']==capture['sha256'])
            after=self.observe();need(after['identity']==identity and after['original']==original and not after['retired'])
            return dict(source='snapshot-receiver-original',request=native_share['request'],copy=original['id'],bytes=len(content),sha256=original['sha256'],capturedEpochMs=before['completedEpochMs']),content
        except Exception:raise NativeUIError('Original shared Snapshot bytes or receiver correlation is invalid') from None

    def require_retired(self):
        row=self.observe();need(row['retired'] and row['workersTerminated'] and not row['activityAlive'] and not row['grantPresent'] and row['originalClosed'] and not row['files'])
        return row

    def acquire_current(self,native_share,capture):
        """Fresh binary acquisition with the original completion kept separate."""
        try:
            started=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms()
            value,raw=self.acquire(native_share,capture)
            epoch=self.clock_ms();now=self.monotonic()
            need(integer(epoch,requested) and number(now,started,1e15) and now-started<5
                and self.last is not None and self.last['capturedEpochMs']>=requested)
            fresh(self.last['capturedEpochMs'],epoch);need(self.guard() is not False)
            return dict(value,capturedEpochMs=epoch,originalCompletedEpochMs=value['capturedEpochMs']),raw
        except Exception:raise NativeUIError('Current original shared Snapshot acquisition failed') from None


class SnapshotConsumerTransport:
    """Fixed shell/DUMP route; caller supplies a separately prepared APK pin.

    No install/discovery/launch-image shortcut. Identity is freshly acquired from
    OS package path+digest, run-as UID and original pid/start ticks on every read.
    """
    def __init__(self,adb,selector,apk_sha256,guard,*,read_only=True):
        need(type(selector) is str and selector and type(apk_sha256) is str and re.fullmatch('[0-9a-f]{64}',apk_sha256)
            and callable(guard) and type(read_only) is bool)
        self.adb,self.selector,self.pin,self.guard,self.read_only=adb,selector,apk_sha256,guard,read_only

    def _execute(self,*arguments,binary=False):
        need(self.guard() is not False)
        remote=' '.join(shlex.quote(value) for value in arguments)
        raw=self.adb.execute_bytes(['exec-out',remote],target=self.selector,timeout=5) if binary else self.adb.execute(['shell',remote],target=self.selector,timeout=5)
        need(self.guard() is not False);return raw

    def _installed(self):
        path=self._execute('pm','path',PACKAGE).strip().splitlines();need(len(path)==1 and path[0].startswith('package:'))
        apk=path[0][8:];need(re.fullmatch('/data/app/[A-Za-z0-9_+=.~/-]+/base[.]apk',apk) and '..' not in apk.split('/'))
        digest=self._execute('sha256sum',apk).strip().split();need(len(digest)==2 and digest[0]==self.pin and digest[1]==apk)
        uid=self._execute('run-as',PACKAGE,'id','-u').strip();need(re.fullmatch('[1-9][0-9]*',uid))
        return digest[0],int(uid)

    def identity(self):
        digest,uid=self._installed()
        process=self.adb.process_state(self.selector,PACKAGE);need(self.guard() is not False)
        need(process.get('running') is True and type(process.get('identity')) is str and re.fullmatch('[1-9][0-9]*:[0-9]+',process['identity']))
        return dict(package=PACKAGE,apkSha256=digest,uid=uid,processId=int(process['identity'].split(':')[0]),processIdentity=process['identity'])

    def read(self,run,id):
        need(nonce(run) and nonce(id));return self._execute('content','read','--uri','content://'+AUTHORITY+'/observations/'+run+'/'+id,binary=True)

    def binary(self,run,copy,id):
        need(nonce(run) and nonce(copy) and nonce(id));return self._execute('content','read','--uri','content://'+AUTHORITY+'/originals/'+run+'/'+copy+'/'+id,binary=True)

    def control(self,operation,run,id):
        need(not self.read_only and nonce(run) and operation in ('arm','cancel','remove-copy','retire')
            and (nonce(id) if operation in ('arm','remove-copy') else id==''))
        args=['content','call','--uri','content://'+AUTHORITY,'--method',operation,'--extra','runId:s:'+run]
        if id:args+=['--extra',('armId' if operation=='arm' else 'copyId')+':s:'+id]
        before=self._installed();ack=self._execute(*args);need(self._installed()==before);return ack
