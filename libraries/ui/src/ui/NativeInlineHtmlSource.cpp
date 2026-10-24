// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "NativeInlineHtmlSource.h"

#include <QQmlContext>
#include <QQmlEngine>
#include <QThread>

NativeInlineHtmlSource::NativeInlineHtmlSource(QQuickItem* nativeRoot, const QString& tabletName,
        const QString& originalSource, const QString& sourceScriptURL, QObject* parent) :
    QObject(parent), _root(nativeRoot),
    _identity("tablet:" + tabletName + ":" + QUuid::createUuid().toString(QUuid::WithoutBraces)),
    _source(originalSource), _script(sourceScriptURL) {
    if (_root) { connect(_root, &QObject::destroyed, this, &NativeInlineHtmlSource::retire); }
}

bool NativeInlineHtmlSource::contains(QQuickItem* page) const {
    if (!page || !_root || page == _root) { return false; }
    for (auto* ancestor = page->parentItem(); ancestor; ancestor = ancestor->parentItem()) {
        if (ancestor == _root) { return true; }
    }
    return false;
}

void NativeInlineHtmlSource::clearBinding() {
    _owner.revoke();
    _document = {};
    _page.clear();
    for (const auto& connection : _pageConnections) { disconnect(connection); }
    _pageConnections.clear();
    emit documentChanged();
}

bool NativeInlineHtmlSource::bind(QObject* page) {
    auto* item = qobject_cast<QQuickItem*>(page);
    if (_retired || QThread::currentThread() != thread()) { return false; }
    if (!contains(item) || item->thread() != thread()) { clearBinding(); return false; }
    auto* context = qmlContext(item);
    const auto* rootContext = qmlContext(_root);
    bool withinNativeContext = false;
    for (auto* ancestor = context; ancestor; ancestor = ancestor->parentContext()) {
        if (ancestor == rootContext) { withinNativeContext = true; break; }
    }
    if (!context || !rootContext || !context->isValid() || !rootContext->isValid() || !withinNativeContext) { clearBinding(); return false; }
    if (_page == item && _document.currentFor(context, _identity, _source)) { return true; }
    clearBinding();
    _document = _owner.issue(context, _identity, _source, _script);
    if (!_document.current()) { return false; }
    _page = item;
    _pageConnections.push_back(connect(item, &QObject::destroyed, this, &NativeInlineHtmlSource::clearBinding));
    _pageConnections.push_back(connect(item, &QQuickItem::visibleChanged, this, [this] {
        if (_page && !_page->isVisible()) { clearBinding(); }
    }));
    for (auto* ancestor = context; ancestor; ancestor = ancestor->parentContext()) {
        _pageConnections.push_back(connect(ancestor, &QObject::destroyed, this, &NativeInlineHtmlSource::clearBinding));
    }
    // A visual container can be moved while the page itself keeps its parent.
    // Observe each real ancestor so a detached branch loses the old root grant.
    for (auto* ancestor = item; ancestor && ancestor != _root; ancestor = ancestor->parentItem()) {
        _pageConnections.push_back(connect(ancestor, &QQuickItem::parentChanged, this, [this] {
            if (!contains(_page)) { clearBinding(); }
        }));
    }
    emit documentChanged();
    return true;
}

void NativeInlineHtmlSource::suspend() {
    if (QThread::currentThread() == thread()) { clearBinding(); }
}

void NativeInlineHtmlSource::retire() {
    if (_retired) { return; }
    _retired = true;
    clearBinding();
    deleteLater();
}
