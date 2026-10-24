"""All nineteen ordinary recipes execute the live original page/VM in host models.

This checks input and original browser facts. It does not replace renderer,
independent actor, paired retirement or whole installed-dispatch qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import time
from feature_journeys.fixtures import context
from feature_journeys.scenarios import SCENARIOS,expand
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_history import derive
from ios.adapters.world_web_api_clock import scope
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebNineteenInputsTests(unittest.TestCase):
    def test_actual_nineteen_normal_recipes_current_dom_http404_restore_back_foreign_and_resume(self):
        whole=ComposedWorldWeb(wall_clock=True);self.addCleanup(whole.close);sdk,source=whole.sdk,whole.source
        actions=whole.actions();lease=None;writes=[]
        write=source.store.write
        def writing(*args,**kwargs):
            started=time.perf_counter()
            try:return write(*args,**kwargs)
            finally:writes.append(time.perf_counter()-started)
        source.store.write=writing
        for index,step in enumerate(SCENARIOS['world-web']['steps'],1):
            call=sdk.activate(step['verb'],expand(step['inputs'],context(sdk.run)))
            started=time.perf_counter();prior_frames=len(source.frames);prior_writes=len(writes)
            try:
                with scope(lambda:sdk.time):self.assertEqual(dict(performed=True),actions.act(call))
                if lease is None:
                    entry=actions.state['calls'][-1];lease=WorldWebLease(whole.scope,source,entry['before'],entry['after'])
                    actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
                ownership=lease.packet();observed=derive(source.browser_frames(),ownership=ownership['files'],directory=ownership['directory'],entity=ownership['returned']['returned']['entityId'],origins=sdk.origins)['public']
                expected=expand(step['state'],context(sdk.run))
                for key,value in expected.items():
                    if isinstance(value,dict):
                        if 'min' in value:self.assertGreaterEqual(observed[key],value['min'],(index,key))
                        if 'max' in value:self.assertLessEqual(observed[key],value['max'],(index,key))
                        if 'oneOf' in value:self.assertIn(observed[key],value['oneOf'],(index,key))
                    else:self.assertEqual(value,observed[key],(index,key))
            except Exception as error:raise AssertionError('Normal World Web step '+str(index)+' '+step['verb']+' failed') from error
            finally:
                actual=source.frames[prior_frames:]
                print('World Web normal step',str(index)+'/19',step['verb'],'CPU seconds',round(time.perf_counter()-started,3),
                    'original ms',[round((frame['clockJoin']['hostAfterMonotonic']-frame['clockJoin']['hostBeforeMonotonic'])*1000) for frame in actual],
                    'durable source writes',len(writes)-prior_writes,'write ms',round(sum(writes[prior_writes:])*1000),flush=True)
        self.assertEqual(19,len(actions.state['calls']));self.assertIsNone(sdk.item_weak())
        self.assertEqual(2,observed['bridgeMessages']);self.assertEqual(2,observed['bridgeEchoes']);self.assertEqual(3,observed['attemptedMessages'])


if __name__=='__main__':unittest.main()
