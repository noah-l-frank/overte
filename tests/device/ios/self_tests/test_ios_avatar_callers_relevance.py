"""Actual source preflight order plus explicit foreign/incomplete DTO boundaries.

Native ordering checks inspect original C++; they are not Qt/V8 execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_scripts
from ios.self_tests import avatar_callers2_fixture as current

ROOT=Path(__file__).resolve().parents[4]


def timer_preflight(source,suffix):
    start=source.index('QString created(int handle,const AvatarV8Callers&')
    body=source[start:source.index('    QString fired(',start)]
    before=body[:body.index('!callers.complete')]
    return 'hasSubmitted("'+suffix+'")' in before and '{ return {}; }' in before


def xhr_preflight(source):
    start=source.index('void XMLHttpRequestClass::featureAvatarSocialOpen()')
    body=source[start:source.index('    _featureAvatarSocialId=',start)];before=body[:body.index('!callers.complete')]
    return all(item in before for item in ('!_engine || !_engine->manager()',
        'QThread::currentThread()!=_engine->thread()', 'membership.value("assigned").userType()!=QMetaType::Bool',
        '"/defaultScripts.js"', 'submitted.value("submitted").userType()!=QMetaType::Bool',
        'manager->featureAvatarScriptObservation().value("code").toList()', 'if (!managerRelevant) { return; }'))


class AvatarCallersRelevanceTests(unittest.TestCase):
    def test_actual_timer_sources_require_observed_specific_modules_before_unavailable(self):
        for name,suffix in (('AvatarScriptObservation.h','/system/libraries/peopleConnection.js'),
                ('AvatarUiWorkObservation.h','/system/avatarapp.js')):
            source=(ROOT/'libraries/script-engine/src'/name).read_text();self.assertTrue(timer_preflight(source,suffix))
            changed=source.replace('callers.hasSubmitted("'+suffix+'")','false')
            self.assertFalse(timer_preflight(changed,suffix))

    def test_global_xhr_source_filters_foreign_manager_before_incomplete_stack_can_poison_it(self):
        source=(ROOT/'libraries/script-engine/src/XMLHttpRequestClass.cpp').read_text();self.assertTrue(xhr_preflight(source))
        for actual in ('if (!managerRelevant) { return; }','"/defaultScripts.js"','!_engine || !_engine->manager()'):
            with self.subTest(guard=actual):self.assertFalse(xhr_preflight(source.replace(actual,'/* removed original guard */')))

    def test_submitted_relevance_is_retained_even_when_the_actual_stack_is_unavailable(self):
        source=(ROOT/'libraries/script-engine/src/AvatarV8Callers.h').read_text()
        self.assertLess(source.index('result.submittedUrls.append'),source.index('actual.value("emitStackVersion")'))
        self.assertIn('PlacesHttpObservation::installed(url,suffix)',source)
        self.assertNotIn('callerChain',source)

    def test_unrelated_native_worker_without_avatar_modules_does_not_become_our_timer_scope(self):
        value=current.scripts2();worker=deepcopy(value['source']['workers'][0]);worker['membership'].update(instance='c'*32,url='qrc:/scripts/foreign.js')
        raw='explicit foreign script'.encode('utf-16-le');worker['code'].update(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest())
        worker['avatar'].update(instance='d'*32,code=[],events=[],callerStacks=[])
        worker['uiWork'].update(instance='e'*32,timers=[],callerStacks=[])
        value['source']['workers'].append(worker);value['source']['revision']=2;avatar_scripts.original(value)
        self.assertEqual([],avatar_scripts.worker(value,'c'*32)['avatar']['code'])

    def test_same_relevant_manager_with_incomplete_original_stack_remains_unqualified(self):
        value=current.scripts2();worker=value['source']['workers'][0];worker['avatar']['complete']=False
        avatar_scripts.original(value)
        with self.assertRaises(NativeUIError):avatar_scripts.worker(value,'b'*32)


if __name__=='__main__':unittest.main()
