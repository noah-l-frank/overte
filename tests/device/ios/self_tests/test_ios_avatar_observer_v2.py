"""Observer2 private staged originals, frozen v1 compatibility and no replay."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_avatar_observer as observer_fixture
from ios.self_tests.avatar_observer_v1_producer import LegacyAvatarObserver1


class Observer2Tests(unittest.TestCase):
    setUp=observer_fixture.AvatarObserverTests.setUp
    owner=observer_fixture.AvatarObserverTests.owner

    def test_frozen_legacy_writer_originals_are_read_unchanged_before_new_writer2(self):
        new=self.owner();legacy=LegacyAvatarObserver1(new.store,new.sources,new.peers,new.surfaces,new.samples,
            new.authority,new.phase,role=new.role,guard=lambda:True,expected_code=new.expected_code,
            epoch_ms=new.epoch_ms,monotonic=new.monotonic)
        first=legacy.observe();before=legacy.store.path.read_bytes();row=deepcopy(legacy.state['rows'][0])
        raw=legacy.originals.path(legacy.originals.expand(row['original'])).read_bytes()
        restored=self.owner();self.assertEqual(before,restored.store.path.read_bytes())
        self.assertEqual(first,restored.validate_original(row)['public'])
        second=restored.observe(first['sequence']);self.assertEqual(2,second['sequence'])
        header=restored.store.read();self.assertEqual(2,header['iosAvatarObserverVersion'])
        records=[restored.read_record(item) for item in restored.state['rows']]
        self.assertEqual([1,2],[item['iosAvatarObservationRecordVersion'] for item in records])
        self.assertEqual(raw,legacy.originals.path(legacy.originals.expand(row['original'])).read_bytes())
        self.assertEqual(1,len(unpack(header['payload'])))

    def test_dense_actual_component_is_owned_outside_fixed_journal_and_reconstructed_file_only(self):
        for surface in self.surfaces.values():surface.previous['actualSyntheticSurfaceHistory']=os.urandom(40000).hex()
        owner=self.owner();public=owner.observe();self.assertLess(owner.store.path.stat().st_size,65536)
        row=owner.state['rows'][0];record=owner.read_record(row)
        self.assertEqual(2,record['iosAvatarObservationRecordVersion']);self.assertIn('parts',record)
        self.assertGreater(len(str(record)),160000)
        before=list(self.calls);restored=self.owner()
        def forbidden(*_args,**_kwargs):raise AssertionError('Historical acquisition invoked SDK continuity')
        restored.guard=forbidden;restored.originals.guard=forbidden
        self.f.client.request=forbidden
        self.assertEqual(public,restored.validate_original(row)['public']);self.assertEqual(before,self.calls)
        for name,ref in record['parts'].items():
            value=restored.carrier('part').read(ref);self.assertEqual(name,value['name']);self.assertEqual(record['partial'][name],value['value'])

    def test_lost_staged_saved_return_is_adopted_without_another_query_or_file(self):
        owner=self.owner();storage=owner.carrier_storage
        def lost(kind,name,value):
            storage(kind,name,value)
            if kind=='staged' and value['phase']=='saved':raise OSError('Actual staged return lost')
        owner.carrier_storage=lost
        with self.assertRaises(OSError):owner.observe()
        self.assertEqual('saved',owner.state['pending']['record']['phase']);self.assertIsNone(owner.state['pending']['original'])
        before=list(self.calls);restored=self.owner();row=restored.recover()
        self.assertEqual('observed',row['status']);self.assertEqual(before,self.calls)
        self.assertEqual(1,len(list(self.f.g.root.glob('avatar-observation-staged-frame-*.json'))))
        self.assertEqual(1,restored.validate_original(row)['public']['sequence'])

    def test_lost_opened_component_retains_private_inode_and_its_actual_partial_bytes(self):
        owner=self.owner();storage=owner.carrier_storage
        def lost(kind,name,value):
            storage(kind,name,value)
            if kind=='part' and owner.writing_part=='authorityBefore' and value['phase']=='opened':raise OSError('Actual component write interrupted')
        owner.carrier_storage=lost
        with self.assertRaises(OSError):owner.observe()
        ref=deepcopy(owner.state['pending']['partial']['authorityBefore']);path=owner.carrier('part').path(ref)
        self.assertEqual(b'',path.read_bytes());inode=path.stat().st_ino;before=list(self.calls)
        restored=self.owner();row=restored.recover();record=restored.read_record(row)
        self.assertEqual('abandoned',row['status']);self.assertEqual(before,self.calls)
        self.assertEqual(inode,path.stat().st_ino);self.assertEqual(ref,record['parts']['authorityBefore'])
        self.assertNotIn('authorityBefore',record['partial']);self.assertEqual(b'',path.read_bytes())
        os.link(path,path.with_name(path.name+'.extra'))
        with self.assertRaises(NativeUIError):restored.read_record(row)

    def test_abandoned_empty_part_cannot_gain_or_lose_same_inode_bytes(self):
        owner=self.owner();storage=owner.carrier_storage
        def lost(kind,name,value):
            storage(kind,name,value)
            if kind=='part' and owner.writing_part=='authorityBefore' and value['phase']=='opened':raise OSError('Opened empty part lost')
        owner.carrier_storage=lost
        with self.assertRaises(OSError):owner.observe()
        ref=deepcopy(owner.state['pending']['partial']['authorityBefore']);path=owner.carrier('part').path(ref)
        restored=self.owner();row=restored.recover();record=restored.read_record(row)
        self.assertEqual(0,record['partFiles']['authorityBefore']['bytes'])
        self.assertEqual(hashlib.sha256(b'').hexdigest(),record['partFiles']['authorityBefore']['sha256'])
        inode=path.stat().st_ino;path.write_bytes(b'{');self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):restored.read_record(row)
        path.write_bytes(b'')
        with self.assertRaises(NativeUIError):restored.read_record(row)
        self.assertEqual('abandoned',self.owner().read_record(row)['status'])

    def test_abandoned_opened_staged_body_keeps_its_actual_partial_hash(self):
        owner=self.owner();storage=owner.carrier_storage
        def lost(kind,name,value):
            storage(kind,name,value)
            if kind=='staged' and value['phase']=='opened':raise OSError('Opened stage lost')
        owner.carrier_storage=lost
        with self.assertRaises(OSError):owner.observe()
        ref=deepcopy(owner.state['pending']['record']);path=owner.carrier('staged').path(ref)
        # A real process may have written a prefix after its opened callback.
        path.write_bytes(b'{');inode=path.stat().st_ino
        restored=self.owner();row=restored.recover();record=restored.read_record(row)
        self.assertEqual(1,record['abandonment']['stagedFile']['bytes'])
        self.assertEqual(hashlib.sha256(b'{').hexdigest(),record['abandonment']['stagedFile']['sha256'])
        path.write_bytes(b'');self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):restored.read_record(row)
        path.write_bytes(b'[')
        with self.assertRaises(NativeUIError):restored.read_record(row)
        path.write_bytes(b'{')
        with self.assertRaises(NativeUIError):restored.read_record(row)
        self.assertEqual('abandoned',self.owner().read_record(row)['status'])

    def test_planned_part_or_final_original_cannot_treat_dangling_reserved_symlink_as_absence(self):
        for kind in ('part','original'):
            with self.subTest(kind=kind):
                # Each callback really stored planned ownership before the
                # writer could create its reserved pathname.
                owner=self.owner()
                if kind=='part':
                    storage=owner.carrier_storage
                    def lost(profile,name,value):
                        storage(profile,name,value)
                        if profile=='part' and value['phase']=='planned':raise OSError('Planned component interrupted')
                    owner.carrier_storage=lost
                else:
                    intent=owner.originals.intent
                    def lost(name,value):
                        intent(name,value)
                        if value['phase']=='planned':raise OSError('Planned final original interrupted')
                    owner.originals.intent=lost
                with self.assertRaises(OSError):owner.observe()
                pending=owner.state['pending']
                ref=pending['partial']['started'] if kind=='part' else pending['original']
                store=owner.carrier('part') if kind=='part' else owner.originals;path=store.path(ref)
                self.assertEqual('planned',ref['phase']);self.assertFalse(path.exists())
                os.symlink(path.with_name('not-created-original'),path)
                self.assertFalse(path.exists());self.assertTrue(os.path.lexists(path))
                with self.assertRaises(NativeUIError):
                    owner.carrier_file('part',ref) if kind=='part' else owner.partial_file(ref)
                path.unlink()
                # Settle only the original passive attempt; no input is sent.
                restored=self.owner();row=restored.recover();restored.read_record(row)
                os.symlink(path.with_name('not-created-original'),path)
                with self.assertRaises(NativeUIError):restored.read_record(row)
                path.unlink()

    def test_staged_descriptor_or_component_bytes_cannot_be_substituted(self):
        owner=self.owner();owner.observe();row=owner.state['rows'][0];record=owner.read_record(row)
        bad=deepcopy(record);bad['parts']['started']['sha256']='0'*64
        with self.assertRaises((NativeUIError,FileNotFoundError)):owner.record(bad)
        bad=deepcopy(row);bad['staged']['file']['inode']+=1
        with self.assertRaises(NativeUIError):owner.read_record(bad)


if __name__=='__main__':unittest.main()
