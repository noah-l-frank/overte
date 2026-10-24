// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#include "IOSSnapshotFiles.h"
#include <QCoreApplication>
#include <QJsonDocument>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    QCoreApplication application(argc, argv);
    if (argc != 2) { return 2; }
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.size() > 4096) { return 3; }
        const auto command = QJsonDocument::fromJson(QByteArray::fromStdString(line)).object();
        const auto result = overte::ios::readSnapshotFiles(command, QString::fromLocal8Bit(argv[1]));
        std::cout << QJsonDocument(result).toJson(QJsonDocument::Compact).constData() << std::endl;
    }
}
