// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <EmbeddedWebPolicy.h>
#include <QDir>
#include <QUrl>
#include <QFile>
#include <QMimeDatabase>
#include <atomic>
#include <memory>
#include <mutex>

namespace overte::android::web {
// Root is supplied once by native product startup, never by QML/page messages.
class NativeResourceMapping {
public:
    NativeResourceMapping(QString root = {}, qint64 handle = 0) : _handle(handle) {
        _root = root.startsWith("qrc:/") ? QStringLiteral("qrc:") + QDir::cleanPath(QUrl(root).path()) : QFileInfo(root).canonicalFilePath();
    }
    const QString& root() const { return _root; }
    bool accepts(const QUrl& source) const { return overte::web::EmbeddedWebSession::isPackagedURL(source, _root); }
    QUrl canonicalSource(const QUrl& source) const {
        if (!accepts(source)) return source;
        QUrl canonical = source.scheme() == "qrc" ? QUrl("qrc:" + QDir::cleanPath(source.path())) : QUrl::fromLocalFile(QFileInfo(source.toLocalFile()).canonicalFilePath());
        canonical.setQuery(source.query()); canonical.setFragment(source.fragment()); return canonical;
    }
    QUrl toBrowser(const QUrl& source) const {
        if (!accepts(source)) return source;
        const QString prefix = _root.startsWith("qrc:/") ? QUrl(_root).path() : QDir(_root).canonicalPath();
        const QString relative = canonicalSource(source).path(QUrl::FullyDecoded).mid(prefix.size() + 1);
        QUrl result;
        result.setScheme("https"); result.setHost("overte-embedded.invalid");
        result.setPath('/' + QString::number(_handle) + '/' + relative);
        result.setQuery(source.query()); result.setFragment(source.fragment());
        return result;
    }
    QUrl toSource(const QUrl& browser) const {
        if (browser.host() != "overte-embedded.invalid") return browser;
        if (browser.scheme() != "https" || browser.port(443) != 443 || !browser.userInfo().isEmpty()) return {};
        const QString path = browser.path(QUrl::FullyDecoded), prefix = '/' + QString::number(_handle) + '/';
        if (!path.startsWith(prefix)) return {};
        const QString relative = path.mid(prefix.size());
        if (relative.isEmpty() || relative.split('/').contains("..") || relative.contains('\\')) return {};
        QUrl source = _root.startsWith("qrc:/") ? QUrl(_root + '/' + relative) : QUrl::fromLocalFile(_root + '/' + relative);
        source.setQuery(browser.query()); source.setFragment(browser.fragment());
        return accepts(source) ? canonicalSource(source) : QUrl();
    }
private:
    QString _root;
    qint64 _handle;
};
}


