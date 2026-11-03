"""Current parser checks must resample real method and namespace mutations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from ios.adapters import chat_draft_runtime,chat_receive_sources,chat_peer_receipts,chat_send_receive
from ios.adapters import chat_archive_round as guards
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.adapters.script_runtime import IOSScriptRuntime

class ChatCurrentParserGuardTests(unittest.TestCase):
    def test_actual_parser_code_change_is_refused_and_every_new_pass_resamples(self):
        self.assertTrue(guards.original_methods());actual=IOSChatDraftOwner.local;original=actual.__code__
        def different(frame):return None
        for _ in range(2):
            try:
                actual.__code__=different.__code__
                self.assertFalse(guards.original_methods());self.assertFalse(guards.original_methods())
            finally:actual.__code__=original
            self.assertTrue(guards.original_methods())
    def test_new_inherited_method_is_not_hidden_by_imported_class_alias_reuse(self):
        self.assertTrue(guards.original_methods());name='_e2e_counter_unexpected_parser_member'
        self.assertNotIn(name,vars(IOSScriptRuntime))
        def unexpected(self):return None
        try:
            setattr(IOSScriptRuntime,name,unexpected)
            self.assertFalse(guards.original_methods());self.assertFalse(guards.original_methods())
        finally:delattr(IOSScriptRuntime,name)
        self.assertTrue(guards.original_methods())
    def test_changed_global_class_alias_is_checked_even_when_other_aliases_are_unchanged(self):
        self.assertTrue(guards.original_methods());original=chat_draft_runtime.IOSChatDraftOwner
        try:
            chat_draft_runtime.IOSChatDraftOwner=object
            self.assertFalse(guards.original_methods())
        finally:chat_draft_runtime.IOSChatDraftOwner=original
        self.assertTrue(guards.original_methods())
