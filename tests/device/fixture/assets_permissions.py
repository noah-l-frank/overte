"""Asset-write control on the same process-owned Settings contract as Create.

Only the existing asset-write permission changes. Rez and unrelated permission
fields retain their actual original values, including during exact restoration.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from fixture.create_permissions import CreatePermissions,standard

WRITE='id_can_write_to_asset_server'


def asset_standard(rows):
    rows=standard(rows)
    need(all(type(row.get(WRITE)) is bool for row in rows))
    return rows


class AssetsPermissions(CreatePermissions):
    VERSION_FIELD='assetsPermissionsVersion'
    CHANGED_FIELDS=(WRITE,)
    validate_rows=staticmethod(asset_standard)
