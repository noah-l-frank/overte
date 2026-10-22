// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QElapsedTimer>
#include <QHash>
#include <QJsonObject>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <functional>
#include "../../tests/device/native/NormalAudioControls.h"
#include "../../tests/device/native/NormalGraphicsControls.h"
#include "../../tests/device/native/NormalLoginControls.h"
#endif

namespace overte::ios {

// The iOS HUD/dialog and screen-space tablet are different live Qt roots.
// This closed normal-input observer cannot mutate a navigation service.
class NormalUiInput {
public:
    NormalUiInput();
#if defined(OVERTE_E2E_FEATURE_TESTS)
    void setAudioReader(std::function<overte::e2e::AudioUiContext()> reader) { _audioReader = std::move(reader); }
    QJsonObject privateLoginEdit(const QJsonObject& command,const QString& origin);
    void setLoginReader(std::function<overte::e2e::LoginUiContext()> reader) { _loginReader = std::move(reader); }
    void setGraphicsReader(std::function<overte::e2e::GraphicsUiContext()> reader) { _graphicsReader = std::move(reader); }
#endif
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
#if defined(OVERTE_E2E_FEATURE_TESTS)
    std::function<overte::e2e::LoginUiContext()> _loginReader;
    QString _loginGeneration;
    qint64 _scriptObservationSequence {0};
    QHash<QQuickItem*, QPointer<QQuickItem>> _scriptRoots;
    QHash<QQuickItem*, QPointer<QQuickItem>> _navigationRoots;
    std::function<overte::e2e::AudioUiContext()> _audioReader;
    std::function<overte::e2e::GraphicsUiContext()> _graphicsReader;
    quint64 _avatarObservationSequence {0};
    QString _emoteGeneration;
    QHash<QQuickItem*, QPointer<QQuickItem>> _emoteRoots;
    quint64 _emoteObservationSequence {0};
    quint64 _placesObservationSequence {0};
    quint64 _navigationDialogSequence {0};
#endif
    QPointer<QQuickItem> _hud;
    QPointer<QQuickItem> _tablet;
    bool _tabletShown { false };
    QHash<QString, Control> _controls;
    QElapsedTimer _clock;
    QString _instance;
    qint64 _sequence { 0 };
};

} // namespace overte::ios
