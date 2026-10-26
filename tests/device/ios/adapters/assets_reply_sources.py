"""Closed independent-reply profile of the exact native-source byte store."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.assets_file_sources import FileSources


class ReplySources(FileSources):
    NAMESPACE='assets-replies-native'
    SCHEMA_PREFIX='iosAssetsReplySource'
    MIGRATION_PREFIX='assets-replies-migration-'
    RECORD_KEY='iosAssetsReplySourceRecordVersion'
    MIGRATION_KEY='iosAssetsReplySourceMigrationVersion'
    MAX_REFS=257
