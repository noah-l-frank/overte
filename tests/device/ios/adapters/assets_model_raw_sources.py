"""Closed raw model-source profile; no legacy model journal is adopted."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.assets_file_sources import FileSources


class ModelRawSources(FileSources):
    NAMESPACE='assets-model-native'
    SCHEMA_PREFIX='iosAssetsModelRawSource'
    MIGRATION_PREFIX='assets-model-native-migration-'
    RECORD_KEY='iosAssetsModelRawSourceRecordVersion'
    MIGRATION_KEY='iosAssetsModelRawSourceMigrationVersion'
    MAX_REFS=1024

    def load(self,value):need(type(value) is dict and value.get('migration') is None);return super().load(value)
    def prepare_migration(self,_previous):need(False)
