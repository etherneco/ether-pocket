#include "../src/files.h"
#include "../src/operations.h"
#include "../src/services.h"
#include <QDir>
#include <QFile>
#include <QPainter>
#include <QPdfWriter>
#include <QSettings>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QUuid>
#include <QtTest>
#include <archive.h>
#include <archive_entry.h>
#include <unistd.h>

class CoreTest : public QObject {
  Q_OBJECT
  static void write(const QString &p, const QByteArray &bytes) {
    QFile f(p);
    QVERIFY(f.open(QIODevice::WriteOnly));
    QCOMPARE(f.write(bytes), bytes.size());
  }
  static QByteArray read(const QString &p) {
    QFile f(p);
    f.open(QIODevice::ReadOnly);
    return f.readAll();
  }
  static QString state(Operations &o) {
    return o.jobs().last().toMap()["state"].toString();
  }
  static void wait(Operations &o) {
    QTRY_VERIFY_WITH_TIMEOUT(
        (!QStringList{"Running", "Queued"}.contains(state(o))), 10000);
  }
  static void archive(const QString &p, const QString &name,
                      const QByteArray &bytes, const QString &link = {}) {
    auto *a = archive_write_new();
    archive_write_set_format_pax_restricted(a);
    QCOMPARE(archive_write_open_filename(a, QFile::encodeName(p)), ARCHIVE_OK);
    auto *e = archive_entry_new();
    archive_entry_set_pathname(e, name.toUtf8());
    archive_entry_set_filetype(e, link.isEmpty() ? AE_IFREG : AE_IFLNK);
    archive_entry_set_perm(e, 0644);
    archive_entry_set_size(e, link.isEmpty() ? bytes.size() : 0);
    if (!link.isEmpty())
      archive_entry_set_symlink(e, link.toUtf8());
    QCOMPARE(archive_write_header(a, e), ARCHIVE_OK);
    if (link.isEmpty())
      archive_write_data(a, bytes.constData(), bytes.size());
    archive_entry_free(e);
    archive_write_close(a);
    archive_write_free(a);
  }
private slots:
  void initTestCase() {
    QCoreApplication::setOrganizationName("EtherFilesTests");
    QCoreApplication::setApplicationName("Isolated");
    QStandardPaths::setTestModeEnabled(true);
  }
  void trashAndRestore() {
    // /tmp can be a system tmpfs on which GIO correctly refuses Trash.
    // Exercise the normal home-filesystem Trash path with an isolated fixture.
    QTemporaryDir d(QDir::homePath() + "/.etherfiles-trash-test-XXXXXX");
    QVERIFY(d.isValid());
    const QString name = "etherfiles-test-" +
                         QUuid::createUuid().toString(QUuid::WithoutBraces) +
                         ".txt";
    const QString path = d.path() + "/" + name;
    write(path, "recoverable");
    Operations o;
    o.submit("trash", {fileUri(path)});
    wait(o);
    QCOMPARE(state(o), QString("Complete"));
    QVERIFY(!QFile::exists(path));
    DirectoryModel trash;
    trash.setLocation("trash:///");
    trash.setQuery(name);
    QTRY_VERIFY_WITH_TIMEOUT(!trash.busy() && trash.rowCount() == 1, 10000);
    const auto item = trash.get(0);
    QCOMPARE(item["original"].toString(), path);
    o.submit("restore", {item["uri"].toString()});
    wait(o);
    QCOMPARE(state(o), QString("Complete"));
    QCOMPARE(read(path), QByteArray("recoverable"));
  }
  void realDirectory() {
    QTemporaryDir d;
    write(d.path() + "/Zażółć-長い名前.txt", "hello");
    write(d.path() + "/.hidden", "secret");
    QDir().mkdir(d.path() + "/folder");
    QVERIFY(QFile::link("/missing/etherfiles-target", d.path() + "/broken"));
    DirectoryModel m;
    m.setLocation(d.path());
    QTRY_VERIFY(!m.busy());
    QCOMPARE(m.rowCount(), 3);
    QVERIFY(m.error().isEmpty());
    QCOMPARE(m.get(0)["name"].toString(), QString("folder"));
    m.setHidden(true);
    QTRY_VERIFY(!m.busy());
    QCOMPARE(m.rowCount(), 4);
    m.setQuery("長い");
    QTRY_COMPARE_WITH_TIMEOUT(m.rowCount(), 1, 5000);
    QVERIFY(m.get(0)["size"].toLongLong() == 5);
    auto info = fileMetadata(d.path() + "/broken");
    QVERIFY(info["symlink"].toBool());
    QVERIFY(!info["target"].toString().isEmpty());
  }
  void createRenameCopyMoveDelete() {
    QTemporaryDir d;
    Operations o;
    o.submit("mkdir", {}, d.path(), "source");
    wait(o);
    QCOMPARE(state(o), QString("Complete"));
    o.submit("touch", {}, d.path() + "/source", "hello.txt");
    wait(o);
    QVERIFY(QFile::exists(d.path() + "/source/hello.txt"));
    write(d.path() + "/source/hello.txt", "real content");
    o.submit("rename", {fileUri(d.path() + "/source/hello.txt")}, {},
             "renamed.txt");
    wait(o);
    QCOMPARE(read(d.path() + "/source/renamed.txt"),
             QByteArray("real content"));
    QDir().mkdir(d.path() + "/target");
    o.submit("copy", {fileUri(d.path() + "/source")}, d.path() + "/target");
    wait(o);
    QCOMPARE(state(o), QString("Complete"));
    QCOMPARE(read(d.path() + "/target/source/renamed.txt"),
             QByteArray("real content"));
    QDir().mkdir(d.path() + "/moved");
    o.submit("move", {fileUri(d.path() + "/target/source")},
             d.path() + "/moved");
    wait(o);
    QVERIFY(!QFile::exists(d.path() + "/target/source"));
    QCOMPARE(read(d.path() + "/moved/source/renamed.txt"),
             QByteArray("real content"));
    o.submit("delete", {fileUri(d.path() + "/moved/source")});
    wait(o);
    QVERIFY(!QFile::exists(d.path() + "/moved/source"));
  }
  void conflictsNeverOverwriteSilently() {
    QTemporaryDir d;
    QDir().mkdir(d.path() + "/a");
    QDir().mkdir(d.path() + "/b");
    write(d.path() + "/a/file", "incoming");
    write(d.path() + "/b/file", "original");
    Operations o;
    o.submit("copy", {fileUri(d.path() + "/a/file")}, d.path() + "/b");
    QTRY_VERIFY(!o.conflict().isEmpty());
    QCOMPARE(read(d.path() + "/b/file"), QByteArray("original"));
    o.resolve("skip", false);
    wait(o);
    QCOMPARE(read(d.path() + "/b/file"), QByteArray("original"));
    o.submit("copy", {fileUri(d.path() + "/a/file")}, d.path() + "/b");
    QTRY_VERIFY(!o.conflict().isEmpty());
    o.resolve("keep", false);
    wait(o);
    QCOMPARE(read(d.path() + "/b/file (copy 1)"), QByteArray("incoming"));
    o.submit("copy", {fileUri(d.path() + "/a/file")}, d.path() + "/b");
    QTRY_VERIFY(!o.conflict().isEmpty());
    o.resolve("replace", false);
    wait(o);
    QCOMPARE(read(d.path() + "/b/file"), QByteArray("incoming"));
  }
  void symlinksAreNotTraversed() {
    QTemporaryDir d;
    QDir().mkdir(d.path() + "/src");
    QDir().mkdir(d.path() + "/outside");
    QDir().mkdir(d.path() + "/dst");
    write(d.path() + "/outside/precious", "keep");
    QVERIFY(QFile::link(d.path() + "/outside", d.path() + "/src/link"));
    Operations o;
    o.submit("copy", {fileUri(d.path() + "/src")}, d.path() + "/dst");
    wait(o);
    QCOMPARE(state(o), QString("Complete"));
    QVERIFY(QFileInfo(d.path() + "/dst/src/link").isSymLink());
    o.submit("delete", {fileUri(d.path() + "/src")});
    wait(o);
    QCOMPARE(read(d.path() + "/outside/precious"), QByteArray("keep"));
    o.submit("symlink", {"outside/precious"}, d.path(), "created-link");
    wait(o);
    QCOMPARE(state(o), QString("Complete"));
    QVERIFY(QFileInfo(d.path() + "/created-link").isSymLink());
    QCOMPARE(read(d.path() + "/created-link"), QByteArray("keep"));
  }
  void invalidNamesAndSelfCopy() {
    QTemporaryDir d;
    Operations o;
    o.submit("touch", {}, d.path(), "../escape");
    wait(o);
    QCOMPARE(state(o), QString("Finished with errors"));
    QDir().mkdir(d.path() + "/a");
    o.submit("copy", {fileUri(d.path() + "/a")}, d.path() + "/a");
    wait(o);
    QCOMPARE(state(o), QString("Finished with errors"));
    QVERIFY(!QFile::exists(d.path() + "/a/a"));
    write(d.path() + "/exists", "preserve");
    o.submit("touch", {}, d.path(), "exists");
    wait(o);
    QCOMPARE(state(o), QString("Finished with errors"));
    QCOMPARE(read(d.path() + "/exists"), QByteArray("preserve"));
  }
  void cancelConflict() {
    QTemporaryDir d;
    QDir().mkdir(d.path() + "/a");
    QDir().mkdir(d.path() + "/b");
    write(d.path() + "/a/file", "one");
    write(d.path() + "/b/file", "two");
    Operations o;
    int id = o.submit("copy", {fileUri(d.path() + "/a/file")}, d.path() + "/b");
    QTRY_VERIFY(!o.conflict().isEmpty());
    o.cancel(id);
    wait(o);
    QCOMPARE(state(o), QString("Cancelled"));
    QCOMPARE(read(d.path() + "/b/file"), QByteArray("two"));
  }
  void archiveTraversalAndSymlinks() {
    QTemporaryDir d;
    Services s;
    archive(d.path() + "/bad.tar", "../escaped", "bad");
    s.extract(fileUri(d.path() + "/bad.tar"), fileUri(d.path()));
    QTRY_VERIFY_WITH_TIMEOUT(s.message() != "Working…", 10000);
    QVERIFY(s.message().contains("Unsafe"));
    QVERIFY(!QFile::exists(d.path() + "/escaped"));
    QVERIFY(!QFile::exists(d.path() + "/bad-extracted"));
    archive(d.path() + "/link.tar", "link", {}, "/tmp");
    s.extract(fileUri(d.path() + "/link.tar"), fileUri(d.path()));
    QTRY_VERIFY_WITH_TIMEOUT(s.message() != "Working…", 10000);
    QVERIFY(s.message().contains("Unsafe"));
    archive(d.path() + "/good.tar", "folder/file.txt", "safe");
    s.extract(fileUri(d.path() + "/good.tar"), fileUri(d.path()));
    QTRY_VERIFY_WITH_TIMEOUT(s.message() != "Working…", 10000);
    QCOMPARE(read(d.path() + "/good-extracted/folder/file.txt"),
             QByteArray("safe"));
  }
  void archiveCreateAndHash() {
    QTemporaryDir d;
    write(d.path() + "/data", "abc");
    Services s;
    s.hash(fileUri(d.path() + "/data"));
    QTRY_VERIFY(s.message() != "Working…");
    QVERIFY(s.message().endsWith(
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
    s.createArchive({fileUri(d.path() + "/data")}, fileUri(d.path()),
                    "data.zip");
    QTRY_VERIFY(s.message() != "Working…");
    QVERIFY(QFile::exists(d.path() + "/data.zip"));
    s.extract(fileUri(d.path() + "/data.zip"), fileUri(d.path()));
    QTRY_VERIFY(s.message() != "Working…");
    QCOMPARE(read(d.path() + "/data-extracted/data"), QByteArray("abc"));
  }
  void previewDoesNotExecute() {
    QTemporaryDir d;
    const QString marker = d.path() + "/executed";
    write(d.path() + "/script.sh", ("#!/bin/sh\ntouch " + marker).toUtf8());
    Services s;
    s.inspect(fileUri(d.path() + "/script.sh"));
    QTRY_VERIFY(!s.preview()["loading"].toBool());
    QVERIFY(s.preview()["text"].toString().contains("touch"));
    QVERIFY(!QFile::exists(marker));
    write(d.path() + "/binary.txt", QByteArray("a\0b", 3));
    s.inspect(fileUri(d.path() + "/binary.txt"));
    QTRY_VERIFY(!s.preview()["loading"].toBool());
    QVERIFY(!s.preview().contains("text"));
  }
  void deniedPermissions() {
    if (geteuid() == 0)
      QSKIP("Permission test requires unprivileged user");
    QTemporaryDir d;
    write(d.path() + "/locked", "original");
    QDir().mkdir(d.path() + "/target");
    QFile::setPermissions(d.path() + "/target",
                          QFile::ReadOwner | QFile::ExeOwner);
    Operations o;
    o.submit("copy", {fileUri(d.path() + "/locked")}, d.path() + "/target");
    wait(o);
    QCOMPARE(state(o), QString("Finished with errors"));
    QCOMPARE(read(d.path() + "/locked"), QByteArray("original"));
    QFile::setPermissions(d.path() + "/target", QFile::ReadOwner |
                                                    QFile::WriteOwner |
                                                    QFile::ExeOwner);
  }
  void resolvedContainmentAndFilters() {
    QTemporaryDir d;
    QDir().mkdir(d.path() + "/source");
    QVERIFY(QFile::link(d.path() + "/source", d.path() + "/alias"));
    Operations o;
    o.submit("copy", {fileUri(d.path() + "/source")},
             fileUri(d.path() + "/alias"));
    wait(o);
    QCOMPARE(state(o), QString("Finished with errors"));
    QVERIFY(!QFile::exists(d.path() + "/source/source"));
    write(d.path() + "/one.txt", "abc");
    write(d.path() + "/two.txt", "123456");
    write(d.path() + "/other.json", "{}");
    DirectoryModel m;
    m.setLocation(d.path());
    m.setFilters({{"extension", "txt"}, {"minimum", 4}});
    QTRY_VERIFY(!m.busy());
    QCOMPARE(m.rowCount(), 1);
    QCOMPARE(m.get(0)["name"].toString(), QString("two.txt"));
  }
  void largeAndObsoleteListings() {
    QTemporaryDir d;
    for (int i = 0; i < 2200; i++)
      write(d.path() + QString("/file-%1.txt").arg(i), "test");
    DirectoryModel m;
    m.setLocation(d.path());
    QTRY_VERIFY_WITH_TIMEOUT(!m.busy(), 10000);
    QCOMPARE(m.rowCount(), 2200);
    m.setQuery("file-2199");
    m.setQuery("file-2198");
    QTRY_COMPARE_WITH_TIMEOUT(m.rowCount(), 1, 5000);
    QCOMPARE(m.get(0)["name"].toString(), QString("file-2198.txt"));
  }
  void imageAndPdfPreviews() {
    QTemporaryDir d;
    QImage image(80, 60, QImage::Format_RGB32);
    image.fill(Qt::blue);
    QVERIFY(image.save(d.path() + "/image.png"));
    Services s;
    s.inspect(fileUri(d.path() + "/image.png"));
    QTRY_VERIFY(!s.preview()["loading"].toBool());
    QVERIFY(s.preview().contains("image"));
    QCOMPARE(s.preview()["dimensions"].toString(),
             QString::fromUtf8("80 × 60"));
    if (QStandardPaths::findExecutable("pdftoppm").isEmpty())
      QSKIP("Install poppler-utils for PDF rendering acceptance");
    {
      QPdfWriter pdf(d.path() + "/document.pdf");
      pdf.setTitle("EtherFiles preview test");
      QPainter painter(&pdf);
      painter.drawText(100, 100, "Untrusted content rendered as pixels");
    }
    s.inspect(fileUri(d.path() + "/document.pdf"));
    QTRY_VERIFY_WITH_TIMEOUT(!s.preview()["loading"].toBool(), 15000);
    QVERIFY(s.preview()["text"].toString().contains("Pages:"));
    QVERIFY(QFileInfo::exists(s.preview()["thumbnailPath"].toString()));
  }
};
QTEST_MAIN(CoreTest)
#include "core_test.moc"
