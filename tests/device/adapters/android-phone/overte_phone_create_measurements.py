"""Create facts from actual native/UI/material/cell originals, never stimuli."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.native_feature_observation import need
from adapters.token_create_ui import snapshot,TokenCreateUI
from feature_journeys.contract import state
from feature_journeys.fixtures import payload
from overte_phone_create_fixture import voxel_data
from overte_phone_script_history import same

class CreatePending(Exception):
    """An actual original is still loading; no public facts are admitted."""


DENIED='Invalid entity type, properties or creation permission.'


def model(row):
    """Qualify loaded originals against the actual entity's source property."""
    render=row['render'];need(render is not None and render['loaded'] and render['visible'] and render['addedToScene'])
    geometry=render['geometry'];need(geometry is not None and geometry['sourcePresent']
        and geometry['sourceSha256']==hashlib.sha256(row['modelUrl'].encode()).hexdigest()
        and geometry['textures']['complete'])
    return render,geometry


def textured(row,run,fixture_url):
    render=row['render']
    if render is None or not render['loaded']:return False
    geometry=render['geometry']
    if geometry is None or not geometry['textures']['complete']:return False
    # This parses the actual editable assignment, and then joins it to the
    # independently consumed resource bytes and actual GPU texture extent.
    try:assignment=json.loads(row['textures']) if row['textures'] else {}
    except ValueError:need(False)
    if type(assignment) is not dict or set(assignment)!={'checker.png'}:return False
    url=assignment['checker.png'];prefix=fixture_url+'tickets/'
    if type(url) is not str or not url.startswith(prefix) or not url.endswith('/checker.png'):return False
    ticket=url[len(prefix):-len('/checker.png')]
    from feature_journeys.contract import identifier
    identifier(ticket);original=payload('checker.png',run,ticket)[1]
    rows=[item for item in geometry['textures']['rows'] if item['name']=='checker.png']
    return bool(rows) and all(item['complete'] and item['loaded'] and not item['failed']
        and item['urlSha256']==hashlib.sha256(url.encode()).hexdigest()
        and item['originalBytes']==len(original) and item['originalSha256']==hashlib.sha256(original).hexdigest()
        and item['gpuWidth']==16 and item['gpuHeight']==16 for item in rows)


def facts(run,fixture_url,packet,ui,owned,voxel_baseline=None):
    snapshot(ui);source=packet['source'];records={row['id']:row for row in owned}
    present={row['id']:row for row in source['entities']};objects=[];known={}
    for identifier,row in present.items():
        need(identifier in records and records[identifier]['instance']==row['instance'])
        role=records[identifier]['role'];need(role in ('model','voxel','cube') and role not in objects)
        need(row['host']=='domain' and row['parentId'] is None and not row['locked'] and row['visible'])
        need(row['name']=='e2e-'+run+'-'+role)
        if role=='model':need(row['type']=='Model')
        elif role=='voxel':need(row['type']=='PolyVox')
        else:need(row['type']=='Box')
        objects.append(role);known[identifier]=role
    pages=[row for row in ui['controls'] if row['id']=='create.page'];need(len(pages)<=1)
    page=pages[0] if pages else None
    selected=page['selectedIds'] if page else []
    need(all(item in known for item in selected))
    error='none'
    if page is not None and page['statusError']:
        need(page['statusText']==DENIED);error='permission-denied'
    voxel_value=0
    for identifier,row in present.items():
        if known[identifier]!='voxel':continue
        actual=row['voxel']
        if not actual['ready'] or actual['cells'] is None:raise CreatePending()
        need(actual['volumeSize']==[8,8,8])
        if voxel_baseline is not None:
            need(voxel_baseline['id']==identifier and voxel_baseline['instance']==row['instance'])
            old=voxel_baseline['voxel'];cells=actual['cells']
            if cells['sha256']!=old['cells']['sha256']:
                need(0<=cells['occupied']<old['cells']['occupied'] and actual['savedSha256']!=old['savedSha256']);voxel_value=1
    result=dict(objects=sorted(objects),editor=page is not None,picker=TokenCreateUI.file_picker(ui) is not None,
        error=error,canRez=source['canRez'],selection=sorted(known[item] for item in selected),
        textured=any(textured(row,run,fixture_url) for identifier,row in present.items() if known[identifier]=='model'),voxelValue=voxel_value)
    return deepcopy(state('create',result,run))
