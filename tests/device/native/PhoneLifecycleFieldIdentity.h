// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PHONE_INTERFACE)
#include <QCoreApplication>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>
#include <QQmlContext>
#include <QThread>
#include <QUuid>
#include <QVector>

namespace overte::e2e {
// Shared original weak-object identity, never a QObject property/locator write.
// Dead weak references cannot match objects later allocated at the same address.
inline QString phoneLifecycleFieldIdentity(QQuickItem* field,QQuickWindow* window,QQmlContext* context) {
    if(!QCoreApplication::instance() || QThread::currentThread()!=QCoreApplication::instance()->thread()
            || !QCoreApplication::arguments().contains("--testScript") || !field || !window || !context
            || field->thread()!=QThread::currentThread() || window->thread()!=QThread::currentThread()
            || context->thread()!=QThread::currentThread() || field->window()!=window)return {};
    struct Original {QPointer<QQuickItem> field;QPointer<QQuickWindow> window;QPointer<QQmlContext> context;QString token;};
    static QVector<Original> originals;
    for(const auto& original:originals)if(original.field && original.field==field && original.window==window && original.context==context)return original.token;
    if(originals.size()>=64)return {};
    const auto token=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');originals.append({field,window,context,token});return token;
}
} // namespace overte::e2e
#endif
