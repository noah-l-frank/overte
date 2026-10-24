"""Actual retained staged Script and reference page exchange multiple real echoes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import unittest
from ios.adapters.world_web_files import originals
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL,TICKET


class WorldWebLiveScriptTests(unittest.TestCase):
    def test_actual_worker_does_not_end_until_normal_stop_and_page_receives_original_script_replies(self):
        source=OriginalSources();raw=originals(RUN,URL,TICKET,'b'*32)
        process=subprocess.Popen(['node',str(Path(__file__).with_name('world_web_page_fixture.js'))],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        def call(value):
            process.stdin.write(json.dumps(dict(value,epoch=source.clock()))+'\n');process.stdin.flush();result=json.loads(process.stdout.readline())
            self.assertNotIn('error',result);source.epoch=max(source.epoch,result['epoch']);return result
        try:
            result=call(dict(op='start',entity='11111111-1111-4111-8111-111111111111',camera=dict(position=dict(x=0,y=1.6,z=7),orientation=dict(x=0,y=0,z=0,w=1)),
                script=raw['script-bundle/main.js'].decode(),companion=raw['script-bundle/companion.js'].decode()))
            self.assertEqual([],result['deleted']);self.assertEqual(['loaded'],[row['value']['event'] for row in result['workEvents']])
            self.assertEqual(1,len(result['created']));self.assertEqual(5.5,result['created'][0]['properties']['position']['z'])
            page=call(dict(op='open',bridge=True,url=source.url,html=source.body.decode()))
            rect=next(row['rect'] for row in page['nodes'] if row['id']=='bridge');x=(rect['left']+rect['right'])/2;y=(rect['top']+rect['bottom'])/2
            # Submit the original product pointer JS at the observed model DOM
            # point. No reply or counter is injected into the page.
            for _ in range(2):
                call(dict(op='pointer',args=['press',x,y,0]));result=call(dict(op='pointer',args=['release',x,y,0]))
            self.assertEqual([1,2],[row['sequence'] for row in result['document']['echoes']]);self.assertEqual([],result['deleted'])
            self.assertEqual(2,len([row for row in result['workEvents'] if row['value']['event']=='script-reply-return']))
            self.assertEqual(2,len([row for row in result['nativeEvents'] if row['kind']=='native-envelope']))
            ended=call(dict(op='stop'));self.assertEqual([result['created'][0]['id']],[row['id'] for row in ended['deleted']])
            self.assertEqual('ending-finally',ended['workEvents'][-1]['value']['event'])
        finally:
            process.stdin.close();process.wait(timeout=5);process.stdout.close();process.stderr.close()


if __name__=='__main__':unittest.main()
