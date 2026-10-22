// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSWorldWebTrace.h"
#include "IOSTabletWebTrace.h"
#include "../../tests/device/native/IOSWebScriptEmissions.h"
namespace overte::ios::browser_trace {
inline quint64 event(const QVariantMap& identity,const QString& kind,const QVariantMap& detail={}) {
    if (identity.value("surface")=="world-entity") { return world_web_trace::event(identity,kind,detail); }
    if (identity.value("surface")=="tablet") {
        // UIKit text entry has its own original trusted DOM/input receipts.
        // Never copy Qt key text/codes into the Tablet transcript.
        if (kind=="key-enter") { return 0; }
        return tablet_web_trace::event(identity,kind,detail);
    }
    return 0;
}
class Callback final {
public:
    Callback(QVariantMap identity,quint64 entry,QVariantMap result={}) : _identity(std::move(identity)),_entry(entry) {
        if (_entry) { event(_identity,"callback-enter",{{"entry",static_cast<qulonglong>(_entry)},{"result",result}}); }
    }
    ~Callback() { if (_entry) { event(_identity,"callback-return",{{"entry",static_cast<qulonglong>(_entry)}}); } }
    Callback(const Callback&)=delete;Callback& operator=(const Callback&)=delete;
private:QVariantMap _identity;quint64 _entry;
};
class Signal final {
public:
    Signal(QVariantMap identity,QString kind,QVariantMap detail) : _identity(std::move(identity)) {
        _entry=event(_identity,kind,detail);
        if ((kind=="page-reply" || kind=="script-event-slot") && overte::e2e::web_script_emissions::enabled()) {
            try { _emission=std::make_unique<overte::e2e::web_script_emissions::SinkScope>(kind,_identity,detail.value("message")); }
            catch (...) { overte::e2e::web_script_emissions::invalid(); }
        }
    }
    ~Signal() { if (_entry) { event(_identity,"signal-return",{{"entry",static_cast<qulonglong>(_entry)}}); } }
    Signal(const Signal&)=delete;Signal& operator=(const Signal&)=delete;
private:QVariantMap _identity;quint64 _entry{0};
    std::unique_ptr<overte::e2e::web_script_emissions::SinkScope> _emission;
};
} // namespace overte::ios::browser_trace
#endif
