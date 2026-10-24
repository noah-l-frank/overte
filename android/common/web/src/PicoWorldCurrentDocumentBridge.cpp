// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "../../../../tests/device/native/PicoWorldCurrentDocumentBridge.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
namespace overte::e2e {
PicoCurrentAnchor picoCurrentAnchor(const QVariantMap& command) {
    if(!picoWorldCurrentDocumentCommand(command))return {};
    struct Record{QByteArray command;PicoCurrentAnchor anchor;};
    static QMutex mutex;static QHash<QString,Record> records;
    QMutexLocker guard(&mutex);const auto id=command.value("commandId").toString();
    const auto raw=QJsonDocument::fromVariant(command).toJson(QJsonDocument::Compact);
    if(records.contains(id))return records[id].command==raw ? records[id].anchor : PicoCurrentAnchor();
    if(records.size()>=4096)return {};
    const auto anchor=std::make_shared<const PicoCurrentClock>();records.insert(id,{raw,anchor});return anchor;
}
}
#endif
