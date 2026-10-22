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
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
// Internal test-cleanup primitive. Only the native owned-file ledger may pass
// its original row/root here; neither is accepted by a public wire command.
QJsonObject removeObservedSnapshotFile(const QJsonObject& original,const QString& observedRoot);
#endif
}
#endif
