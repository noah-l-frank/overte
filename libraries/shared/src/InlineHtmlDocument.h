// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <QChar>
#include <QByteArray>
#include <QCryptographicHash>
#include <QMetaType>
#include <QObject>
#include <QEvent>
#include <QThread>
#include <QPointer>
#include <QStringList>
#include <QUuid>
#include <QUrl>
#include <atomic>
#include <cstdint>
#include <limits>
#include <functional>
#include <memory>

namespace overte::web {

// This decodes the document, not a grant. Ordinary data: navigation remains
// separate from a native source owner's explicitly issued document lifetime.
struct InlineHtmlBytes {
    enum class Error { None, TooLarge, UnsupportedURL, UnsupportedMime, InvalidMetadata, InvalidBase64 };
    static constexpr int MAX_SOURCE_BYTES = 1024 * 1024;
    QByteArray body;
    QString charset;
    Error error { Error::UnsupportedURL };
    bool valid() const { return error == Error::None; }

    static InlineHtmlBytes decode(const QString& source) {
        InlineHtmlBytes result;
        if (source.size() > MAX_SOURCE_BYTES) { result.error = Error::TooLarge; return result; }
        const auto encoded = source.toUtf8();
        if (encoded.size() > MAX_SOURCE_BYTES) { result.error = Error::TooLarge; return result; }
        if (!source.startsWith("data:", Qt::CaseInsensitive)) { return result; }
        // A fragment identifies a location in the document, never body bytes.
        const auto fragment = encoded.indexOf('#');
        const auto input = fragment < 0 ? encoded : encoded.left(fragment);
        const auto comma = input.indexOf(',');
        if (comma < 5) { return result; }
        const auto metadata = input.mid(5, comma - 5);
        for (const auto byte : metadata) {
            if (static_cast<unsigned char>(byte) < 32 || static_cast<unsigned char>(byte) > 126) {
                result.error = Error::InvalidMetadata; return result;
            }
        }
        auto parts = QString::fromLatin1(metadata).split(';');
        if (parts.takeFirst().trimmed().compare("text/html", Qt::CaseInsensitive) != 0) {
            result.error = Error::UnsupportedMime; return result;
        }
        bool base64 = false;
        if (!parts.isEmpty() && parts.last().trimmed().compare("base64", Qt::CaseInsensitive) == 0) {
            base64 = true; parts.removeLast();
        }
        for (const auto& field : parts) {
            const auto parameter = field.trimmed();
            const auto equals = parameter.indexOf('=');
            if (equals <= 0) { result.error = Error::InvalidMetadata; return result; }
            const auto name = parameter.left(equals).trimmed();
            auto value = parameter.mid(equals + 1).trimmed();
            if (name.compare("charset", Qt::CaseInsensitive) != 0) { continue; }
            if (value.size() >= 2 && value.startsWith('"') && value.endsWith('"')) {
                value = value.mid(1, value.size() - 2);
            }
            if (value.isEmpty()) { result.error = Error::InvalidMetadata; return result; }
            for (const auto character : value) {
                const auto c = character.unicode();
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                      (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.')) {
                    result.error = Error::InvalidMetadata; return result;
                }
            }
            if (result.charset.isEmpty()) { result.charset = value; }
        }
        const auto hex = [](char c) {
            if (c >= '0' && c <= '9') { return c - '0'; }
            if (c >= 'a' && c <= 'f') { return c - 'a' + 10; }
            if (c >= 'A' && c <= 'F') { return c - 'A' + 10; }
            return -1;
        };
        QByteArray bytes;
        bytes.reserve(input.size() - comma - 1);
        for (int i = comma + 1; i < input.size(); ++i) {
            const auto c = input[i];
            if (c == '%' && i + 2 < input.size() && hex(input[i + 1]) >= 0 && hex(input[i + 2]) >= 0) {
                bytes.append(char(hex(input[i + 1]) * 16 + hex(input[i + 2]))); i += 2;
            } else {
                // URL percent-decoding preserves a literal malformed percent;
                // '+' is also literal, unlike application/x-www-form-urlencoded.
                bytes.append(c);
            }
        }
        if (base64) {
            QByteArray compact;
            for (const auto c : bytes) {
                if (c != ' ' && c != '\t' && c != '\n' && c != '\r' && c != '\f') { compact.append(c); }
            }
            if (compact.size() % 4 == 0) {
                if (compact.endsWith("==")) { compact.chop(2); }
                else if (compact.endsWith('=')) { compact.chop(1); }
            }
            if (compact.size() % 4 == 1) { result.error = Error::InvalidBase64; return result; }
            for (const auto c : compact) {
                if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
                      (c >= '0' && c <= '9') || c == '+' || c == '/')) {
                    result.error = Error::InvalidBase64; return result;
                }
            }
            // Validation precedes Qt's permissive decoder. Browser-compatible
            // whitespace and omitted padding do not authorize invalid symbols.
            while (compact.size() % 4) { compact.append('='); }
            bytes = QByteArray::fromBase64(compact);
        }
        result.body = bytes;
        result.error = Error::None;
        return result;
    }
};

