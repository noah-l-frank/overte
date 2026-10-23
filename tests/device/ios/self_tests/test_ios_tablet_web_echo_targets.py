"""Independent native weak-ID namespaces join through the actual State2 target."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_echoes import chain
from ios.adapters.tablet_web_history import derive
from ios.self_tests.tablet_web_history_fixture import frame
from ios.self_tests.test_ios_tablet_web_documents import ORIGINS
from ios.self_tests.test_ios_emote_sources import BINDING


class TabletEchoTargetTests(unittest.TestCase):
    def originals(self):
        value,app=frame();touches=value['touches'];old=touches['targets'][0]['view'];new='e2'*16
        for row in touches['objects']:
            if row['id']==old:row['id']=new
        touches['targets'][0]['view']=new
        for contact in touches['contacts']:
            if contact['target']==old:contact['target']=new
            contact['source']['view']=new;contact['source']['ancestry']=[new if item==old else item for item in contact['source']['ancestry']]
        for dispatch in touches['dispatches']:
            for phase in dispatch['phases']:
                if phase['target']==old:phase['target']=new
                phase['source']['view']=new;phase['source']['ancestry']=[new if item==old else item for item in phase['source']['ancestry']]
        state=value['state'];owner=state['owners'][0];state.update(iosTabletWebStateVersion=2,presentations=[dict(owner=owner['id'],handle=owner['handle'],
            source=deepcopy(owner['source']),generation=owner['current']['generation'],snapshot=deepcopy(value['document']['source']['presentationAfter']),target=new)])
        state['targets'][0]['source']=deepcopy(touches['targets'][0])
        return value,app
    def test_actual_distinct_IDs_complete_full_native_call_and_DOM_receive_and_history_without_relabel(self):
        value,app=self.originals();before=deepcopy(value)
        self.assertNotEqual(value['touches']['targets'][0]['view'],value['document']['source']['presentationAfter']['view'])
        actual=derive([value],[app],BINDING,ORIGINS)
        self.assertEqual((1,1,1),tuple(actual['public'][key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        self.assertEqual(before,value)
    def test_foreign_target_presentation_or_source_and_missing_current_seam_cannot_borrow_contacts(self):
        value,app=self.originals();profile=app['scripts']['source']['engines'][0]
        from ios.adapters.tablet_web_app_origin import admitted
        proof=admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],BINDING,after_epoch=app['afterEpochMs'])
        kwargs={key:value[key] for key in ('ledger','sources','document','touches','emitter')};kwargs.update(profile=proof['profile'],locations=proof['locations'])
        with self.assertRaises(NativeUIError):chain(**kwargs)  # Literal old helper cannot equate the actual distinct IDs.
        for fault in ('target','presentation','source','legacy'):
            changed=deepcopy(value['state'])
            if fault=='target':changed['presentations'][0]['target']='f'*32
            elif fault=='presentation':changed['presentations'][0]['snapshot']['view']='f'*32
            elif fault=='source':changed['presentations'][0]['source']['navigation']='f'*32
            else:changed['iosTabletWebStateVersion']=1;changed.pop('presentations')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):chain(**kwargs,state_packet=changed)


if __name__=='__main__':unittest.main()
