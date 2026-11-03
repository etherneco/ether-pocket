#pragma once
#include <QDir>
#include <QFile>

namespace KeyboardInput {
// Linux exposes native-word bitmaps, most significant word first. Parse using
// the kernel's word size, which may differ from the application's word size.
inline bool typingKeys(const QString &bitmap, int wordBits) {
    const auto words=bitmap.simplified().split(' ',Qt::SkipEmptyParts);
    for(int code:{28,30,44,57}) { // Enter, A, Z, Space; excludes buttons/remotes.
        const int index=words.size()-1-code/wordBits;
        if(index<0)return false;
        bool ok=false;const auto word=words[index].toULongLong(&ok,16);
        if(!ok||!(word&(quint64(1)<<(code%wordBits))))return false;
    }
    return true;
}
inline bool connected(const QString &inputRoot="/sys/class/input",int wordBits=sizeof(unsigned long)*8) {
    const QDir inputs(inputRoot);
    for(const auto &event:inputs.entryList({"event*"},QDir::Dirs|QDir::System|QDir::NoDotAndDotDot)) {
        QFile keys(inputs.filePath(event+"/device/capabilities/key"));
        if(keys.open(QIODevice::ReadOnly)&&typingKeys(QString::fromLatin1(keys.readAll()),wordBits))return true;
    }
    return false;
}
}
