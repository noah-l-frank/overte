"""Real generated host callbacks for the composed ordinary-input fixture."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from ios.adapters.tablet_web_app_files import originals
from ios.self_tests.tablet_web_host_app import TabletHostApp
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT,TICKET


class TabletHostAppTests(unittest.TestCase):
    def app(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);root.chmod(0o700);(root/'script-bundle').mkdir(mode=0o700)
        for name,raw in originals(RUN,ROOT,TICKET,'c'*32).items():path=root/name;path.write_bytes(raw);path.chmod(0o600)
        return TabletHostApp(self,root/'script.js'),root
    def test_actual_returned_handlers_choose_HTTP_inline_and_reply_then_Ending_disconnects(self):
        app,root=self.app();start=app.original
        self.assertEqual(3,len(start['buttons']));self.assertEqual(3,len(start['requires']));self.assertEqual([],start['navigations'])
        actual=app.call('click',semanticId=start['buttons'][0]['properties']['semanticId'])
        self.assertEqual(ROOT+'tickets/'+TICKET+'/index.html',actual['navigations'][-1]['source'])
        inline=next(row for row in start['buttons'] if row['properties']['semanticId'].endswith('.inline'))
        actual=app.call('click',semanticId=inline['properties']['semanticId']);self.assertTrue(actual['navigations'][-1]['source'].startswith('data:text/html;'))
        message=json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=17))
        actual=app.call('web',message=message);self.assertEqual(17,json.loads(actual['emissions'][-1]['message'])['sequence'])
        self.assertIn((root/'script.js').as_uri(),actual['emissions'][-1]['stack'])
        ended=app.call('stop');self.assertEqual(0,ended['connections']);self.assertTrue(all(row['removed'] and row['connections']==0 for row in ended['buttons']))
        self.assertEqual(ended['emissions'],app.call('web',message=message)['emissions'])
        with self.assertRaises(AssertionError):app.call('click',semanticId=inline['properties']['semanticId'])
    def test_actual_reference_DOM_handler_and_generated_app_echo_share_original_server_response(self):
        from feature_journeys.browser_fixture import BrowserResources
        browser=BrowserResources(clock_ms=lambda:1700000000000);browser.open(RUN)
        status,_headers,body,_mime=browser.resource(RUN,TICKET,'reference.html',origin='primary');self.assertEqual(200,status)
        app,_root=self.app();url=ROOT+'tickets/'+TICKET+'/reference.html'
        app.call('page-create',url=url,html=body.decode(),inline=False,bridge=True,inlineToken='',epoch=1700000000010)
        initial=app.call('page-read',requestId='ios-'+'1'*32,epoch=1700000000020)
        response=browser.snapshot(RUN)['responses'][-1]
        self.assertEqual(response['responseId'],initial['dom']['document']['responseId'])
        app.call('page-text',id='text',text='Überte 🙂',epoch=1700000000030)
        app.call('page-click',id='bridge',epoch=1700000000040)
        actual=app.call('page-read',requestId='ios-'+'2'*32,epoch=1700000000050)
        self.assertEqual('Überte 🙂',actual['dom']['editor']['text']);self.assertEqual(1,len(actual['dom']['echoes']))
        self.assertEqual(actual['emissions'][-1]['message'],actual['dom']['echoes'][0]['message'])
        self.assertEqual('tablet',json.loads(actual['dom']['echoes'][0]['message'])['surface'])
        self.assertEqual(1,len([row for row in actual['dom']['events'] if row['kind']=='click' and row['target']['id']=='bridge']))


if __name__=='__main__':unittest.main()
