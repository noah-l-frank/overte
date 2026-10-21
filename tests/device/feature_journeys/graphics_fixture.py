"""Owned serverless Graphics subjects; geometry is stimulus, never evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import uuid
from urllib.parse import urlsplit

VIEW = dict(position=dict(x=0.0,y=1.6,z=0.0),rotation=dict(x=0.0,y=0.0,z=0.0,w=1.0))
VERSION = 2
NAMES = ('zone','floor','fog-board','resolution-bars','reflector','reflected-color','marker')


def subject_ids(run):
    from .contract import identifier
    namespace=uuid.UUID(hex=identifier(run))
    return {name:str(uuid.uuid5(namespace,'graphics-subject-v1/'+name)) for name in NAMES}


def scene(run, ticket, fixture_url):
    from .contract import identifier
    identifier(run); identifier(ticket)
    if type(fixture_url) is not str or len(fixture_url)>512:
        raise ValueError('Graphics fixture requires its actual owned resource root')
    parsed=urlsplit(fixture_url)
    if (parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path!='/feature-fixture/v1/runs/'+run+'/'):
        raise ValueError('Graphics fixture resource root belongs to another run')
    parsed.port
    namespace=uuid.UUID(hex=run)
    def entity(name,kind,position,dimensions,**properties):
        return dict(id='{'+str(uuid.uuid5(namespace,'graphics-subject-v1/'+name))+'}',
            name='e2e-'+run+'-graphics-'+name,type=kind,position=dict(zip(('x','y','z'),position)),
            dimensions=dict(zip(('x','y','z'),dimensions)),rotation=dict(VIEW['rotation']),
            collisionless=True,locked=False,**properties)
    entities=[
        entity('zone','Zone',(0,1.6,-10),(120,120,120),hazeMode='enabled',
            haze=dict(hazeRange=18,hazeColor=dict(red=25,green=90,blue=210),
                hazeEnableGlare=False,hazeAltitudeEffect=False,hazeBackgroundBlend=0.0),
            keyLightMode='enabled',keyLight=dict(color=dict(red=255,green=255,blue=255),
                intensity=1.0,direction=dict(x=-0.5,y=-1.0,z=-0.5)),
            ambientLightMode='enabled',ambientLight=dict(ambientIntensity=0.8)),
        entity('floor','Box',(0,-0.05,-15),(30,0.1,60),color=dict(red=95,green=95,blue=95)),
        entity('fog-board','Box',(-3,2,-28),(7,4,0.1),color=dict(red=240,green=240,blue=240)),
        entity('resolution-bars','Box',(-2,1.6,-5),(0.05,2.5,0.1),color=dict(red=250,green=250,blue=250)),
        entity('reflector','Box',(2,1.7,-4),(2,3,0.01),mirrorMode='mirror',
            canCastShadow=False,isVisibleInSecondaryCamera=False),
        # Reflecting z=2 about z=-4 puts the virtual color center at (5,1.6,-10).
        # Its ray from VIEW crosses the actual mirror rectangle at x=2, z=-4.
        entity('reflected-color','Box',(5,1.6,2),(1,1,1),color=dict(red=255,green=90,blue=0)),
        # Keep the challenge near the camera: the forward Web shader also
        # applies Zone haze, so a distant black/white card loses decode contrast.
        entity('marker','Web',(0,1.67,-0.25),(0.2,0.05,0.01),dpi=100,
            sourceUrl=fixture_url+'tickets/'+ticket+'/graphics-marker.v1.html'),
    ]
    # A marker page is loaded through one registered ticket. It independently
    # polls /current for later marker bytes; no desired graphics state is sent.
    return dict(DataVersion=3,Entities=entities)


LEGACY_PROFILE = 'legacy-v2'
PICO_PROFILE = 'pico-stereo-cues-v1'
PICO_RESOURCE = 'graphics-scene.pico-stereo.v1.json'


def pico_scene(run,ticket,fixture_url):
    """Explicit VR stimulus variant; default legacy geometry remains unchanged."""
    from .graphics_surface_cues import RESOURCES
    value=scene(run,ticket,fixture_url)
    for entity in value['Entities']:
        name=entity['name'].rsplit('-graphics-',1)[1]
        if name=='zone':entity['haze']['hazeRange']=90
        if name not in ('fog-board','reflected-color'):continue
        surface='haze' if name=='fog-board' else 'reflection'
        entity.update(type='Web',dpi=100,color=dict(red=255,green=255,blue=255),canCastShadow=False,
            isVisibleInSecondaryCamera=name=='reflected-color',
            sourceUrl=fixture_url+'tickets/'+ticket+'/'+RESOURCES[surface]+'.html')
        entity['dimensions']=dict(x=14,y=6,z=.01) if name=='fog-board' else dict(x=4.6,y=2.3,z=.01)
        if name=='fog-board':entity['position']=dict(x=-7,y=2,z=-28)
        if name=='reflected-color':entity['rotation']=dict(x=0,y=1,z=0,w=0)
    return value
