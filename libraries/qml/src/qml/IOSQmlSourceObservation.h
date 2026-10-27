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
};
}