namespace detail {
struct InlineDocumentLifetime;
class InlineDocumentContextFence final : public QObject {
public:
    std::weak_ptr<InlineDocumentLifetime> lifetime;
    bool eventFilter(QObject*, QEvent* event) override;
};
struct InlineDocumentLifetime {
    std::atomic<bool> live { true };
    std::unique_ptr<InlineDocumentContextFence> revocation { new InlineDocumentContextFence };
    void revoke() {
        if (live.exchange(false, std::memory_order_acq_rel)) { revocation.reset(); }
    }
    ~InlineDocumentLifetime() { revoke(); }
};
inline bool InlineDocumentContextFence::eventFilter(QObject*, QEvent* event) {
    // ThreadChange is delivered on the old thread before QObject migration.
    // Retire authority there, so the destroyed callback never has to dispatch
    // across threads or delete its notifier from a different thread.
    if (event->type() == QEvent::ThreadChange) {
        if (const auto current = lifetime.lock()) { current->revoke(); }
    }
    return false;
}
struct InlineDocumentPayload {
    QThread* issuingThread { nullptr };
    QPointer<QObject> context;
    QString sourceIdentity, sourceURL, scriptURL, charset, token;
    QByteArray body, sha256;
    QUrl transportURL;
    std::uint64_t revision { 0 };
};
} // namespace detail

class InlineHtmlDocumentOwner;

// Only lifetimeCurrent() is a cross-thread authority read: it touches immutable
// ownership and an atomic bool, never QObject/QPointer/context. Other descriptor
// access/subscription belongs to the issuing UI thread. Native policy/IO threads
// use UI-validated immutable copies plus that atomic lifetime lease.
// An opaque QVariant carrier. No QML constructor, writable fields or map/string
// conversion issues a document. The native backend checks its own real context.
class InlineHtmlDocument {
public:
    InlineHtmlDocument() = default;
    bool lifetimeCurrent() const {
        const auto lifetime = _lifetime.lock();
        return _payload && lifetime && lifetime->live.load(std::memory_order_acquire);
    }
    bool current() const {
        return lifetimeCurrent() && _payload->issuingThread == QThread::currentThread() &&
            !_payload->context.isNull();
    }
    bool currentFor(const QObject* context, const QString& identity, const QString& source) const {
        return current() && _payload->context == context && _payload->sourceIdentity == identity && _payload->sourceURL == source;
    }
    QObject* context() const { return current() ? _payload->context.data() : nullptr; }
    QString sourceURL() const { return current() ? _payload->sourceURL : QString(); }
    // Native adapters subscribe before navigation and cancel input, callbacks,
    // responses and bridge grants synchronously when authority is revoked.
    QMetaObject::Connection onRevoked(QObject* receiver, std::function<void()> callback,
                                      Qt::ConnectionType type = Qt::AutoConnection) const {
        const auto lifetime = _lifetime.lock();
        if (!receiver || !current() || !lifetime || !lifetime->revocation) { return {}; }
        return QObject::connect(lifetime->revocation.get(), &QObject::destroyed, receiver,
                                [callback](QObject*) { callback(); }, type);
    }
    QByteArray bytes() const { return current() ? _payload->body : QByteArray(); }
    QByteArray sha256() const { return current() ? _payload->sha256 : QByteArray(); }
    QString charset() const { return current() ? _payload->charset : QString(); }
    QString scriptURL() const { return current() ? _payload->scriptURL : QString(); }
    QString token() const { return current() ? _payload->token : QString(); }
    QUrl transportURL() const { return current() ? _payload->transportURL : QUrl(); }
    std::uint64_t revision() const { return current() ? _payload->revision : 0; }
private:
    friend class InlineHtmlDocumentOwner;
    std::shared_ptr<const detail::InlineDocumentPayload> _payload;
    std::weak_ptr<detail::InlineDocumentLifetime> _lifetime;
};

