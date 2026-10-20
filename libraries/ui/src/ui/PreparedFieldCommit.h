// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QObject>
#include <QString>
#include <QElapsedTimer>
#include <QPointer>
#include <QVariantMap>
#include <QVector>
#include <memory>

class QInputMethodEvent;
class QQmlContext;
class QQuickItem;
class QQuickWindow;
class QTimer;

namespace overte::ui {

// Test-only ownership of one actual, not yet dispatched native IME event.
// This is not a UI locator, a process binding or a complete lifecycle adapter.
// The owning native UI bridge must select one actual current source/control,
// bind its original token and preserve durable intent before calling this API.
class PreparedFieldCommit final : public QObject {
public:
    ~PreparedFieldCommit() override;
    QVariantMap observation(const QString& requestId);
    // currentField/currentSurface must come from a fresh original native UI
    // walk, never from command arguments or the retained old field itself.
    // True means an actual attempt was processed, including native rejection.
    // It does not mean text editing or any product feature succeeded.
    bool dispatch(QQuickItem* currentField, QQuickWindow* currentSurface);
    bool release();

private:
    friend std::unique_ptr<PreparedFieldCommit> prepareFocusedScriptFilterCommit(
        QQuickItem*, QQuickWindow*, const QString&);
    PreparedFieldCommit(QQuickItem*, QQuickWindow*, QQmlContext*, const QString&,
        int, int, std::unique_ptr<QInputMethodEvent>);
    bool onNativeThread() const;
    void expire();
    void finish(const QString& kind, const QString& reason);
    void record(const QString& kind, const QString& reason);
    qint64 epoch();

    QPointer<QQuickItem> _field;
    QPointer<QQuickWindow> _surface;
    QPointer<QQmlContext> _context;
    QVector<QPointer<QQuickItem>> _ancestors;
    std::unique_ptr<QInputMethodEvent> _commit;
    QElapsedTimer _clock;
    QTimer* _timer;
    QString _instance, _eventId, _sourceUrl, _initialSha, _inputSha;
    int _inputUnits, _cursor, _anchor;
    qint64 _createdEpoch {0}, _lastEpoch {0};
    quint64 _sequence {0};
    QVariantList _events;
    bool _valid {true}, _dispatching {false};
};

// Only the actual Running Scripts filter and closed owned lifecycle fixture
// text qualify. This never intercepts ordinary production input. It uses the
// existing native Select All route and retains a real QInputMethodEvent.
std::unique_ptr<PreparedFieldCommit> prepareFocusedScriptFilterCommit(
    QQuickItem* field, QQuickWindow* surface, const QString& text);

} // namespace overte::ui
#endif
