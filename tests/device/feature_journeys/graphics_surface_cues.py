"""Owned world-surface code stimulus; not an observation or effect verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
import zlib
from .contract import identifier

VERSION=1
COLUMNS,ROWS,CELL=26,8,8
MAGIC={'haze':b'OHZ1','reflection':b'OMR1'}
PALETTES={'haze':((16,16,16),(240,240,240)), 'reflection':((16,16,16),(255,90,0))}
RESOURCES={surface:'graphics-'+surface+'-code.v1' for surface in MAGIC}


def challenge(run,ticket,surface):
    identifier(run);identifier(ticket)
    if type(surface) is not str or surface not in MAGIC:raise ValueError('Unknown Graphics world surface')
    return hashlib.sha256(b'overte-graphics-world-surface-v1\0'+surface.encode()+b'\0'+run.encode()+b'\0'+ticket.encode()).digest()[:16]


def payload(run,ticket,surface):
    nonce=challenge(run,ticket,surface);data=MAGIC[surface]+nonce
    return data+zlib.crc32(data).to_bytes(4,'big')


def decode(raw,surface,*,run=None,ticket=None):
    if (type(surface) is not str or surface not in MAGIC or type(raw) is not bytes or len(raw)!=24
            or raw[:4]!=MAGIC[surface] or int.from_bytes(raw[20:],'big')!=zlib.crc32(raw[:20])):
        raise ValueError('Original Graphics surface code is invalid')
    if (run is None)!=(ticket is None):raise ValueError('Incomplete original Graphics code context')
    return dict(surfaceCodeVersion=VERSION,surface=surface,challengeSha256=hashlib.sha256(raw[4:20]).hexdigest(),
        current=None if run is None else raw[4:20]==challenge(run,ticket,surface))


def cells(run,ticket,surface):
    bits=''.join(format(value,'08b') for value in payload(run,ticket,surface))
    return [[0,1]+[int(value) for value in bits[row*24:(row+1)*24]] for row in range(ROWS)]


def png_bytes(run,ticket,surface):
    from PIL import Image
    grid=cells(run,ticket,surface);palette=PALETTES[surface]
    image=Image.new('RGB',(COLUMNS*CELL,ROWS*CELL))
    for row in range(ROWS):
        for column in range(COLUMNS):
            image.paste(palette[grid[row][column]],(column*CELL,row*CELL,(column+1)*CELL,(row+1)*CELL))
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()


def document(run,scene_ticket,fixture_url,surface):
    from .graphics_resources import fixture_url as base_url
    identifier(scene_ticket);identifier(run);challenge(run,scene_ticket,surface)
    if type(fixture_url) is not str or fixture_url!=base_url(fixture_url.rsplit('/runs/',1)[0])+'/runs/'+run+'/':
        raise ValueError('Graphics surface resource belongs to another fixture run')
    configuration=json.dumps(dict(run=run,root=fixture_url,name=RESOURCES[surface]+'.png'),sort_keys=True,separators=(',',':'))
    # Fixed same-origin resources, no product bridge, result facts or settings.
    # Late image callbacks cannot replace a newer observed ticket. The actual
    # Web view/runtime owner remains responsible for timer/renderer retirement.
    return ('''<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#101010}
canvas{display:block;width:100%;height:100%;image-rendering:pixelated}</style>
<canvas width="208" height="64"></canvas><script>
'use strict';const config='''+configuration+''';
const canvas=document.querySelector('canvas'),context=canvas.getContext('2d',{alpha:false});
let wanted=null,shown=null,pending=false;
context.fillStyle='#101010';context.fillRect(0,0,canvas.width,canvas.height);
async function update(){
 if(pending)return;pending=true;
 try{
  const response=await fetch(new URL('current',config.root),{cache:'no-store',credentials:'omit'});
  if(!response.ok)throw new Error('owned current unavailable');const current=await response.json();
  if(!current || Object.keys(current).join(',')!=='ticket' || !/^[0-9a-f]{32}$/.test(current.ticket))throw new Error('foreign current');
  if(current.ticket!==wanted){
   wanted=current.ticket;const ticket=wanted,image=new Image();
   image.onload=function(){if(ticket!==wanted)return;context.imageSmoothingEnabled=false;
    context.drawImage(image,0,0,canvas.width,canvas.height);shown=ticket;};
   image.onerror=function(){if(ticket===wanted && shown!==ticket)wanted=null;};
   image.src=new URL('tickets/'+ticket+'/'+config.name,config.root).href;
  }
 }catch(_error){}finally{pending=false;}
}
update();setInterval(update,200);
</script>''').encode()
