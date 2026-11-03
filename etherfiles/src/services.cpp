#include "services.h"
#include "files.h"
#include <QClipboard>
#include <QCryptographicHash>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDesktopServices>
#include <QDir>
#include <QDirIterator>
#include <QElapsedTimer>
#include <QFile>
#include <QFileInfo>
#include <QGuiApplication>
#include <QImageReader>
#include <QMimeData>
#include <QMimeDatabase>
#include <QProcess>
#include <QRunnable>
#include <QSettings>
#include <QStandardPaths>
#include <QStorageInfo>
#include <QTemporaryDir>
#include <QUrl>
#include <archive.h>
#include <archive_entry.h>
#include <sys/resource.h>
#include <sys/stat.h>
#undef signals
#include <gio/gio.h>

static bool previewProcess(QProcess &process, const QString &program,
                           const QStringList &arguments, std::atomic_bool &stop,
                           int timeout = 6000) {
  process.setChildProcessModifier([] {
    struct rlimit memory{512ULL * 1024 * 1024, 512ULL * 1024 * 1024};
    setrlimit(RLIMIT_AS, &memory);
    struct rlimit cpu{10, 10};
    setrlimit(RLIMIT_CPU, &cpu);
  });
  process.start(program, arguments);
  if (!process.waitForStarted(1000))
    return false;
  QElapsedTimer timer;
  timer.start();
  while (!process.waitForFinished(100)) {
    if (stop.load() || timer.elapsed() > timeout) {
      process.kill();
      process.waitForFinished(1000);
      return false;
    }
  }
  return process.exitStatus() == QProcess::NormalExit &&
         process.exitCode() == 0;
}

