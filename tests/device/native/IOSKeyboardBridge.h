// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QJsonObject>
#include <QRegularExpression>
#include <QVariant>
#include <functional>
namespace overte::e2e::keyboard {
using Provider=std::function<QVariantMap(const QVariantMap&)>;
inline const char* property() {return "_overteE2EOriginalIOSKeyboardV1";}
inline bool command(const QVariantMap& value) {
    const auto row=QJsonObject::fromVariantMap(value);
    return row.keys()==QStringList{"action","commandId","runId","schemaVersion"}
        && row.value("schemaVersion")==QJsonValue(1) && row.value("action")==QJsonValue("feature-ios-keyboard")
        && row.value("commandId").isString() && row.value("runId").isString()
        && QRegularExpression("\\Aios-[a-f0-9]{32}\\z").match(row.value("commandId").toString()).hasMatch()
        && QRegularExpression("\\A[a-f0-9]{32}\\z").match(row.value("runId").toString()).hasMatch();
}
}
Q_DECLARE_METATYPE(overte::e2e::keyboard::Provider)
#endif
