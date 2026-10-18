// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#include <InlineHtmlDocument.h>
#include <QQuickItem>
#include <QVariant>
#include <QVector>

// Created only by the native tablet navigation caller for one immutable source
// request. QML may attach this existing request to its actual page; it cannot
// supply different HTML, script, identity, context or a replacement native root.
class NativeInlineHtmlSource final : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString sourceIdentity READ sourceIdentity CONSTANT)
    Q_PROPERTY(QVariant document READ document NOTIFY documentChanged)
public:
    NativeInlineHtmlSource(QQuickItem* nativeRoot, const QString& tabletName,
                           const QString& originalSource, const QString& sourceScriptURL,
                           QObject* parent = nullptr);
    QString sourceIdentity() const { return _identity; }
    QVariant document() const {
        return _document.current() ? QVariant::fromValue(_document) : QVariant();
    }
    Q_INVOKABLE bool bind(QObject* page);
    Q_INVOKABLE void suspend();
    Q_INVOKABLE void retire();
signals:
    void documentChanged();
private:
    bool contains(QQuickItem* page) const;
    void clearBinding();
    QPointer<QQuickItem> _root, _page;
    const QString _identity, _source, _script;
    bool _retired { false };
    overte::web::InlineHtmlDocumentOwner _owner;
    overte::web::InlineHtmlDocument _document;
    QVector<QMetaObject::Connection> _pageConnections;
};
