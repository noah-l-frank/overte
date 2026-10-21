"""Original motion artifact bytes through the existing private file engine."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import context
from feature_journeys import emote_motion
from feature_journeys.contract import arguments,identifier,state as validate_state
from overte_phone_graphics_images import PhoneGraphicsImages

VERSION=1
FIELDS={'emoteMotionFileVersion','binding','runId','role','stage','ticket','call','state','capturedEpochMs',
        'requestId','name','bytes','sha256','phase','file'}


class PhoneEmoteMotionFiles(PhoneGraphicsImages):
    KIND='emote-motion'
    LIMIT=2*1024*1024

    @classmethod
    def valid_stage(cls,stage):return integer(stage,1,1024)

    @classmethod
    def record(cls,value):
        exact(value,FIELDS);context(value['binding']);identifier(value['runId']);identifier(value['ticket']);identifier(value['requestId'])
        need(type(value['emoteMotionFileVersion']) is int and value['emoteMotionFileVersion']==VERSION
            and value['role'] in ('primary','actor') and cls.valid_stage(value['stage'])
            and value['phase'] in ('planned','opened','saved') and integer(value['bytes'],2,cls.LIMIT)
            and type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256'])
            and number(value['capturedEpochMs'],1,1e15))
        call=arguments('feature.emotes.act',value['call'])
        need(call['runId']==value['runId'] and call['ticket']==value['ticket'] and call['verb'] in ('play','sit','override'))
        validate_state('emotes',value['state'],value['runId']);need(value['state']['override'] is True)
        name='emote-motion-'+value['runId']+'-'+value['role']+'-'+str(value['stage'])+'-'+value['requestId']+'.json'
        need(value['name']==name)
        if value['phase']=='planned':need(value['file'] is None)
        else:
            exact(value['file'],{'device','inode'});need(integer(value['file']['device'],0,2**64-1) and integer(value['file']['inode'],1,2**64-1))
        return value

    def value(self,ticket,capture):
        exact(capture,{'call','state','capturedEpochMs','requestId','bytes','sha256'})
        name='emote-motion-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+capture['requestId']+'.json'
        return dict(emoteMotionFileVersion=VERSION,binding=deepcopy(self.binding),runId=self.run,role=self.role,stage=self.stage,
            ticket=ticket,name=name,phase='planned',file=None,**deepcopy(capture))

    def content(self,value,raw):
        need(type(raw) is bytes and len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
        emote_motion.read(raw,call=value['call'],role=value['role'],epoch=value['capturedEpochMs'],
            captured=value['capturedEpochMs'],state=value['state'])
        actual=json.loads(raw)
        need(actual['after']['group']['native']['requestId']==value['requestId'])