namespace overte::android::web {
// All fields are copied on the Qt owner thread. No QObject/context is retained.
struct NativeResourceSource {
    quint64 grant { 0 }, creation { 0 }, revision { 0 };
    NativeResourceMapping mapping;
    QUrl inlineURL;
    QByteArray bytes;
    QString charset;
    std::shared_ptr<std::atomic<bool>> valid { std::make_shared<std::atomic<bool>>(true) };
};
struct NativeResourceResponse {
    enum Action { Denied, Local, Network };
    Action action { Denied };
    QByteArray bytes;
    QString mime { "text/plain" }, charset { "UTF-8" };
};
// Native-issued load leases bind the actual creation/source/page before loadUrl.
// This object is independently retained by interception; destroying the Item only
// revokes its atomic source flag. Interception never reads the Item or its QML context.
class NativeResourceState {
public:
    explicit NativeResourceState(NativeResourceSource source) : _source(std::move(source)) { }
    void revoke() const { _source.valid->store(false, std::memory_order_release); }
    bool active() const { return _source.valid->load(std::memory_order_acquire); }
    quint64 begin(quint64 creation, quint64 grant, quint64 page, const QUrl& document) {
        std::lock_guard<std::mutex> guard(_mutex);
        if (!active() || creation != _source.creation || grant != _source.grant || !page
                || page < _highestPage || !navigation(document, true, "GET") || _load == quint64(std::numeric_limits<qint64>::max())) return 0;
        ++_load; _page = _highestPage = page; _bound = false; _document = document; return _load;
    }
    bool bind(quint64 creation, quint64 grant, quint64 load, quint64 pendingPage, quint64 actualPage, const QUrl& document) {
        std::lock_guard<std::mutex> guard(_mutex);
        if (!matches(creation, grant, load, pendingPage) || _bound || actualPage <= _highestPage
                || document.adjusted(QUrl::RemoveFragment) != _document.adjusted(QUrl::RemoveFragment)) return false;
        _bound = true; _highestPage = actualPage; return true;
    }
    bool current(quint64 creation, quint64 grant, quint64 load, quint64 page) const {
        std::lock_guard<std::mutex> guard(_mutex);
        return matches(creation, grant, load, page);
    }
    NativeResourceResponse response(quint64 creation, quint64 grant, quint64 load, quint64 page,
                                    const QUrl& url, bool mainFrame, const QString& method) const {
        {
            std::lock_guard<std::mutex> guard(_mutex);
            if (!matches(creation, grant, load, page)) return {};
            if (reservedInline(url) && url.adjusted(QUrl::RemoveFragment) != _document.adjusted(QUrl::RemoveFragment)) return {};
        }
        NativeResourceResponse result;
        const auto verb = method.toUpper();
        if (reservedInline(url)) {
            if (_source.inlineURL.isEmpty() || _source.bytes.size() > 1024 * 1024 || !mainFrame || (verb != "GET" && verb != "HEAD")
                    || url.adjusted(QUrl::RemoveFragment) != _source.inlineURL.adjusted(QUrl::RemoveFragment)) return {};
            result.action = NativeResourceResponse::Local; result.mime = "text/html";
            result.charset = _source.charset;
            if (verb != "HEAD") result.bytes = _source.bytes;
        } else if (url.host().compare("overte-embedded.invalid", Qt::CaseInsensitive) == 0) {
            if (verb != "GET" && verb != "HEAD") return {};
            const auto local = _source.mapping.toSource(url);
            if (!_source.mapping.accepts(local)) return {};
            QFile file(local.scheme() == "qrc" ? ':' + local.path() : local.toLocalFile());
            if (!file.open(QFile::ReadOnly) || file.size() > 8 * 1024 * 1024) return {};
            result.action = NativeResourceResponse::Local;
            result.mime = QMimeDatabase().mimeTypeForFile(local.path(), QMimeDatabase::MatchExtension).name();
            if (verb != "HEAD") result.bytes = file.read(8 * 1024 * 1024 + 1);
            if (result.bytes.size() > 8 * 1024 * 1024 || file.error() != QFile::NoError) return {};
        } else if (navigation(url, mainFrame, verb)) result.action = NativeResourceResponse::Network;
        if (!current(creation, grant, load, page)) return {};
        return result;
    }
    static bool reservedInline(const QUrl& url) {
        auto host = url.host().toLower();
        while (host.endsWith('.')) host.chop(1);
        return host == "overte-inline.invalid" || host.endsWith(".overte-inline.invalid");
    }
private:
    bool matches(quint64 creation, quint64 grant, quint64 load, quint64 page) const {
        return active() && creation && creation == _source.creation && grant && grant == _source.grant
            && load && load == _load && page && page == _page;
    }
    bool navigation(const QUrl& url, bool mainFrame, const QString& method) const {
        const auto verb = method.toUpper();
        if (reservedInline(url)) return !_source.inlineURL.isEmpty() && mainFrame && (verb == "GET" || verb == "HEAD")
            && url.adjusted(QUrl::RemoveFragment) == _source.inlineURL.adjusted(QUrl::RemoveFragment);
        if (url.host().compare("overte-embedded.invalid", Qt::CaseInsensitive) == 0)
            return _source.mapping.accepts(_source.mapping.toSource(url)) && (verb == "GET" || verb == "HEAD");
        return overte::web::EmbeddedWebSession::isNetworkURL(url)
            && (verb == "GET" || verb == "HEAD" || verb == "POST" || verb == "PUT" || verb == "PATCH"
                || verb == "DELETE" || verb == "OPTIONS");
    }
    const NativeResourceSource _source;
    mutable std::mutex _mutex;
    quint64 _load { 0 }, _page { 0 }, _highestPage { 0 };
    bool _bound { false };
    QUrl _document;
};
}
