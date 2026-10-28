// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "NormalChatControls.h"
#include <qml/IOSQmlSourceObservation.h>
#include <QElapsedTimer>
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonDocument>
#include <QPointer>
#include <QThread>
#include <QUuid>
#include <functional>
#include <cmath>

namespace overte::e2e {
inline bool chatQmlWireValue(const QVariant &value,int depth,int &nodes) {
    if (depth>32 || ++nodes>16384) return false;
    switch (value.metaType().id()) {
    case QMetaType::QVariantMap:
        for (const auto &child:value.toMap()) if (!chatQmlWireValue(child,depth+1,nodes)) return false;
        return true;
    case QMetaType::QVariantList:
        for (const auto &child:value.toList()) if (!chatQmlWireValue(child,depth+1,nodes)) return false;
        return true;
    case QMetaType::QString:case QMetaType::Bool:case QMetaType::Int:case QMetaType::UInt:return true;
    // Actual V8 cast converts Long/ULong through toInt/toUInt, even on LP64.
    case QMetaType::Long:return value.toLongLong()>=-2147483648LL && value.toLongLong()<=2147483647LL;
    case QMetaType::ULong:return value.toULongLong()<=4294967295ULL;
    case QMetaType::LongLong:return value.toLongLong()>=-9007199254740991LL && value.toLongLong()<=9007199254740991LL;
    case QMetaType::ULongLong:return value.toULongLong()<=9007199254740991ULL;
    case QMetaType::Float:case QMetaType::Double: {
        const auto number=value.toDouble();return std::isfinite(number) && std::trunc(number)==number && std::abs(number)<=9007199254740991.0;
    }
    default:return false;
    }
}
inline bool chatQmlWireValue(const QVariantMap &value) { int nodes=0;return chatQmlWireValue(QVariant(value),0,nodes); }
}


namespace overte::e2e {
class IOSChatQmlSourcesObservation {
public:
    static IOSChatQmlSourcesObservation& instance() { static IOSChatQmlSourcesObservation value; return value; }
    QVariantMap read(const QString& request, const QString& run,
            const std::function<QVariantMap(const void *)>& imageReader = {}) {
        if (!qApp || QThread::currentThread() != qApp->thread()
                || !QCoreApplication::arguments().contains("--testScript") || _sequence >= 1000000000ULL) { return {}; }
        const auto before = clock();
        QPointer<QQuickItem> page;
        // All successful observed loads participate, including roots whose
        // cache/compiler association is unavailable. No Tablet getter creates UI.
        for (auto object : hifi::qml::IOSQmlSourceObservation::liveObjects()) {
            auto item = qobject_cast<QQuickItem*>(object);
            if (!item || item->thread() != qApp->thread() || chatPage(item) != item || page) { return {}; }
            page = item;
        }
        if (!page) { return {}; }
        const auto source = hifi::qml::IOSQmlSourceObservation::read(page);
        const auto control = chatControlSource(page, "chat.page");
        if (source.isEmpty() || control.isEmpty()) { return {}; }
        QVariantMap image,dependencyImage;
        const auto version=source.value("iosLoadedQmlSourceVersion").toInt();
        const bool cached=version==2 || version==3;
        if (cached) {
            const auto actual=hifi::qml::IOSQmlSourceObservation::cacheObservationSymbol(page);
            if (!actual || !imageReader) return {};
            image=imageReader(actual);if (image.isEmpty()) return {};
        }
        if (version==3) {
            const auto actual=hifi::qml::IOSQmlSourceObservation::dependencyObservationSymbol(page);
            if (!actual || !imageReader) return {};
            dependencyImage=imageReader(actual);if (dependencyImage.isEmpty()) return {};
        }
        if (!page || (cached && !hifi::qml::IOSQmlSourceObservation::cacheObservationSymbol(page))
                || (version==3 && !hifi::qml::IOSQmlSourceObservation::dependencyObservationSymbol(page))) return {};
        const auto after = clock();
        QVariantMap result {{"iosChatQmlSourcesVersion", version==3?3:cached?2:1}, {"requestId", request}, {"runId", run},
            {"instance", _instance}, {"sequence", qulonglong(++_sequence)}, {"processId", QCoreApplication::applicationPid()},
            {"clockDomain", "native-main-chat-qml-sources"}, {"clockBefore", before}, {"clockAfter", after},
            {"pageControlSourceSha256", control}, {"source", source}};
        if (cached) result.insert("qtEntryImage",image);
        if (version==3) result.insert("qtDependencyEntryImage",dependencyImage);
        // Check before the actual QVariantMap -> ScriptEngineV8 -> JSNumber
        // conversion. Filesystem IDs/offsets are strings; every Number is exact.
        return chatQmlWireValue(result) && QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size() <= 65536 ? result : QVariantMap();
    }
private:
    IOSChatQmlSourcesObservation() { _timer.start(); }
    QVariantMap clock() const { return {{"epochMs", QDateTime::currentMSecsSinceEpoch()}, {"monotonicMs", _timer.elapsed()}}; }
    QElapsedTimer _timer;
    quint64 _sequence { 0 };
    const QString _instance { QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') };
};
}
#endif
