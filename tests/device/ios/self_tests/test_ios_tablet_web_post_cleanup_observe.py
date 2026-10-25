"""Loaded Tablet cleanup -> inspect -> the unchanged common quiet checkpoint.

The initial file load uses the real ordinary manager/picker/Home input chain.
Original QML/JS, W3C/HTTP/private files and an independent Actor execute. Native/UI clocks
remain models. This case qualifies neither the whole journey nor process end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import tempfile
import traceback
import unittest
from functools import wraps
from feature_journeys.engine import Journey
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from feature_journeys.terminal import PROFILE,description
from ios.self_tests.tablet_web_prepared_paired import PreparedTabletPair
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


def private_original_context(function):
    """Expose a masked body traceback only in this private host test log.

    No production outcome, exception classification or authority comes from
    this diagnostic context walk. The exact raised object is preserved.
    """
    @wraps(function)
    def wrapped(*args,**kwargs):
        try:return function(*args,**kwargs)
        except BaseException as error:
            original=error;seen=set()
            while original.__context__ is not None and id(original) not in seen:
                seen.add(id(original));original=original.__context__
            if original is not error:print('Actual original Tablet body exception:\n'+''.join(traceback.format_exception(original)),flush=True)
            raise
    return wrapped


class TabletPostCleanupObserveTests(unittest.TestCase):
    @private_original_context
    def test_loaded_cleanup_inspection_keeps_fresh_advancing_common_paired_samples(self):
        def retained_fixture(test):
            fixture=PairedTabletFixture(test);b=fixture.boundary
            # Preserve this test's actual original root before prepared entry,
            # including when the independent Open publication never arrives.
            matches=[(index,row) for index,row in enumerate(b.context_test._cleanups)
                if isinstance(getattr(row[0],'__self__',None),tempfile.TemporaryDirectory)
                and row[0].__self__.name==str(b.root) and row[0].__name__=='cleanup']
            self.assertEqual(1,len(matches));index,row=matches[0]
            row[0].__self__._finalizer.detach();b.context_test._cleanups.pop(index)
            print('Post-cleanup original root retained: '+str(b.root),flush=True);return fixture
        pair=PreparedTabletPair(self,fixture_factory=retained_fixture,load_normally=True);fixture=pair.fixture;b=pair.b;primary=fixture.primary
        text=context(RUN)['unicode'];last=None
        for ticket,verb,inputs,predicate in (
            ('c'*32,'focus-type',dict(text=text),lambda facts:facts['text']==text),
            ('d'*32,'submit',{},lambda facts:facts['bridgeEchoes']==1),
            ('e'*32,'clear-text',{},lambda facts:facts['text']=='')):
            fixture.fixture.journal.activate(RUN,ticket,verb,inputs)
            self.assertEqual(dict(performed=True),primary.act(dict(contractVersion=16,runId=RUN,ticket=ticket,
                fixtureUrl=b.source.fixture,verb=verb,inputs=inputs)))
            last=primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
            self.assertTrue(predicate(last['state']));pair.wait(ticket,predicate)
            print('Actual partial input '+verb+' observed by both roles',flush=True)
        ticket='9'*32;fixture.fixture.journal.activate(RUN,ticket,'cleanup',{});barrier=b.host()
        for _index in range(2):
            self.assertEqual(dict(performed=True),primary.cleanup(dict(contractVersion=16,runId=RUN)))
        pair.wait(ticket,lambda facts:not facts['open'])
        descriptor=primary.terminal(dict(contractVersion=1,runId=RUN,stage='inspect'))['description']
        description(descriptor,area='tablet-web',run=RUN,ticket=ticket)
        print('Actual loaded paired cleanup inspected',flush=True)
        def invoke(operation,values):
            self.assertEqual('feature.tablet-web.observe',operation)
            return primary.observe(values)
        def continuity(_stage,_verb):
            adapter=primary.runtime.adapter
            client,session,state,target,_scope=primary.runtime._existing(primary.selector)
            actual=adapter._binding(primary.selector,client,session,state,target).continuity()
            self.assertEqual(int(b.binding['processIdentity']),actual['pid'])
        journey=Journey('tablet-web',RUN,b.source.fixture,invoke=invoke,
            witness=lambda:fixture.controller.request('/runs/'+RUN),
            activate=lambda *_args: self.fail('Checkpoint must not issue another activation'),
            read_artifact=lambda _name:self.fail('Cleanup checkpoint requests no artifact'),
            image_policy=dict(screen=fixture.settings['imagePolicy']),monotonic=b.mono,
            epoch_ms=b.host,sleep=primary.sleep,terminal_profile=PROFILE,continuity=continuity,
            report=lambda _value:self.fail('An isolated checkpoint does not produce a journey report'))
        journey.sequence=last['sequence'];journey.last_epoch=last['capturedEpochMs'];journey.terminal_descriptor=descriptor
        expected=expand(SCENARIOS['tablet-web']['baseline'],context(RUN))
        measured=journey.wait('cleanup-restored-baseline',ticket,barrier,expected,['peer'],duration=3.)
        self.assertGreater(measured['sequence'],last['sequence']);self.assertGreaterEqual(len(journey.terminal_samples),3)
        self.assertTrue(all(journey.terminal_samples[-1][role]['capturedEpochMs']-journey.terminal_samples[0][role]['capturedEpochMs']>=3000
            for role in ('primary','actor')))
        self.assertEqual([],fixture.sdk.errors)


if __name__=='__main__':unittest.main()
