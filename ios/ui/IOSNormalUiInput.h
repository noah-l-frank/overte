// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QElapsedTimer>
#include <QHash>
#include <QJsonObject>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>

namespace overte::ios {

// The iOS HUD/dialog and screen-space tablet are different live Qt roots.
// This closed normal-input observer cannot mutate a navigation service.
class NormalUiInput {
public:
    NormalUiInput();
    QJsonObject observe(QQuickItem* hud, QQuickItem* tablet, bool tabletShown);
    QQuickItem* item(const QString& controlId, const QString& token);
    QRectF projectedFrame(const QString& controlId, const QString& token,
                         const QRectF& windowBounds, const QRectF& safeBounds);
    bool press(const QString& controlId, const QString& token);
    QJsonObject edit(const QJsonObject& command);
    static bool validRequest(const QJsonObject& command);
    QJsonObject request(const QJsonObject& command);
private:
    struct Control {
        QPointer<QQuickItem> item;
        QPointer<QQuickWindow> window;
        QString token;
        QString source;
    };
    bool guiThread() const;
    QPointer<QQuickItem> _hud;
    QPointer<QQuickItem> _tablet;
    bool _tabletShown { false };
    QHash<QString, Control> _controls;
    QElapsedTimer _clock;
    QString _instance;
    qint64 _sequence { 0 };
};

} // namespace overte::ios
