// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <InlineHtmlDocument.h>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQmlContext>
#include <QQmlEngine>
#include <QVariant>

namespace overte::ios {

// A descriptor is only usable by a real descendant of its issuing QML context.
// No QObject parent, context-property string, map or URL issues authority.
class IOSInlineDocumentBinding {
public:
    bool bind(const QVariant& carrier, QObject* consumer, const QString& identity,
              const QString& originalSource, const QString& originalScript) {
        clear();
        if (carrier.userType() != qMetaTypeId<web::InlineHtmlDocument>()) { return false; }
        const auto document = carrier.value<web::InlineHtmlDocument>();
        if (document.scriptURL() != originalScript) { return false; }
        for (auto* context = qmlContext(consumer); context; context = context->parentContext()) {
            if (document.currentFor(context, identity, originalSource)) {
                _document = document;
                _context = context;
                _identity = identity; _source = originalSource; _script = originalScript;
                return true;
            }
        }
        return false;
    }
    bool current(const QObject* consumer) const {
        if (!_context || !_document.currentFor(_context, _identity, _source) ||
                _document.scriptURL() != _script) { return false; }
        for (auto* context = qmlContext(consumer); context; context = context->parentContext()) {
            if (context == _context) { return true; }
        }
        return false;
    }
    void clear() { _document = {}; _context.clear(); _identity.clear(); _source.clear(); _script.clear(); }
    const web::InlineHtmlDocument& document() const { return _document; }
    const QQmlContext* context() const { return _context.data(); }
private:
    web::InlineHtmlDocument _document;
    QPointer<QQmlContext> _context;
    QString _identity, _source, _script;
};

// One expected native simulated request. This is not source authority: callers
// still require the current document/session/frame checks before using it.
class IOSInlineNavigation {
public:
    void issued(std::uint64_t generation, const QUrl& url, const QString& token) {
        _generation = generation; _url = url; _token = token;
    }
    bool consume(std::uint64_t generation, const QUrl& url, const QString& token) {
        const bool matches = generation && generation == _generation && url == _url &&
            !token.isEmpty() && token == _token;
        clear();
        return matches;
    }
    void clear() { _generation = 0; _url = QUrl(); _token.clear(); }
private:
    std::uint64_t _generation { 0 };
    QUrl _url;
    QString _token;
};

// WebKit evaluates its own compiled rule, for every resource type. This is not
// an HTTP URLSchemeHandler or a process-global networking interception. The
// source-owned simulated main response has no network connection to exempt.
inline QString iosInlineNamespacePattern() {
    return QStringLiteral(R"RULE(^[a-z][a-z0-9+.-]*://([^/?#]*@)?([^/?#]*\.)?overte-inline\.invalid\.*([:/?#].*)?$)RULE");
}
inline QString iosInlineNamespaceRules() {
    return QString::fromUtf8(QJsonDocument(QJsonArray {
        QJsonObject {
            { QStringLiteral("trigger"), QJsonObject {
                { QStringLiteral("url-filter"), iosInlineNamespacePattern() },
                { QStringLiteral("url-filter-is-case-sensitive"), false }
            } },
            { QStringLiteral("action"), QJsonObject { { QStringLiteral("type"), QStringLiteral("block") } } }
        }
    }).toJson(QJsonDocument::Compact));
}
} // namespace overte::ios