Services::Services(QObject *p) : QObject(p) {
  qDBusRegisterMetaType<StorageInterfaces>();
  qDBusRegisterMetaType<StorageObjects>();
  m_pool.setMaxThreadCount(2);
  m_tasks.setMaxThreadCount(1);
  refreshDevices();
  auto bus = QDBusConnection::systemBus();
  bus.connect("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2",
              "org.freedesktop.DBus.ObjectManager", "InterfacesAdded", this,
              SLOT(storageChanged()));
  bus.connect("org.freedesktop.UDisks2", "/org/freedesktop/UDisks2",
              "org.freedesktop.DBus.ObjectManager", "InterfacesRemoved", this,
              SLOT(storageChanged()));
  bus.connect("org.freedesktop.UDisks2", {}, "org.freedesktop.DBus.Properties",
              "PropertiesChanged", this, SLOT(storageChanged()));
}
void Services::storageChanged() { refreshDevices(); }
Services::~Services() {
  cancelPreview();
  cancelTask();
  m_pool.clear();
  m_pool.waitForDone();
  m_tasks.waitForDone();
}
QString Services::home() const { return fileUri(QDir::homePath()); }
QVariantList Services::places() const {
  QVariantList result;
  auto add = [&](QString name, QString path, QString icon) {
    if (!path.isEmpty())
      result.append(
          QVariantMap{{"name", name}, {"uri", fileUri(path)}, {"icon", icon}});
  };
  add("Home", QDir::homePath(), "⌂");
  const QList<QPair<QString, QStandardPaths::StandardLocation>> dirs{
      {"Desktop", QStandardPaths::DesktopLocation},
      {"Documents", QStandardPaths::DocumentsLocation},
      {"Downloads", QStandardPaths::DownloadLocation},
      {"Pictures", QStandardPaths::PicturesLocation},
      {"Music", QStandardPaths::MusicLocation},
      {"Videos", QStandardPaths::MoviesLocation}};
  for (auto d : dirs)
    add(d.first, QStandardPaths::writableLocation(d.second), "▱");
  result.append(
      QVariantMap{{"name", "Trash"}, {"uri", "trash:///"}, {"icon", "♲"}});
  result.append(QVariantMap{
      {"name", "Recent files"}, {"uri", "recent:///"}, {"icon", "◷"}});
  return result;
}
QVariantList Services::devices() const { return m_devices; }
QVariantList Services::bookmarks() const {
  QVariantList list;
  for (auto u : QSettings().value("bookmarks").toStringList())
    list.append(QVariantMap{
        {"uri", u},
        {"name", QUrl(u).fileName().isEmpty() ? u : QUrl(u).fileName()}});
  return list;
}
void Services::bookmark(const QString &uri) {
  QSettings s;
  auto list = s.value("bookmarks").toStringList();
  if (list.contains(uri))
    list.removeAll(uri);
  else
    list.append(uri);
  s.setValue("bookmarks", list);
  emit bookmarksChanged();
}
void Services::notify(const QString &s) {
  m_message = s;
  emit messageChanged();
}
void Services::open(const QString &u) {
  if (!QDesktopServices::openUrl(QUrl(fileUri(u))))
    notify("No default application could open this file.");
}
QVariantList Services::applications(const QString &uri) const {
  const QString mime =
      QMimeDatabase()
          .mimeTypeForFile(QUrl(uri).fileName(), QMimeDatabase::MatchExtension)
          .name();
  GList *apps = g_app_info_get_all_for_type(mime.toUtf8());
  QVariantList result;
  for (GList *node = apps; node; node = node->next) {
    auto *info = G_APP_INFO(node->data);
    const char *id = g_app_info_get_id(info);
    if (id && g_app_info_should_show(info))
      result.append(QVariantMap{
          {"id", QString::fromUtf8(id)},
          {"name", QString::fromUtf8(g_app_info_get_display_name(info))}});
  }
  g_list_free_full(apps, g_object_unref);
  return result;
}
void Services::openWith(const QString &uri, const QString &applicationId) {
  const QString mime =
      QMimeDatabase()
          .mimeTypeForFile(QUrl(uri).fileName(), QMimeDatabase::MatchExtension)
          .name();
  GList *apps = g_app_info_get_all_for_type(mime.toUtf8());
  bool found = false;
  for (GList *node = apps; node; node = node->next) {
    auto *info = G_APP_INFO(node->data);
    if (QString::fromUtf8(g_app_info_get_id(info)) != applicationId)
      continue;
    GFile *file = g_file_new_for_uri(fileUri(uri).toUtf8());
    GList *files = g_list_append(nullptr, file);
    GError *error = nullptr;
    found = true;
    if (!g_app_info_launch(info, files, nullptr, &error))
      notify(error ? QString::fromUtf8(error->message)
                   : "Application launch failed.");
    if (error)
      g_error_free(error);
    g_list_free(files);
    g_object_unref(file);
    break;
  }
  g_list_free_full(apps, g_object_unref);
  if (!found)
    notify("That application is no longer registered for this file type.");
}
void Services::terminal(const QString &u) {
  QString p = localPath(u);
  if (p.isEmpty()) {
    notify("Open Terminal Here requires a local directory.");
    return;
  }
  if (!QFileInfo(p).isDir())
    p = QFileInfo(p).absolutePath();
  if (p.isEmpty() ||
      !QProcess::startDetached("xfce4-terminal", {"--working-directory", p}))
    notify("Terminal unavailable for this location.");
}
void Services::copyText(const QString &s) {
  QGuiApplication::clipboard()->setText(s);
}
void Services::clipboard(const QStringList &uris, bool cut) {
  auto *mime = new QMimeData;
  QList<QUrl> urls;
  QByteArray gnome = cut ? "cut" : "copy";
  for (auto u : uris) {
    urls.append(QUrl(u));
    gnome += '\n' + u.toUtf8();
  }
  mime->setUrls(urls);
  mime->setData("x-special/gnome-copied-files", gnome);
  mime->setData("application/x-kde-cutselection", cut ? "1" : "0");
  QGuiApplication::clipboard()->setMimeData(mime);
  notify(cut ? "Files marked for move. Choose a folder and Paste."
             : "Files copied. Choose a folder and Paste.");
}
QVariantMap Services::paste() const {
  const auto *m = QGuiApplication::clipboard()->mimeData();
  QStringList urls;
  for (auto u : m->urls())
    urls.append(u.toString(QUrl::FullyEncoded));
  QByteArray g = m->data("x-special/gnome-copied-files");
  if (urls.isEmpty() && !g.isEmpty()) {
    auto lines = g.split('\n');
    lines.removeFirst();
    for (auto l : lines)
      if (!l.isEmpty())
        urls.append(QString::fromUtf8(l));
  }
  return {{"uris", urls},
          {"cut", g.startsWith("cut\n") ||
                      m->data("application/x-kde-cutselection") == "1"}};
}
void Services::refreshDevices() {
  m_devices.clear();
  for (auto s : QStorageInfo::mountedVolumes()) {
    if (!s.isValid() || !s.isReady() || s.rootPath().startsWith("/proc") ||
        s.rootPath().startsWith("/sys") || s.rootPath().startsWith("/dev"))
      continue;
    m_devices.append(QVariantMap{
        {"name", s.displayName().isEmpty() ? s.rootPath() : s.displayName()},
        {"uri", fileUri(s.rootPath())},
        {"device", QString::fromUtf8(s.device())},
        {"type", QString::fromUtf8(s.fileSystemType())},
        {"capacity", s.bytesTotal()},
        {"free", s.bytesAvailable()},
        {"label", QLocale().formattedDataSize(s.bytesAvailable()) + " free / " +
                      QLocale().formattedDataSize(s.bytesTotal())}});
  }
  emit devicesChanged();
  auto msg = QDBusMessage::createMethodCall(
      "org.freedesktop.UDisks2", "/org/freedesktop/UDisks2",
      "org.freedesktop.DBus.ObjectManager", "GetManagedObjects");
  auto *w = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(msg, 5000), this);
  connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
    QDBusPendingReply<StorageObjects> reply = *w;
    m_removable.clear();
    if (!reply.isError()) {
      const auto objects = reply.value();
      for (auto it = objects.begin(); it != objects.end(); ++it) {
        auto block = it.value().value("org.freedesktop.UDisks2.Block");
        if (block.isEmpty() ||
            !it.value().contains("org.freedesktop.UDisks2.Filesystem") ||
            block["HintSystem"].toBool() || block["HintIgnore"].toBool())
          continue;
        const auto drive =
            objects.value(qvariant_cast<QDBusObjectPath>(block["Drive"]))
                .value("org.freedesktop.UDisks2.Drive");
        if (!drive["Removable"].toBool() && !drive["MediaRemovable"].toBool() &&
            drive["ConnectionBus"].toString() != "usb")
          continue;
        const QString label = block["IdLabel"].toString();
        m_removable.append(QVariantMap{
            {"block", it.key().path()},
            {"drive", qvariant_cast<QDBusObjectPath>(block["Drive"]).path()},
            {"name", label.isEmpty()
                         ? QString::fromUtf8(block["Device"].toByteArray())
                               .remove(QChar(0))
                         : label},
            {"type", block["IdType"]},
            {"size", block["Size"]}});
      }
    }
    emit devicesChanged();
    w->deleteLater();
  });
}
void Services::storageAction(const QString &block, const QString &action) {
  QVariantMap selected;
  for (auto r : m_removable)
    if (r.toMap()["block"] == block)
      selected = r.toMap();
  if (selected.isEmpty() ||
      !QStringList{"Mount", "Unmount", "Eject"}.contains(action)) {
    notify("Choose a discovered removable filesystem.");
    return;
  }
  auto msg = QDBusMessage::createMethodCall(
      "org.freedesktop.UDisks2",
      action == "Eject" ? selected["drive"].toString() : block,
      action == "Eject" ? "org.freedesktop.UDisks2.Drive"
                        : "org.freedesktop.UDisks2.Filesystem",
      action);
  msg << QVariantMap();
  auto *w = new QDBusPendingCallWatcher(
      QDBusConnection::systemBus().asyncCall(msg, 30000), this);
  connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
    auto reply = w->reply();
    notify(reply.type() == QDBusMessage::ErrorMessage
               ? reply.errorMessage()
               : "Storage request completed.");
    refreshDevices();
    w->deleteLater();
  });
}
void Services::cancelPreview() {
  if (m_previewCancel)
    *m_previewCancel = true;
}
void Services::cancelTask() {
  if (m_taskCancel)
    *m_taskCancel = true;
}
void Services::inspect(const QString &uri) {
  cancelPreview();
  m_pool.clear();
  auto stop = m_previewCancel = std::make_shared<std::atomic_bool>(false);
  const auto generation = ++m_generation;
  m_preview = {{"name", QUrl(uri).fileName()}, {"uri", uri}, {"loading", true}};
  emit previewChanged();
  m_pool.start(QRunnable::create([this, uri, generation, stop] {
    if (stop->load())
      return;
    QVariantMap result = fileMetadata(uri);
    result["uri"] = uri;
    const QString path = localPath(uri);
    const qint64 size = result["size"].toLongLong();
    const QString mime = result["mime"].toString();
    if (!path.isEmpty() && !result["directory"].toBool() &&
        !result["symlink"].toBool()) {
      if (mime.startsWith("image/") && size <= 32 * 1024 * 1024) {
        QImageReader reader(path);
        const auto dim = reader.size();
        result["dimensions"] =
            QString("%1 × %2").arg(dim.width()).arg(dim.height());
        if (dim.isValid() && qint64(dim.width()) * dim.height() <= 64000000) {
          result["image"] = uri;
          result["thumbnailPath"] = path;
        }
      } else if (mime.startsWith("text/") || mime.contains("json") ||
                 mime.contains("xml") || mime.contains("javascript") ||
                 QStringList{"txt", "json", "yaml", "yml", "xml", "ini", "log",
                             "sh", "py", "php", "js", "ts", "html", "css", "md"}
                     .contains(QFileInfo(path).suffix().toLower())) {
        QFile file(path);
        if (file.open(QIODevice::ReadOnly)) {
          const QByteArray bytes = file.read(128 * 1024);
          if (!bytes.contains('\0'))
            result["text"] =
                QString::fromUtf8(bytes) +
                (size > bytes.size() ? "\n… Preview limited to 128 KiB." : "");
        }
      } else if (mime.contains("pdf")) {
        QProcess p;
        if (previewProcess(p, "pdfinfo", {path}, *stop))
          result["text"] =
              QString::fromUtf8(p.readAllStandardOutput()).left(32000);
        else
          result["text"] = "PDF metadata unavailable; install poppler-utils or "
                           "open in your viewer.";
      } else if (mime.contains("zip") || mime.contains("tar") ||
                 mime.contains("7z")) {
        archive *a = archive_read_new();
        archive_read_support_filter_all(a);
        archive_read_support_format_all(a);
        QStringList names;
        archive_entry *e = nullptr;
        if (archive_read_open_filename(a, QFile::encodeName(path), 65536) ==
            ARCHIVE_OK) {
          QElapsedTimer time;
          time.start();
          while (names.size() < 2000 && !stop->load() &&
                 time.elapsed() < 5000 &&
                 archive_read_next_header(a, &e) == ARCHIVE_OK) {
            names.append(QString::fromUtf8(archive_entry_pathname(e)));
            archive_read_data_skip(a);
          }
          result["text"] = names.join('\n');
        }
        archive_read_free(a);
      }
      if ((mime.contains("pdf") || mime.startsWith("video/")) &&
          size < 512LL * 1024 * 1024 && !stop->load()) {
        const QString cache =
            QStandardPaths::writableLocation(QStandardPaths::CacheLocation) +
            "/previews";
        QDir().mkpath(cache);
        const auto key =
            QCryptographicHash::hash(
                (path + result["modified"].toString() + QString::number(size))
                    .toUtf8(),
                QCryptographicHash::Sha256)
                .toHex();
        const QString image = cache + "/" + key + ".png";
        // Keep the disk cache bounded without reading image contents.
        auto existing =
            QDir(cache).entryInfoList({"*.png"}, QDir::Files, QDir::Time);
        qint64 sum = 0;
        for (const auto &f : existing) {
          sum += f.size();
          if (sum > 64 * 1024 * 1024)
            QFile::remove(f.absoluteFilePath());
        }
        if (!QFile::exists(image)) {
          QProcess process;
          if (mime.contains("pdf"))
            previewProcess(process, "pdftoppm",
                           {"-f", "1", "-l", "1", "-singlefile", "-scale-to",
                            "1024", "-png", path, cache + "/" + key},
                           *stop);
          else
            previewProcess(
                process, "ffmpeg",
                {"-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
                 "-threads", "1", "-i", path, "-frames:v", "1", "-vf",
                 "scale=1024:1024:force_original_aspect_ratio=decrease", "-y",
                 image},
                *stop);
        }
        if (QFile::exists(image)) {
          result["image"] = fileUri(image);
          result["thumbnailPath"] = image;
        }
      }
    }
    if (stop->load())
      return;
    QMetaObject::invokeMethod(
        this,
        [this, generation, result] {
          if (generation != m_generation)
            return;
          m_preview = result;
          emit previewChanged();
        },
        Qt::QueuedConnection);
  }));
}
void Services::task(std::function<QString(std::atomic_bool &)> work) {
  if (m_taskCancel && !m_taskCancel->load()) {
    notify("Another developer/network/archive task is running. Cancel it or "
           "wait.");
    return;
  }
  auto stop = m_taskCancel = std::make_shared<std::atomic_bool>(false);
  notify("Working…");
  m_tasks.start(QRunnable::create([this, stop, work] {
    QString result;
    try {
      result = work(*stop);
    } catch (const std::exception &e) {
      result = QString::fromUtf8(e.what());
    }
    *stop = true;
    QMetaObject::invokeMethod(
        this, [this, result] { notify(result); }, Qt::QueuedConnection);
  }));
}
void Services::hash(const QString &uri, bool sha512) {
  task([uri, sha512](std::atomic_bool &stop) {
    QFile f(localPath(uri));
    if (!f.open(QIODevice::ReadOnly))
      return f.errorString();
    QCryptographicHash hash(sha512 ? QCryptographicHash::Sha512
                                   : QCryptographicHash::Sha256);
    while (!f.atEnd()) {
      if (stop)
        return QString("Hash cancelled.");
      auto b = f.read(1024 * 1024);
      if (b.isEmpty() && f.error() != QFile::NoError)
        return f.errorString();
      hash.addData(b);
    }
    return QString(sha512 ? "SHA-512: " : "SHA-256: ") +
           QString::fromLatin1(hash.result().toHex());
  });
}
void Services::connectNetwork(const QString &uri, const QString &username,
                              const QString &password) {
  QUrl u(uri);
  if (!QStringList{"sftp", "smb", "dav", "davs"}.contains(u.scheme()) ||
      u.host().isEmpty() || !u.password().isEmpty()) {
    notify("Use sftp://, smb://, dav:// or davs:// with a host. Enter the "
           "password only in its password field.");
    return;
  }
  if (!username.isEmpty())
    u.setUserName(username);
  const QString target = u.toString(QUrl::FullyEncoded);
  task([this, target, username, password](std::atomic_bool &stop) {
    struct State {
      GMainLoop *loop;
      GCancellable *cancel;
      QString user, password, error;
      bool ok = false;
      std::atomic_bool *stop;
      int ticks = 0;
      int prompts = 0;
    };
    GMainContext *ctx = g_main_context_new();
    g_main_context_push_thread_default(ctx);
    State state{g_main_loop_new(ctx, false),
                g_cancellable_new(),
                username,
                password,
                {},
                false,
                &stop,
                0};
    GFile *f = g_file_new_for_uri(target.toUtf8());
    GMountOperation *op = g_mount_operation_new();
    g_signal_connect(
        op, "ask-password",
        G_CALLBACK(+[](GMountOperation *op, const char *, const char *user,
                       const char *domain, GAskPasswordFlags flags,
                       gpointer data) {
          auto *s = static_cast<State *>(data);
          if (++s->prompts > 2) {
            s->error = "Authentication failed. Check your username and "
                       "password, then reconnect.";
            g_mount_operation_reply(op, G_MOUNT_OPERATION_ABORTED);
            return;
          }
          g_mount_operation_set_username(
              op, s->user.isEmpty() ? user : s->user.toUtf8().constData());
          if (flags & G_ASK_PASSWORD_NEED_DOMAIN)
            g_mount_operation_set_domain(op, domain ? domain : "");
          g_mount_operation_set_password(op, s->password.toUtf8());
          g_mount_operation_set_password_save(op, G_PASSWORD_SAVE_NEVER);
          if ((flags & G_ASK_PASSWORD_NEED_PASSWORD) && s->password.isEmpty())
            g_mount_operation_reply(op, G_MOUNT_OPERATION_ABORTED);
          else
            g_mount_operation_reply(op, G_MOUNT_OPERATION_HANDLED);
        }),
        &state);
    g_signal_connect(
        op, "ask-question",
        G_CALLBACK(+[](GMountOperation *op, const char *message,
                       const char *const *choices, gpointer data) {
          auto *s = static_cast<State *>(data);
          s->error = QString::fromUtf8(message) +
                     "\nIdentity confirmation is required. Verify and "
                     "connect with your system network client first.";
          int count = 0;
          while (choices && choices[count])
            ++count;
          if (count >= 2)
            g_mount_operation_set_choice(op, count - 1);
          else
            g_cancellable_cancel(s->cancel);
          g_mount_operation_reply(op, count >= 2 ? G_MOUNT_OPERATION_HANDLED
                                                 : G_MOUNT_OPERATION_ABORTED);
        }),
        &state);
    GSource *timer = g_timeout_source_new(100);
    g_source_set_callback(
        timer,
        +[](gpointer data) -> gboolean {
          auto *s = static_cast<State *>(data);
          if (s->stop->load() || ++s->ticks > 600)
            g_cancellable_cancel(s->cancel);
          return G_SOURCE_CONTINUE;
        },
        &state, nullptr);
    g_source_attach(timer, ctx);
    g_file_mount_enclosing_volume(
        f, G_MOUNT_MOUNT_NONE, op, state.cancel,
        +[](GObject *obj, GAsyncResult *r, gpointer data) {
          auto *s = static_cast<State *>(data);
          GError *e = nullptr;
          s->ok = g_file_mount_enclosing_volume_finish(G_FILE(obj), r, &e);
          if (e) {
            if (g_error_matches(e, G_IO_ERROR, G_IO_ERROR_ALREADY_MOUNTED))
              s->ok = true;
            else if (s->error.isEmpty())
              s->error = QString::fromUtf8(e->message);
            g_error_free(e);
          }
          g_main_loop_quit(s->loop);
        },
        &state);
    g_main_loop_run(state.loop);
    g_source_destroy(timer);
    g_source_unref(timer);
    g_object_unref(op);
    g_object_unref(f);
    g_object_unref(state.cancel);
    g_main_loop_unref(state.loop);
    g_main_context_pop_thread_default(ctx);
    g_main_context_unref(ctx);
    state.ok = state.ok && state.error.isEmpty();
    if (state.ok)
      QMetaObject::invokeMethod(
          this, [this, target] { emit networkReady(target); },
          Qt::QueuedConnection);
    return state.ok ? QString("Connected using GVfs.") : state.error;
  });
}
void Services::extract(const QString &uri, const QString &destination) {
  task([uri, destination](std::atomic_bool &stop) {
    const QString parent = localPath(destination);
    if (!QFileInfo(parent).isDir())
      return QString("Extract to a local directory.");
    QTemporaryDir staging(parent + "/.etherfiles-extract-XXXXXX");
    if (!staging.isValid())
      return QString("Cannot create private extraction directory.");
    archive *a = archive_read_new();
    archive_read_support_filter_all(a);
    archive_read_support_format_all(a);
    if (archive_read_open_filename(a, QFile::encodeName(localPath(uri)),
                                   65536) != ARCHIVE_OK) {
      QString error = QString::fromUtf8(archive_error_string(a));
      archive_read_free(a);
      return error;
    }
    QString error;
    archive_entry *entry = nullptr;
    qint64 total = 0;
    int count = 0;
    QElapsedTimer elapsed;
    elapsed.start();
    const qint64 packed = QFileInfo(localPath(uri)).size();
    while (!stop && archive_read_next_header(a, &entry) == ARCHIVE_OK) {
      QString name = QString::fromUtf8(archive_entry_pathname(entry));
      const QString clean = QDir::cleanPath(name);
      if (++count > 100000 || elapsed.elapsed() > 60000 || clean == ".." ||
          clean.startsWith("../") || QDir::isAbsolutePath(name) ||
          name.contains('\\') || archive_entry_symlink(entry) ||
          archive_entry_hardlink(entry)) {
        error = "Unsafe archive entry or extraction limit reached: " + name;
        break;
      }
      const auto type = archive_entry_filetype(entry);
      if (type != AE_IFREG && type != AE_IFDIR) {
        error = "Unsupported special archive entry: " + name;
        break;
      }
      QString path = staging.path() + "/" + clean;
      if (type == AE_IFDIR) {
        if (!QDir().mkpath(path)) {
          error = "Cannot create archive directory.";
          break;
        }
        continue;
      }
      if (!QDir().mkpath(QFileInfo(path).absolutePath())) {
        error = "Cannot create archive parent.";
        break;
      }
      QFile out(path);
      if (!out.open(QIODevice::WriteOnly | QIODevice::NewOnly)) {
        error = out.errorString();
        break;
      }
      char buffer[65536];
      la_ssize_t n;
      while ((n = archive_read_data(a, buffer, sizeof buffer)) > 0) {
        total += n;
        if (stop || total > 1024LL * 1024 * 1024 ||
            total > qMax(64LL * 1024 * 1024, packed * 1000) ||
            elapsed.elapsed() > 60000) {
          error = "Cancelled or archive exceeds 1 GiB, 1000× ratio or 60 "
                  "second limit.";
          break;
        }
        if (out.write(buffer, n) != n) {
          error = out.errorString();
          break;
        }
      }
      if (n < 0)
        error = QString::fromUtf8(archive_error_string(a));
      if (!error.isEmpty())
        break;
    }
    if (archive_errno(a) && error.isEmpty())
      error = QString::fromUtf8(archive_error_string(a));
    archive_read_free(a);
    if (stop)
      return QString("Extraction cancelled; staging removed.");
    if (!error.isEmpty())
      return error;
    const QString target = parent + "/" +
                           QFileInfo(localPath(uri)).completeBaseName() +
                           "-extracted";
    if (QFileInfo::exists(target) || !QDir().rename(staging.path(), target))
      return QString("Extraction destination exists or cannot be committed. No "
                     "files replaced.");
    staging.setAutoRemove(false);
    return "Extracted to " + target;
  });
}
void Services::createArchive(const QStringList &uris,
                             const QString &destination, const QString &name) {
  task([uris, destination, name](std::atomic_bool &stop) {
    if (name.isEmpty() || name.contains('/') || name.contains(QChar(0)) ||
        name == "." || name == "..")
      return QString("Enter a simple archive name.");
    if (localPath(destination).isEmpty() || uris.isEmpty())
      return QString("Select local files and a local destination.");
    for (const auto &u : uris) {
      QFileInfo source(localPath(u));
      if (localPath(u).isEmpty() || !source.exists() || source.isSymLink())
        return QString(
            "Select existing local files or folders without symlinks.");
      const QString dest =
                        QFileInfo(localPath(destination)).canonicalFilePath(),
                    root = source.canonicalFilePath();
      if (source.isDir() && (dest == root || dest.startsWith(root + "/")))
        return QString(
            "The archive destination must be outside selected folders.");
    }
    const QString target = localPath(destination) + "/" + name;
    if (QFileInfo::exists(target))
      return QString("Archive destination exists.");
    QTemporaryDir temp(localPath(destination) + "/.etherfiles-archive-XXXXXX");
    if (!temp.isValid())
      return QString("Cannot create archive staging.");
    const QString staged = temp.path() + "/archive.zip";
    archive *a = archive_write_new();
    archive_write_set_format_zip(a);
    if (archive_write_open_filename(a, QFile::encodeName(staged)) !=
        ARCHIVE_OK) {
      QString e = QString::fromUtf8(archive_error_string(a));
      archive_write_free(a);
      return e;
    }
    QString error;
    QSet<QString> used;
    QElapsedTimer elapsed;
    elapsed.start();
    int count = 0;
    for (const auto &u : uris) {
      QString root = localPath(u);
      QStringList paths{root};
      if (QFileInfo(root).isDir()) {
        QDirIterator it(root,
                        QDir::AllEntries | QDir::NoDotAndDotDot | QDir::Hidden,
                        QDirIterator::Subdirectories);
        while (it.hasNext()) {
          paths.append(it.next());
          if (paths.size() > 100000) {
            error = "Archive entry limit reached.";
            break;
          }
        }
      }
      for (const auto &p : paths) {
        if (stop || elapsed.elapsed() > 60000 || ++count > 100000) {
          error = "Archive cancelled or resource limit reached.";
          break;
        }
        QFileInfo f(p);
        if (f.isSymLink() || (!f.isDir() && !f.isFile())) {
          error = "Symlinks and special files are not archived.";
          break;
        }
        const QString n =
            QFileInfo(root).fileName() +
            (p == root ? QString() : "/" + QDir(root).relativeFilePath(p));
        if (used.contains(n)) {
          error = "Duplicate archive path: " + n;
          break;
        }
        used.insert(n);
        archive_entry *e = archive_entry_new();
        archive_entry_set_pathname(e, n.toUtf8());
        archive_entry_set_filetype(e, f.isDir() ? AE_IFDIR : AE_IFREG);
        archive_entry_set_perm(e, f.isDir() ? 0755 : 0644);
        archive_entry_set_size(e, f.isDir() ? 0 : f.size());
        if (archive_write_header(a, e) != ARCHIVE_OK)
          error = QString::fromUtf8(archive_error_string(a));
        if (f.isFile() && error.isEmpty()) {
          QFile input(p);
          if (!input.open(QIODevice::ReadOnly))
            error = input.errorString();
          while (!input.atEnd() && error.isEmpty()) {
            if (stop || elapsed.elapsed() > 60000) {
              error = "Archive cancelled or timed out.";
              break;
            }
            auto b = input.read(65536);
            if (b.isEmpty() && input.error() != QFile::NoError) {
              error = input.errorString();
              break;
            }
            if (archive_write_data(a, b.constData(), b.size()) != b.size())
              error = "Archive write failed.";
          }
        }
        archive_entry_free(e);
        if (!error.isEmpty())
          break;
      }
      if (!error.isEmpty())
        break;
    }
    if (archive_write_close(a) != ARCHIVE_OK && error.isEmpty())
      error = "Archive close failed.";
    archive_write_free(a);
    if (!error.isEmpty())
      return error;
    if (!QFile::rename(staged, target))
      return QString("Cannot commit archive; destination may exist.");
    return "Archive created: " + target;
  });
}
