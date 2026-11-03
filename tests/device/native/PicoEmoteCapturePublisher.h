// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PicoEmoteCaptureFile.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QMap>
#include <QSet>
#include <memory>

namespace overte::e2e {
// Explicit Policy2-only publisher, wired through the gated TSI source.
// The original Source4 owner holds this object BEFORE open() and retains
// every partial/unknown member. Defaults do not select it; it is uncompiled.
class PicoEmoteCapturePublisher {
public:
    bool open(const QString& root,std::function<bool()> permit) {
        if (_opened) { return fail(); }
        _opened=true;_root=root;_permit=std::move(permit);
        if (!_permit || !_permit()) { return fail(); }
        const auto names=QDir(root).entryList(QDir::AllEntries|QDir::Hidden|QDir::System|QDir::NoDotAndDotDot);
        if (names.size()>4096) {return fail();}
        for (const auto& name:names) {
            if (name.startsWith("world-render-storage-") || name==PicoEmoteCaptureFile::Pending) {return fail();}
        }
        for (const auto& leaf : QStringList{"world-render-observation.json","feature-pico-world-model-draws.json",
                "world-render-receipts-result.json"}) {
            // Strong holder precedes the actual resource constructor/open.
            auto file=std::make_shared<PicoEmoteCaptureFile>();_fixed.insert(leaf,file);
            if (!file->open(_root,leaf,_permit)) { return fail(); }
        }
        return resources();
    }
    bool handles(const QString& leaf) const {
        return _fixed.contains(leaf)
            || QRegularExpression("\\Aworld-render-storage-[0-9a-f]{32}\\.json\\z").match(leaf).hasMatch();
    }
    bool publish(const QString& leaf,const QString& nonce,const QByteArray& originalBytes) {
        if (_failed || _stopped || _closed || _busy || !_permit || !_permit() || !resources() || !handles(leaf)) { return fail(); }
        _busy=true;std::shared_ptr<PicoEmoteCaptureFile> selected;
        if (_fixed.contains(leaf)) { selected=_fixed.value(leaf); }
        else {
            if (leaf!="world-render-storage-"+nonce+".json" || _receipts.contains(nonce) || _receipts.size()>=1024) { return fail(); }
            selected=std::make_shared<PicoEmoteCaptureFile>();_receipts.insert(nonce,selected);
            if (!selected->open(_root,leaf,_permit)) { return fail(); }
        }
        // Byte limits apply to the ACTUAL unchanged QJsonDocument output,
        // never to a prediction, caller pixel bound or compact stand-in.
        if (!selected->publish(nonce,originalBytes) || !_permit() || !resources()) { return fail(); }
        _busy=false;return true;
    }
    bool removeReceipt(const QString& nonce,const QByteArray& originalDigest) {
        if (_failed || _stopped || _closed || _busy || !_permit || !_permit() || !resources()
                || !_receipts.contains(nonce) || _receipts.value(nonce)->retired()) { return fail(); }
        _busy=true;
        if (!_receipts.value(nonce)->retireReceipt(nonce,originalDigest) || !_permit() || !resources()) { return fail(); }
        _busy=false;return true;
    }
    bool pendingWrite() const { return _busy; }
    void stop() { _stopped=true; }
    bool drain() {
        if (_closed) { return true; }
        if (_failed || !_stopped || _busy || !resources()) { return fail(); }
        for (auto file : _receipts) { if (!file->retired()) { return fail(); } }
        for (auto file : _fixed) { if (!file->close()) { return fail(); } }
        _closed=true;return true;
    }
    bool settled() { return !_failed && !_busy && (_closed || resources()); }
private:
    bool resources() {
        if (_failed || !_opened || _closed || _fixed.size()!=3) { return false; }
        for (auto file : _fixed) { if (!file->ready()) { return fail(); } }
        for (auto file : _receipts) { if (!file->retired() && !file->ready()) { return fail(); } }
        return true;
    }
    bool fail() { _failed=true;return false; }
    QString _root;std::function<bool()> _permit;
    QMap<QString,std::shared_ptr<PicoEmoteCaptureFile>> _fixed,_receipts;
    bool _opened{false},_failed{false},_stopped{false},_closed{false},_busy{false};
};
}
#endif
