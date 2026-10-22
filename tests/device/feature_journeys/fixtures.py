"""Owned, deterministic challenge data. Never real accounts, recordings or peers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
import wave

from voice_peer.voice_signal import RATE, samples


def context(run):
    name,renamed='e2e-'+run,'renamed-'+run
    return dict(name=name, renamed=renamed,
                assetGltf=name+'/main.gltf',assetBin=name+'/mesh/triangle.bin',assetTexture=name+'/textures/checker.png',
                renamedAssetGltf=renamed+'/main.gltf',renamedAssetBin=renamed+'/mesh/triangle.bin',
                renamedAssetTexture=renamed+'/textures/checker.png',assetObj=name+'/main.obj',
                assetMtl=name+'/materials/palette.mtl',assetFbx=name+'/stand.fbx',
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
    return dict(DataVersion=0, Entities=[dict(name=context(run)['name'] + '-model',
        type='Model', dimensions=dict(x=1.0, y=1.0, z=1.0),
        modelURL=base + 'gltf-bundle/main.gltf', textures={'checker.png': fixture_url + 'tickets/' + (texture_ticket or model_ticket or '02' * 16) + '/checker.png'})])


def import_document(run,ticket,fixture_url):
    # Controlled INPUT for the ordinary JSON picker. This is never an export
    # observation. An explicit actual owned origin prevents placeholder URLs
    # from entering a product import or copied future texture expectations.
    from .contract import arguments
    from .scenarios import VERSION
    arguments('feature.create.act',dict(contractVersion=VERSION,runId=run,ticket=ticket,
        fixtureUrl=fixture_url,verb='import-picker-open',inputs={'resource':'entity-import.json'}))
    value=document(run,fixture_url,model_ticket=ticket)
    del value['Entities'][0]['textures']
    value['DataVersion']=3 # Controlled entity-JSON INPUT, distinct from the native export-tree version.
    return value


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
    if resource == 'asset-stand.fbx':
        return 'application/octet-stream',pinned_resource(resource)
    if resource == 'avatar-a.fst' or resource.startswith('mannequin/'):
        try:
            return 'application/octet-stream', pinned_resource(resource)
        except ValueError:
            return None
    if resource=='navigation-interactable.v1.js':
        from pathlib import Path
        return 'application/javascript',(Path(__file__).resolve().parents[1]/'fixture/scripted_interactable.js').read_bytes()
    if resource == 'marker.png':
        return 'image/png', marker_bytes(run, ticket)
    if resource == 'challenge.wav':
        return 'audio/wav', wav_bytes(run, ticket)
    if resource == 'preview-challenge.v1.wav':
        return 'audio/wav', wav_bytes(run, ticket, profile='recorded-preview-v1')
    if resource in ('graphics-marker.v1.html','navigation-marker.v1.html'):
        current='/feature-fixture/v1/runs/'+run+'/current'
        body=('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>Owned Graphics marker</title><style>html,body{margin:0;width:100%;height:100%;background:#808080}'
              'img{width:100%;height:100%;image-rendering:pixelated}</style><img id="marker" alt="Owned challenge">'
              '<script>let pending=false;async function refresh(){if(pending)return;pending=true;try{'
              'let r=await fetch('+json.dumps(current)+',{cache:"no-store"});if(!r.ok)return;let v=await r.json();'
              'if(!/^[0-9a-f]{32}$/.test(v.ticket))return;let p="/feature-fixture/v1/runs/'+run+'/tickets/"+v.ticket+"/marker.png";'
              'let m=document.querySelector("#marker");if(m.getAttribute("src")!==p)m.src=p;'
              '}finally{pending=false}}refresh();setInterval(refresh,100);</script>')
        if resource=='navigation-marker.v1.html':body=body.replace('Owned Graphics marker','Owned Navigation marker')
        return 'text/html; charset=utf-8',body.encode()
    # Browser documents/scripts are served by BrowserResources from the original
    # parity fixture, with actual HTTP status/response IDs. An HTTP inline.html
    # page cannot exercise the native inline-source carrier.
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
