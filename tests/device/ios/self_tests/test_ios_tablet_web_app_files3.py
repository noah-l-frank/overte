"""Literal old file bytes and new compact Tablet inline fixture inputs only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_app_files import originals,COMPACT_INLINE_STYLE
from ios.self_tests.test_ios_tablet_web_app_files import ROOT,RUN,TICKET,NONCE,TabletWebAppFilesTests

# Generated independently from committed e614f70dae; never derive these pins
# from the current writer under test. The shared canonical inline input stays
# unchanged; only the new outer app-input version carries the extra CSS.
OLD={
    'companion.js':'ef5dd004a08004b10f0ef8195ca8d41cb9a7142b41324af1928bd8d78093e561',
    'script-bundle/main.js':'dbdd27439989d4ffca4ea342b50d00341350febb9a6ed0804b87eac265d120f5',
    'script-bundle/companion.js':'712a62a9fc3d5113a967f6a6d4d3676fdea1a37bf9a6afc0bcafdeed95e1bbf3'}
ROOT_PINS={1:'edfe7d17d47ca70387328969027d23c2ba71d1d3d75f69b54fc553b14e3225d1',
    2:'f4e4f43898bcd848701e79052cdc20348489649a25b83e64ab0ea4b46798c8cc'}


def inline(files):
    url=''.join(json.loads(files[name].decode().removeprefix('module.exports=').removesuffix(';\n')) for name in ('companion.js','script-bundle/main.js'))
    return base64.b64decode(url.split(',',1)[1],validate=True).decode()


class TabletWebAppFiles3Tests(unittest.TestCase):
    def test_frozen_one_and_two_input_bytes_are_literal_and_never_receive_new_CSS(self):
        for version in (1,2):
            actual=originals(RUN,ROOT,TICKET,NONCE,version=version)
            self.assertEqual(dict(OLD,**{'script.js':ROOT_PINS[version]}),{name:hashlib.sha256(raw).hexdigest() for name,raw in actual.items()})
            self.assertNotIn(COMPACT_INLINE_STYLE,inline(actual))
    def test_new_three_only_adds_compact_fixture_layout_with_unchanged_handlers_and_bounded_files(self):
        old=originals(RUN,ROOT,TICKET,NONCE,version=2);current=originals(RUN,ROOT,TICKET,NONCE)
        body=inline(current);self.assertEqual(1,body.count(COMPACT_INLINE_STYLE))
        self.assertEqual(inline(old),body.replace(COMPACT_INLINE_STYLE,''))
        self.assertEqual(old['script.js'],current['script.js'])
        self.assertTrue(all(0<len(raw)<=8192 for raw in current.values()))
        for token in ('grid-column:2;grid-row:1/span 2','max-width:100%','justify-self:end','body>section{display:contents}'):
            self.assertIn(token,COMPACT_INLINE_STYLE)
        for version in (False,True,0,4):
            with self.subTest(version=version),self.assertRaises(NativeUIError):originals(RUN,ROOT,TICKET,NONCE,version=version)
    def test_current_reader_preserves_independently_authored_legacy_two_owned_envelope(self):
        fixture=TabletWebAppFilesTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        actual=fixture.files().reserve_app(RUN,ROOT,TICKET);legacy=deepcopy(actual)
        legacy.update(tabletWebAppFilesVersion=2,nonce=NONCE,hashes=dict(OLD,**{'script.js':ROOT_PINS[2]}))
        fixture.store.write(legacy,actual)
        before=fixture.store.path.stat();raw=fixture.store.path.read_bytes()
        self.assertEqual(legacy,fixture.files().owned())
        self.assertEqual(before,fixture.store.path.stat());self.assertEqual(raw,fixture.store.path.read_bytes())
    def test_new_three_source_admission_still_requires_actual_readback_and_VM_root_code(self):
        from ios.self_tests.test_ios_tablet_web_app_origin import originals_boundary,admit
        current=originals_boundary(version=3);self.assertEqual(current[0]['nonce'],admit(current)['controls']['open']['nonce'])
        bad=list(deepcopy(current));bad[0]['tabletWebAppFilesVersion']=4
        with self.assertRaises(NativeUIError):admit(bad)
    def test_actual_generated_inline_button_delivers_new_CSS_and_DOM_marker_geometry(self):
        from ios.self_tests.test_ios_tablet_web_host_app import TabletHostAppTests
        from ios.adapters.tablet_web_image_measurements import projected
        from ios.self_tests.tablet_web_dom_fixture import shown
        fixture=TabletHostAppTests();self.addCleanup(fixture.doCleanups);app,_root=fixture.app()
        button=next(row for row in app.original['buttons'] if row['properties']['semanticId'].endswith('.inline'))
        actual=app.call('click',semanticId=button['properties']['semanticId']);source=actual['navigations'][-1]['source']
        body=base64.b64decode(source.split(',',1)[1],validate=True).decode();self.assertIn(COMPACT_INLINE_STYLE,body)
        url='http://'+'6'*32+'.overte-inline.invalid/index.html'
        app.call('page-create',url=url,html=body,inline=True,bridge=True,inlineToken='6'*32,epoch=1700000000000)
        page=app.call('page-read',requestId='ios-'+'e'*32,epoch=1700000000100)
        actual=shown();actual['screenScale']=1.
        document=dict(source=dict(presentationAfter=actual,dom=page['dom']))
        policy=dict(source='native-screen',marker=[334,56,462,88],subject=[150,50,320,80])
        self.assertEqual(policy['marker'],projected(policy,document,[500,800])['marker'])
        self.assertTrue(page['render']['markerSource'].startswith('data:image/png;base64,'))
        wrong=deepcopy(policy);wrong['marker'][0]+=8
        with self.assertRaises(NativeUIError):projected(wrong,document,[500,800])


if __name__=='__main__':unittest.main()
