"""Closed reuse of the actual marker owner; no native or render qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.create_marker_scope import CreateMarkerScope,marker_name
from ios.adapters.create_marker_recovery import IOSCreateMarkerRecovery
from ios.adapters.create_marker_files import OwnedCreateMarkerFiles
from ios.adapters.create_originals import IOSCreateOriginals
from ios.self_tests.test_ios_create_marker_scope import MarkerScopeTests


class AssetsMarkerNamespaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture=MarkerScopeTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.template=self.fixture.owner();self.root=self.fixture.root
    def owner(self,namespace):
        scope=object.__new__(CreateMarkerScope);scope.__dict__=dict(self.template.__dict__)
        scope.namespace=namespace;scope.store=PrivateFeatureState(self.root/marker_name(scope.role,namespace))
        scope.frames=[];scope.state=deepcopy(self.template.state);scope.previous=scope.store.read()
        scope._version=(2 if namespace=='create' else 3) if scope.previous is None else scope.previous['iosCreateMarkerScopeVersion']
        scope.files=OwnedCreateMarkerFiles(None,scope.marker_store('files'),scope.binding)
        scope.originals=IOSCreateOriginals(self.root,scope.binding,scope.run,scope.role,scope.guard,scope.storage_intent,
            kind='inputs',namespace='create' if namespace=='create' else 'assets-marker')
        if scope.previous is not None:scope.state=scope.decode(scope.previous)
        return scope

    def test_existing_create_wal_and_its_original_bytes_do_not_collide_with_assets_scope_same_root_and_run(self):
        legacy=self.owner('create');calls=[];legacy.once('open-marker-manager',lambda:calls.append('old') or dict(delivered=True))
        before=legacy.store.path.stat().st_ino,legacy.store.path.read_bytes();assets=self.owner('assets')
        assets.once('open-marker-manager',lambda:calls.append('assets') or dict(delivered=True))
        self.assertEqual(['old','assets'],calls);self.assertEqual(before,(legacy.store.path.stat().st_ino,legacy.store.path.read_bytes()))
        old,new=legacy.store.read(),assets.store.read();self.assertEqual(2,old['iosCreateMarkerScopeVersion']);self.assertNotIn('scopeNamespace',old)
        self.assertEqual(3,new['iosCreateMarkerScopeVersion']);self.assertEqual('assets',new['scopeNamespace'])
        for kind in ('scope','files','script','recovery'):
            self.assertNotEqual(legacy.marker_store(kind).path,assets.marker_store(kind).path)
        restored=self.owner('assets');self.assertEqual(dict(delivered=True),restored.once('open-marker-manager',lambda:need(False)))
        self.assertEqual(['old','assets'],calls)

    def test_archive_requires_independently_supplied_namespace_and_rejects_header_relabeling(self):
        old=self.owner('create');new=self.owner('assets');old.save();new.save()
        def archive(value,namespace='create'):
            return CreateMarkerScope.archive(value,root=self.root,binding=old.binding,run=old.run,role=old.role,lock=old.lock,namespace=namespace)
        self.assertEqual(old.state,archive(old.store.read()).state);self.assertEqual(new.state,archive(new.store.read(),'assets').state)
        for value,namespace in ((new.store.read(),'create'),(old.store.read(),'assets'),(new.store.read(),'unknown')):
            with self.subTest(namespace=namespace),self.assertRaises(NativeUIError):archive(value,namespace)
        relabeled=deepcopy(new.store.read());relabeled['iosCreateMarkerScopeVersion']=2
        with self.assertRaises(NativeUIError):archive(relabeled)
        relabeled=deepcopy(new.store.read());relabeled['scopeNamespace']='create'
        with self.assertRaises(NativeUIError):archive(relabeled,'assets')

    def test_original_and_manifest_schema_hash_inode_and_stream_counter_boundaries_stay_disjoint(self):
        old=self.owner('create');assets=self.owner('assets');stores=[];frame=dict(opaqueOriginal='unchanged marker source bytes')
        for scope in (old,assets):
            store=IOSCreateOriginals(self.root,scope.binding,scope.run,scope.role,lambda:True,lambda *_:True,kind='inputs',namespace=scope.originals.namespace)
            reference=store.write(1,frame);manifest=store.append([],reference);stores.append((store,reference,manifest))
        a,refa,ma=stores[0];b,refb,mb=stores[1]
        self.assertNotEqual(a.path(a.expand(refa)),b.path(b.expand(refb)));self.assertNotEqual(a.key('FrameVersion'),b.key('FrameVersion'))
        before={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.root.iterdir() if path.is_file()}
        self.assertEqual([frame],a.restore(ma,1));self.assertEqual([frame],b.restore(mb,1))
        for store,reference,manifest in ((a,refb,mb),(b,refa,ma)):
            with self.assertRaises((NativeUIError,OSError)):store.restore(manifest,1)
            with self.assertRaises((NativeUIError,OSError)):store.read(store.expand(reference))
        with self.assertRaises(NativeUIError):b.append(mb,refb)
        changed=deepcopy(refb);changed['sha256']='f'*64
        with self.assertRaises((NativeUIError,OSError)):b.read(b.expand(changed))
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.root.iterdir() if path.is_file()})

    def test_recovery_and_abandoned_read_prefix_keep_original_namespace_and_counters(self):
        old=self.owner('create');assets=self.owner('assets');old.save();assets.save()
        legacy=IOSCreateMarkerRecovery(old);legacy.save();before=(legacy.store.path.stat().st_ino,legacy.store.path.read_bytes())
        assets.state['pending']=dict(label='unknown-passive-source',original=None,manifest=None,partial={});assets.save()
        recovery=IOSCreateMarkerRecovery(assets);recovery.recover()
        self.assertEqual(1,len(recovery.state['records']));self.assertIsNone(assets.state['pending']);self.assertEqual(2,recovery.store.read()['iosCreateMarkerRecoveryVersion'])
        self.assertEqual('assets',recovery.store.read()['scopeNamespace']);self.assertEqual(before,(legacy.store.path.stat().st_ino,legacy.store.path.read_bytes()))
        self.assertNotEqual(legacy.record_store(1).path,recovery.record_store(1).path)
        reference=recovery.state['records'][0];record=recovery.record(reference);self.assertEqual(2,record['iosCreateMarkerAbandonedReadVersion'])
        self.assertEqual('assets',record['scopeNamespace']);self.assertEqual(3,record['priorOwner']['iosCreateMarkerScopeVersion'])
        for reader,value in ((legacy,recovery.store.read()),(recovery,legacy.store.read())):
            with self.assertRaises(NativeUIError):reader.decode(value)
        corrupted=dict(reference,sha256='f'*64)
        with self.assertRaises(NativeUIError):recovery.record(corrupted)
        self.assertEqual(recovery.state,IOSCreateMarkerRecovery(self.owner('assets')).state)

    def test_unknown_namespace_or_private_child_kind_cannot_select_arbitrary_paths(self):
        for namespace in ('assets-marker','../assets','','create-other',None):
            with self.subTest(namespace=namespace),self.assertRaises(NativeUIError):marker_name('primary',namespace)
        with self.assertRaises(NativeUIError):marker_name('primary','assets','../files')
        with self.assertRaises(NativeUIError):IOSCreateOriginals(self.root,self.template.binding,self.template.run,'primary',lambda:True,lambda *_:True,namespace='other')

    def test_pending_manifest_namespace_and_counter_cannot_adopt_foreign_index_or_schema(self):
        scope=self.owner('assets');writer=IOSCreateOriginals(self.root,scope.binding,scope.run,scope.role,lambda:True,lambda *_:True,kind='inputs',namespace='assets-marker')
        original=writer.write(1,dict(opaquePendingSource='retained before acceptance'));manifests=writer.append([],original)
        state=deepcopy(scope.state);state['pending']=dict(label='pending-original',original=writer.expand(original),partial={},
            manifest=dict(assetsMarkerManifestVersion=1,reference=manifests[0],phase='saved'))
        self.assertEqual(state,scope.decode(scope.envelope(state)))
        for fault in ('namespace','counter','version'):
            bad=deepcopy(state);manifest=bad['pending']['manifest']
            if fault=='namespace':manifest['createManifestVersion']=manifest.pop('assetsMarkerManifestVersion')
            elif fault=='counter':manifest['reference']['count']+=1
            else:manifest['assetsMarkerManifestVersion']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):scope.decode(scope.envelope(bad))


class AssetsMarkerNamespaceFactoryTests(unittest.TestCase):
    def test_actual_runtime_constructor_keeps_create_default_two_and_assets_three_canonical_stores_without_input(self):
        from ios.self_tests.assets_runtime_fixture import RuntimeBoundary
        from ios.self_tests.assets_reply_fixture import RUN,TICKET,URL
        b=RuntimeBoundary(self);before=b.f.sessions,b.f.launches,deepcopy(b.f.commands)
        legacy=CreateMarkerScope(b.runtime,'test-only',b.root,RUN,'primary',URL,TICKET,b.lock);legacy.save()
        old=(legacy.store.path.stat().st_ino,legacy.store.path.read_bytes())
        assets=CreateMarkerScope(b.runtime,'test-only',b.root,RUN,'primary',URL,TICKET,b.lock,namespace='assets');assets.save()
        self.assertEqual(2,legacy.store.read()['iosCreateMarkerScopeVersion']);self.assertEqual(3,assets.store.read()['iosCreateMarkerScopeVersion'])
        self.assertEqual('assets-marker',assets.originals.namespace);self.assertEqual('assetsMarker',assets.originals.schema_prefix)
        self.assertEqual('ios-assets-marker-scope-primary.json',assets.store.path.name)
        self.assertEqual('ios-assets-marker-scope-primary-files.json',assets.files.store.path.name)
        self.assertEqual(old,(legacy.store.path.stat().st_ino,legacy.store.path.read_bytes()));self.assertEqual(before[:2],(b.f.sessions,b.f.launches))
        self.assertEqual(before[2],b.f.commands[:len(before[2])])
        current=b.f.commands[len(before[2]):];self.assertTrue(current)
        self.assertTrue(all(operation in ('mobile: overteProcessSourceInfo','mobile: overteProcessInfo','mobile: pullFile') for operation,_values in current))
        self.assertEqual([],b.asset_requests);self.assertEqual([],b.afc)
