// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QElapsedTimer>
#include <QHash>
#include <QJsonObject>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>
#include <functional>

namespace overte::pico::e2e {

// Closed Go To, Snapshot and opt-in Script input on the actual VR scene graph. The
// caller supplies its live surface and ordinary pointer route. No navigation
// service, QML handler, expected scene or acceptance verdict is available here.
class NavigationUi {
public:
    NavigationUi();
    QJsonObject observe(QQuickItem* root, QQuickWindow* window, bool open);
    QJsonObject apply(QQuickItem* root, QQuickWindow* window, bool open,
                      const QJsonObject& command,
                      const std::function<bool(QQuickItem*)>& pointerClick,
                      const std::function<bool(QQuickItem*, const QPointF&)>& pointerAt = {});
private:
    struct Control {
        QPointer<QQuickItem> item;
        QString token;
        QString source;
    };
    QPointer<QQuickItem> _root;
    QPointer<QQuickWindow> _window;
    QHash<QString, Control> _controls;
    QString _bridgeId;
    QString _generation;
    QElapsedTimer _clock;
    qint64 _lastCommandSequence { 0 };
    bool _open { false };
};

} // namespace overte::pico::e2e
