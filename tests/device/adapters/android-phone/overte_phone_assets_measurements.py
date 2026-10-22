"""Assets facts from fresh original widget/server/file/model consumers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
from PIL import Image
from adapters.native_feature_observation import need
from adapters.token_assets_ui import snapshot,TokenAssetsUI
from feature_journeys.contract import state
from overte_phone_assets_backend import inventory,owned_inventory,bytes_for,bake,reader_chain,sha
from overte_phone_create_measurements import CreatePending
from overte_phone_script_history import same


def model(row,selected,packet,resolution,downloads,claim):
    need(row['type']=='Model' and row['host']=='domain' and row['visible'] and not row['locked'] and row['parentId'] is None
        and row['modelUrl']=='atp:'+selected and row['textures']=='')
    render=row['render']
    if render is None or not render['loaded'] or not render['visible'] or not render['addedToScene']:raise CreatePending()
    geometry=render['geometry']
    if geometry is None or not geometry['textures']['complete'] or geometry.get('reader') is None:raise CreatePending()
    chain=reader_chain(selected,packet,resolution,downloads);reader=geometry['reader']
    need(reader['sourceSha256']==sha(chain['url']) and reader['originalSha256']==chain['sha256'] and reader['originalBytes']==chain['bytes']
        and (not geometry['sourcePresent'] or geometry['sourceSha256']==reader['sourceSha256']))
    # Normal companion uploads must be consumed by the current material/GPU,
    # independently of the uploader and downloadable mapping bytes.
    if 'textures/checker.png' in claim['files']:
        original=claim['files']['textures/checker.png'];textures=geometry['textures']['rows']
        root=selected.rsplit('/',1)[0];url='atp:'+root+'/textures/checker.png';digest=original['sha256']
        need(digest in downloads);raw=bytes_for(downloads[digest],digest)
        with Image.open(io.BytesIO(raw)) as image:extent=image.size;image.load()
        need(textures and all(item['complete'] and item['loaded'] and not item['failed'] and item['urlSha256']==sha(url)
            and item['originalSha256']==digest and item['originalBytes']==len(raw) and (item['gpuWidth'],item['gpuHeight'])==extent for item in textures))
    return render,geometry,chain


def facts(run,ui,packet,backend,original,claims,entities,owned,files,resolution,downloads,barrier=None):
    snapshot(ui);need(ui['ready']);rows=owned_inventory(packet,backend,original,claims,run);pages=[row for row in ui['controls'] if row['id']=='assets.page'];need(len(pages)<=1);page=pages[0] if pages else None
    need(page is None or page['canWrite']==packet['source']['canWrite'])
    picker=TokenAssetsUI.file_picker(ui);selected='' if page is None else page['selectedPath']
    # Folder selection belongs only to an in-flight input and is never reported
    # as a selected primary checkpoint.
    need(not selected or selected in rows)
    bake_state='none';available=False;baking=False;companions=[]
    if selected:
        need(resolution is not None);bake_state=bake(selected,packet,backend,resolution,downloads,barrier if selected.endswith('/stand.fbx') and rows[selected]['bakeStatus']==4 else None)
        baking=bake_state=='baking';checkbox=next((row for row in ui['controls'] if row['id']=='assets.baking'),None);need(checkbox is not None)
        available=checkbox['enabled'];need(available==(packet['source']['canWrite'] and not page['busy'] and rows[selected]['bakeStatus']!=0))
        root=selected.rsplit('/',1)[0]+'/'
        companions=sorted(path[len(root):] for path in rows if path.startswith(root) and path!=selected)
        for path in rows:
            need(rows[path]['hash'] in downloads);bytes_for(downloads[rows[path]['hash']],rows[path]['hash'])
    error='none';picker_file='';staged=False
    if picker is not None:
        need(files is not None and files['source']['exists'])
        actual=files['source'];main=next(row for row in actual['files'] if row['name']=='gltf-bundle/main.gltf')
        staged=main['exists'] and not actual['retiring'];main_url=actual['directory']+'/gltf-bundle/main.gltf'
        need(all(url==main_url for url in picker['selectedUrls']))
        if picker['selectedUrls']:picker_file='main.gltf'
        if picker['error']:
            need(picker['error']=='A selected file is no longer available.' and not main['exists'] and picker['selectedUrls']==[main_url]);error='file-unavailable'
    models=entities['source']['entities'];records={row['id']:row for row in owned}
    need(all(row['id'] in records and records[row['id']]['instance']==row['instance'] and row['name']=='e2e-'+run+'-model' for row in models))
    need(len(models)<=1);scene=False
    if models:
        need(selected and resolution is not None)
        claim=next((claim for claim in reversed(claims) if any(row['hash']==rows[selected]['hash'] for row in claim['published'].values())),None);need(claim is not None and claim['complete'])
        model(models[0],selected,packet,resolution,downloads,claim);scene=True
    delete=next((row for row in ui['controls'] if row['id']=='assets.delete'),None)
    if page is not None:need(delete is not None and delete['enabled']==(packet['source']['canWrite'] and not page['busy'] and bool(page['selection'])))
    value=dict(mappings=sorted(path[1:] for path in rows),selected=selected[1:] if selected else '',baking=baking,bakeState=bake_state,bakeAvailable=available,
        canWrite=packet['source']['canWrite'],deleteEnabled=False if delete is None else delete['enabled'],error=error,open=page is not None,sceneModel=scene,
        companions=companions,picker=picker is not None,pickerFile=picker_file,stagedAvailable=staged)
    return deepcopy(state('assets',value,run))
