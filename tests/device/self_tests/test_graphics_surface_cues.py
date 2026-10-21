"""World-surface stimulus codec; no browser/renderer/device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
import math
import subprocess
import unittest
from PIL import Image
from feature_journeys.graphics_surface_cues import challenge,payload,decode,cells,png_bytes,document,COLUMNS,ROWS,CELL,PALETTES
from feature_journeys.fixtures import challenge as near_challenge

RUN='b'*32
TICKET='c'*32
ROOT='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'


class GraphicsSurfaceCueTests(unittest.TestCase):
    def test_original_stimulus_is_unique_per_surface_run_ticket_and_separate_from_near_marker(self):
        haze=challenge(RUN,TICKET,'haze');mirror=challenge(RUN,TICKET,'reflection')
        self.assertEqual(16,len(haze));self.assertNotEqual(haze,mirror);self.assertNotEqual(haze,near_challenge(RUN,TICKET))
        self.assertNotEqual(haze,challenge('d'*32,TICKET,'haze'));self.assertNotEqual(haze,challenge(RUN,'e'*32,'haze'))
        self.assertEqual(hashlib.sha256(haze).hexdigest(),decode(payload(RUN,TICKET,'haze'),'haze')['challengeSha256'])

    def test_magic_crc_and_full_challenge_are_decoded_without_inventing_currentness(self):
        for surface in ('haze','reflection'):
            raw=payload(RUN,TICKET,surface);self.assertEqual(24,len(raw));self.assertIsNone(decode(raw,surface)['current'])
            self.assertTrue(decode(raw,surface,run=RUN,ticket=TICKET)['current'])
            self.assertFalse(decode(raw,surface,run=RUN,ticket='d'*32)['current'])
            for bad in (raw[:-1],bytes(24),raw[:9]+bytes([raw[9]^1])+raw[10:],raw[:20]+bytes(4)):
                with self.subTest(surface=surface),self.assertRaises(ValueError):decode(bad,surface)
            with self.assertRaises(ValueError):decode(raw,'reflection' if surface=='haze' else 'haze')
            with self.assertRaises(ValueError):decode(raw,surface,run=RUN)

    def test_literal_grid_has_two_row_calibrators_and_all_192_original_bits(self):
        for surface in ('haze','reflection'):
            grid=cells(RUN,TICKET,surface);self.assertEqual(8,len(grid));self.assertTrue(all(row[:2]==[0,1] and len(row)==26 for row in grid))
            bits=''.join(str(bit) for row in grid for bit in row[2:]);self.assertEqual(192,len(bits))
            self.assertEqual(payload(RUN,TICKET,surface),int(bits,2).to_bytes(24,'big'))
            with Image.open(io.BytesIO(png_bytes(RUN,TICKET,surface))) as image:
                self.assertEqual((208,64),image.size);self.assertEqual('RGB',image.mode)
                for y in range(ROWS):
                    for x in range(COLUMNS):self.assertEqual(PALETTES[surface][grid[y][x]],image.getpixel((x*CELL+CELL//2,y*CELL+CELL//2)))

    def test_owned_far_board_retains_nominal_cell_contrast_under_authored_haze(self):
        from feature_journeys.graphics_fixture import pico_scene,VIEW
        rows={row['name'].split('-graphics-',1)[1]:row for row in pico_scene(RUN,TICKET,ROOT)['Entities']}
        board=rows['fog-board'];haze=rows['zone']['haze']
        distance=math.sqrt(sum((abs(board['position'][a]-VIEW['position'][a])+board['dimensions'][a]/2)**2 for a in 'xyz'))
        alpha=1-math.exp(math.log(.05)*distance/haze['hazeRange'])
        def srgb(value):return 255*(12.92*value if value<=.0031308 else 1.055*value**(1/2.4)-.055)
        def linear(value):
            value/=255
            return value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4
        for channel in ('red','green','blue'):
            color=haze['hazeColor'][channel]/255
            black=srgb((1-alpha)*linear(16)+alpha*color)
            white=srgb((1-alpha)*linear(240)+alpha*color)
            self.assertGreater(white-black,24)
        # This is stimulus arithmetic, not an actual shader/image observation.

    def test_document_is_only_fixed_owned_resource_polling_with_late_callback_guard(self):
        text=document(RUN,TICKET,ROOT,'haze').decode()
        self.assertIn('graphics-haze-code.v1.png',text);self.assertIn('if(ticket!==wanted)return',text)
        self.assertIn('credentials:\'omit\'',text);self.assertNotIn('EventBridge',text);self.assertNotIn('expectedState',text)
        with self.assertRaises(ValueError):document(RUN,TICKET,ROOT,'unknown')
        with self.assertRaises(ValueError):document(RUN,TICKET,ROOT.replace(RUN,'d'*32),'haze')


    def test_actual_document_script_rejects_late_images_and_foreign_current_without_a_bridge(self):
        script=document(RUN,TICKET,ROOT,'reflection').decode().split('<script>',1)[1].split('</script>',1)[0]
        before="""const assert=require('assert');const images=[],draws=[];let current,foreign=false,interval;
const mockCanvas={width:208,height:64,getContext:()=>({fillRect:()=>{},drawImage:image=>draws.push(image.src)})};
const document={querySelector:()=>mockCanvas};global.Image=class{constructor(){images.push(this);}};
const setInterval=callback=>{interval=callback;};const fetch=async()=>({ok:true,json:async()=>foreign?({runId:'f'.repeat(32),ticket:current}):({ticket:current})});
"""
        after="""
(async()=>{await new Promise(resolve=>setImmediate(resolve));
 assert.equal(images.length,1);const old=images[0];current='e'.repeat(32);await interval();assert.equal(images.length,2);
 old.onload();assert.equal(draws.length,0);images[1].onload();assert.equal(draws.length,1);assert(draws[0].includes('/tickets/'+current+'/'));
 foreign=true;await interval();assert.equal(images.length,2);assert.equal(draws.length,1);
 foreign=false;current='d'.repeat(32);await interval();images[2].onerror();await interval();assert.equal(images.length,4);
 images[3].onload();assert.equal(draws.length,2);assert(draws[1].endsWith('graphics-reflection-code.v1.png'));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
"""
        program='const RUN='+json.dumps(RUN)+';'+before+'current='+json.dumps(TICKET)+';'+script+after
        done=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,done.returncode,done.stderr)


if __name__=='__main__':unittest.main()
