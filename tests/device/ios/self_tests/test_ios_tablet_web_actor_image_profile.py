"""Single scheduled Actor image publication with explicit prepared-app boundary.

This avoids repeating ordinary file-picker setup while measuring the actual
current original decoder/publisher path. Native and render/clock models are
unchanged. It qualifies neither the whole journey nor native timing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
from pathlib import Path
import time
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.self_tests.tablet_web_actor_profile import commanded_actor
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletActorImageProfileTests(unittest.TestCase):
    def test_single_original_image_publication_after_actual_independent_Home_admission(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary;primary=fixture.primary
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        context=multiprocessing.get_context('spawn');receive,send=context.Pipe(duplex=True)
        inputs=(str(b.root),fixture.metadata,fixture.settings,fixture.fixture_url,b.base)
        actor=context.Process(target=commanded_actor,args=(inputs,fixture.clock,send));actor.start();send.close()
        def publish(label):
            started=time.monotonic();receive.send('publish')
            self.assertTrue(receive.poll(300),'Scheduled diagnostic original publication did not return')
            value=receive.recv();self.assertNotIn('error',value,value.get('traceback'))
            if value['audit'] is not None:
                self.assertEqual([],value['audit']['drift']);self.assertEqual([],value['audit']['added'])
                import json
                Path('.ios-host-tmp/tablet-web-actor-'+label+'-profile-audit.json').write_text(json.dumps(value['audit'],sort_keys=True))
            Path('.ios-host-tmp/tablet-web-actor-'+label+'-profile.txt').write_text(value['profile'])
            print('Actual Actor '+label+' wall seconds '+str(round(time.monotonic()-started,3)),flush=True)
            return value
        try:
            publish('baseline');ticket='b'*32;fixture.fixture.journal.activate(RUN,ticket,'open',{})
            with primary.parts() as runtime:
                owner=TabletWebAppOwner(runtime);owner_file='tabletweb-app-files-'+RUN+'-1.json'
                owned=OwnedTabletWebAppFiles(None,PrivateFeatureState(b.root/owner_file),b.binding).reserve_app(RUN,b.source.fixture,ticket)
                runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(RUN,owned['fixtureUrl'],ticket,owned['nonce']))
                directory=b.directories[owned['runId']].as_uri();b.load(directory+'/script.js');b.ui.qt.opened=True
                admission=runtime.remember_app(owned)
                owner.state['generations'].append(dict(index=1,ticket=ticket,ownerFile=owner_file,reserved=True,ownership=owned,directory=directory,admission=admission,dialogBefore=None))
                owner.save()  # Input custody cue only; Actor acquires all originals independently.
            publish('home')
            with primary.parts() as runtime:
                ui=NativeUI(runtime.client,b.binding['sessionId'],lambda:runtime.process() is not None,monotonic=b.mono,sleep=b.sleep)
                row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.open')
                ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.open'),row['token'])
            publish('image')
            rows=fixture.fixture.journal.snapshot(RUN)['entries'];self.assertTrue(rows[-1]['facts']['open'])
        finally:
            try:receive.send('end')
            except (OSError,EOFError):pass
            actor.join(30);receive.close()
            if actor.is_alive():actor.terminate();actor.join(5)


if __name__=='__main__':unittest.main()
