"""Original SessionEnd v2 OS query ownership, no native/device end claim.

The prior complete Tablet/OS authority is the existing explicit component
fixture. The real current reader, WAL, HTTP and CAS paths execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.self_tests import test_ios_tablet_web_session_end as fixture


class TabletSessionOSWALTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TabletSessionEndTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def literal_v1(self,owner):
        value=deepcopy(owner.store.read());state=unpack(value['payload'])[0]
        state.pop('osPending');state.pop('osBlocked');value['tabletWebSessionEndVersion']=1;value['payload']=pack([state])
        owner.store.write(value,owner.store.read());return value

    def test_actual_query_id_is_saved_before_wire_and_returned_original_keeps_its_clocks(self):
        with self.f.lock.held():
            owner=self.f.owner();send=self.f.os.send;seen=[];readers=[]
            def observed(query):
                saved=owner.store.read();state=unpack(saved['payload'])[0]
                self.assertEqual(2,saved['tabletWebSessionEndVersion']);self.assertEqual('preparing-os',state['phase'])
                self.assertEqual(query,state['osPending']['query']);self.assertEqual([],state['osHistory'])
                seen.append(deepcopy(query));return send(query)
            self.f.os.send=observed;factory=self.f.os.reader
            def reader():
                value=factory();readers.append((value,value.send));return value
            self.f.os.reader=reader;owner.prepare()
            self.assertEqual(1,len(seen));self.assertEqual(seen[0]['commandId'],owner.state['osOriginal']['commandId'])
            self.assertEqual(self.f.os.original,owner.state['osOriginal']);self.assertIsNone(owner.state['osPending'])
            self.assertIs(readers[0][0].send,readers[0][1]);self.assertEqual([],self.f.server.calls)

    def test_lost_return_keeps_original_pending_query_and_reconstruction_never_resends(self):
        with self.f.lock.held():
            send=self.f.os.send
            def lost(query):send(query);raise OSError('Actual original OS reply return lost')
            self.f.os.send=lost;owner=self.f.owner()
            with self.assertRaises(NativeUIError):owner.advance()
            saved=owner.store.path.read_bytes();inode=owner.store.path.stat().st_ino
            self.assertEqual(self.f.os.queries[-1],owner.state['osPending']['query'])
            self.assertEqual([],owner.state['osHistory']);self.assertEqual([],self.f.server.calls)
            calls=deepcopy(self.f.os.queries);self.f.os.send=send
            with self.assertRaises(NativeUIError):self.f.owner().advance()
            self.assertEqual(calls,self.f.os.queries);self.assertEqual([],self.f.server.calls)
            self.assertEqual(saved,owner.store.path.read_bytes());self.assertEqual(inode,owner.store.path.stat().st_ino)

    def test_slow_issued_WAL_keeps_original_deadline_and_blocks_wire_before_any_new_OS_query(self):
        with self.f.lock.held():
            owner=self.f.owner();write=owner.store.write;slow=[];calls=deepcopy(self.f.os.queries)
            def delayed(value,previous):
                write(value,previous)
                if owner.state['osPending'] is not None and not slow:slow.append(True);self.f.os.clock+=2
            owner.store.write=delayed
            with self.assertRaises(NativeUIError):owner.advance()
            self.assertTrue(slow);self.assertIsNotNone(owner.state['osPending'])
            self.assertEqual(calls,self.f.os.queries);self.assertEqual([],self.f.server.calls)
            with self.assertRaises(NativeUIError):self.f.owner().advance()
            self.assertEqual(calls,self.f.os.queries);self.assertEqual([],self.f.server.calls)

    def test_invalid_return_cannot_erase_issued_nonce_or_enable_a_fresh_query_on_reentry(self):
        with self.f.lock.held():
            self.f.os.mutate=lambda value:value.update(commandId='ios-'+'f'*32)
            owner=self.f.owner()
            with self.assertRaises(NativeUIError):owner.advance()
            query=deepcopy(self.f.os.queries[-1]);self.assertNotEqual(query['commandId'],self.f.os.original['commandId'])
            self.assertEqual(query,owner.state['osPending']['query']);self.assertEqual([],owner.state['osHistory'])
            saved=owner.store.path.read_bytes();calls=deepcopy(self.f.os.queries);self.f.os.mutate=None
            with self.assertRaises(NativeUIError):self.f.owner().advance()
            self.assertEqual(saved,owner.store.path.read_bytes());self.assertEqual(calls,self.f.os.queries)
            self.assertEqual([],self.f.server.calls);self.assertTrue(self.f.server.present)

    def returned_save_failure(self,after):
        owner=self.f.owner();write=owner.store.write;lost=[]
        def interrupted(value,previous):
            returned=owner.state['osHistory'] and owner.state['osPending'] is None
            if returned and not lost:
                lost.append(True)
                if after:write(value,previous)
                raise OSError('Actual returned OS parent-save acknowledgement lost')
            return write(value,previous)
        owner.store.write=interrupted
        with self.assertRaises(OSError):owner.advance()
        self.assertTrue(lost);self.assertEqual([],self.f.server.calls);return owner

    def test_saved_return_reentry_adopts_original_first_receipt_without_querying_it_again(self):
        with self.f.lock.held():
            self.returned_save_failure(True);first=deepcopy(self.f.os.original);count=len(self.f.os.queries)
            rebuilt=self.f.owner();self.assertEqual('preparing-os',rebuilt.state['phase'])
            self.assertIsNone(rebuilt.state['osPending']);self.assertEqual(first,rebuilt.state['osHistory'][0]['original'])
            self.assertIsNotNone(rebuilt.advance());self.assertEqual('complete',rebuilt.state['phase'])
            self.assertEqual(count+1,len(self.f.os.queries))  # Only the distinct pre-DELETE current check.
            self.assertEqual(first,rebuilt.state['osHistory'][0]['original'])
            self.assertEqual(1,sum(method=='DELETE' for method,_path in self.f.server.calls))

    def test_unsaved_return_reentry_retains_issued_query_without_HTTP_or_OS_retry(self):
        with self.f.lock.held():
            owner=self.returned_save_failure(False);calls=deepcopy(self.f.os.queries)
            rebuilt=self.f.owner();self.assertIsNotNone(rebuilt.state['osPending'])
            self.assertEqual([],rebuilt.state['osHistory']);saved=owner.store.path.read_bytes()
            with self.assertRaises(NativeUIError):rebuilt.advance()
            self.assertEqual(calls,self.f.os.queries);self.assertEqual([],self.f.server.calls)
            self.assertEqual(saved,owner.store.path.read_bytes())

    def test_literal_v1_completed_archive_remains_read_only_without_rewrite(self):
        with self.f.lock.held():
            owner=self.f.owner();owner.advance();legacy=self.literal_v1(owner)
            saved=owner.store.path.read_bytes();inode=owner.store.path.stat().st_ino
            requests=list(self.f.server.calls);queries=deepcopy(self.f.os.queries)
            self.assertEqual(legacy,self.f.owner().advance())
            self.assertEqual(saved,owner.store.path.read_bytes());self.assertEqual(inode,owner.store.path.stat().st_ino)
            self.assertEqual(requests,self.f.server.calls);self.assertEqual(queries,self.f.os.queries)

    def test_literal_v1_unissued_preparation_cannot_gain_new_OS_or_DELETE_authority(self):
        with self.f.lock.held():
            owner=self.f.owner();owner.prepare();self.literal_v1(owner)
            saved=owner.store.path.read_bytes();queries=deepcopy(self.f.os.queries)
            with self.assertRaises(NativeUIError):self.f.owner().advance()
            self.assertEqual(saved,owner.store.path.read_bytes());self.assertEqual(queries,self.f.os.queries)
            self.assertEqual([],self.f.server.calls)

    def test_literal_v1_uncertain_DELETE_reconciles_GET404_without_another_DELETE_or_OS_query(self):
        with self.f.lock.held():
            self.f.server.lose=True;owner=self.f.owner()
            with self.assertRaises((ValueError,RuntimeError)):owner.advance()
            self.assertEqual('delete-issued',owner.state['phase']);self.literal_v1(owner)
            queries=deepcopy(self.f.os.queries);result=self.f.owner().advance()
            self.assertEqual(1,result['tabletWebSessionEndVersion']);self.assertEqual(queries,self.f.os.queries)
            self.assertEqual(1,sum(method=='DELETE' for method,_path in self.f.server.calls))
            self.assertEqual('GET',self.f.server.calls[-1][0]);self.assertIsNone(self.f.fixture.store.read())

    def test_rehashed_v2_blocked_presence_cannot_be_relabelled_as_absent_or_legacy(self):
        with self.f.lock.held():
            owner=self.f.owner();owner.prepare()
            self.f.os.mutate=lambda value:value['pidChecks'][0].update(running=True)
            with self.assertRaises(NativeUIError):owner.advance()
            value=deepcopy(owner.store.read());state=unpack(value['payload'])[0];self.assertTrue(state['osBlocked'])
            state['osBlocked']=False;value['payload']=pack([state])
            with self.assertRaises(NativeUIError):owner.decode(value)
            state.pop('osPending');state.pop('osBlocked');value['tabletWebSessionEndVersion']=1;value['payload']=pack([state])
            with self.assertRaises(NativeUIError):owner.decode(value)
            self.assertTrue(self.f.server.present);self.assertEqual(0,sum(method=='DELETE' for method,_path in self.f.server.calls))


if __name__=='__main__':unittest.main()
