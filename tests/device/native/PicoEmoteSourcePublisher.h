// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PicoEmoteCaptureFile.h"
#include "PicoEmoteSourceTransaction.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <memory>
#include <QSet>

namespace overte::e2e {
// NEW, not wired/compiled. Needs the exact reviewed additive fixed-leaf bound
// in existing PicoEmoteCaptureFile before open can succeed. Uses that ORIGINAL
// paired-OFD/marker/full-byte/readback/fsync writer; no parallel file writer.
class PicoEmoteSourcePublisher {
public:
    static constexpr const char* Leaf="feature-pico-emote-source-transaction.wire";
    static constexpr const char* Receipt="feature-pico-emote-source-receipt.json";
    bool open(const QString& root,std::function<bool()> permit) {
        if (_opened) {return fail();}
        _opened=true;_permit=std::move(permit);
        _file=std::make_shared<PicoEmoteCaptureFile>(); // Strong BEFORE open.
        if (!_permit || !_permit() || !_file->open(root,Leaf,_permit)) {return fail();}
        _receipt=std::make_shared<PicoEmoteCaptureFile>(); // Strong before second original open.
        if (!_receipt->open(root,Receipt,_permit)) {return fail();}
        return _file->ready();
    }
    bool publish(const QString& nonce,QByteArray& original) {
        if (_failed || _stopped || _closed || _busy || !_file || !_permit || !_permit()
                || !_file->ready() || _nonces.contains(nonce) || _nonces.size()>=512) {return fail();}
        _busy=true;_nonces.insert(nonce); // Uncertain publication consumes it.
        if (original.isEmpty() || original.size()>PicoEmoteSourceTransaction::WireLimit
                || !_file->publish(nonce,original) || !_permit() || !_file->ready()) {return fail();}
        const auto wire=_file->originalProof(),receipt=_receipt->originalProof(true);
        if (wire.isEmpty() || receipt.isEmpty()) {return fail();}
        // The ORIGINAL file/expected-bytes owner now holds the complete wire.
        // No second full assembler survives while Host receives/parses it.
        original.clear();
        _receiptOriginal=QJsonDocument::fromVariant(QVariantMap{{"picoEmoteSourceReceiptVersion",1},{"commandId",nonce},
            {"wire",wire},{"receiptNode",receipt.value("sampleNode")},{"builderSettled",true}}).toJson(QJsonDocument::Compact);
        if (_receiptOriginal.isEmpty() || _receiptOriginal.size()>PicoEmoteSourceTransaction::ReceiptLimit
                || !_receipt->publish(nonce,_receiptOriginal) || !_permit() || !_receipt->ready() || !_file->ready()) {return fail();}
        _busy=false;return true;
    }
    QVariantMap originalProof() {
        return !_failed && !_busy && _file ? _file->originalProof() : QVariantMap{};
    }
    void stop() {_stopped=true;}
    bool drain() {
        if (_closed) {return true;}
        // Existing close verifies physical/current bytes and actual OFDs;
        // it does not require a renewed business permit after original Stop.
        if (_failed || !_stopped || _busy || !_file || !_receipt || !_file->close() || !_receipt->close()) {return fail();}
        _closed=true;return true;
    }
    bool pending() const {return _failed || _busy || (_opened && !_closed);}
private:
    bool fail() {_failed=true;return false;}
    std::shared_ptr<PicoEmoteCaptureFile> _file,_receipt;std::function<bool()> _permit;QSet<QString> _nonces;
    QByteArray _receiptOriginal;
    bool _opened{false},_failed{false},_stopped{false},_closed{false},_busy{false};
};
}
#endif
