"""Actual Java owner/FS plus synthetic Android SDK normal Save/cancel proofs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from urllib.request import Request,urlopen
import uuid

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(Path(__file__).parent)]
from adapters.normal_ui import NativeUIError
from snapshot_documents_journey_boundary import (install_documents,OriginalDocumentsProcess,PICKER,PHONE_UID,APK_SHA256,PACKAGE,NativeUI,PhoneSnapshotDocumentsUI,
    keepalive_handler,install_keepalive_snapshot_rpc,close_snapshot_rpc,ScopeGuardTrace)
from test_snapshot_capture_files import Producer
from test_snapshot_os_retirement_source import boundary as readback_seed
from test_snapshot_system_context import BINDING
from test_snapshot_source import Boundary as SnapshotNative
from overte_phone_snapshot_readbacks import source as validate_readbacks

RUN='a'*32;ARM='b'*32


class Model:
    def __init__(self,root,sdk=26):
        self.root=root;self.sdk=sdk;self.lock=threading.RLock();self.component='io.github.noah_be.overte.phone/io.github.noah_be.overte.phone.MainActivity';self.app_state=4
        self.producer=Producer(root/'snapshot-app');self.producer.epoch=time.time_ns()//1000000
        self.producer.send(dict(operation='plan',operationId=uuid.uuid4().hex,runId=RUN,prefix='e2e-'+RUN,commandId=uuid.uuid4().hex,action='phone-snapshot-files-control'))
        row,path=self.producer.capture();self.current_path=row['path']
        from PIL import Image
        image=Image.new('RGB',(24,24),(255,50,60));image.putpixel((0,0),(10,50,250));raw=BytesIO();image.save(raw,format='PNG');self.raw_png=raw.getvalue()
        path.write_bytes(self.raw_png);row.update(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        self.readbacks=dict(snapshotExportReadbacksVersion=1,initialized=False,complete=True)
        self.vm=SimpleNamespace(snapshot=SnapshotNative());self.vm.snapshot.export_events=[];self.vm.snapshot.export_active=''
        self.events=self.vm.snapshot.export_events;self.seq=0
    def now(self):return time.time_ns()//1000000
    def save_image(self):raise AssertionError('SDK29 Save cannot be used')
    def initialize_readbacks(self):
        if self.readbacks.get('initialized') is False:
            self.readbacks=readback_seed().component
            self.readbacks.update(copiesRetired=False,workersTerminated=False,destinations=[],jobs=[],files=[],removedCopies=[])
            self.readbacks['osDestinations']['rows']=[]
    def export_event(self,kind,value='',auxiliary='',*,request,action):
        self.vm.snapshot.epoch=self.now();self.vm.snapshot.export_event(kind,value,auxiliary,request=request,action=action)
        self.events[-1]['source']=self.current_path
    def rpc(self,kind,value):
        if kind=='clock':return self.now()
        if kind=='binding':return deepcopy(BINDING)
        if kind=='snapshot-state':return dict(component=self.component,foreground=self.app_state==4)
        if kind=='os-sdk':return self.os_sdk(*value)
        raise AssertionError(kind)
    def os_sdk(self,method,path,body):
        if method=='DELETE' and path.endswith('/actions'):return None
        if path.endswith('/current_package'):return self.component.split('/')[0]
        if path.endswith('/current_activity'):return self.component.split('/')[1]
        if path.endswith('/source'):return '<hierarchy><node package="'+self.component.split('/')[0]+'" displayed="true"/></hierarchy>'
        raise AssertionError((method,path))
    def readback_source(self,request):
        op=request['operation']
        if op=='retire-copies':
            for row in self.readbacks['files']:
                actual=self.root/'snapshot-app/files'/Path(row['path']).parent.name/Path(row['path']).name
                actual.unlink();self.readbacks['removedCopies'].append(row['id'])
            self.readbacks.update(files=[],copiesRetired=True,workersTerminated=True)
        elif op=='remove-destination':raise AssertionError('MediaStore deletion cannot be used')
        elif op=='inspect-destinations':
            self.readbacks['osDestinations'].update(checkId=request['resourceId'],checkedEpochMs=self.now())
            for row in self.readbacks['osDestinations']['rows']:row['checkedEpochMs']=self.now()
        self.seq+=1;self.readbacks.update(sequence=self.seq,capturedEpochMs=self.now())
        return dict(accepted=False,source=deepcopy(self.readbacks))


class Proxy:
    def __init__(self,url):self.url=url
    def call(self,kind,value):
        request=Request(self.url,json.dumps(dict(kind=kind,value=value)).encode(),{'Content-Type':'application/json'})
        with urlopen(request,timeout=6) as response:
            result=json.loads(response.read())
        if 'error' in result:raise RuntimeError(result['error'])
        return result['value']
    def clock_ms(self):return self.call('clock',None)
    def _snapshot_system_context(self,*args):raise AssertionError('Share context cannot authorize Documents')


class SnapshotDocumentsJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):OriginalDocumentsProcess.compile(ROOT/'build/snapshot-documents-journey')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.model=Model(self.root)
        self.boundary=install_documents(self.model,Proxy)
        model=self.model
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                try:reply=dict(value=model.rpc(request['kind'],request['value']))
                except Exception as error:reply=dict(error=str(error))
                raw=json.dumps(reply).encode();self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.proxy=Proxy('http://127.0.0.1:'+str(self.server.server_port))
        self.resolution=self.proxy._snapshot_document_resolution(None).read()
        self.owner=self.proxy._snapshot_documents(None,RUN,ARM,APK_SHA256,BINDING,self.resolution,lambda:True,read_only=False)
        self.owner.control('arm');self.initial=self.owner.observe()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.boundary.close();self.temp.cleanup()
    def flow(self):return self.proxy._snapshot_document_ui(None,BINDING,self.resolution,lambda intent:self.boundary.intents.append(deepcopy(intent)) or True,lambda:True)
    def save(self):
        self.model.save_image();self.flow().select_root();self.flow().save(Path(self.model.current_path).name)
        return self.owner.observe()['documents'][-1]
    def identity(self):return self.model.readbacks['osDestinations']['rows'][-1]['identity']
    def capture(self):
        raw=self.boundary.capture_path().read_bytes();return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    def retire(self):
        for row in self.model.readbacks['osDestinations']['rows']:
            self.model.readback_source(dict(operation='remove-destination',exportRequest=row['request'],resourceId=uuid.uuid4().hex))
        self.model.readback_source(dict(operation='retire-copies',exportRequest='',resourceId=''))
        self.owner.control('retire');return self.owner.require_retired()

    def test_package_manager_original_queries_and_actual_separate_provider_process(self):
        self.assertEqual(3,len(self.boundary.pm_calls));self.assertEqual(PICKER,self.resolution['component'])
        identity=self.boundary.provider.identity();self.assertNotEqual(__import__('os').getpid(),identity['processId'])
        self.assertTrue(Path('/proc/'+str(identity['processId'])).is_dir());self.assertEqual([],self.initial['documents']);self.assertEqual([],self.boundary.inputs)

    def test_normal_cancel_creates_no_document_or_copy_and_empty_retirement_is_actual(self):
        self.model.save_image();self.assertEqual([],self.owner.observe()['documents']);self.assertEqual([],self.model.readbacks['files'])
        self.flow().cancel();self.assertEqual(['request-active','document-launched','document-result','result-ready','delivered'],[row['kind'] for row in self.model.events])
        self.assertEqual('cancelled',self.model.events[-1]['value']);retired=self.retire()
        self.assertTrue(retired['workersTerminated']);self.assertFalse((self.boundary.provider.parent/('overte-snapshot-documents-'+RUN)).exists())
        self.owner.control('retire');self.assertTrue(self.owner.require_retired()['retired'])

    def test_drawer_back_then_picker_back_is_normal_cancel_without_files(self):
        self.model.save_image();self.boundary.stage='drawer';self.flow().cancel()
        self.assertEqual(2,len(self.boundary.inputs));self.assertEqual([],self.owner.observe()['documents']);self.retire()

    def test_normal_save_acquires_original_java_bytes_inode_and_independent_phone_readback(self):
        doc=self.save();row=self.owner.observe();self.assertEqual(1,len(row['documents']))
        self.assertEqual(PHONE_UID,doc['writerUid']);self.assertEqual(self.resolution['uid'],doc['createUid'])
        path=self.boundary.provider.parent/('overte-snapshot-documents-'+RUN)/(doc['documentId']+'.png')
        self.assertEqual(path.stat().st_ino,doc['inode']);self.assertTrue(all(fd['closed'] for fd in row['fdLifetimes']))
        measured,raw=self.owner.acquire(doc['documentId'],self.identity(),self.capture(),PHONE_UID,self.resolution)
        self.assertEqual(path.read_bytes(),raw);self.assertEqual(self.model.raw_png,raw);self.assertEqual(doc['writeClosedEpochMs'],measured['capturedEpochMs'])
        rb=self.model.readback_source(dict(operation='observe',exportRequest='',resourceId=''));validate_readbacks(rb)
        self.assertEqual(['document-show-roots','document-select-owned-root','document-save'],[row['action'] for row in self.boundary.intents])
        self.assertEqual(3,len(self.boundary.inputs));self.assertEqual('success',self.model.events[-1]['value'])
        self.retire();self.assertFalse(path.exists());self.assertFalse(list((self.root/'snapshot-app/files').glob('overte-snapshot-e2e-*/*.bin')))

    def test_readonly_second_reader_uses_original_floor_independent_bytes_and_fresh_retirement(self):
        actor=self.proxy._snapshot_system_documents(None,RUN,ARM,APK_SHA256,BINDING,self.resolution,lambda:True,binding=self.owner.binding())
        doc=self.save();own=actor.observe();self.assertGreater(own['sequence'],self.initial['sequence'])
        self.assertEqual(self.model.raw_png,actor.acquire(doc['documentId'],self.identity(),self.capture(),PHONE_UID,self.resolution)[1])
        with self.assertRaises(NativeUIError):actor.control('retire')
        self.retire();self.assertTrue(actor.require_retired()['workersTerminated'])

    def test_ignored_normal_save_ack_creates_no_file_and_is_not_replayed(self):
        self.model.save_image();flow=self.flow();flow.select_root();self.boundary.ignored=True
        before=len(self.boundary.inputs)
        # Keep the production finite wait; virtualize only its SDK wait clock.
        clock=[flow.ui._now()];flow.ui.monotonic=lambda:clock[0];flow.ui.sleep=lambda delay:clock.__setitem__(0,clock[0]+delay)
        flow.monotonic=lambda:clock[0];flow.sleep=lambda delay:clock.__setitem__(0,clock[0]+delay)
        with self.assertRaises(NativeUIError):flow.save(Path(self.model.current_path).name)
        self.assertEqual(before+1,len(self.boundary.inputs));self.assertEqual([],self.owner.observe()['documents']);self.assertEqual([],self.model.readbacks['files'])
        self.boundary.ignored=False;flow.cancel();self.retire()

    def test_foreign_toolbar_and_filename_never_issue_os_save_or_create_file(self):
        self.model.save_image();self.flow().select_root();before=len(self.boundary.inputs)
        self.boundary.xml_filter=lambda raw:raw.replace(LABEL,'Foreign root')
        with self.assertRaises(NativeUIError):self.flow().save(Path(self.model.current_path).name)
        self.assertEqual(before,len(self.boundary.inputs));self.assertEqual([],self.owner.observe()['documents'])
        self.boundary.xml_filter=lambda raw:raw.replace(Path(self.model.current_path).name,'foreign.png')
        with self.assertRaises(NativeUIError):self.flow().save(Path(self.model.current_path).name)
        self.assertEqual(before,len(self.boundary.inputs));self.boundary.xml_filter=lambda raw:raw;self.flow().cancel();self.retire()

    def test_pending_original_close_retains_fd_and_cannot_be_acquired_deleted_or_retired(self):
        self.boundary.close_mode='pending';doc=self.save();self.assertEqual(0,doc['writeClosedEpochMs']);self.assertEqual([],self.model.readbacks['files'])
        row=self.owner.observe();self.assertFalse(row['fdLifetimes'][0]['closed'])
        with self.assertRaises(RuntimeError):self.boundary.provider.binary(RUN,doc['documentId'],uuid.uuid4().hex)
        with self.assertRaises(RuntimeError):self.boundary.provider.call('delete',doc['documentId'])
        with self.assertRaises(NativeUIError):self.owner.control('retire')
        self.assertEqual('error',self.model.events[-1]['value'])
        self.boundary.provider.call('close',self.boundary.pending_descriptor,'false');self.boundary.provider.call('delete',doc['documentId']);self.owner.control('retire');self.owner.require_retired()

    def test_foreign_samebytes_inode_is_never_adopted_or_removed(self):
        doc=self.save();path=self.boundary.provider.parent/('overte-snapshot-documents-'+RUN)/(doc['documentId']+'.png')
        old=path.with_suffix('.retained');path.rename(old);path.write_bytes(old.read_bytes());path.chmod(0o600)
        self.assertNotEqual(path.stat().st_ino,doc['inode'])
        with self.assertRaises(NativeUIError):self.owner.observe()
        with self.assertRaises(RuntimeError):self.boundary.provider.call('delete',doc['documentId'])
        self.assertTrue(path.exists());self.assertTrue(old.exists())

    def test_changed_native_original_capture_prevents_copy_despite_ordinary_save_input(self):
        self.model.save_image();self.flow().select_root();path=self.boundary.capture_path();old=path.with_suffix('.old');path.rename(old);path.write_bytes(old.read_bytes())
        with self.assertRaises(NativeUIError):self.flow().save(Path(self.model.current_path).name)
        self.assertEqual([],self.owner.observe()['documents']);self.assertEqual([],self.model.readbacks['files'])

    def test_independent_uid_apk_and_native_uri_identity_mismatches_fail_original_join(self):
        doc=self.save();identity=self.identity()
        for fault in ('uid','uri','inode','instance'):
            changed=deepcopy(identity);uid=PHONE_UID
            if fault=='uid':uid+=1
            elif fault=='uri':changed['uri']+='foreign'
            elif fault=='inode':changed['inode']+=1
            else:changed['providerInstance']='f'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.owner.acquire(doc['documentId'],changed,self.capture(),uid,self.resolution)
        self.boundary.provider.identity_value['apkSha256']='f'*64
        with self.assertRaises(NativeUIError):self.owner.observe()
        self.boundary.provider.identity_value['apkSha256']=APK_SHA256;self.retire()

    def test_wrong_original_writer_callback_uid_cannot_qualify_as_phone_writer(self):
        self.boundary.writer_uid=PHONE_UID+55;doc=self.save();self.assertEqual(PHONE_UID+55,doc['writerUid'])
        with self.assertRaises(NativeUIError):self.owner.acquire(doc['documentId'],self.identity(),self.capture(),PHONE_UID,self.resolution)
        self.retire()

    def test_late_original_file_after_retirement_is_not_hidden_by_old_receipt(self):
        self.save();retired=self.retire();root=self.boundary.provider.parent/('overte-snapshot-documents-'+RUN);root.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):self.owner.require_retired()
        self.assertTrue(root.exists());self.assertTrue(retired['retired'])

    def test_foreign_current_window_and_changed_original_session_forbid_os_reads(self):
        self.model.save_image();self.model.component='foreign.app/foreign.app.Activity'
        with self.assertRaises(NativeUIError):self.flow().capture()
        original=self.model.rpc
        def mutated(kind,value):
            if kind=='binding':return dict(BINDING,generation=BINDING['generation']+1)
            return original(kind,value)
        self.model.rpc=mutated;self.model.component=PICKER
        with self.assertRaises(NativeUIError):self.flow().capture()

    def test_sdk27_and28_use_same_ordinary_document_flow_and_actual_original_owner(self):
        for sdk in (27,28):
            with self.subTest(sdk=sdk),tempfile.TemporaryDirectory() as temporary:
                model=Model(Path(temporary),sdk);boundary=install_documents(model)
                try:
                    boundary.provider.control('arm',RUN,ARM);model.save_image()
                    self.assertEqual(PICKER,model.component);self.assertEqual([],boundary.provider.observe(RUN,uuid.uuid4().hex)['documents'])
                    client=SimpleNamespace(call=lambda method,path,body=None:model.os_sdk(method,path,body))
                    flow=PhoneSnapshotDocumentsUI(NativeUI(client,'synthetic',lambda:True),lambda row:boundary.intents.append(row) or True,model.now,PICKER)
                    flow.select_root();flow.save(Path(model.current_path).name)
                    self.assertEqual(3,len(boundary.inputs))
                    actual=boundary.provider.observe(RUN,uuid.uuid4().hex)
                    self.assertEqual(1,len(actual['documents']));self.assertEqual(model.raw_png,boundary.provider.binary(RUN,actual['documents'][0]['documentId'],uuid.uuid4().hex))
                    request=model.readbacks['osDestinations']['rows'][0]['request'];model.readback_source(dict(operation='remove-destination',exportRequest=request,resourceId=uuid.uuid4().hex))
                    boundary.provider.control('retire',RUN);self.assertTrue(boundary.provider.observe(RUN,uuid.uuid4().hex)['workersTerminated'])
                finally:boundary.close()

    def test_lost_delete_reply_recovers_from_original_absence_without_second_delete(self):
        doc=self.save();row=self.model.readbacks['osDestinations']['rows'][-1];id=uuid.uuid4().hex
        request=dict(operation='remove-destination',exportRequest=row['request'],resourceId=id)
        original=self.boundary.provider.call;lost=[True]
        def interrupted(operation,*args):
            result=original(operation,*args)
            if operation=='delete' and lost[0]:lost[0]=False;raise RuntimeError('Explicit lost reply after actual original unlink')
            return result
        self.boundary.provider.call=interrupted
        with self.assertRaises(RuntimeError):self.model.readback_source(request)
        self.assertTrue(row['deleteIssued']);self.assertFalse(row['absent'])
        reply=self.model.readback_source(request);validate_readbacks(reply)
        actual=self.owner.observe()['documents'][-1]
        self.assertTrue(actual['absent']);self.assertEqual(1,actual['deleteCalls']);self.assertEqual(1,len([call for call in self.boundary.provider.calls if call[0]=='delete']))
        with self.assertRaises(RuntimeError):self.model.readback_source(dict(request,resourceId=uuid.uuid4().hex))
        self.model.readback_source(dict(operation='retire-copies',exportRequest='',resourceId=''));self.owner.control('retire');self.owner.require_retired()

    def test_actual_provider_exit_prevents_fresh_original_acquisition(self):
        self.save();self.boundary.close();self.assertIsNotNone(self.boundary.provider.process.returncode)
        with self.assertRaises(NativeUIError):self.owner.observe()

    def test_only_sdk26_to28_can_attach_and_control_cannot_write_or_choose_paths(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaises(ValueError):install_documents(Model(Path(path),29))
        for operation in ('write','create','delete'):
            with self.subTest(operation=operation),self.assertRaises(RuntimeError):self.boundary.provider.control(operation,RUN,ARM)
        self.assertEqual([],self.owner.observe()['documents'])


class SnapshotKeepaliveBoundaryTests(unittest.TestCase):
    """Actual TCP/HTTP framing and one-send failure semantics, no RPC stubs."""
    def setUp(self):
        self.records=[];self.peers=set();self.framing='valid';self.lost=False;self.counter=0
        owner=self
        class Source(BaseHTTPRequestHandler):
            def handle(self):
                try:super().handle()
                except ConnectionResetError:
                    if owner.framing=='valid':raise
            def do_POST(self):
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                owner.records.append(value);owner.peers.add(self.client_address)
                if owner.lost:
                    owner.lost=False;self.connection.shutdown(__import__('socket').SHUT_RDWR);self.connection.close();return
                owner.counter+=1;raw=json.dumps(dict(sequence=owner.counter,inputs=len(owner.records))).encode()
                self.send_response(200)
                if owner.framing!='missing':self.send_header('Content-Length',str(len(raw) if owner.framing!='oversize' else 64*1024*1024+1))
                if owner.framing=='duplicate':self.send_header('Content-Length',str(len(raw)))
                self.end_headers();self.wfile.write(raw)
            def log_message(self,*_):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),keepalive_handler(Source));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.proxies=[]
        class Client:pass
        install_keepalive_snapshot_rpc(Client);self.proxy_type=Client
    def proxy(self):
        value=self.proxy_type();value.url='http://127.0.0.1:'+str(self.server.server_port);self.proxies.append(value);return value
    def tearDown(self):
        for value in self.proxies:close_snapshot_rpc(value)
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
    def test_actual_connection_reuse_and_independent_actor_connection(self):
        primary=self.proxy();actor=self.proxy()
        self.assertEqual(1,primary.call('observe',None)['sequence']);self.assertEqual(2,primary.call('observe',None)['sequence'])
        self.assertEqual(1,len(self.peers));self.assertEqual(3,actor.call('observe',None)['sequence']);self.assertEqual(2,len(self.peers))
        self.assertIsNot(primary._snapshot_rpc_lock,actor._snapshot_rpc_lock)
    def test_lost_input_reply_is_never_retried_or_cached(self):
        proxy=self.proxy();self.lost=True
        with self.assertRaises(Exception):proxy.call('ordinary-input',dict(controlId='save'))
        self.assertEqual(1,len(self.records));self.assertNotIn('_snapshot_rpc_connection',proxy.__dict__)
        actual=proxy.call('observe',None)
        self.assertEqual(2,actual['inputs']);self.assertEqual(1,len([row for row in self.records if row['kind']=='ordinary-input']))
        self.assertEqual(2,len(self.peers))
    def test_unqualified_missing_duplicate_and_oversize_content_length_are_red(self):
        for framing in ('missing','duplicate','oversize'):
            with self.subTest(framing=framing):
                self.framing=framing;proxy=self.proxy();before=len(self.records)
                with self.assertRaises(RuntimeError):proxy.call('observe',None)
                self.assertEqual(before+1,len(self.records));self.assertNotIn('_snapshot_rpc_connection',proxy.__dict__)
    def test_same_proxy_serializes_concurrent_original_requests(self):
        proxy=self.proxy();results=[];failures=[]
        def read():
            try:
                for index in range(4):results.append(proxy.call('observe',None)['sequence'])
            except Exception as error:failures.append(error)
        threads=[threading.Thread(target=read) for index in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=5)
        self.assertEqual([],failures);self.assertEqual(list(range(1,9)),sorted(results));self.assertEqual(1,len(self.peers))
    def test_nonloopback_credentials_or_other_scheme_never_reaches_transport(self):
        for url in ('http://example.invalid:123','https://127.0.0.1:123','http://user:secret@127.0.0.1:123','http://127.0.0.1:123/foreign'):
            proxy=self.proxy();proxy.url=url
            with self.subTest(url=url),self.assertRaises(RuntimeError):proxy.call('observe',None)
        self.assertEqual([],self.records)


class SnapshotScopeTraceTests(unittest.TestCase):
    def test_actual_guard_queries_errors_and_original_methods_are_preserved(self):
        from test_snapshot_system_context import Source
        from overte_phone_snapshot_system_context import SnapshotSystemContext
        from overte_phone_snapshot_documents_ui import SnapshotDocumentContext
        original,documents=SnapshotSystemContext.guard,SnapshotDocumentContext.guard
        source=Source();self.assertTrue(source.reader.guard());before=source.calls
        with ScopeGuardTrace() as trace:
            self.assertTrue(source.reader.guard());self.assertEqual(2,source.calls-before)
            source.component='foreign.app/foreign.app.Activity'
            with self.assertRaises(NativeUIError):source.reader.guard()
            self.assertEqual(2,sum(trace.counts.values()))
        self.assertIs(original,SnapshotSystemContext.guard);self.assertIs(documents,SnapshotDocumentContext.guard)
    def test_denied_authority_still_stops_before_any_sdk_queries(self):
        from test_snapshot_system_context import Source
        source=Source();source.authorized=False
        with ScopeGuardTrace('actor') as trace:
            with self.assertRaises(NativeUIError):source.reader.guard()
            self.assertEqual(0,source.calls);self.assertEqual(1,sum(trace.counts.values()))


class SnapshotDocumentsCommonJourneyTests(unittest.TestCase):
    """Reuse the guarded public harness; select only the actual SDK26 profile."""
    SDK=26
    @classmethod
    def setUpClass(cls):
        import test_snapshots_feature_journey as shared
        cls.shared=shared
        shared.SnapshotJourneyTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):cls.shared.SnapshotJourneyTests.tearDownClass.__func__(cls)
    def setUp(self):
        from unittest.mock import patch
        shared=self.shared;original=shared.SnapshotTarget
        if __import__('os').environ.get('OVERTE_SNAPSHOT_SCOPE_TRACE')=='1':
            trace=ScopeGuardTrace('parent');trace.__enter__();self.addCleanup(trace.__exit__);self.addCleanup(trace.report)
        # Use the existing host RAM filesystem for this IO-heavy transport
        # replay. Real files/inodes/bytes and every fsync still execute; this
        # establishes no Android storage or power-loss durability claim.
        p=patch('tempfile.tempdir','/tmp');p.start();self.addCleanup(p.stop)
        def target(*args,**kwargs):
            model=original(*args,**kwargs);boundary=install_documents(model,shared.SnapshotProxy)
            self.addCleanup(boundary.close);return model
        p=patch.object(shared,'SnapshotTarget',side_effect=target);p.start();self.addCleanup(p.stop)
        script=shared.ACTOR.replace("configuration=PrivateFeatureState", "from snapshot_documents_journey_boundary import install_proxy_documents\nfrom snapshots_journey_producers import SnapshotProxy\ninstall_proxy_documents(SnapshotProxy)\nconfiguration=PrivateFeatureState")
        if script==shared.ACTOR:raise AssertionError('Original guarded actor insertion point changed')
        if __import__('os').environ.get('OVERTE_SNAPSHOT_SCOPE_TRACE')=='1':
            script=script.replace("configuration=PrivateFeatureState","from snapshot_documents_journey_boundary import ScopeGuardTrace\nscope_trace=ScopeGuardTrace('actor');scope_trace.__enter__()\nconfiguration=PrivateFeatureState")
            script=script.replace("    time.sleep(.1)","    scope_trace_steps=globals().get('scope_trace_steps',0)+1\n    if scope_trace_steps in (1,8,32):scope_trace.report(5)\n    time.sleep(.1)")
        p=patch.object(shared,'ACTOR',script);p.start();self.addCleanup(p.stop)
        shared.SnapshotJourneyTests.setUp(self)
        # urllib retains its original HTTPS context after earlier HTTP-only
        # unit tests. Acquire a fresh context under the actual fixture CA;
        # certificate and hostname checks remain enabled.
        p=patch('urllib.request._opener',None);p.start();self.addCleanup(p.stop)
        for name in ('_snapshot_document_resolution','_snapshot_document_ui','_snapshot_documents','_snapshot_system_documents','_snapshot_phone_uid'):
            p=patch.object(self.adapter,name,getattr(self.proxy,name));p.start();self.addCleanup(p.stop)
    def invoke(self,*args,**kwargs):return self.shared.SnapshotJourneyTests.invoke(self,*args,**kwargs)
    def act(self,*args,**kwargs):return self.shared.SnapshotJourneyTests.act(self,*args,**kwargs)
    def start_actor(self,*args,**kwargs):
        self.shared.SnapshotJourneyTests.start_actor(self,*args,**kwargs)
        if __import__('os').environ.get('OVERTE_SNAPSHOT_SCOPE_TRACE')=='1':
            def trace_results():
                if self.actor.poll() is None:self.actor.terminate()
                _out,err=self.actor.communicate(timeout=5)
                lines=[line for line in err.splitlines() if line.startswith('Snapshot SDK guard callers ')]
                if lines:print(lines[-1],file=sys.stderr,flush=True)
            self.addCleanup(trace_results)
    def actor_ok(self,*args,**kwargs):return self.shared.SnapshotJourneyTests.actor_ok(self,*args,**kwargs)
    def test_normal_public_document_picker_open_cancel_and_success_acquires_original(self):
        from feature_journeys.scenarios import VERSION
        self.client.activate('c'*32)
        self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=self.shared.RUN,afterSequence=0))
        self.act('open');self.act('capture',dict(mode='still',format='png'))
        self.act('save-picker-open');self.act('save-picker-cancel');self.act('save-picker-open');self.act('save')
        result=self.invoke('feature.snapshots.observe',dict(contractVersion=VERSION,runId=self.shared.RUN,afterSequence=1))
        self.assertEqual('document-picker',result['state']['saveBackend']);self.assertEqual(1,result['state']['saved'])




# Used by the public normal-toolbar mutation counterprobe above.
from overte_phone_snapshot_system_ui import LABEL
if __name__=='__main__':unittest.main()
