#include "../src/files.h"
#include "../src/operations.h"
#include "../src/services.h"
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>
#include <QUrl>
#include <QUuid>
#include <functional>
#include <stdexcept>
#include <unistd.h>

namespace {
void require(bool condition, const QString &why) {
  if (!condition)
    throw std::runtime_error(why.toStdString());
}
void until(const std::function<bool()> &predicate, int timeout = 35000) {
  QElapsedTimer t;
  t.start();
  while (!predicate()) {
    require(t.elapsed() < timeout,
            "Timed out waiting for integration operation");
    QTest::qWait(20);
  }
}
QString child(QString uri, const QString &name) {
  if (!uri.endsWith('/'))
    uri += '/';
  return uri + QString::fromUtf8(QUrl::toPercentEncoding(name));
}
QVariantList list(const QString &uri, bool recursive = false,
                  const QString &query = {}) {
  DirectoryModel m;
  m.setLocation(uri);
  m.setRecursive(recursive);
  m.setQuery(query);
  m.refresh();
  until([&] { return !m.busy(); });
  require(m.error().isEmpty(), "Directory enumeration: " + m.error());
  QVariantList result;
  for (int i = 0; i < m.rowCount(); i++)
    result.append(m.get(i));
  return result;
}
QVariantMap operation(Operations &o, const QString &action,
                      const QStringList &sources, const QString &dest = {},
                      const QString &name = {}) {
  int id = o.submit(action, sources, dest, name);
  require(id >= 0, "Operation queue rejected submission");
  until([&] {
    for (auto v : o.jobs()) {
      auto j = v.toMap();
      if (j["id"].toInt() == id)
        return j["state"] != "Queued" && j["state"] != "Running";
    }
    return false;
  });
  for (auto v : o.jobs()) {
    auto j = v.toMap();
    if (j["id"].toInt() == id) {
      require(j["errors"].toStringList().isEmpty(),
              j["errors"].toStringList().join("\n"));
      return j;
    }
  }
  return {};
}
QByteArray read(const QString &path) {
  QFile f(path);
  require(f.open(QIODevice::ReadOnly), f.errorString());
  return f.readAll();
}
bool mount(Services &s, const QVariantMap &target, const QString &password,
           QString &error) {
  bool done = false, ok = false;
  auto a = QObject::connect(&s, &Services::networkReady, &s,
                            [&](const QString &) { ok = true; });
  auto b = QObject::connect(&s, &Services::messageChanged, &s, [&] {
    if (s.message() != "Working…") {
      error = s.message();
      done = true;
    }
  });
  s.connectNetwork(target["uri"].toString(), target["user"].toString(),
                   password);
  until([&] { return done; }, 65000);
  QObject::disconnect(a);
  QObject::disconnect(b);
  return ok;
}
} // namespace
int main(int argc, char **argv) {
  if (geteuid() == 0) {
    fprintf(stderr,
            "Run integration tests as an isolated unprivileged user.\n");
    return 2;
  }
  QGuiApplication app(argc, argv);
  app.setOrganizationName("EtherFilesNetworkTests");
  app.setApplicationName("Isolated");
  if (argc != 3) {
    fprintf(
        stderr,
        "Usage: etherfiles-network-tests PRIVATE_FIXTURE_JSON RESULT_JSON\n");
    return 2;
  }
  QFile config(QString::fromLocal8Bit(argv[1]));
  if (!config.open(QIODevice::ReadOnly))
    return 2;
  const auto fixture =
      QJsonDocument::fromJson(config.readAll()).toVariant().toMap();
  config.close();
  QVariantMap report;
  int failures = 0;
  for (const auto &v : fixture["reject"].toList()) {
    const auto target = v.toMap();
    QVariantMap result;
    Services services;
    QString error;
    try {
      require(!mount(services, target, target["password"].toString(), error),
              "Unsafe connection unexpectedly succeeded");
      require(error.contains("Identity", Qt::CaseInsensitive) ||
                  error.contains("certificate", Qt::CaseInsensitive) ||
                  error.contains("TLS", Qt::CaseInsensitive) ||
                  error.contains("key", Qt::CaseInsensitive),
              "Connection failed without reaching identity verification: " +
                  error);
      result = {{"passed", true}, {"error", error}};
    } catch (const std::exception &e) {
      result = {{"passed", false}, {"error", QString::fromUtf8(e.what())}};
      ++failures;
    }
    report[target["name"].toString()] = result;
    fprintf(stdout, "%s: %s\n", qPrintable(target["name"].toString()),
            result["passed"].toBool() ? "PASS" : "FAIL");
    fflush(stdout);
  }
  for (const auto &v : fixture["targets"].toList()) {
    const auto target = v.toMap();
    QVariantMap result;
    Services services;
    Operations operations;
    QString remoteScratch;
    QString decision = "skip";
    QObject::connect(&operations, &Operations::conflictChanged, &operations,
                     [&] {
                       if (!operations.conflict().isEmpty())
                         operations.resolve(decision, false);
                     });
    try {
      QString error;
      require(!mount(services, target, "invalid-fixture-password", error),
              "Wrong-password authentication unexpectedly succeeded");
      result["bad_password_rejected"] = true;
      require(mount(services, target, target["password"].toString(), error),
              "Authentication/mount: " + error);
      result["authenticated_mount"] = true;
      QString uri = target["uri"].toString();
      if (!target["user"].toString().isEmpty()) {
        QUrl u(uri);
        u.setUserName(target["user"].toString());
        uri = u.toString(QUrl::FullyEncoded);
      }
      const auto entries = list(uri);
      require(!entries.isEmpty(), "Server directory was empty");
      require(fileMetadata(child(uri, "server.txt"))["size"].toLongLong() > 0,
              "Server sentinel metadata unavailable");
      result["real_listing_metadata"] = true;
      QTemporaryDir local;
      require(local.isValid(), "Local fixture directory failed");
      operation(operations, "copy", {child(uri, "server.txt")},
                fileUri(local.path()));
      require(read(local.path() + "/server.txt") ==
                  fixture["sentinel"].toByteArray(),
              "Download content mismatch");
      result["download_verified"] = true;
      const QString scratchName =
          "etherfiles-test-" +
          QUuid::createUuid().toString(QUuid::WithoutBraces);
      remoteScratch = child(uri, scratchName);
      operation(operations, "mkdir", {}, uri, scratchName);
      QByteArray original(65536, 'x');
      original.replace(0, 8, "original");
      const QString filename = QString::fromUtf8("Zażółć-長い.txt");
      QFile upload(local.path() + "/" + filename);
      require(upload.open(QIODevice::WriteOnly), upload.errorString());
      require(upload.write(original) == original.size(),
              "Local fixture write failed");
      upload.close();
      operation(operations, "copy", {fileUri(upload.fileName())},
                remoteScratch);
      result["unicode_upload"] = true;
      QDir().mkdir(local.path() + "/download");
      operation(operations, "copy", {child(remoteScratch, filename)},
                fileUri(local.path() + "/download"));
      require(read(local.path() + "/download/" + filename) == original,
              "Round-trip content mismatch");
      result["round_trip_bytes_verified"] = true;
      require(upload.open(QIODevice::WriteOnly | QIODevice::Truncate),
              upload.errorString());
      upload.write("replacement");
      upload.close();
      operation(operations, "copy", {fileUri(upload.fileName())},
                remoteScratch);
      QFile::remove(local.path() + "/download/" + filename);
      operation(operations, "copy", {child(remoteScratch, filename)},
                fileUri(local.path() + "/download"));
      require(read(local.path() + "/download/" + filename) == original,
              "Skip overwrote existing destination");
      result["conflict_skip_preserves_bytes"] = true;
      decision = "replace";
      operation(operations, "copy", {fileUri(upload.fileName())},
                remoteScratch);
      QFile::remove(local.path() + "/download/" + filename);
      operation(operations, "copy", {child(remoteScratch, filename)},
                fileUri(local.path() + "/download"));
      require(read(local.path() + "/download/" + filename) == "replacement",
              "Explicit replace did not commit");
      result["explicit_replace_verified"] = true;
      operation(operations, "rename", {child(remoteScratch, filename)}, {},
                "renamed.txt");
      operation(operations, "mkdir", {}, remoteScratch, "subfolder");
      operation(operations, "move", {child(remoteScratch, "renamed.txt")},
                child(remoteScratch, "subfolder"));
      require(fileMetadata(child(child(remoteScratch, "subfolder"),
                                 "renamed.txt"))["size"]
                      .toLongLong() == 11,
              "Remote rename/move did not preserve bytes");
      result["rename_move"] = true;
      require(list(remoteScratch, true, "renamed.txt").size() == 1,
              "Recursive search did not find moved remote file");
      result["recursive_search"] = true;
      operation(operations, "delete", {remoteScratch});
      remoteScratch.clear();
      result["explicit_fixture_delete"] = true;
      bool secret = false;
      for (const auto &dir :
           {QStandardPaths::writableLocation(QStandardPaths::AppConfigLocation),
            QStandardPaths::writableLocation(
                QStandardPaths::AppLocalDataLocation)}) {
        for (auto f : QDir(dir).entryInfoList(QDir::Files))
          if (read(f.absoluteFilePath())
                  .contains(target["password"].toByteArray()))
            secret = true;
      }
      require(!secret, "Fixture password found in application state");
      result["no_password_in_app_state"] = true;
      result["passed"] = true;
    } catch (const std::exception &e) {
      result["passed"] = false;
      result["error"] = QString::fromUtf8(e.what());
      ++failures;
      if (!remoteScratch.isEmpty()) {
        try {
          operation(operations, "delete", {remoteScratch});
        } catch (...) {
        }
      }
    }
    report[target["name"].toString()] = result;
    fprintf(stdout, "%s: %s %s\n", qPrintable(target["name"].toString()),
            result["passed"].toBool() ? "PASS" : "FAIL",
            qPrintable(result["error"].toString()));
    fflush(stdout);
  }
  QFile output(QString::fromLocal8Bit(argv[2]));
  if (!output.open(QIODevice::WriteOnly))
    return 2;
  output.write(QJsonDocument::fromVariant(report).toJson());
  return failures ? 1 : 0;
}
