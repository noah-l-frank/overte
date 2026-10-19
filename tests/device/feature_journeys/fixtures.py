"""Owned, deterministic challenge data. Never real accounts, recordings or peers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
import wave

from voice_peer.voice_signal import RATE, samples


def context(run):
    return dict(name='e2e-' + run, renamed='renamed-' + run,
                unicode='Overte ä Ω 東京 ' + run, destination='owned-place-' + run,
                reply='reply-' + run, hidden='hidden-' + run, retry='retry-' + run)


def challenge(run, ticket):
    return hashlib.sha256((run + ':' + ticket).encode('ascii')).digest()[:16]


def wav_bytes(run, ticket, *, profile='voice-v1'):
    output = io.BytesIO()
    data = samples(challenge(run, ticket).hex(), profile=profile)
    import sys
    if sys.byteorder != 'little':
        data.byteswap()
    with wave.open(output, 'wb') as stream:
        stream.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
        stream.writeframes(data.tobytes())
    return output.getvalue()


def marker_bytes(run, ticket):
    """128-bit high-contrast card; the actual UI/world must display this resource."""
    from PIL import Image, ImageDraw
    image = Image.new('RGB', (160, 40), (128, 128, 128))
    draw = ImageDraw.Draw(image)
    bits = ''.join(f'{byte:08b}' for byte in challenge(run, ticket))
    for index, bit in enumerate(bits):
        x, y = 4 + index % 32 * 4, 4 + index // 32 * 8
        draw.rectangle((x, y, x + 3, y + 7), fill='white' if bit == '1' else 'black')
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def document(run, fixture_url=None, model_ticket=None, texture_ticket=None):
    fixture_url = fixture_url or f'http://controlled.test/feature-fixture/v1/runs/{run}/'
    base = fixture_url + 'tickets/' + (model_ticket or '02' * 16) + '/'
    return dict(DataVersion=3, Entities=[dict(name=context(run)['name'] + '-model',
        type='Model', dimensions=dict(x=1.0, y=1.0, z=1.0),
        modelURL=base + 'gltf-bundle/main.gltf', textures={'material': fixture_url + 'tickets/' + (texture_ticket or model_ticket or '02' * 16) + '/checker.png'})])


def payload(resource, run, ticket):
    if resource == 'checker.png':
        from PIL import Image
        image = Image.new('RGB', (16, 16))
        for y in range(16):
            for x in range(16):
                image.putpixel((x, y), (255, 0, 255) if (x // 4 + y // 4) % 2 else (0, 0, 0))
        output = io.BytesIO()
        image.save(output, format='PNG')
        return 'image/png', output.getvalue()
    if resource == 'wearable.json':
        return 'application/json', json.dumps(dict(DataVersion=3, Entities=[dict(
            type='Shape', shape='Cube', name=context(run)['name'] + '-wearable',
            dimensions=dict(x=0.2, y=0.2, z=0.2), color=dict(red=255, green=128, blue=0),
            localPosition=dict(x=0, y=0.3, z=0), parentJointIndex=63)])).encode()
    if resource == 'avatar-a.fst' or resource.startswith('mannequin/'):
        try:
            return 'application/octet-stream', pinned_resource(resource)
        except ValueError:
            return None
    if resource == 'marker.png':
        return 'image/png', marker_bytes(run, ticket)
    if resource == 'challenge.wav':
        return 'audio/wav', wav_bytes(run, ticket)
    if resource == 'preview-challenge.v1.wav':
        return 'audio/wav', wav_bytes(run, ticket, profile='recorded-preview-v1')
    if resource == 'export.json':
        return 'application/json', json.dumps(document(run), sort_keys=True).encode()
    if resource == 'graphics-marker.v1.html':
        current='/feature-fixture/v1/runs/'+run+'/current'
        body=('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>Owned Graphics marker</title><style>html,body{margin:0;width:100%;height:100%;background:#808080}'
              'img{width:100%;height:100%;image-rendering:pixelated}</style><img id="marker" alt="Owned challenge">'
              '<script>let pending=false;async function refresh(){if(pending)return;pending=true;try{'
              'let r=await fetch('+json.dumps(current)+',{cache:"no-store"});if(!r.ok)return;let v=await r.json();'
              'if(!/^[0-9a-f]{32}$/.test(v.ticket))return;let p="/feature-fixture/v1/runs/'+run+'/tickets/"+v.ticket+"/marker.png";'
              'let m=document.querySelector("#marker");if(m.getAttribute("src")!==p)m.src=p;'
              '}finally{pending=false}}refresh();setInterval(refresh,100);</script>')
        return 'text/html; charset=utf-8',body.encode()
    if resource in {'reference.html', 'page-b.html', 'inline.html'}:
        # Browser observations are independently received via the actor journal;
        # origin rejection is also verified by the unchanged product counter.
        page = {'reference.html': 'reference', 'page-b.html': 'B', 'inline.html': 'inline'}[resource]
        color = {'reference': '#186840', 'B': '#602060', 'inline': '#204080'}[page]
        current = '/feature-fixture/v1/runs/' + run + '/current'
        body = ('<!doctype html><meta charset="utf-8"><title>Owned ' + page + '</title>'
                '<body style="background:' + color + ';color:white"><h1>Owned ' + page + '</h1>'
                '<img id="marker" src="marker.png"><input id="owned-text"><button id="submit">Send</button>'
                '<output id="echo"></output><script>'
                'setInterval(async()=>{let r=await fetch(' + json.dumps(current) + ',{cache:"no-store"});'
                'let v=await r.json();let p="/feature-fixture/v1/runs/' + run + '/tickets/"+v.ticket+"/marker.png";'
                'let m=document.querySelector("#marker");if(m.getAttribute("src")!==p)m.src=p;},250);'
                'document.querySelector("#submit").onclick=()=>{let v=document.querySelector("input").value;'
                'document.querySelector("output").textContent=v;'
                'if(window.EventBridge)EventBridge.emitWebEvent(JSON.stringify({text:v}));};'
                '</script>')
        return 'text/html; charset=utf-8', body.encode()
    if resource in {'model.gltf', 'model.obj'}:
        return 'application/octet-stream', companion('gltf-bundle/main.gltf' if resource.endswith('gltf') else 'obj-bundle/main.obj')
    aliases = {'mesh/triangle.bin': 'gltf-bundle/mesh/triangle.bin',
               'textures/checker.png': 'gltf-bundle/textures/checker.png',
               'materials/palette.mtl': 'obj-bundle/materials/palette.mtl'}
    if resource in aliases:
        return 'application/octet-stream', companion(aliases[resource])
    if resource in {'script.js', 'script-bundle/main.js'}:
        # Execution, not source download, must yield ticks and companion identity.
        body = ("var companion = Script.require('./companion.js');\n"
                "var ticks = 0; var owned = Entities.addEntity({type:'Box',name:NAME,"
                "dimensions:{x:0.2,y:0.2,z:0.2},position:Vec3.sum(MyAvatar.position,{x:0,y:0,z:-2})},'local');\n"
                "var handle = Script.setInterval(function(){ticks += companion.delta;"
                "Entities.editEntity(owned,{userData:JSON.stringify({runId:RUN,ticks:ticks}),"
                "color:{red:(ticks%2)*255,green:128,blue:0}});},250);\n"
                "Script.scriptEnding.connect(function(){Script.clearInterval(handle);Entities.deleteEntity(owned);});\n")
        body = body.replace('NAME', json.dumps(context(run)['name'] + '-script')).replace('RUN', json.dumps(run))
        return 'application/javascript', body.encode()
    if resource in {'companion.js', 'script-bundle/companion.js'}:
        return 'application/javascript', b'module.exports = {delta: 1};\n'
    return None


def companion(name):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'fixture/parity/companions'
    manifest = json.loads((root / 'manifest.json').read_text())
    if name not in manifest['files']:
        raise ValueError('Resource is outside the pinned companion inventory')
    content = (root / name).read_bytes()
    if hashlib.sha256(content).hexdigest() != manifest['files'][name]:
        raise ValueError('Pinned companion fixture checksum differs')
    return content


def pinned_resource(name):
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads(Path(__file__).with_name('resource-pins.v1.json').read_text())
    if name not in manifest['resources']:
        raise ValueError('Resource is outside the closed repository fixture inventory')
    entry = manifest['resources'][name]
    content = (root / entry['source']).read_bytes()
    if hashlib.sha256(content).hexdigest() != entry['sha256']:
        raise ValueError('Pinned repository fixture checksum differs')
    return content


def check():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'fixture/parity/companions'
    manifest = json.loads((root / 'manifest.json').read_text())
    for name in manifest['files']:
        companion(name)
    extra = json.loads(Path(__file__).with_name('resource-pins.v1.json').read_text())
    for name in extra['resources']:
        pinned_resource(name)
    return len(manifest['files']) + len(extra['resources'])
