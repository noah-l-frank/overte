"""Closed immutable Audio settings raw profile; no legacy adoption."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from ios.adapters.assets_file_sources import FileSources


class SettingsRawSources(FileSources):
    NAMESPACE='ios-audio-settings-source-raw'
    SCHEMA_PREFIX='iosAudioSettingsRaw'
    MIGRATION_PREFIX='ios-audio-settings-source-raw-migration-'
    RECORD_KEY='iosAudioSettingsRawRecordVersion'
    MIGRATION_KEY='iosAudioSettingsRawMigrationVersion'
    MAX_REFS=1024

    def load(self,value):need(type(value) is dict and value.get('migration') is None);return super().load(value)
    def prepare_migration(self,_previous):need(False)
