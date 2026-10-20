// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include "../../native/PendingFieldCommitOwner.h"
#include <DependencyManager.h>
#include <OffscreenUi.h>
#include <QMouseEvent>

namespace overte::e2e {
inline void installPhonePendingCommitOwner(const std::function<bool()>& launchGuard) {
    if (!qApp || QThread::currentThread() != qApp->thread() || !launchGuard || !launchGuard()
            || qApp->property(pendingCommitProviderProperty()).isValid()) { return; }
    const auto roots = [] {
        PendingFieldCommitOwner::Roots result;
        if (QGuiApplication::applicationState() != Qt::ApplicationActive || !DependencyManager::isSet<OffscreenUi>()) { return result; }
        const auto ui = DependencyManager::get<OffscreenUi>();
        auto root = ui->getRootItem(); auto window = ui->getWindow();
        if (!root || !window || root->window() != window || root->thread() != qApp->thread()
                || window->thread() != qApp->thread()) { return result; }
        result.available = true; result.items.append(root); return result;
    };
    const auto pointer = [roots](QQuickItem* item, QQuickWindow* window, const QPointF& point) {
        const auto current = roots();
        if (!current.available || !item || !window || item->window() != window
                || !NormalControlUi::ownsPoint(item, window, point)) { return false; }
        QPointer<QQuickItem> original = item;
        QPointer<QQuickWindow> surface = window;
        QMouseEvent move(QEvent::MouseMove, point, Qt::NoButton, Qt::NoButton, Qt::NoModifier);
        QCoreApplication::sendEvent(surface, &move);
        if (!original || !surface || !NormalControlUi::ownsPoint(original, surface, point)) { return false; }
        QMouseEvent press(QEvent::MouseButtonPress, point, Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
        const bool pressed = QCoreApplication::sendEvent(surface, &press);
        bool released {false};
        if (surface) {
            QMouseEvent release(QEvent::MouseButtonRelease, point, Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
            released = QCoreApplication::sendEvent(surface, &release);
        }
        return pressed && released && original && surface;
    };
    const auto owner = std::make_shared<PendingFieldCommitOwner>(roots, pointer);
    PendingCommitProvider provider = [owner, launchGuard](const QVariantMap& command) {
        if (!qApp || QThread::currentThread() != qApp->thread() || !launchGuard()) { return QVariantMap(); }
        return owner->request(command);
    };
    qApp->setProperty(pendingCommitProviderProperty(), QVariant::fromValue(provider));
}
} // namespace overte::e2e
#endif
