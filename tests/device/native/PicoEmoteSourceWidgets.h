// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QCoreApplication>
#include <QPointer>
#include <QThread>
#include <QVariantMap>
#include <functional>
#include <unistd.h>

namespace overte::e2e {
// NEW, not installed or compiled. TabletBridge must retain this provider and
// capture its original SAME NavigationUi member; no replacement observer or
// input/screen/pose API is exposed. TSI pins the exact shared object once.
class PicoEmoteSourceWidgets {
public:
    PicoEmoteSourceWidgets(QObject* owner,std::function<QVariantMap()> actual):
        _owner(owner),_actual(std::move(actual)) {}
    QVariantMap observe() {
        if (_failed || _busy || !context() || !_actual) {return fail();}
        _busy=true;_original=_actual(); // Keep produced bytes/values before post-callback refusal.
        if (_failed || !context() || _original.isEmpty()) {return fail();}
        QVariantMap result;result.swap(_original); // Explicit empty member on success; no lingering DTO duplicate.
        _busy=false;return result;
    }
    bool available() const {return !_failed && !_busy && context();}
private:
    bool context() const {return ::getpid()==_pid && _owner && _application
        && QCoreApplication::instance()==_application && QThread::currentThread()==_thread
        && _owner->thread()==_thread && _application->thread()==_thread;}
    QVariantMap fail() {_failed=true;return {};}
    const pid_t _pid{::getpid()};QCoreApplication* const _application{QCoreApplication::instance()};
    QThread* const _thread{QThread::currentThread()};const QPointer<QObject> _owner;
    const std::function<QVariantMap()> _actual;QVariantMap _original;bool _failed{false},_busy{false};
};
}
#endif
