"""Producer-only native/SDK/OS seams for the unchanged Snapshot public journey.

No feature verb, scenario expected state or witness fact is accepted by this
transport. Ordinary widget commands mutate UI; native callbacks, actual host
files and real TLS replies independently supply effect-source observations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from collections import Counter
from contextlib import nullcontext, ExitStack
import os
import re
import shlex
import subprocess
from unittest.mock import patch
import hashlib
import base64
from urllib.error import HTTPError
import io
import json
from pathlib import Path
import time
from types import SimpleNamespace
import uuid
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from feature_journeys.account_provider import PROFILE_PATH,RUN_HEADER,TICKET_HEADER,REQUEST_HEADER

from PIL import Image,ImageDraw
from create_feature_target import Target as CreateTarget,Proxy as CreateProxy,RUN,DOMAIN,POLICY
from test_snapshot_ui import Product
from test_snapshots_role import SnapshotRolesBoundary
from test_snapshot_settings import Boundary as Settings
from test_snapshot_capture_files import Producer,LocalTransport
from test_snapshot_measurements import Boundary as Vm
from self_tests.test_native_account_observation import account,event,append
from adapters.native_script_roots import NativeScriptRoots
from adapters.native_script_observation import NativeScriptObservation
from overte_phone_snapshot_source import PhoneSnapshotSource
from overte_phone_snapshot_handoff import PhoneSnapshotHandoff,PhoneSnapshotHandoffControl
from overte_phone_snapshot_system_context import SnapshotSystemContext
from overte_phone_snapshot_system_ui import PhoneSnapshotSystemUI,RECEIVER_COMPONENT,LABEL
from overte_phone_snapshot_consumer import PhoneSnapshotConsumer
from overte_phone_snapshot_saved_files import PhoneSnapshotSavedFiles
from test_snapshot_saved_files import SdkBoundary as SavedSdk
from test_snapshot_consumer_source import Boundary as Consumer
from test_snapshot_os_retirement_source import boundary as readback_seed
from adapters.normal_ui import NativeUI
from overte_phone_snapshot_measurements import PhoneSnapshotMeasurements
from overte_phone_snapshot_controls import PhoneSnapshotIO
from overte_phone_snapshot_ui import PhoneSnapshotControls
from overte_phone_snapshot_settings import PhoneSnapshotSettings
from overte_phone_snapshot_capture_source import PhoneSnapshotCaptureFileSource
from overte_phone_snapshot_capture_files import PhoneSnapshotCaptureFiles
from overte_phone_snapshot_platform import PhoneSnapshotPlatform
from overte_phone_snapshot_cancel import PhoneSnapshotCancel
from adapters.native_script_work import NativeScriptWork
from self_tests.test_native_script_work import ScopedWorkBoundary,activity
from overte_phone_snapshot_readbacks import PhoneSnapshotReadbacks
from overte_phone_snapshot_upload_source import PhoneSnapshotUploadSource
from overte_phone_snapshot_system_ui import PRIMARY
from feature_journeys.fixtures import marker_bytes


def now():return time.time_ns()//1000000


class HostOnlyBoundary(ExitStack):
    """Fail before any unprovisioned Android transport or adb subprocess."""
    def __enter__(self):
        super().__enter__()
        original = subprocess.Popen
        def guarded(command, *args, **kwargs):
            words = shlex.split(command) if isinstance(command, str) else list(command)
            executable = os.path.basename(os.fsdecode(words[0])) if words else ''
            allowed = {'sh','bash','dash','python','python3',Path(__import__('sys').executable).name,
                       'openssl','java','javac'}
            override = kwargs.get('executable')
            override_name = os.path.basename(os.fsdecode(override)) if override is not None else executable
            if (executable not in allowed or override_name != executable
                    or (kwargs.get('shell') and not isinstance(command,str))):
                raise AssertionError('Device subprocess forbidden: unprovisioned host command')
            shell_text = command if kwargs.get('shell') else (
                words[-1] if executable in ('sh','bash','dash') and '-c' in words else '')
            if isinstance(shell_text,str) and re.search(r'(?<![\w-])(?:[^\s;/]+/)?adb(?:\.exe)?(?=\s|$|[;&|])',shell_text):
                raise AssertionError('Device subprocess forbidden in host Snapshot replay')
            return original(command, *args, **kwargs)
        self.enter_context(patch('subprocess.Popen', guarded))
        self.enter_context(patch('adb_transport.AdbTransport.__init__', side_effect=AssertionError(
            'Unprovisioned Android transport forbidden in host Snapshot replay')))
        return self


class SnapshotProduct(Product):
    def __init__(self,model):self.model=model;super().__init__()
    def send(self,command):
        self.epoch=self.model.now()
        request=command['request']
        if request['action']!='observe':
            self.refresh();rows=[row for row in self.controls if row['id']==request['controlId']]
            if (request['instance']!=self.instance or request['generation']!=self.generation
                    or request['sequence']!=self.commands+1 or len(rows)!=1
                    or rows[0]['token']!=request['controlToken'] or not rows[0]['enabled'] or not rows[0]['inputReady']):
                raise RuntimeError('Original live Snapshot widget admission rejected the input')
            if request['action']=='replace' and not rows[0]['focused']:
                raise RuntimeError('Original Snapshot text field is not focused')
            self.intents.append(dict(request=deepcopy(request)))
        super().send(command)
        request=command['request']
        if request['action']!='observe' and request['controlId'] not in self.ignored:
            self.model.widget(request)
    def refresh(self):
        super().refresh()
        if self.shown and self.page=='snapshot':
            page=self.controls[0];page.update(statusError=bool(self.model.ui_error),statusText=self.model.ui_error,capturing=self.model.pending_capture)
            if self.model.pending_capture:self.controls.append(self.row('snapshot.cancel-capture'))
    def open_tablet(self):super().open_tablet();self.model.tablet=self.shown
    def close_tablet(self):super().close_tablet();self.model.tablet=self.shown


class SnapshotTarget(CreateTarget):
    def __init__(self,root,sdk=29):
        self.query_epoch=now();self.rpc_counts=Counter()
        super().__init__(root,SimpleNamespace(process=SimpleNamespace(pid=31,poll=lambda:None)))
        # Reuse only the raw original-source/capture producers, never its
        # pre-completed feature or the reducer's already projected state.
        (root/'original-producers').mkdir(mode=0o700)
        self.seed=SnapshotRolesBoundary(root/'original-producers')
        self.vm=self.seed.vm;self.vm.snapshot.events=[];self.script_events=[]
        compiled=(Path(__file__).resolve().parents[4]/'scripts/system/snapshot.js').read_text().encode('utf-16-le',errors='surrogatepass')
        actual=dict(encoding='utf-16le-code-units',codeUnits=len(compiled)//2,sha256=hashlib.sha256(compiled).hexdigest())
        self.vm.code.update(actual);self.vm.compilation.update(actual)
        self.vm.snapshot.fault=self.snapshot_fault
        self.producer=Producer(root/'snapshot-app');self.producer.outer='a'*32;self.lease_settings=Settings();self.lease_settings.epoch=now()
        self.ui_error='';self.pending_capture=False;self.product=SnapshotProduct(self);self.sdk=sdk
        self.component=PRIMARY+'/'+PRIMARY+'.MainActivity';self.app_state=4;self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        self.account=account();self.account['observation']['credentialActive']=True
        self.story_id=None;self.origin=None;self.token=None;self.opener=None;self.raw_png=None;self.current_path=None
        self.handoff=None;self.job_sources={};self.model_binding=None;self.work_packets={};self.export_tickets={};self.marker_seen=False;self.marker_command=None;self.marker_receipt=None
        self.readbacks=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True)
        self.consumer=None;self.os_files={};self.handoff_jobs={};self.handoff_last=None;self.handoff_count=0
        self.upload=dict(snapshotUploadObservationVersion=1,instance='7'*32,complete=True,capturedEpochMs=now(),sequence=0,events=[],jobs=[])
    def now(self):return self.query_epoch
    def close(self):
        # CreateTarget.settings is its separate ordinary domain settings server.
        super().close()
    def snapshot_fault(self,packet):
        packet['instance']='a'*32
        packet['source']['scriptHistory'].update(sequence=len(self.script_events),events=deepcopy(self.script_events))
        packet['source']['review']=self.review()
    def review(self):
        if not(self.product.shown and self.product.page=='snapshot'):return dict(snapshotReviewObservationVersion=1,present=False,review=None)
        return dict(snapshotReviewObservationVersion=1,present=True,review=dict(componentUrl='file:///original/scripts/system/snapshot/NativeSnapshotReview.qml',visible=True,
            capturing=self.pending_capture,processing=False,loggedIn=self.account['loggedIn'],canShare=True,canBlast=False,statusError=bool(self.ui_error),captureSettingsLoaded=True,
            statusText=self.ui_error,uploadPath='',exportTicket='',mode=self.product.mode,format=('png','webp')[self.product.format],capabilities=['save','share'],
            exportBusy=False,exportError='',images=[] if self.current_path is None else [dict(path=self.current_path,storyPresent=self.story_id is not None)]))
    def image(self):
        image=Image.new('RGBA',(1000,750),(70,90,120,255));draw=ImageDraw.Draw(image)
        for y in range(80,700,30):
            for x in range(220,780,40):draw.rectangle((x,y,x+39,y+29),fill=(230,70,30,255) if (x//40+y//30)%2 else (30,170,210,255))
        with Image.open(io.BytesIO(marker_bytes(RUN,self.ticket))) as card:image.paste(card,(20,20))
        out=io.BytesIO();image.save(out,format='PNG');return out.getvalue()
    def marker_input(self,request):
        from overte_phone_create_marker import input_command,current_input
        input_command(request)
        if request['runId']!=RUN:raise RuntimeError('Original marker run required')
        if self.marker_command is not None and request['commandId']==self.marker_command['commandId']:
            if request!=self.marker_command:raise RuntimeError('Original marker command changed')
            return deepcopy(self.marker_receipt)
        if request['operation']=='prepare':
            if self.marker_seen:raise RuntimeError('Native marker owner cannot be prepared twice for the same run')
        elif request['operation']=='refresh':
            if (not self.marker_active or self.marker['phase']!='active' or request['fixtureInstance']!=self.marker['fixtureInstance']
                    or len(self.marker['objects'])!=3 or len(self.marker['entities'])!=3):
                raise RuntimeError('Original active marker refresh owner required')
            inputs=[self.marker['originalInput'],*[row['input'] for row in self.marker.get('refreshes',[])]]
            if len(inputs)>256 or any(row['commandId']==request['commandId'] or row['ticket']==request['ticket'] for row in inputs):
                raise RuntimeError('Original marker refresh input cannot replay')
            for row in self.marker['entities']:
                if (not row['originalObject'] or row['hostType']!='local' or row['locked'] or row['parentId']!='00000000-0000-0000-0000-000000000000'
                        or not any(item['id']==row['id'] and item['role']==row['role'] for item in self.marker['objects'])):
                    raise RuntimeError('Original marker entity was replaced')
            row=next(row for row in self.marker['entities'] if row['role']=='marker')
            root=self.marker['originalInput']['fixtureUrl']
            if row['sourceUrl']!=root+'tickets/'+current_input(self.marker)['ticket']+'/graphics-marker.v1.html':
                raise RuntimeError('Original marker URL changed before refresh')
            row.update(sourceUrl=root+'tickets/'+request['ticket']+'/graphics-marker.v1.html',lastEditedEpochUs=self.now()*1000)
            self.marker.update(phoneCreateFixtureVersion=3,lastRefreshInput=deepcopy(request),
                refreshes=[*self.marker.get('refreshes',[]),dict(input=deepcopy(request),editedEpochMs=self.now())])
            self.ticket=request['ticket']
            receipt=dict(phoneCreateFixtureInputVersion=1,commandId=request['commandId'],runId=RUN,fixtureInstance=self.marker['fixtureInstance'],operation='refresh',recorded=True)
            self.marker_command=deepcopy(request);self.marker_receipt=deepcopy(receipt)
            return receipt
        elif request['operation']=='release':
            if not self.marker_seen or request['fixtureInstance']!=self.marker['fixtureInstance']:
                raise RuntimeError('Original marker release owner required')
        else:raise RuntimeError('Unsupported native marker operation')
        receipt=super().marker_input(request)
        if request['operation']=='prepare':self.ticket=request['ticket'];self.marker_seen=True
        self.marker_command=deepcopy(request);self.marker_receipt=deepcopy(receipt)
        return receipt
    def capture_packet(self,request):
        packet=super().capture_packet(request);raw=self.image()
        with Image.open(io.BytesIO(raw)) as image:
            packet['source']['image'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),pixelSha256=hashlib.sha256(image.tobytes()).hexdigest())
        self.world.storage.raw=raw;self.capture=deepcopy(packet);return packet
    def script_event(self,kind,id,mode):
        epoch=self.now();row=self.vm.event(kind,len(self.script_events)+1)
        row.update(id=id,mode=mode,capturedEpochMs=epoch)
        row['caller'].update(sequence=len(self.script_events)+1,invokedEpochMs=epoch)
        row['caller']['snapshotWork'].update(capturedEpochMs=epoch,signalInvocations=len(self.script_events)+1)
        self.script_events.append(row);return row
    def login(self,credentials):
        raw=urlencode(dict(grant_type='password',scope='owner',**credentials)).encode()
        with urlopen(Request(self.origin+'/oauth/token',data=raw,headers={'Content-Type':'application/x-www-form-urlencoded'}),timeout=3) as reply:
            status=reply.code;grant=json.loads(reply.read())
        generation=self.account['observation']['credentialGeneration']+1
        append(self.account,event(len(self.account['observation']['events'])+1,'login-reply',self.now(),generation,status))
        self.account['observation']['events'][-1]['networkError']=0
        self.token=grant['access_token']
        ticket=self.service.runs[RUN]['ticket']
        headers={'Authorization':'Bearer '+self.token,RUN_HEADER:RUN,TICKET_HEADER:ticket,REQUEST_HEADER:uuid.uuid4().hex}
        with urlopen(Request(self.origin+PROFILE_PATH,headers=headers),timeout=3) as reply:
            status=reply.code;profile=json.loads(reply.read())
        principal=profile['data']['user']['username']
        append(self.account,event(len(self.account['observation']['events'])+1,'profile-reply',self.now(),generation,status))
        self.account['observation']['events'][-1]['networkError']=0
        self.account.update(loggedIn=True,principalSha256=hashlib.sha256(principal.encode()).hexdigest())
        self.account['observation'].update(credentialActive=True,tokenPresent=True,tokenValid=True)

    def widget(self,request):
        id=request['controlId']
        if id=='snapshot.cancel-capture':
            self.pending_capture=False;self.script_event('cancelled',self.script_events[-1]['id'],'animated')
        elif id=='snapshot.capture':
            if self.story_id is not None:
                self.product_http('DELETE','/api/v1/user_stories/'+str(self.story_id),b'','application/json');self.story_id=None
            capture='snap_'+str(self.now())+'_'+str(len(self.producer.body['captures'])+1)
            self.script_event('pending',capture,('still','animated','panorama','cubemap')[self.product.mode])
            if self.product.mode==1:
                self.pending_capture=True
                row=self.script_events[-1];row['caller']['snapshotWork']['timers']=[dict(handle=i,active=True,singleShot=True,intervalMs=ms,remainingMs=ms) for i,ms in ((1,350),(2,60000))]
                row['caller']['snapshotWork']['timerRegistrations']=2
            if self.product.mode==0:
                self.producer.epoch=self.now();row,path=self.producer.capture();path.write_bytes(self.image())
                # The source names originate from the actual producer-created
                # output, and all bytes/inodes are measured from that file.
                row['captureId']=capture;self.producer.body['captures'][-1]['captureId']=capture
                row.update(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                self.current_path=row['path'];self.product.image=self.current_path;self.raw_png=path.read_bytes()
                self.vm.snapshot.epoch=self.now();self.vm.snapshot.event('capture-begin',capture)
                self.vm.snapshot.event('capture-status',capture,'complete',self.current_path)
                self.script_event('complete',capture,'still')
        elif id.startswith('snapshot.save.'):
            self.save_image()
        elif id.startswith('snapshot.share.'):
            self.share_image()
        elif id.startswith('snapshot.upload.'):
            self.upload_image()
    def product_http(self,method,path,raw,content_type):
        headers={'Content-Type':content_type,'Authorization':'Bearer '+self.token}
        status=0;reply=b'';response_id='';error=0
        try:
            try:response=urlopen(Request(self.origin+path,data=raw if method=='POST' else None,method=method,headers=headers),timeout=3)
            except HTTPError as actual:response=actual
            with response:
                status=response.code;reply=response.read();response_id=response.headers.get('X-Overte-Fixture-Response','')
                if status>=400:error=2
        except (OSError,__import__('http.client').client.RemoteDisconnected):error=2
        row=dict(id=uuid.uuid4().hex,stage='image' if path=='/api/v1/snapshots' else 'story',url=self.origin+path,operation=4,
            authRequired=True,authorizationPresent=bool(self.token),multipart=path=='/api/v1/snapshots',boundary='owned-qt-boundary' if path=='/api/v1/snapshots' else '',
            jsonBytes=len(raw) if path=='/api/v1/user_stories' else 0,jsonSha256=hashlib.sha256(raw if path=='/api/v1/user_stories' else b'').hexdigest(),
            dispatchCurrent=True,sentBytes=len(raw),totalBytes=len(raw),finished=True,destroyed=True,status=status,networkError=error,
            responseId=response_id,replyBytes=len(reply),replySha256=hashlib.sha256(reply).hexdigest(),replyBase64=base64.b64encode(reply).decode())
        return row,reply
    def upload_image(self):
        from test_snapshot_upload_service import body
        self.ui_error='';id=uuid.uuid4().hex;path=self.root/'snapshot-app/files/Snapshots'/Path(self.current_path).name
        raw=path.read_bytes();info=path.stat();requests=[];terminal='error'
        query=urlencode(dict(now='2026-10-22T12:00:00Z',include_actions='concurrency',domain_id=DOMAIN,restriction='open,hifi'))
        self.product_http('GET','/api/v1/user_stories?'+query,b'','application/json')
        image,reply=self.product_http('POST','/api/v1/snapshots',body(raw,filename=Path(self.current_path).name),'multipart/form-data; boundary=owned-qt-boundary');requests.append(image)
        if image['status']==200:
            resource=json.loads(reply)['data'];details={key:resource[key] for key in ('image_url','original_image_file_name')};details['snapshot_id']=resource['id']
            story=dict(user_story=dict(details=json.dumps(details),thumbnail_url=resource['thumbnail_url'],place_name='Owned domain',path='/1,2,3',action='snapshot',audience='for_url'))
            published,reply=self.product_http('POST','/api/v1/user_stories',json.dumps(story).encode(),'application/json');requests.append(published)
            if published['status']==200:self.story_id=json.loads(reply)['user_story']['id'];terminal='success'
        if terminal=='error':self.ui_error='Snapshot upload failed'
        job=dict(id=id,path=self.current_path,href='hifi://owned/1,2,3',uploaderAlive=False,fileAlive=False,multipartAlive=False,
            file=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),device=info.st_dev,inode=info.st_ino,readBytes=len(raw),readSha256=hashlib.sha256(raw).hexdigest()),
            cancelRequested=False,terminal=terminal,requests=requests)
        self.upload['jobs'].append(job);self.upload['jobs'].sort(key=lambda job:job['id'])
        for kind in ('begin','file-open','multipart-created','terminal','uploader-destroyed','file-destroyed','multipart-destroyed'):
            self.upload['events'].append(dict(sequence=len(self.upload['events'])+1,jobId=id,kind=kind,capturedEpochMs=self.now()))
        self.upload.update(sequence=len(self.upload['events']),capturedEpochMs=self.now())
    def initialize_readbacks(self):
        if self.readbacks.get('initialized') is False:
            self.readbacks=readback_seed().component
            self.readbacks.update(copiesRetired=False,workersTerminated=False,destinations=[],jobs=[],files=[],removedCopies=[])
            self.readbacks['osDestinations']['rows']=[]
    def export_event(self,kind,value='',auxiliary='',*,request,action):
        self.export_tickets.setdefault(request,str(len(self.export_tickets)+1))
        self.vm.snapshot.epoch=self.now();self.vm.snapshot.export_event(kind,value,auxiliary,request=request,action=action,ticket=self.export_tickets[request])
        self.vm.snapshot.export_events[-1]['source']=self.current_path
    def save_image(self):
        self.initialize_readbacks();request=uuid.uuid4().hex;id=uuid.uuid4().hex;copy=uuid.uuid4().hex
        directory=self.root/'snapshot-app/files'/('overte-snapshot-e2e-'+'e'*32);directory.mkdir(mode=0o700,exist_ok=True)
        path=directory/(copy+'.bin');path.write_bytes(self.raw_png);path.chmod(0o600)
        osroot=self.root/'os-destinations';osroot.mkdir(mode=0o700,exist_ok=True);destination=osroot/id;destination.write_bytes(path.read_bytes());info=destination.stat()
        self.os_files[request]=destination;uri='content://media/external/images/media/'+str(len(self.os_files)+400)
        original=dict(id=copy,request=request,path='/data/user/0/'+PRIMARY+'/files/'+directory.name+'/'+path.name,phase='complete',
            bytes=info.st_size,sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),capturedEpochMs=self.now())
        self.readbacks['files'].append(original);self.readbacks['jobs'].append(dict(id=id,request=request,phase='complete',startedEpochMs=self.now(),completedEpochMs=self.now(),original=deepcopy(original)))
        self.readbacks['jobs'].sort(key=lambda row:row['id']);self.readbacks['files'].sort(key=lambda row:row['id'])
        self.readbacks['destinations'].append(dict(request=request,uri=uri,inserted=True,published=True));self.readbacks['destinations'].sort(key=lambda row:row['request'])
        self.readbacks['osDestinations']['rows'].append(dict(request=request,inserted=True,phase='qualified',identity=dict(uri=uri,providerUid=10001,ownerPackage=PRIMARY,
            displayName=Path(self.current_path).name,device=info.st_dev,inode=info.st_ino),original={key:original[key] for key in ('bytes','sha256')},acquiredEpochMs=self.now(),deleteId='',deleteIssued=False,deleteCount=-1,checkedEpochMs=0,absent=False))
        self.readbacks['osDestinations']['rows'].sort(key=lambda row:row['request'])
        for kind,val,aux in (('request-active','',''),('destination-created',uri,''),('destination-copied',uri,''),('destination-published',uri,'1'),('result-ready','success',''),('delivered','success','')):
            self.export_event(kind,val,aux,request=request,action='save')
    def readback_source(self,request):
        if self.readbacks.get('initialized') is not False:
            op=request['operation'];id=request['resourceId'];export=request['exportRequest'];rows=self.readbacks['osDestinations']['rows'];grants=self.readbacks['shareGrants']['rows']
            if op=='remove-destination':
                row=next(row for row in rows if row['request']==export)
                if not row['deleteIssued']:
                    row.update(deleteId=id,deleteIssued=True);self.os_files[export].unlink();row.update(phase='retired',deleteCount=1,absent=not self.os_files[export].exists(),checkedEpochMs=self.now())
            elif op=='revoke-share':
                row=next(row for row in grants if row['request']==export);row.update(revokeId=id,revokeIssued=True,granted=False,chooserGranted=False,checkedEpochMs=self.now())
                if self.consumer:self.consumer.source['grantPresent']=False
            elif op=='retire-copies':
                for row in self.readbacks['files']:
                    path=self.root/'snapshot-app/files'/Path(row['path']).parent.name/Path(row['path']).name;path.unlink();self.readbacks['removedCopies'].append(row['id'])
                self.readbacks.update(files=[],copiesRetired=True,workersTerminated=True)
            elif op in ('inspect-destinations','inspect-shares'):
                key='osDestinations' if op=='inspect-destinations' else 'shareGrants';self.readbacks[key].update(checkId=id,checkedEpochMs=self.now())
                for row in self.readbacks[key]['rows']:row['checkedEpochMs']=self.now()
            self.readbacks.update(sequence=self.count('readbacks-body'),capturedEpochMs=self.now())
        return self.envelope('readback',request,dict(accepted=False,source=deepcopy(self.readbacks)))|dict(runId=RUN)
    def share_image(self):
        self.initialize_readbacks();self.component='com.android.intentresolver/com.android.intentresolver.ChooserActivity';self.app_state=3;request=uuid.uuid4().hex
        uri='content://'+PRIMARY+'.snapshot.files/snapshots/'+Path(self.current_path).name
        row=dict(request=request,uri=uri,ownerUid=10001,component='',receiverUid=0,chooserComponent=self.component,chooserUid=10038,
            revokeId='',revokeIssued=False,granted=True,chooserGranted=True,checkedEpochMs=self.now())
        self.readbacks['shareGrants']['rows'].append(row);self.readbacks['shareGrants']['rows'].sort(key=lambda row:row['request'])
        self.export_event('request-active',request=request,action='share');self.export_event('share-uri',uri,request=request,action='share')
    def consumer_control(self,value):
        operation,run,id=value
        if operation=='arm':
            self.consumer=Consumer();self.consumer.identity['apkSha256']='e'*64;self.consumer.source.update(runId=run,armId=id,phase='armed',identity=None,original=None,files=[],startedEpochMs=0,completedEpochMs=0,grantPresent=False,retired=False,workersTerminated=False)
        elif operation=='retire':
            if self.consumer.source['files']:
                self.consumer.path.unlink();self.consumer.source['removedCopies']=[row['id'] for row in self.consumer.source['files']]
            self.consumer.source.update(retired=True,workersTerminated=True,grantPresent=False,files=[])
        return {'accepted':True}
    def select_consumer(self):
        row=next(row for row in self.readbacks['shareGrants']['rows'] if row['request']==self.vm.snapshot.export_active);b=self.consumer
        row.update(component=RECEIVER_COMPONENT,receiverUid=10002)
        root=self.root/'receiver';root.mkdir(mode=0o700,exist_ok=True);b.path=root/(b.original['id']+'.bin');b.path.write_bytes(self.raw_png);b.path.chmod(0o600)
        b.raw=b.path.read_bytes();b.original.update(request=b.source['armId'],bytes=b.path.stat().st_size,sha256=hashlib.sha256(b.raw).hexdigest(),capturedEpochMs=self.now())
        b.source.update(phase='complete',original=deepcopy(b.original),files=[deepcopy(b.original)],identity=dict(uri=row['uri'],providerPackage=PRIMARY,providerUid=10001,
            receiverUid=10002,receiverPid=42,receiverPackage=b.identity['package'],component=RECEIVER_COMPONENT,readFlag=True,clipUri=row['uri'],permissionAtOpen=True),
            startedEpochMs=self.now(),completedEpochMs=self.now(),grantPresent=True,originalClosed=True)
        for kind,val in (('share-chosen',RECEIVER_COMPONENT),('result-ready','success'),('delivered','success')):self.export_event(kind,val,request=row['request'],action='share')
        self.component=RECEIVER_COMPONENT
    def os_sdk(self,method,path,body):
        package=self.component.split('/')[0]
        if path.endswith('/current_package'):return package
        if path.endswith('/current_activity'):return self.component.split('/')[1]
        if path.endswith('/source'):return '<hierarchy><node package="'+package+'" enabled="true" clickable="true" bounds="[0,0][300,400]"><node package="'+package+'" text="'+LABEL+'" enabled="true" bounds="[10,100][200,160]"/></node></hierarchy>'
        if method=='POST' and path.endswith('/actions'):self.select_consumer();return None
        if method=='DELETE' and path.endswith('/actions'):return None
        if method=='POST' and path.endswith('/back'):
            if self.component!=RECEIVER_COMPONENT:
                row=next(row for row in self.readbacks['shareGrants']['rows'] if row['request']==self.vm.snapshot.export_active);self.export_event('cancelled','cancelled',request=row['request'],action='share')
            self.component=PRIMARY+'/'+PRIMARY+'.MainActivity';self.app_state=4;return None
        raise AssertionError('Unrecognized original OS input')
    def group(self):
        def query(key,action):return self.source(key,dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=action,**(dict(runId=RUN) if key=='snapshot' else {})))
        before=query('roots','feature-script-roots-observe');script=query('scripts','feature-script-observe');snapshot=query('snapshot','phone-snapshot-observe');after=query('roots','feature-script-roots-observe')
        return dict(rootsBefore=before,script=script,snapshot=snapshot,rootsAfter=after)
    def passive(self):
        h=self.handoff;h['sequence']+=1;epoch=self.now()
        request=dict(commandId=uuid.uuid4().hex,runId=RUN,operation='observe',exportRequest='',resourceId='')
        readbacks=self.readback_source(request);files=self.source('snapshot-files',dict(schemaVersion=1,commandId=uuid.uuid4().hex,runId=RUN,action='phone-snapshot-files-observe'))
        upload=self.source('snapshot-upload',dict(commandId=uuid.uuid4().hex,runId=RUN))
        context=dict(snapshotHandoffContextVersion=1,requestedEpochMs=epoch,capturedEpochMs=epoch,lifecycle=deepcopy(self.lifecycle),account=deepcopy(self.account))
        context['account']['observation']['capturedEpochMs']=epoch
        h.update(capturedEpochMs=epoch,source=dict(context=context,group=self.group(),readbacks=readbacks,captureFiles=files,upload=upload))
        jobs=[{key:row[key] for key in ('runId','handoffId','instance','retired','timerActive','readActive','complete')} for _,row in sorted(self.handoff_jobs.items())]
        self.handoff_last=dict(snapshotHandoffSourceVersion=1,instance='a'*32,processId=31,publishedEpochMs=epoch,source=deepcopy(h),jobs=jobs)
        return deepcopy(self.handoff_last)
    def handoff_control(self,request):
        if request['operation']=='start':
            h=dict(snapshotHandoffVersion=1,instance=uuid.uuid4().hex,runId=RUN,handoffId=request['handoffId'],processId=31,sequence=0,
                startedEpochMs=self.now(),deadlineEpochMs=self.now()+60000,capturedEpochMs=self.now(),complete=True,error='',retired=False,timerActive=True,readActive=False,source={})
            self.handoff=h;self.handoff_jobs[h['handoffId']]=h
        if request['operation']=='retire':self.handoff.update(retired=True,timerActive=False)
        original=self.passive();return dict(snapshotHandoffControlVersion=1,requestId=request['commandId'],runId=RUN,handoffId=request['handoffId'],instance='a'*32,
            processId=31,sequence=self.count('handoff-control'),capturedEpochMs=self.now(),source=original['source'],jobs=original['jobs'])
    def native_core(self):
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-snapshot-observe',runId=RUN)
        self.vm.snapshot.epoch=self.now()-10;self.vm.snapshot.send(request);packet=json.loads(self.vm.snapshot.raw)
        body=packet['source'];body.pop('review');body.pop('androidExport');body['phoneSnapshotObservationVersion']=1
        return body
    def cancel_frame(self,closed_nonce=None):
        value=dict(capturedEpochMs=self.now(),native=self.native_core(),review=self.review())
        if not value['review']['present']:
            assert closed_nonce in self.work_packets
            value['scriptWork']=deepcopy(self.work_packets[closed_nonce])
        return value
    def cancel_source(self,request):
        id=request['jobId'];op=request['operation']
        if op=='start':
            command=deepcopy(request['request']);before=self.cancel_frame()
            self.product.send(dict(schemaVersion=1,commandId=command['commandId'],action='phone-snapshot-ui',request=command))
            capture=json.loads(self.product.raw);capture.pop('action')
            pending=self.cancel_frame();cancel=dict(command,commandId=uuid.uuid4().hex,controlId='snapshot.cancel-capture',
                controlToken=hashlib.sha256(b'snapshot.cancel-capture').hexdigest()[:32],sequence=command['sequence']+1)
            self.product.send(dict(schemaVersion=1,commandId=cancel['commandId'],action='phone-snapshot-ui',request=cancel))
            receipt=json.loads(self.product.raw);receipt.pop('action');cancelled=self.cancel_frame()
            self.job_sources[id]=dict(snapshotFastCancelVersion=1,instance=uuid.uuid4().hex,job=id,runId=RUN,phase='complete',error='',
                startedEpochMs=before['capturedEpochMs'],completedEpochMs=cancelled['capturedEpochMs'],observedEpochMs=self.now(),timerActive=False,retired=False,
                request=pending['native']['scriptHistory']['events'][-1]['id'],captureCommand=command,captureInput=capture,cancelCommand=cancel,cancelInput=receipt,
                before=before,pending=pending,cancelled=cancelled,retirement={},current=cancelled)
        row=self.job_sources[id];current=self.cancel_frame(request.get('closedReadWorkRequestId'))
        if op=='retire' and not row['retired']:row.update(retired=True,retirement=deepcopy(current))
        row.update(current=current,observedEpochMs=self.now())
        packet=self.envelope('cancel',request,row)|dict(runId=RUN)
        packet['jobs']=[{key:job[key] for key in ('job','runId','instance','phase','timerActive','retired')} for _,job in sorted(self.job_sources.items())]
        return packet
    def work_source(self,request):
        b=ScopedWorkBoundary();b.member=deepcopy(self.vm.manager);b.code=deepcopy(self.vm.code)
        b.compiled=dict(compiledSourcesVersion=1,complete=True,compilations=[deepcopy(self.vm.compilation)])
        b.activity=([activity(self.vm.compilation['scriptId'],signal_calls=len(self.script_events),registrations=2*len(self.job_sources))]
            if self.script_events or self.job_sources else [])
        epoch=self.now();b.epoch=epoch;b.sequence=self.count('work')-1;b.work_sequence=b.sequence
        b.send(request);value=deepcopy(b.value)
        self.work_packets[request['commandId']]=deepcopy(value);return value
    def source(self,key,request):
        epoch=self.now()
        if key=='handoff-control':return self.handoff_control(request)
        if key=='snapshot-cancel':return self.cancel_source(request)
        if key=='script-work':return self.work_source(request)
        if key=='snapshot-ui':
            self.product.send(request);return json.loads(self.product.raw)
        if key in ('roots','scripts','snapshot'):
            if key=='roots':self.vm.roots.epoch=epoch;self.vm.roots.send(request);return deepcopy(self.vm.roots.value)
            if key=='scripts':
                self.vm.scripts.send(request);value=deepcopy(self.vm.scripts.sample);value.update(requestedEpochMs=epoch,capturedEpochMs=epoch);return value
            self.vm.snapshot.epoch=epoch-10;self.vm.snapshot.send(request);return json.loads(self.vm.snapshot.raw)
        if key=='snapshot-files':
            self.producer.epoch=epoch;self.producer.send(request);value=json.loads(self.producer.read());value['processId']=31;return value
        if key=='snapshot-settings':
            self.lease_settings.epoch=epoch;self.lease_settings.send(request);value=json.loads(self.lease_settings.raw);value['processId']=31;return value
        if key=='web':
            value=super().source(key,request)
            if self.marker_active:
                actual=next(row['sourceUrl'] for row in self.marker['entities'] if row['role']=='marker')
                creation=self.marker['originalInput'];old=hashlib.sha256((creation['fixtureUrl']+'tickets/'+creation['ticket']+'/graphics-marker.v1.html').encode()).hexdigest()
                current=hashlib.sha256(actual.encode()).hexdigest()
                for original in (*value['source']['nativeBefore']['views'],*value['source']['nativeAfter']['views'],*value['source']['java']['views']):
                    for name in ('sourceSha256','documentSha256','creationSha256'):
                        if original.get(name)==old:original[name]=current
            return value
        if key=='native':
            value=super().source(key,request);value['lifecycle']=deepcopy(self.lifecycle)
            value['account']=deepcopy(self.account);value['account']['observation']['capturedEpochMs']=epoch
            return value
        if key=='snapshot-readbacks':return self.readback_source(request)
        if key=='snapshot-upload':
            self.upload['capturedEpochMs']=epoch
            return self.envelope(key,request,self.upload)|dict(runId=RUN)
        return super().source(key,request)
    def rpc(self,kind,value):
        with self.lock:
            self.rpc_counts[kind]+=1
            if kind!='clock':self.query_epoch+=1
            if kind=='binding':return deepcopy(self.model_binding)
            if kind=='scope-status':
                if value is not None:raise ValueError('SDK status cannot accept caller fields')
                return dict(binding=deepcopy(self.model_binding),foreground=self.app_state==4,running=True,appState=self.app_state)
            if kind=='clock':return self.now()
            if kind=='sdk-version':return self.sdk
            if kind=='system-ui':
                xml='<hierarchy><node package="'+self.component.split('/')[0]+'" displayed="true" /></hierarchy>'
                epoch=self.now();return dict(snapshotSystemUiVersion=1,observationId=uuid.uuid4().hex,component=self.component,requestedEpochMs=epoch,capturedEpochMs=epoch,sourceSha256=hashlib.sha256(xml.encode()).hexdigest(),xml=xml)
            if kind=='share-resolution':
                from test_snapshot_resolution import Boundary
                b=Boundary();b.epoch=self.now();return b.reader().read()
            if kind=='lifecycle-input':
                if value=='background':self.app_state=3;self.lifecycle['backgrounds']+=1
                elif value=='resume':self.app_state=4;self.lifecycle['activations']+=1
                return None
            if kind=='logout':
                self.account.update(loggedIn=False,principalSha256=hashlib.sha256(b'').hexdigest());self.account['observation'].update(tokenPresent=False,tokenValid=False,refreshPresent=False);self.token=None
                append(self.account,event(len(self.account['observation']['events'])+1,'logout-complete',self.now(),self.account['observation']['credentialGeneration']+1))
                return None
            if kind=='os-sdk':return self.os_sdk(*value)
            if kind=='consumer-control':return self.consumer_control(value)
            if kind=='consumer-installed':return self.consumer.identity
            if kind=='consumer-observe':
                self.consumer.epoch=self.now();return json.loads(self.consumer.observe(*value))
            if kind=='consumer-binary':return self.consumer.path.read_bytes().hex()
            if kind=='handoff-read':return self.passive()
            if kind=='login-submit':self.login(value);return None
            if kind=='login-open':self.product.shown=True;self.product.page='home';return None
            if kind=='login-close':self.product.shown=False;return None
            if kind=='tablet-visible':return self.product.shown
            if kind=='tablet-input':
                self.product.sdk_intents.append(dict(action=value))
                {'tablet.open':self.product.open_tablet,'tablet.close':self.product.close_tablet,'input.release':self.product.release}[value]();return None
            if kind=='snapshot-state':return dict(component=self.component,foreground=self.app_state==4,lifecycle=self.lifecycle)
            if kind=='source':return self.source(value['key'],value['request'])
            return super().rpc(kind,value)


class SnapshotProxy(CreateProxy):
    def capture_transport(self,artifact):
        transport=LocalTransport(self.root/'snapshot-app',artifact)
        # LocalTransport's stand-alone test constant is not the current target.
        transport.context={key:self.binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')}
        transport.adb=SavedSdk(self.root/'snapshot-app');transport.selector='synthetic-readback-only'
        return transport

    def _snapshot_source(self,_):return self.reader('snapshot',PhoneSnapshotSource)
    def _snapshot_measurements(self,_):
        return PhoneSnapshotMeasurements(self.reader('roots',NativeScriptRoots),self.reader('scripts',NativeScriptObservation),
            self._snapshot_source(None),lambda:True,self.clock_ms,31)
    def _snapshot_normal_controls(self,_s,intent,*,read_only=False):
        io=self.reader('snapshot-ui',PhoneSnapshotIO,intent=intent)
        tablet=SimpleNamespace(tablet_visible=lambda:self.call('tablet-visible',None),
            open_tablet=lambda:self.call('tablet-input','tablet.open'),close_tablet=lambda:self.call('tablet-input','tablet.close'),
            release=lambda:self.call('tablet-input','input.release'))
        return PhoneSnapshotControls(io,tablet,intent)
    def _snapshot_capture_file_source(self,_s,*,read_only=True):return self.reader('snapshot-files',PhoneSnapshotCaptureFileSource,read_only=read_only)
    def _snapshot_capture_files(self,_s,artifact,owner,*,read_only=False):
        Path(artifact).mkdir(mode=0o700,exist_ok=True)
        source=self.reader('snapshot-files',PhoneSnapshotCaptureFileSource,read_only=read_only)
        return PhoneSnapshotCaptureFiles(self.capture_transport(Path(artifact)),source,self.binding,owner,read_only=read_only,clock_ms=self.clock_ms)
    def _snapshot_settings(self,_s,*,read_only=False):return self.reader('snapshot-settings',PhoneSnapshotSettings,read_only=read_only)
    def _snapshot_platform(self,_):return PhoneSnapshotPlatform(lambda:str(self.call('sdk-version',None)),lambda:True,self.clock_ms)
    def _snapshot_share_resolution(self,_):return SimpleNamespace(read=lambda:self.call('share-resolution',None))
    def _snapshot_share_ui(self,_s,*_args):return SimpleNamespace(capture=lambda:self.call('system-ui',None))
    def _snapshot_readbacks(self,_s,*,read_only=False):return self.reader('snapshot-readbacks',PhoneSnapshotReadbacks)
    def _snapshot_upload_source(self,_s):return self.reader('snapshot-upload',PhoneSnapshotUploadSource)
    def _login_controls(self,_s,intent,run,origin):
        fields={}
        def stage(name):intent(name,self.call('snapshot-state',None),None)
        def opened():stage('open');self.call('login-open',None)
        def fill(value):stage('fill');fields.update(value)
        def submit():
            stage('submit')
            try:self.call('login-submit',fields)
            finally:fields.clear()
        def cancel():stage('cancel');self.call('login-close',None)
        return SimpleNamespace(open=opened,fill=fill,submit=submit,cancel=cancel)
    def _snapshot_cancel(self,_s,*,read_only=False):return self.reader('snapshot-cancel',PhoneSnapshotCancel)
    def _script_work(self,_s,*,read_only=True):return self.reader('script-work',NativeScriptWork)
    def _snapshot_saved_files(self,_s,run,root):
        return PhoneSnapshotSavedFiles(SavedSdk(self.root/'snapshot-app'),'synthetic-readback-only',PRIMARY,
            {key:self.binding[key] for key in ('sourceRevision','artifactSha256','processIdentity')},lambda:True,root,self._snapshot_readbacks(None),run)
    def _snapshot_system_context(self,_s,binding,resolution,authority):
        def status():
            return self.call('scope-status',None)
        return SnapshotSystemContext(binding,resolution,status,lambda:self.call('snapshot-state',None)['component'],authority)
    def _snapshot_share_ui(self,_s,binding,resolution,intent,authority):
        scope=self._snapshot_system_context(_s,binding,resolution,authority)
        client=SimpleNamespace(call=lambda method,path,body=None:self.call('os-sdk',[method,path,body]))
        return PhoneSnapshotSystemUI(NativeUI(client,'synthetic',scope.guard),intent,self.clock_ms,resolution['component'])
    def _snapshot_consumer(self,_s,run,arm,sha,*,read_only=True,binding=None):
        return PhoneSnapshotConsumer(lambda r,n:json.dumps(self.call('consumer-observe',[r,n])).encode(),
            lambda *args:bytes.fromhex(self.call('consumer-binary',args)),lambda *args:self.call('consumer-control',args),
            lambda:self.call('consumer-installed',None),self.clock_ms,lambda:True,run,arm,read_only=read_only,binding=binding)
    def _snapshot_system_consumer(self,_s,run,arm,sha,*_args,**kwargs):return self._snapshot_consumer(_s,run,arm,sha,read_only=kwargs.get('read_only',True),binding=kwargs.get('binding'))
    def _snapshot_handoff_control(self,_,*,read_only=False):return self.reader('handoff-control',PhoneSnapshotHandoffControl)
    def _snapshot_handoff_source(self,_s,binding,resolution,authority,owner):
        scope=self._snapshot_system_context(_s,binding,resolution,authority)
        return PhoneSnapshotHandoff(lambda:json.dumps(self.call('handoff-read',None)),self.clock_ms,scope.guard,owner)
    def _snapshot_system_platform(self,_s,binding,resolution,authority):return self._snapshot_platform(_s)
    def _snapshot_system_files(self,_s,root,owner,binding,resolution,authority,handoff):
        from overte_phone_snapshot_system_files import SnapshotSystemFileSource
        source=SnapshotSystemFileSource(handoff)
        return PhoneSnapshotCaptureFiles(self.capture_transport(root),source,binding,owner,read_only=True,clock_ms=self.clock_ms)
    def _graphics_lifecycle_status(self,_s,binding):
        value=self.call('snapshot-state',None)
        return dict(binding=self.call('binding',None),foreground=value['foreground'],running=True,appState=4 if value['foreground'] else 3)
    def _account_menu(self,_s,intent,run,origin):
        def logout():intent('logout',self.call('snapshot-state',None),None);self.call('logout',None)
        return SimpleNamespace(logout=logout)


class SnapshotActorProxy(SnapshotProxy):
    """Separate-process reader using the real public owner factory.

    The target connection is synthetic SDK IO; primary fixture credentials and
    functional input calls are never provisioned to this process.
    """
    def __init__(self,url,root):super().__init__(url,root);self.candidate=object()
    def target(self,_):return dict(appId=PRIMARY)
    def controlled_android_client(self,_):return True
    def normal_feature_runtime(self,_s,*,read_only):
        assert read_only
        actual=self.call('binding',None)
        def guard():
            assert self.call('binding',None)==actual
            assert self.call('snapshot-state',None)['foreground']
            return True
        guard();return None,None,actual,guard,None
    def snapshots_feature_store(self,selector):
        from appium_adapter import PhoneAppiumAdapter
        return PhoneAppiumAdapter.snapshots_feature_store(self,selector)
    @staticmethod
    def _snapshots_configuration(metadata=None):
        from appium_adapter import PhoneAppiumAdapter
        return PhoneAppiumAdapter._snapshots_configuration(metadata)
    def actor(self,selector,run,client):
        from appium_adapter import PhoneAppiumAdapter
        return PhoneAppiumAdapter._snapshots_actor(self,selector,run,client=client)