// The entity/surface owner keeps this native object for one acquisition. Issue,
// invalid replacement, explicit revoke, context death and owner death invalidate
// every copied old descriptor. Source revisions never wrap or reuse a token.
// Mutation is serialized on the first request's real context thread; rejecting a
// foreign caller does not retire that thread's existing request.
class InlineHtmlDocumentOwner {
public:
    InlineHtmlDocumentOwner() = default;
    InlineHtmlDocumentOwner(const InlineHtmlDocumentOwner&) = delete;
    InlineHtmlDocumentOwner& operator=(const InlineHtmlDocumentOwner&) = delete;
    ~InlineHtmlDocumentOwner() { revoke(); }
    void revoke() {
        const auto lifetime = std::move(_lifetime);
        if (lifetime) { lifetime->revoke(); }
    }
    InlineHtmlDocument issue(QObject* context, const QString& identity, const QString& source,
                             const QString& sourceScriptURL = QString()) {
        InlineHtmlDocument document;
        // A foreign caller must not mutate/revoke an existing UI-owned request.
        auto* callingThread = QThread::currentThread();
        if (_issuingThread && callingThread != _issuingThread) { return document; }
        if (!context || context->thread() != callingThread) { revoke(); return document; }
        _issuingThread = callingThread;
        revoke();
        if (identity.trimmed().isEmpty() || _revision == std::numeric_limits<std::uint64_t>::max()) { return document; }
        const auto decoded = InlineHtmlBytes::decode(source);
        if (!decoded.valid()) { return document; }
        auto payload = std::make_shared<detail::InlineDocumentPayload>();
        payload->issuingThread = _issuingThread;
        payload->context = context; payload->sourceIdentity = identity; payload->sourceURL = source;
        payload->scriptURL = sourceScriptURL;
        payload->body = decoded.body; payload->charset = decoded.charset;
        payload->sha256 = QCryptographicHash::hash(decoded.body, QCryptographicHash::Sha256);
        payload->token = QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
        // Native adapters intercept this exact document locally. This unique
        // neutral origin never borrows a remote server, script or file origin.
        // HTTP keeps ordinary HTTP media usable under mixed-content blocking.
        payload->transportURL = QUrl("http://" + payload->token + ".overte-inline.invalid/index.html");
        payload->transportURL.setFragment(QUrl(source).fragment());
        payload->revision = ++_revision;
        _lifetime = std::make_shared<detail::InlineDocumentLifetime>();
        const std::weak_ptr<detail::InlineDocumentLifetime> weakLifetime(_lifetime);
        _lifetime->revocation->lifetime = weakLifetime;
        context->installEventFilter(_lifetime->revocation.get());
        QObject::connect(context, &QObject::destroyed, _lifetime->revocation.get(), [weakLifetime] {
            if (const auto lifetime = weakLifetime.lock()) { lifetime->revoke(); }
        }, Qt::DirectConnection);
        document._payload = payload; document._lifetime = _lifetime;
        return document;
    }
private:
    QThread* _issuingThread { nullptr };
    std::shared_ptr<detail::InlineDocumentLifetime> _lifetime;
    std::uint64_t _revision { 0 };
};

} // namespace overte::web

Q_DECLARE_METATYPE(overte::web::InlineHtmlDocument)
