// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#if defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QJsonObject>
#include <QString>

namespace overte::ios {
// Read-only original files from the source-owned Snapshot root. A root argument
// is available to host component tests, never to the wire command or script API.
bool validSnapshotFileRequest(const QJsonObject& command);
QJsonObject readSnapshotFiles(const QJsonObject& command, const QString& root = {});
}
#endif
