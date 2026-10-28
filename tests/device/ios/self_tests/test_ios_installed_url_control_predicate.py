"""Current installed-source strings retain literal URL/control semantics.

Every call scans the actual exact string; no URI, source or verdict cache is
introduced. These parser cases do not qualify native execution or Photo End.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import builtins
import re
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import places_http as source


class InstalledURLControlPredicateTests(unittest.TestCase):
    suffix='/modules/request.js'
    def url(self,text='safe'):return 'qrc:/scripts/'+text+self.suffix

    def test_every_raw_C0_and_DEL_refuses_at_all_three_URL_positions(self):
        for ordinal in (*range(32),127):
            for value in (chr(ordinal)+self.url(),self.url('safe'+chr(ordinal)),self.url()+chr(ordinal)):
                with self.subTest(ordinal=ordinal),self.assertRaises(NativeUIError):source.installed(value,self.suffix)

    def test_noncontrol_Unicode_and_lone_surrogates_keep_original_string_identity(self):
        for text in (' ','\u0080','\u0085','\u00a0','\u200b','\u2028','\u2029','\ufeff','\uffff','\U00010000','\U0010ffff','\ud800','\udfff','\ud800\udc00'):
            value=self.url('part'+text)
            with self.subTest(ordinal=[ord(c) for c in text]):self.assertIs(value,source.installed(value,self.suffix))

    def test_exact_4096_boundary_and_rejection_before_subclass_or_opaque_hooks(self):
        class Foreign(str):
            def __len__(self):raise AssertionError('Subclass length hook reached')
            def __iter__(self):raise AssertionError('Subclass iterator hook reached')
            def __str__(self):raise AssertionError('Subclass stringify hook reached')
        class Opaque:
            def __str__(self):raise AssertionError('Opaque stringify hook reached')
        prefix='qrc:/scripts/';value=prefix+'x'*(4096-len(prefix)-len(self.suffix))+self.suffix
        self.assertEqual(4096,len(value));self.assertIs(value,source.installed(value,self.suffix))
        too_long=prefix+'x'*(4097-len(prefix)-len(self.suffix))+self.suffix
        self.assertEqual(4097,len(too_long));self.assertTrue(too_long.endswith(self.suffix))
        for invalid in (too_long,Foreign(self.url()),Opaque(),b'qrc:/scripts/modules/request.js',None,True,42):
            with self.subTest(kind=type(invalid).__name__),self.assertRaises(NativeUIError):source.installed(invalid,self.suffix)

    def test_original_URL_scheme_authority_query_fragment_and_dot_checks_remain(self):
        for value in ('https://host/scripts'+self.suffix,'file://foreign/scripts'+self.suffix,
                self.url()+'?query=1',self.url()+'#fragment','qrc:/scripts/../x'+self.suffix,
                'qrc:/scripts/./x'+self.suffix,self.url()+'x'):
            with self.subTest(value=value),self.assertRaises(NativeUIError):source.installed(value,self.suffix)
        for value in ('file:///app/scripts'+self.suffix,self.url('part%00'),self.url('part%1f'),self.url('part%7f')):
            # Preserve the original distinction: raw control admission precedes
            # unquote; this optimization does not add a new decoded-path policy.
            self.assertIs(value,source.installed(value,self.suffix))

    def test_current_ord_override_keeps_literal_two_calls_and_short_circuit_effect(self):
        calls=[]
        def current(character):
            calls.append(character)
            return 32 if len(calls)==1 else 127
        with patch.object(source,'ord',current,create=True),self.assertRaises(NativeUIError):source.installed(self.url(),self.suffix)
        self.assertEqual(['q','q'],calls)
        self.assertIsNotNone(source.installed(self.url(),self.suffix))

    def test_current_builtin_ord_alias_retains_normal_predicate_result(self):
        calls=[]
        def current(character):calls.append(character);return builtins.ord(character)
        value=self.url('Unicode\u0085')
        with patch.object(source,'ord',current,create=True):self.assertIs(value,source.installed(value,self.suffix))
        self.assertEqual(2*len(value),len(calls))

    def test_foreign_pattern_alias_never_dispatches_opaque_search(self):
        class ForeignPattern:
            def search(self,value):raise AssertionError('Foreign regex hook reached')
        value=self.url()
        with patch.object(source,'_INSTALLED_CONTROLS',ForeignPattern()):self.assertIs(value,source.installed(value,self.suffix))

    def test_different_real_pattern_cannot_bypass_original_raw_control_refusal(self):
        foreign=re.compile('never-match-this')
        with patch.object(source,'_INSTALLED_CONTROLS',foreign),self.assertRaises(NativeUIError):source.installed(self.url('bad\n'),self.suffix)

    def test_global_regex_hooks_and_repeated_current_values_supply_no_verdict(self):
        def forbidden(*_a,**_k):raise AssertionError('Foreign regex module hook reached')
        value=self.url()
        for attribute in ('search','compile'):
            with patch.object(re,attribute,forbidden):self.assertIs(value,source.installed(value,self.suffix))
        current={'url':value};self.assertIs(value,source.installed(current['url'],self.suffix))
        current['url']=self.url('bad\x00')
        with self.assertRaises(NativeUIError):source.installed(current['url'],self.suffix)
        current['url']=value;self.assertIs(value,source.installed(current['url'],self.suffix))


if __name__=='__main__':unittest.main()
