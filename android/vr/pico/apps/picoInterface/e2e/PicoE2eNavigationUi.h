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
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <memory>
namespace overte::e2e { class AudioPageObservation; class ViewMenuLifetimes; }
#endif

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
                      const std::function<bool(QQuickItem*, const QPointF&)>& pointerAt = {},
                      const std::function<bool(QQuickItem*, const QPointF&, int)>& pointerScroll = {});
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
#if defined(OVERTE_E2E_FEATURE_TESTS)
    quint64 _emoteSourceSequence { 0 };
#endif
    bool _open { false };
#if defined(OVERTE_E2E_FEATURE_TESTS)
    std::shared_ptr<overte::e2e::AudioPageObservation> _audioPages;
    std::shared_ptr<overte::e2e::ViewMenuLifetimes> _viewMenuLifetimes;
#endif
};

} // namespace overte::pico::e2e
