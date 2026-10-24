"""Real Pico Favorite/Scale/URL owners over declared SDK/Qt/model DTO actors.

Original QML, Qt callbacks and actual persistent sources have separate native
owning tests. These actors never supply device, fetched-model or pixel proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import inspect
import os
import shutil
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
import test_avatar_urls_owner as url_fixture
RUN,ORIGINAL=url_fixture.RUN,url_fixture.ORIGINAL
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4 import avatar_bookmarks as books,avatar_bookmark_loads as loads
from adapters.pico4.navigation import NativeNavigationIO
from adapters.script_journey.history import unpack


class AvatarFavoritesTests(unittest.TestCase):
    def setUp(self):
        f=self.fixture=url_fixture.AvatarUrlsTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        f.source['avatarEntityStorage']['rows']=[]
        self.bookmarks={'unowned':dict(version=3,avatarUrl='qrc:/meshes/unowned.fst',avatarScale=1,avatarEntites=[])}
        self.original=deepcopy(self.bookmarks);self.events=[];self.packets={};self.sequences={'books':0,'loads':0};self.revision=0
        self.dialog_kind=None;self.managing=False;self.settings=False;self.ui_scale=1;self.ignore_scale=False;self.lose=None
        self.old_reader=f.reader;self.old_widgets=f.widgets;old_write=f.native.write_debug_app_file;old_read=f.native.read_debug_app_file
        f.reader=self.reader;f.widgets=self.widgets
        def read(target,package,path,**kwargs):
            for kind,module in (('books',books),('loads',loads)):
                if path=='files/overte-e2e/'+module.FILE:return '' if kind not in self.packets else json.dumps(self.packets[kind])
            return old_read(target,package,path,**kwargs)
        def write(target,package,path,raw):
            command=json.loads(raw);identifier=command['controlId']
            special=identifier.startswith('avatar.bookmark.') or identifier in ('avatar.settings','avatar.scale','avatar.settings.confirm') or identifier=='avatar.dialog.confirm' and self.dialog_kind is not None
            if not special:
                result=old_write(target,package,path,raw)
                if identifier=='avatar.dialog.cancel':self.dialog_kind=None
                return result
            current=self.widgets();row=next(row for row in current['controls'] if row['id']==identifier)
            self.assertEqual(row['token'],command['controlToken']);self.assertEqual(f.native.sequence+1,command['sequence'])
            f.native.inputs.append(deepcopy(command));f.native.sequence+=1
            if identifier=='avatar.bookmark.add':self.dialog_kind='save';f.dialog=True;f.focus=False;f.entered=''
            elif identifier=='avatar.bookmark.manage':self.managing=not self.managing
            elif identifier.startswith('avatar.bookmark.row.'):
                self.dialog_kind='delete' if self.managing else 'choose';f.dialog=True;f.focus=False;f.entered=''
            elif identifier=='avatar.settings':self.settings=True;self.ui_scale=f.source['scale']
            elif identifier=='avatar.scale':
                self.ui_scale=command['value']/10
                if not self.ignore_scale:f.source['scale']=f.source['targetScale']=self.ui_scale
            elif identifier=='avatar.settings.confirm':
                if not self.ignore_scale:f.source['scale']=f.source['targetScale']=self.ui_scale
                self.settings=False
            elif identifier=='avatar.dialog.confirm':
                if self.dialog_kind=='save':
                    self.assertEqual('e2e-'+RUN,f.entered);self.bookmarks[f.entered]=dict(version=3,avatarUrl=f.source['requestedUrl'],avatarScale=f.source['scale'],avatarEntites=[],avatarIcon='');self.revision+=1
                elif self.dialog_kind=='delete':del self.bookmarks['e2e-'+RUN];self.revision+=1
                else:self.apply_bookmark()
                f.dialog=False;f.focus=False;self.dialog_kind=None
            else:raise AssertionError(identifier)
            f.native.status=dict(schemaVersion=1,bridgeId=f.native.bridge_id,commandId=command['commandId'],sequence=command['sequence'],performed=True,error='',processId=123,updatedEpochMs=f.epoch)
            if self.lose==identifier:raise OSError('Declared lost result after original actor consumption')
        for boundary in (patch.object(f.native,'read_debug_app_file',side_effect=read),patch.object(f.native,'write_debug_app_file',side_effect=write),patch.object(f.native,'snapshot',side_effect=self.widgets)):
            boundary.start();self.addCleanup(boundary.stop)
        self.store=PrivateFeatureState(f.store.path.with_name(f.store.path.name.replace('avatar-urls-owner-','avatar-favorites-owner-')))
        if os.environ.get('OVERTE_AVATAR_NATIVE_ARTIFACTS'):
            destination=Path(tempfile.mkdtemp(prefix=self._testMethodName+'-',dir=os.environ['OVERTE_AVATAR_NATIVE_ARTIFACTS']))
            def retain_originals():
                identities={}
                for path in f.root.rglob('*'):
                    if path.is_file() and not path.is_symlink():
                        info=path.lstat();identities[str(path.relative_to(f.root))]=dict(device=info.st_dev,inode=info.st_ino,mode=info.st_mode,
                            bytes=info.st_size,modifiedNs=info.st_mtime_ns,changedNs=info.st_ctime_ns,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                shutil.copytree(f.root,destination/'original-state',symlinks=True)
                (destination/'original-identities.json').write_text(json.dumps(dict(kind='historical-fixture-originals-not-live-source',
                    sourceRoot=str(f.root),files=identities),sort_keys=True)+'\n')
            self.addCleanup(retain_originals)
    def apply_bookmark(self):
        f=self.fixture;record=self.bookmarks['e2e-'+RUN]
        if f.source['requestedUrl']!=record['avatarUrl']:f.effect(record['avatarUrl'])
        f.source['scale']=f.source['targetScale']=record['avatarScale']
        self.events.append(dict(id=uuid.uuid4().hex,nameSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest(),urlSha256=hashlib.sha256(record['avatarUrl'].encode()).hexdigest(),
            avatarInstance=f.source['avatarLoads']['instance'],sessionId=f.source['sessionId'],createdEpochMs=f.epoch,enteredEpochMs=f.epoch,returnedEpochMs=f.epoch,
            bookmarkScale=record['avatarScale'],bookmarkEntities=0,senderAlive=True,captureAlive=False,connectionObserved=True,connected=True,
            disconnectObserved=True,disconnected=True,dispatches=1,active=0,completed=True,ownerThreadOnly=True))
    def widgets(self):
        f=self.fixture;value=self.old_widgets()
        if f.page!='avatar':return value
        if self.dialog_kind in ('choose','delete'):value['controls']=[row for row in value['controls'] if row['id']!='avatar.dialog.input']
        for row in value['controls']:
            if 'managing' in row:row['managing']=self.managing
        def add(identifier,**extra):
            row=dict(id=identifier,enabled=True,focused=False,inputReady=True,managing=self.managing,**extra)
            row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,json.dumps(row,sort_keys=True)));value['controls'].append(row)
        add('avatar.bookmark.add');add('avatar.bookmark.manage');add('avatar.settings')
        for index,name in enumerate(sorted(self.bookmarks)):add('avatar.bookmark.row.'+str(index),bookmarkName=name)
        if self.settings:add('avatar.scale',value=self.ui_scale*10,**{'from':1,'to':40,'stepSize':.1});add('avatar.settings.confirm')
        return value
    def reader(self):
        reader=self.old_reader();send=reader.send
        def dispatch(request):
            if request['action']==books.ACTION:self.publish('books',request)
            elif request['action']==loads.ACTION:self.publish('loads',request)
            else:return send(request)
        reader.send=dispatch;return reader
    def publish(self,kind,request):
        f=self.fixture;self.sequences[kind]+=1
        if kind=='books':
            raw=json.dumps(self.bookmarks,sort_keys=True,separators=(',',':')).encode();digest=hashlib.sha256(raw).hexdigest()
            import base64
            storage=dict(avatarBookmarkStorageVersion=1,capturedEpochMs=f.epoch,pathSha256='1'*64,present=True,
                file=dict(bytes=len(raw),sha256=digest,revisionSha256=hashlib.sha256(str(self.revision).encode()).hexdigest()),rawBase64=base64.b64encode(raw).decode(),
                rawSha256=digest,cacheBase64=base64.b64encode(raw).decode(),mapSha256=digest,bookmarks=deepcopy(self.bookmarks))
            source=dict(picoAvatarBookmarksVersion=1,instance='6'*32,storage=storage)
        else:source=dict(picoAvatarBookmarkLoadsVersion=1,instance='7'*32,loads=dict(avatarBookmarkLoadsVersion=1,instance='8'*32,capturedEpochMs=f.epoch,rows=deepcopy(self.events)))
        self.packets[kind]=dict(schemaVersion=1,requestId=request['commandId'],instance='c'*32,sequence=self.sequences[kind],processId=123,requestedEpochMs=f.epoch,capturedEpochMs=f.epoch,source=source)
    def invoke(self,operation):
        f=self.fixture
        with f.lock.held():return f.instance._avatar_favorites(f.target,RUN,source_lock=f.lock).invoke(operation)
    def prepare(self):
        f=self.fixture;f.invoke('prepare');self.invoke('prepare');f.activate('avatar-url',dict(resource='avatar-a.fst'));f.invoke('act')
    def test_normal_save_scale_missing_choose_restore_delete_remains_owned(self):
        f=self.fixture;self.prepare()
        for verb,inputs in (('avatar-bookmark-save',dict(name='e2e-'+RUN)),('avatar-scale',dict(value=1.5))):f.activate(verb,inputs);self.invoke('act')
        self.assertEqual(1.5,f.source['scale']);f.activate('avatar-url',dict(resource='missing.fst'));f.invoke('act')
        self.assertEqual(1.5,f.source['scale']);f.activate('avatar-bookmark-choose',dict(name='e2e-'+RUN));self.invoke('act')
        self.assertEqual(1,f.source['scale']);self.assertTrue(f.source['requestedUrl'].endswith('/avatar-a.fst'));self.assertEqual(1,len(self.events))
        f.activate('avatar-restore');f.invoke('act');self.assertEqual(ORIGINAL,f.source['requestedUrl'])
        f.activate('avatar-bookmark-delete',dict(name='e2e-'+RUN));self.invoke('act');self.assertEqual(self.original,self.bookmarks)
        f.activate('cleanup');self.invoke('cleanup');self.assertEqual('retained',unpack(self.store.read()['payload'])[0]['stage'])
        self.assertTrue(f.instance._avatar_favorites_owned(f.target));self.assertIsNotNone(self.store.read())
    def save_owned(self):
        self.prepare();f=self.fixture;f.activate('avatar-bookmark-save',dict(name='e2e-'+RUN));self.invoke('act')
    def test_cached_callback_foreign_raw_preference_change_is_not_adopted(self):
        from adapters.pico4.avatar_preferences import baseline
        f=self.fixture;self.prepare();f.activate('avatar-bookmark-save',dict(name='e2e-'+RUN));self.invoke('act')
        original=self.apply_bookmark
        def foreign_during_callback():
            original();f.persisted_scale=2.5
        self.apply_bookmark=foreign_during_callback
        ticket=f.activate('avatar-bookmark-choose',dict(name='e2e-'+RUN))
        with f.lock.held():
            owner=f.instance._avatar_favorites(f.target,RUN,source_lock=f.lock)
            from adapters.normal_ui import NativeUIError
            with self.assertRaises(NativeUIError):owner.invoke('act')
            call=owner.state['calls'][-1];self.assertEqual(ticket,owner.state['pending']);self.assertFalse(call['settled'])
            before=owner.decode_frame(owner.state['frames'][call['before']-1])
            after=owner.decode_frame(owner.state['frames'][-1]);baseline(after['preferences'])
            self.assertEqual(before['native']['source']['requestedUrl'],after['native']['source']['requestedUrl'])
            self.assertEqual(1,after['native']['source']['scale'])
            key='Avatar/scale';a=before['preferences']['source']['snapshot'];b=after['preferences']['source']['snapshot']
            self.assertNotEqual(a['cache']['rows'][key],b['cache']['rows'][key])
            self.assertNotEqual(a['writer']['physical']['rows'],b['writer']['physical']['rows'])
            self.assertEqual(1,len(self.events));self.assertTrue(self.events[-1]['completed']);self.assertFalse(self.events[-1]['captureAlive'])
        self.assertTrue(f.instance._avatar_favorites_owned(f.target));self.assertEqual(2.5,f.persisted_scale)

    def test_lost_original_scale_confirm_reconciles_without_resend(self):
        f=self.fixture;self.save_owned();f.activate('avatar-scale',dict(value=1.5));self.lose='avatar.settings.confirm'
        with self.assertRaises(RuntimeError):self.invoke('act')
        self.assertEqual(1.5,f.source['scale']);count=len(f.native.inputs);self.lose=None;self.invoke('reconcile')
        self.assertEqual(count,len(f.native.inputs));self.assertIsNone(unpack(self.store.read()['payload'])[0]['pending'])
        self.assertTrue(f.instance._avatar_favorites_owned(f.target))
    def test_phase_advance_at_final_native_guard_prevents_favorite_input(self):
        f=self.fixture;self.prepare();f.activate('avatar-bookmark-save',dict(name='e2e-'+RUN));before=len(f.native.inputs)
        original=NativeNavigationIO.guard;fired=[]
        def guard(io):
            original(io)
            if inspect.currentframe().f_back.f_code.co_name=='send' and not fired:fired.append(True);f.activate('cleanup')
        with patch.object(NativeNavigationIO,'guard',guard),self.assertRaises(RuntimeError):self.invoke('act')
        self.assertEqual([True],fired);self.assertEqual(before,len(f.native.inputs));self.assertEqual(self.original,self.bookmarks)
        self.assertIsNotNone(unpack(self.store.read()['payload'])[0]['pending']);self.assertTrue(f.instance._avatar_favorites_owned(f.target))
    def test_foreign_preferences_before_scale_cannot_be_adopted_by_url_effect_proof(self):
        import base64,struct
        f=self.fixture;self.save_owned();original=f.preference_send
        def foreign(request):
            original(request);snapshot=f.preferences_packet['source']['snapshot'];key='Avatar/foreign-retained-setting'
            data=struct.pack('>IBi',2,0,7);raw=dict(present=True,typeId=2,typeName='int',base64=base64.b64encode(data).decode(),sha256=hashlib.sha256(data).hexdigest())
            encoded=dict(base64=base64.b64encode(b'7').decode(),sha256=hashlib.sha256(b'7').hexdigest())
            for kind in ('cache','writer'):
                snapshot[kind]['rows'][key]=deepcopy(raw);snapshot[kind]['encodedRows']['values'][key]=deepcopy(encoded);snapshot[kind]['encodedRows']['count']=len(snapshot[kind]['encodedRows']['values'])
            snapshot['writer']['physical']['rows']['values'][key]=deepcopy(encoded);snapshot['writer']['physical']['rows']['count']=len(snapshot['writer']['physical']['rows']['values'])
        f.preference_send=foreign;f.activate('avatar-scale',dict(value=1.5));self.invoke('act');before=len(f.native.inputs)
        f.activate('avatar-url',dict(resource='missing.fst'))
        with f.lock.held():
            owner=f.make();frame=owner.sample();known=owner.state['frames'][owner.state['calls'][-1]['quiet']['last']-1]
            native=json.loads(known['native']['raw'])['source']
            from adapters.pico4.avatar_favorite_effect import current
            from adapters.pico4.avatar_favorites import validate_frame
            proof=owner.favorites_factory().effect_proof()
            current(proof,owner.binding,RUN,owner.phase.fixture_url,json.loads(frame['native']['raw']),owner.preference_packet(frame['preferences']),frame['phaseAfter'])
            actual=validate_frame(proof['frames'][proof['before']-1],123,owner.binding,RUN)['preferences']
            key='Avatar/foreign-retained-setting'
            self.assertIn(key,actual['source']['snapshot']['writer']['physical']['rows']['values'])
            self.assertNotIn(key,owner.preference_packet(known['preferences'])['source']['snapshot']['writer']['physical']['rows']['values'])
            self.assertEqual(owner.stable(native),owner.stable(validate_frame(proof['frames'][proof['before']-1],123,owner.binding,RUN)['native']['source']))
            # This typed inner assertion sees the actual exception before the
            # shared lock deliberately hides all source errors. A NameError
            # or unrelated implementation error must fail this countercase.
            with self.assertRaises(NativeUIError):owner.favorite_admission(frame,native)
        with self.assertRaises(RuntimeError):f.invoke('act')
        self.assertEqual(before,len(f.native.inputs));self.assertEqual(1.5,f.source['scale'])
        self.assertTrue(f.instance._avatar_favorites_owned(f.target));self.assertTrue(f.instance._avatar_urls_owned(f.target))
    def test_nonempty_persisted_entity_size_refuses_even_with_empty_live_handles(self):
        import base64,struct
        f=self.fixture;original=f.preference_send
        def persisted(request):
            original(request);snapshot=f.preferences_packet['source']['snapshot'];key='Avatar/avatarEntityData/size'
            data=struct.pack('>IBi',2,0,1);raw=dict(present=True,typeId=2,typeName='int',base64=base64.b64encode(data).decode(),sha256=hashlib.sha256(data).hexdigest())
            encoded=dict(base64=base64.b64encode(b'1').decode(),sha256=hashlib.sha256(b'1').hexdigest())
            for kind in ('cache','writer'):
                snapshot[kind]['rows'][key]=deepcopy(raw);snapshot[kind]['encodedRows']['values'][key]=deepcopy(encoded);snapshot[kind]['encodedRows']['count']=len(snapshot[kind]['encodedRows']['values'])
            snapshot['writer']['physical']['rows']['values'][key]=deepcopy(encoded);snapshot['writer']['physical']['rows']['count']=len(snapshot['writer']['physical']['rows']['values'])
        f.preference_send=persisted
        with self.assertRaises(RuntimeError):self.invoke('prepare')
        self.assertFalse(f.native.inputs);self.assertEqual(self.original,self.bookmarks);self.assertTrue(f.instance._avatar_favorites_owned(f.target))
    def test_unowned_avatar_data_refuses_before_any_normal_favorite_input(self):
        f=self.fixture;f.source['avatarEntityStorage']['rows']=[dict(id='88888888-8888-4888-8888-888888888888',bytes=7,sha256=hashlib.sha256(b'unowned').hexdigest(),base64='dW5vd25lZA==')]
        with self.assertRaises(RuntimeError):self.invoke('prepare')
        self.assertFalse(f.native.inputs);self.assertEqual(self.original,self.bookmarks);self.assertTrue(f.instance._avatar_favorites_owned(f.target))

if __name__=='__main__':unittest.main()
