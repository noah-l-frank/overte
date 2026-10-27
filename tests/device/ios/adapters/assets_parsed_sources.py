"""Closed durable parser-origin acquisition on the existing Model owner.

Old Model-source journals retain their literal schemas and source order. This
separate profile saves every new origin raw carrier before native parsing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import assets_model_origin as origin
from ios.adapters.assets_model_owner import OwnedAssetsModel
from ios.adapters.assets_model_raw_sources import ModelRawSources
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_model_creation_round import ModelCreationRound,eligible,function


class ParsedRawSources(ModelRawSources):
    NAMESPACE='assets-parsed-native'
    SCHEMA_PREFIX='iosAssetsParsedRawSource'
    MIGRATION_PREFIX='assets-parsed-native-migration-'
    RECORD_KEY='iosAssetsParsedRawSourceRecordVersion'
    MIGRATION_KEY='iosAssetsParsedRawSourceMigrationVersion'


class AssetsParsedSources(AssetsModelSources):
    OWNER_KEY='iosAssetsParsedSourcesVersion'
    FRAME_KEY='assetParsedSourceFrameVersion'
    NAMESPACE='assets-parsed-source'
    SCHEMA_PREFIX='iosAssetsParsedSource'
    RAW_TYPE=ParsedRawSources
    ORIGINAL_KEYS=AssetsModelSources.ORIGINAL_KEYS|{'origin'}

    def __init__(self,model,reader,store,*,lock):
        need(isinstance(model,OwnedAssetsModel) and isinstance(reader,origin.IOSAssetsModelOrigin)
            and reader.pid==model.sources.native.pid);self.model,self.origin_reader=model,reader;source=model.sources
        super().__init__(model.usage,source.native,source.readers['state'],source.readers['work'],store,
            lock=lock,epoch_ms=source.epoch_ms,monotonic=source.monotonic)

    def guard(self):
        super().guard();self.model.guard();return True

    def reader_map(self,state,work):return dict(state=state,work=work,origin=self.origin_reader)
    def reader_module(self,kind):return origin if kind=='origin' else super().reader_module(kind)
    def restore_readers(self,originals):
        super().restore_readers(originals);self.origin_reader.last=deepcopy(originals['origin'])
    def external(self,originals):return [originals['createBefore'],originals['work'],originals['origin'],originals['createAfter']]
    def read_originals(self):
        return dict(createBefore=self.readers['state'].read(self.run),work=self.readers['work'].read(self.run),
            origin=self.origin_reader.read(self.run),createAfter=self.readers['state'].read(self.run))

    def decode(self,value):
        if (type(self) is not AssetsParsedSources
                or tuple(function(value) for value in (self.frame,self._frame_from_creation,self._origin_source,self._origin_frame))!=_FRAME_FUNCTIONS
                or getattr(self._decode_with_frame,'__func__',None) is not _BASE_DECODE or not eligible(self)):
            return super().decode(value)
        round_=ModelCreationRound(self)
        try:return self._decode_with_frame(value,lambda frame,previous:self._frame_from_creation(frame,previous,round_))
        except BaseException as primary:
            try:round_.close()
            except BaseException as secondary:primary.add_note('Closing Assets original Model decode also failed: '+type(secondary).__name__)
            raise
        finally:
            if round_.active:round_.close()

    def _origin_source(self,value):
        originals=value['originals'];packet=originals['origin'];source=packet['source']
        before,after=originals['createBefore'],originals['createAfter'];current=after['source']
        need(source['complete'] and source['domainId']==current['domainId'] and source['localSessionId']==current['localSessionId']
            and same(source['tree'],before['source']['tree']) and same(source['tree'],current['tree'])
            and before['clockAfter']['epochMs']<=packet['clockBefore']['epochMs']<=packet['clockAfter']['epochMs']<=after['clockBefore']['epochMs'])
        return packet,source

    def frame(self,value,previous=None):
        super().frame(value,previous);self._origin_source(value)
        self.model.decode(self.model.previous);need(self.model.state['creation'] is not None)
        return self._origin_frame(value,previous,self.model.state['creation'])

    def _frame_from_creation(self,value,previous,round_):
        round_.check();super().frame(value,previous);self._origin_source(value);round_.check()
        result=self._origin_frame(value,previous,round_.creation);round_.check();return result

    def _origin_frame(self,value,previous,creation):
        packet=value['originals']['origin'];source=packet['source'];proof=creation['proof']
        need(proof['runId']==packet['runId'] and proof['processId']==packet['processId']
            and proof['domainId']==source['domainId'] and proof['clientNodeId']==source['localSessionId'])
        if previous is not None:
            origin.validate(packet,dict(schemaVersion=1,action=origin.ACTION,commandId=packet['requestId'],runId=packet['runId']),packet['processId'],previous=previous['originals']['origin'])
        return value


_PARSED_FRAME=AssetsParsedSources.frame
_BASE_DECODE=AssetsModelSources._decode_with_frame
_INTERNAL_FRAME=AssetsParsedSources._frame_from_creation
_ORIGIN_SOURCE=AssetsParsedSources._origin_source
_ORIGIN_FRAME=AssetsParsedSources._origin_frame
_FRAME_FUNCTIONS=tuple(function(value) for value in (_PARSED_FRAME,_INTERNAL_FRAME,_ORIGIN_SOURCE,_ORIGIN_FRAME))
