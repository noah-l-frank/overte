// SPDX-License-Identifier: Apache-2.0
// Actual production format methods; only the stored preference is a fixture.
#include <QBuffer>
#include <QCoreApplication>
#include <QDebug>
#include <QImage>
#include <QImageReader>
#include <QImageWriter>
#include <QStringList>
#include <stdexcept>

class Snapshot {
public:
    struct Preference {
        QString value;
        QString get() const { return value; }
        void set(const QString& next) { value = next; }
    } _snapshotFormat;
    QString getSnapshotFormat();
    void setSnapshotFormat(const QString&);
    QStringList getAvailableSnapshotFormats();
    QStringList getAvailableSnapshotFormatsWithDescriptions();
};
#include "production-formats.inc"

static void require(bool value, const char* message) {
    if (!value) { throw std::runtime_error(message); }
}

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const bool isolated = app.arguments().contains("--no-plugins");
    if (isolated) { QCoreApplication::setLibraryPaths({}); }
    Snapshot snapshot;
    const auto available = snapshot.getAvailableSnapshotFormats();
    const auto descriptions = snapshot.getAvailableSnapshotFormatsWithDescriptions();
    const auto writers = QImageWriter::supportedImageFormats();
    require(available.contains("png"), "Core PNG capture must remain available");
    require(available.size() == descriptions.size(), "Format labels must match the actual encoder list");
    for (const auto& format : {QString("png"), QString("jpg"), QString("webp")}) {
        require(available.contains(format) == writers.contains(format.toLatin1()),
                "Snapshot advertises a missing encoder or loses an installed one");
    }
    for (int i = 0; i < available.size(); ++i) {
        const auto format = available[i];
        require(descriptions[i].startsWith(format.toUpper()), "Format descriptions must retain order");
        QImage source(16,16,QImage::Format_RGB32); source.fill(QColor(190,40,70));
        QByteArray encoded;
        QBuffer output(&encoded); require(output.open(QIODevice::WriteOnly), "Open image output");
        QImageWriter writer(&output, format.toLatin1());
        require(writer.write(source) && !encoded.isEmpty(), "Every offered format must encode real pixels");
        QBuffer input(&encoded); require(input.open(QIODevice::ReadOnly), "Open image input");
        QImageReader reader(&input, format.toLatin1());
        const auto decoded = reader.read();
        require(decoded.size() == source.size(), "Encoded format must decode a complete image");
        const auto color = decoded.pixelColor(0,0);
        require(qAbs(color.red()-190)<15 && qAbs(color.green()-40)<15 && qAbs(color.blue()-70)<15,
                "Encoded format must retain source pixels within lossy-codec tolerance");
        snapshot.setSnapshotFormat(format);
        require(snapshot.getSnapshotFormat() == format, "Supported preference must be retained");
    }
    snapshot._snapshotFormat.value = "obsolete-codec";
    require(snapshot.getSnapshotFormat() == available.first(), "A stale preference must fall back to an encoder");
    require(snapshot._snapshotFormat.value == "obsolete-codec", "Runtime fallback must not erase user preferences");
    snapshot.setSnapshotFormat("unsupported-codec");
    require(snapshot._snapshotFormat.value == "obsolete-codec", "Reject unavailable format changes");
    qInfo() << "Snapshot actual encoder/preference contract PASS; isolated plugins:" << isolated
            << "formats:" << available;
}
