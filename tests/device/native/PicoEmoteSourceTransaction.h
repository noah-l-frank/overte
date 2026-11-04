// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include "PicoEmoteSourceJsonBudget.h"
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE) && defined(Q_OS_LINUX)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QVariantMap>
#include <cstring>
#include <functional>
#include <memory>
#include <unistd.h>

namespace overte::e2e {
struct PicoEmoteSourceTransactionRequest {
    explicit PicoEmoteSourceTransactionRequest(QVariantMap value):command(std::move(value)),requested(QDateTime::currentMSecsSinceEpoch()) {age.start();}
    bool fresh() const {const auto now=QDateTime::currentMSecsSinceEpoch();return age.isValid() && age.elapsed()>=0
        && age.elapsed()<5000 && now>=requested && now-requested<5000;}
    const QVariantMap command;const qint64 requested;QElapsedTimer age;
};
// NEW, not wired or compiled. All builders must run on the original GUI/TSI
// thread and call the existing original readers, including the SAME existing
// NavigationUi. The owner is held BEFORE start/any delegated file constructor.
// One wire contains actual lexical originals; it never combines historical
// SDK returns, fabricates source IDs or advances an expired Parent policy.
class PicoEmoteSourceTransaction {
public:
    // SAME 1MiB SDK literal reservation: leave the existing fixed physical
    // wire reader's 1+4096-byte envelope allowance BEFORE native publication.
    // This is an enforced source-file bound, not a guessed PNG/GPU bound.
    static constexpr qsizetype ReceiptLimit=4096;
    static constexpr qsizetype WireLimit=1048576-1-4096-ReceiptLimit;
    using Builder=std::function<QVariantMap(const QString&,const QString&)>;
    using Permit=std::function<bool()>;
    using Publisher=std::function<bool(const QString&,QByteArray&)>;
    PicoEmoteSourceTransaction(std::shared_ptr<const PicoEmoteSourceTransactionRequest> original,Builder builder,Permit permit,Publisher publish):
        _original(std::move(original)),_request(_original ? _original->command : QVariantMap{}),
        _builder(std::move(builder)),_permit(std::move(permit)),_publish(std::move(publish)) {}
    static bool command(const QVariantMap& value) {
        const QStringList expected{"action","commandId","originalPolicySha256","parentBaselineSha256","runId","schemaVersion"};
        if (value.keys()!=expected) {return false;}
        const auto version=value.value("schemaVersion");const auto number=version.userType();
        if (!(number==QMetaType::Double || number==QMetaType::Float || number==QMetaType::Int || number==QMetaType::UInt
                || number==QMetaType::LongLong || number==QMetaType::ULongLong) || version.toDouble()!=1
                || value.value("action").userType()!=QMetaType::QString
                || value.value("action")!=QVariant("feature-pico-emote-source-transaction")) {return false;}
        for (const auto& key:QStringList{"commandId","runId","originalPolicySha256","parentBaselineSha256"}) {
            const auto count=(key=="commandId" || key=="runId") ? 32 : 64;
            const auto field=value.value(key);
            if (field.userType()!=QMetaType::QString
                    || !QRegularExpression("\\A[0-9a-f]{"+QString::number(count)+"}\\z").match(field.toString()).hasMatch()) {return false;}
        }
        return true;
    }
    // Called again ONLY for the existing Native pending ID by the bounded
    // original probe scheduler. No internal timer, new epoch or new request.
    QVariantMap advance(const QVariantMap& request) {
        if (_failed || !context() || request!=_request || !command(request) || !_builder || !_publish || !fresh()) {return fail();}
        if (_complete) {return acknowledgement();} // No repeat builders or publication.
        if (_busy) {return fail();}
        _busy=true;
        if (_next==0 && _wire.isEmpty()) {
            auto header=_request;header.insert("picoEmoteSourceTransactionVersion",1);
            header.insert("complete",true);header.insert("sourceCount",6);
            _wire=QByteArray("OVT_PICO_EMOTE_SOURCE_TRANSACTION_V1\n")
                +QJsonDocument::fromVariant(header).toJson(QJsonDocument::Compact)+'\n';
            // ONE assembler buffer, never records + another complete wire.
            // Header is private/unpublished until all six originals exist.
            _wire.reserve(WireLimit);
        }
        while (_next<labels().size()) {
            if (!fresh()) {return fail();}
            const auto label=labels().at(_next);
            // Distinct real original nonces. The actual builder receives its
            // nonce once; a pending native read keeps THAT SAME request ID.
            auto id=_ids.value(label);
            if (id.isEmpty()) {
                id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');_ids.insert(label,id);
            }
            _actual=_builder(label,id); // Keep returned original strongly before ANY encoding/check.
            const qsizetype limit=(label=="rootsBefore" || label=="rootsAfter") ? 16384 : 262144;
            PicoEmoteSourceJsonBudget bytes(limit);
            if (_actual.isEmpty() || !bytes.fits(_actual)) {return fail();}
            _literal=QJsonDocument::fromVariant(_actual).toJson(); // Original saveObject pretty bytes.
            if (_actual.isEmpty() || _literal.isEmpty()) {return fail();}
            if (label=="native" && _actual.value("pending")==QVariant(true)) {
                if (_actual.keys()!=QStringList{"pending","requestId","schemaVersion"}
                        || _actual.value("schemaVersion")!=QVariant(1) || _actual.value("requestId")!=QVariant(id)
                        || _literal.size()>256 || _pending>=51 || !append("nativePending",_literal)) {return fail();}
                ++_pending;_actual.clear();_literal.clear();_busy=false;
                return {{"schemaVersion",1},{"requestId",_request.value("commandId")},{"pending",true}};
            }
            // Oversized originals remain in _actual/_literal and earlier
            // complete originals remain in _wire. No truncate-success.
            if (_literal.size()>limit || !append(label,_literal)) {return fail();}
            _actual.clear();_literal.clear();++_next;
            if (!fresh()) {return fail();}
        }
        constexpr const char* footer="OVT_PICO_EMOTE_SOURCE_TRANSACTION_END_V1\n";
        if (_wire.size()+qsizetype(strlen(footer))>WireLimit || !fresh()) {return fail();}
        _wire+=footer;_publishedBytes=_wire.size();
        // The publisher must be the separately admitted strong fixed-file
        // owner with guaranteed SAME compound allowance before the first IO.
        // Unknown publication retains this owner, its wire and actual writer.
        // Publisher clears this assembler ONLY after actual successful wire
        // readback; its strong original FD/full-byte owner retains the wire.
        // It THEN publishes the actual node/hash receipt, so Host decoding
        // cannot overlap a second live complete assembler buffer.
        if (!fresh() || !_publish(_request.value("commandId").toString(),_wire) || !_wire.isEmpty() || !fresh()) {return fail();}
        _complete=true;_busy=false;return acknowledgement();
    }
    bool complete() const {return _complete && !_failed;}
    bool pending() const {return !_complete || _failed || _busy;}
    const QByteArray& originalWire() const {return _wire;}
private:
    static QStringList labels() {return {"rootsBefore","script","inventory","native","rootsAfter","widgets"};}
    bool context() const {return ::getpid()==_pid && QCoreApplication::instance()==_application
        && QThread::currentThread()==_thread && _application && _thread==_application->thread()
        && QCoreApplication::arguments().contains("--testScript");}
    bool fresh() const {return context() && _original && _original->fresh() && _permit && _permit() && _original->fresh();}
    bool append(const QString& label,const QByteArray& bytes) {
        const auto line=label.toLatin1()+' '+QByteArray::number(static_cast<qlonglong>(bytes.size()))+' '
            +QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()+'\n';
        // Reserve framing/header/footer space BEFORE expanding the one
        // lexical records buffer. All previous originals remain unchanged.
        if (_wire.size()+line.size()+bytes.size()+1>WireLimit-8192) {return false;}
        _wire+=line;_wire+=bytes;_wire+='\n';return true;
    }
    QVariantMap fail() {_failed=true;return {};}
    QVariantMap acknowledgement() const {return {{"schemaVersion",1},{"requestId",_request.value("commandId")},
        {"picoEmoteSourceTransactionVersion",1},{"complete",true},{"wireBytes",_publishedBytes}};}
    const pid_t _pid{::getpid()};QCoreApplication* const _application{QCoreApplication::instance()};
    QThread* const _thread{QThread::currentThread()};
    const std::shared_ptr<const PicoEmoteSourceTransactionRequest> _original;
    const QVariantMap _request;const Builder _builder;const Permit _permit;const Publisher _publish;
    int _next{0},_pending{0};QMap<QString,QString> _ids;
    QVariantMap _actual;QByteArray _literal,_wire;qsizetype _publishedBytes{};
    bool _failed{false},_complete{false},_busy{false};
};
}
#endif
