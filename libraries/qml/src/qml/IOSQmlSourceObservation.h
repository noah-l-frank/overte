// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QString>
#include <QList>
#include <QUrl>
#include <QVariantMap>

class QObject;
class QQmlComponent;
class QQmlContext;

namespace hifi::qml {
// Passive, bounded direct-unit observation. No source loader, cache operation,
// product input, expected source or ownership transfer is provided here.
class IOSQmlSourceObservation {
public:
    static QString begin(const QUrl& requested, const QUrl& selected, QQmlContext* context) noexcept;
    static void attach(const QString& ticket, QQmlComponent* component) noexcept;
    static void complete(QQmlComponent* component, QQmlContext* context, QObject* object) noexcept;
    static QVariantMap read(QObject* object) noexcept;
    static QList<QObject*> liveObjects() noexcept;
    // Native diagnostic identity only: this exact live weak QObject's
    // existing observed-load birth. No code/source/retirement authority.
    static QVariantMap objectIdentity(QObject* object) noexcept;
    // Internal native bridge only. No pointer enters a Script/JSON receipt.
    static const void* cacheObservationSymbol(QObject* object) noexcept;
    static const void* dependencyObservationSymbol(QObject* object) noexcept;
};
}
