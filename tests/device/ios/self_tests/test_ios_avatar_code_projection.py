"""Code-only original projections do not fabricate a timer or caller stack."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import canonical
from ios.adapters import avatar_entities,avatar_scripts
from ios.self_tests import avatar_callers2_fixture as current
from ios.self_tests.test_ios_avatar_entities import packet as legacy_entities1


class AvatarCodeProjectionTests(unittest.TestCase):
    def test_original_ledger2_code_projection_is_read_without_an_invented_empty_event_stream(self):
        worker=current.scripts2()['source']['workers'][0]
        projection={key:deepcopy(worker['avatar'][key]) for key in ('avatarScriptVersion','instance','complete','code')}
        who=dict(callerVersion=1,method='addEntity',sequence=1,invokedEpochMs=current.EPOCH+20,manager=deepcopy(worker['membership']),
            code=deepcopy(worker['code']),callerChain=['qrc:/scripts/system/avatarapp.js'],avatarCode=projection)
        raw=canonical(who);avatar_entities.caller(who,current.EPOCH+30);self.assertEqual(raw,canonical(who))
        self.assertEqual(2,projection['avatarScriptVersion']);self.assertNotIn('events',projection);self.assertNotIn('callerStacks',projection)
        self.assertEqual(1,who['callerVersion']);self.assertNotIn('callerStack',who)

    def test_actual_legacy_projection1_is_unchanged_and_does_not_gain_stronger_callers(self):
        original=legacy_entities1()[0]['source']['events'][0]['caller'];raw=canonical(original)
        avatar_entities.caller(original,1700000000200);self.assertEqual(raw,canonical(original))
        self.assertEqual(1,original['avatarCode']['avatarScriptVersion'])

    def test_projection_is_closed_and_never_accepts_timer_fields_or_boolean_version(self):
        worker=current.scripts2()['source']['workers'][0];value={key:deepcopy(worker['avatar'][key]) for key in ('avatarScriptVersion','instance','complete','code')}
        for key,extra in (('events',[]),('callerStacks',[]),('avatarScriptVersion',True)):
            changed=deepcopy(value);changed[key]=extra
            with self.subTest(key=key),self.assertRaises(NativeUIError):avatar_scripts.code_projection(changed,current.EPOCH+100)


if __name__=='__main__':unittest.main()
