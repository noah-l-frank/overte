"""Explicit raw range profiles; real bytes/OFD/CAS, no native/device producer."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import tempfile
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_raw_archive import AudioRawArchive,MAX_LITERAL,PART
from adapters.script_journey.lock import ScriptSourceLock


class RawLiteralProfileTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.lock=ScriptSourceLock(self.path/'script-sources.lock')
        self.cost=dict(parts=0,storedBytes=0,decodedBytes=0);self.counter=0

    def make(self,*,scope=None,limit=MAX_LITERAL):
        value=AudioRawArchive(self.path/'raw.json',dict(testOnlyRawProfileVersion=1) if scope is None else scope,
            self.lock,self.lock.assert_held,lambda:dict(self.cost),lambda:1.,literal_limit=limit)
        self.addCleanup(lambda:self.assertTrue(value.close_host()));return value

    def large(self):
        return self.make(scope=dict(testOnlyRawProfileVersion=1,maximumLiteralBytes=4*MAX_LITERAL),limit=4*MAX_LITERAL)

    def test_exact_four_mib_binary_original_and_ranges_survive_actual_close(self):
        archive=self.large();literal=hashlib.shake_256(b'actual private binary original').digest(4*MAX_LITERAL)
        token=archive.reserve('assets-source',dict(operation='get-original'),len(literal))
        reference=archive.retain(token,literal);self.assertEqual(literal,archive.literal(reference))
        self.assertEqual(64,archive.bill()['parts']);self.assertEqual(1,archive.state['reads'])
        self.assertFalse(archive.state['pending'])
        self.assertTrue(all(row['bytes']<=PART for row in archive.state['parts']))
        with self.lock.held():archive.seal_part()
        self.assertTrue(all(row['closed'] for row in archive.state['parts']))
        self.assertEqual(literal,archive.literal(reference));self.assertEqual(1,archive.bill()['receipts'])

    def test_default_one_mib_profile_refuses_larger_reservation_before_getter(self):
        archive=self.make();calls=[]
        with self.assertRaises(NativeUIError):
            token=archive.reserve('native',dict(operation='read'),MAX_LITERAL+1);calls.append(True)
        self.assertEqual([],calls);self.assertEqual([],archive.state['pending']);self.assertEqual(0,archive.state['reads'])

    def test_four_mib_is_not_selected_without_matching_explicit_scope(self):
        with self.assertRaises(NativeUIError):self.make(limit=4*MAX_LITERAL)
        self.assertFalse((self.path/'raw.json').exists())
        with self.assertRaises(NativeUIError):self.make(scope=dict(maximumLiteralBytes=4*MAX_LITERAL))
        self.assertFalse((self.path/'raw.json').exists())

    def test_unsupported_or_aliased_profile_is_refused_before_any_file(self):
        for value in (None,True,float(MAX_LITERAL),0,2*MAX_LITERAL,8*MAX_LITERAL):
            with self.subTest(value=value),self.assertRaises(NativeUIError):
                self.make(scope=dict(maximumLiteralBytes=value),limit=value)
            self.assertFalse((self.path/'raw.json').exists())

    def test_mutated_live_or_private_limit_cannot_expand_existing_scope(self):
        archive=self.make()
        archive.literal_limit=archive._literal_limit=4*MAX_LITERAL
        with self.assertRaises(NativeUIError):archive.reserve('native',dict(operation='read'),4*MAX_LITERAL)
        self.assertEqual([],archive.state['pending']);self.assertEqual(0,archive.state['reads'])

    def test_scope_limit_or_profile_carrier_replacement_cannot_reseal_owner(self):
        archive=self.large();archive.literal_profile=tuple([*archive.literal_profile])
        with self.assertRaises(NativeUIError):archive.verify()
        self.assertEqual([],archive.state['pending'])

    def test_compound_part_budget_still_precedes_actual_get(self):
        archive=self.large();self.cost['parts']=448;calls=[]
        with self.assertRaises(NativeUIError):
            token=archive.reserve('native',dict(operation='read'),4*MAX_LITERAL);calls.append(True)
        self.assertEqual([],calls);self.assertEqual([],archive.state['pending'])

    def test_existing_command_cap_is_not_raised(self):
        archive=self.large();calls=[]
        with self.assertRaises(NativeUIError):
            token=archive.reserve('native',dict(operation='read',padding='x'*4096),4*MAX_LITERAL);calls.append(True)
        self.assertEqual([],calls);self.assertEqual([],archive.state['pending'])


    def test_existing_side_byte_cap_refuses_before_any_original_read(self):
        archive=self.large();calls=[]
        with self.assertRaises(NativeUIError):
            token=archive.reserve('native',dict(operation='read'),4*MAX_LITERAL,
                side_bytes=2*(11*48000*2*2+44)+1);calls.append(True)
        self.assertEqual([],calls);self.assertEqual([],archive.state['pending'])
        self.assertEqual(0,archive.state['reads'])

    def test_compound_sixteen_mib_budget_is_not_raised_with_larger_literals(self):
        for field in ('storedBytes','decodedBytes'):
            with self.subTest(field=field):
                # Each subcase owns an original namespace; no failed owner is retried.
                self.counter+=1
                archive=AudioRawArchive(self.path/f'budget-{self.counter}.json',
                    dict(maximumLiteralBytes=4*MAX_LITERAL),self.lock,self.lock.assert_held,
                    lambda:dict(self.cost),lambda:1.,literal_limit=4*MAX_LITERAL)
                self.addCleanup(lambda value=archive:self.assertTrue(value.close_host()))
                self.cost.update(parts=0,storedBytes=0,decodedBytes=0)
                self.cost[field]=16*MAX_LITERAL
                with self.assertRaises(NativeUIError):archive.reserve('native',dict(operation='read'),4*MAX_LITERAL)
                self.assertEqual([],archive.state['pending']);self.assertEqual(0,archive.state['reads'])


if __name__=='__main__':unittest.main()
