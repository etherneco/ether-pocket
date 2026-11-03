#include "operations.h"
#include "files.h"
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonDocument>
#include <QRunnable>
#include <QSaveFile>
#include <QStandardPaths>
#include <QUrl>
#include <QUuid>
#include <fcntl.h>
#include <functional>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>
#undef signals
#include <gio/gio.h>

namespace {
struct File {
  GFile *p;
  explicit File(const QString &u)
      : p(g_file_new_for_uri(fileUri(u).toUtf8())) {}
  explicit File(GFile *f) : p(f) {}
  ~File() { g_object_unref(p); }
  QString uri() const {
    char *s = g_file_get_uri(p);
    QString u = QString::fromUtf8(s);
    g_free(s);
    return u;
  }
};
void check(bool ok, GError *e) {
  if (!ok) {
    QString message = e ? QString::fromUtf8(e->message) : "Operation failed";
    if (e)
      g_error_free(e);
    throw std::runtime_error(message.toStdString());
  }
  if (e)
    g_error_free(e);
}
#define GIO_CHECK(expr)                                                        \
  do {                                                                         \
    bool succeeded = (expr);                                                   \
    check(succeeded, e);                                                       \
    e = nullptr;                                                               \
  } while (false)
bool exists(GFile *f) { return g_file_query_exists(f, nullptr); }
QString childUri(const QString &parent, const QString &name) {
  File p(parent);
  File child(g_file_get_child(p.p, name.toUtf8()));
  return child.uri();
}
QString resolvedPath(const QString &path) {
  QFileInfo info(path);
  QString tail;
  while (!info.exists() && !info.isSymLink()) {
    const QString parent = info.absolutePath();
    if (parent == info.absoluteFilePath())
      break;
    tail = "/" + info.fileName() + tail;
    info = QFileInfo(parent);
  }
  return info.canonicalFilePath() + tail;
}
bool validName(const QString &n) {
  return !n.isEmpty() && n != "." && n != ".." && !n.contains('/') &&
         !n.contains(QChar(0));
}
} // namespace
struct Operations::Task {
  int id;
  QString action, destination, name;
  QStringList sources;
  GCancellable *cancel = g_cancellable_new();
  QString policy;
  bool apply = false;
  int done = 0;
  QStringList errors, skipped;
  bool stopped = false;
  ~Task() { g_object_unref(cancel); }
};
Operations::Operations(QObject *p) : QObject(p) {
  m_pool.setMaxThreadCount(1);
  QFile journal(
      QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation) +
      "/operations.json");
  if (journal.open(QIODevice::ReadOnly) && journal.size() < 2 * 1024 * 1024) {
    const auto loaded =
        QJsonDocument::fromJson(journal.readAll()).toVariant().toList();
    for (auto value : loaded) {
      auto m = value.toMap();
      if (!m.contains("id") || !m.contains("state"))
        continue;
      m_next = qMax(m_next, m["id"].toInt());
      if (QStringList{"Running", "Queued"}.contains(m["state"].toString())) {
        m["state"] = "Interrupted";
        m["errors"] = QStringList{
            "The previous process stopped. Review source/destination and any "
            ".etherfiles-* temporary entries before retrying. Completed files "
            "were retained."};
      }
      m_jobs.append(m);
    }
  }
}
void Operations::saveJobs() {
  const QString dir =
      QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
  QDir().mkpath(dir);
  QSaveFile file(dir + "/operations.json");
  if (file.open(QIODevice::WriteOnly)) {
    file.setPermissions(QFile::ReadOwner | QFile::WriteOwner);
    file.write(QJsonDocument::fromVariant(m_jobs).toJson());
    file.commit();
  }
}
Operations::~Operations() {
  for (auto t : m_tasks)
    g_cancellable_cancel(t->cancel);
  m_answer.wakeAll();
  m_pool.waitForDone();
}
void Operations::update(int id, const QVariantMap &v) {
  QMetaObject::invokeMethod(
      this,
      [this, id, v] {
        for (auto &j : m_jobs) {
          auto m = j.toMap();
          if (m["id"] == id) {
            for (auto i = v.begin(); i != v.end(); ++i)
              m[i.key()] = i.value();
            j = m;
            break;
          }
        }
        if (v.contains("state"))
          saveJobs();
        emit changed();
      },
      Qt::QueuedConnection);
}
int Operations::submit(const QString &action, const QStringList &sources,
                       const QString &destination, const QString &name) {
  const QStringList allowed{"copy",        "move",   "trash", "delete",
                            "restore",     "mkdir",  "touch", "rename",
                            "permissions", "symlink"};
  if (!allowed.contains(action) || m_tasks.size() >= 32)
    return -1;
  auto t = std::make_shared<Task>();
  t->id = ++m_next;
  t->action = action;
  t->sources = sources;
  t->destination = destination;
  t->name = name;
  m_tasks.insert(t->id, t);
  m_jobs.append(QVariantMap{
      {"id", t->id},
      {"action", action},
      {"sources", sources},
      {"destination", destination},
      {"state", "Queued"},
      {"done", 0},
      {"total", (action == "mkdir" || action == "touch" || action == "symlink")
                    ? 1
                    : sources.size()},
      {"current", ""},
      {"errors", QStringList()}});
  while (m_jobs.size() > 64)
    m_jobs.removeFirst();
  saveJobs();
  emit changed();
  m_pool.start(QRunnable::create([this, t] {
    run(t);
    QMetaObject::invokeMethod(
        this,
        [this, t] {
          m_tasks.remove(t->id);
          emit completed();
        },
        Qt::QueuedConnection);
  }));
  return t->id;
}
void Operations::cancel(int id) {
  if (m_tasks.contains(id)) {
    g_cancellable_cancel(m_tasks[id]->cancel);
    m_answer.wakeAll();
  }
}
void Operations::resolve(const QString &d, bool remaining) {
  QMutexLocker l(&m_mutex);
  if (!QStringList{"replace", "skip", "keep", "cancel"}.contains(d) &&
      !(d.startsWith("rename:") && validName(d.mid(7))))
    return;
  m_decision = d;
  m_remaining = remaining && !d.startsWith("rename:");
  m_answer.wakeAll();
}
QString Operations::ask(const QString &s, const QString &d,
                        const std::shared_ptr<Task> &t) {
  if (t->apply)
    return t->policy;
  QMutexLocker l(&m_mutex);
  m_decision.clear();
  QMetaObject::invokeMethod(
      this,
      [this, s, d] {
        m_conflict = {{"source", s}, {"destination", d}};
        emit conflictChanged();
      },
      Qt::QueuedConnection);
  while (m_decision.isEmpty() && !g_cancellable_is_cancelled(t->cancel))
    m_answer.wait(&m_mutex, 200);
  QString choice =
      g_cancellable_is_cancelled(t->cancel) ? "cancel" : m_decision;
  t->apply = m_remaining;
  t->policy = choice;
  QMetaObject::invokeMethod(
      this,
      [this] {
        m_conflict.clear();
        emit conflictChanged();
      },
      Qt::QueuedConnection);
  return choice;
}
void Operations::run(const std::shared_ptr<Task> &t) {
  update(t->id, {{"state", "Running"}});
  auto cancelled = [&] {
    if (g_cancellable_is_cancelled(t->cancel))
      throw std::runtime_error("Cancelled; completed items remain in place.");
  };
  // Each committed file is a complete copy. Interrupted copies remove only
  // their own temporary file.
  std::function<void(const QString &, QString, bool)> transfer;
  transfer = [&](const QString &s, QString d, bool moving) {
    cancelled();
    File src(s);
    File dst(d);
    GError *e = nullptr;
    if (g_file_equal(src.p, dst.p) || g_file_has_prefix(dst.p, src.p))
      throw std::runtime_error("Destination is the source or is inside it.");
    auto type = g_file_query_file_type(
        src.p, G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS, t->cancel);
    if (type == G_FILE_TYPE_DIRECTORY && !localPath(s).isEmpty() &&
        !localPath(d).isEmpty()) {
      const QString source = QFileInfo(localPath(s)).canonicalFilePath(),
                    destination = resolvedPath(localPath(d));
      if (!source.isEmpty() &&
          (source == destination || destination.startsWith(source + "/")))
        throw std::runtime_error(
            "Destination resolves inside the source directory.");
    }
    bool replace = false;
    if (exists(dst.p)) {
      const QString decision = ask(s, d, t);
      if (decision == "cancel") {
        g_cancellable_cancel(t->cancel);
        cancelled();
      }
      if (decision == "skip") {
        t->skipped.append(s);
        return;
      }
      if (decision.startsWith("rename:")) {
        File parent(g_file_get_parent(dst.p));
        transfer(s, childUri(parent.uri(), decision.mid(7)), moving);
        return;
      }
      if (decision == "keep") {
        File parent(g_file_get_parent(dst.p));
        char *n = g_file_get_basename(dst.p);
        const QString base = QString::fromUtf8(n);
        g_free(n);
        int i = 1;
        do {
          d = childUri(parent.uri(), base + QString(" (copy %1)").arg(i++));
          File candidate(d);
          if (!exists(candidate.p))
            break;
        } while (i < 10000);
        transfer(s, d, moving);
        return;
      }
      replace = true;
      if (type == G_FILE_TYPE_DIRECTORY ||
          g_file_query_file_type(dst.p, G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS,
                                 t->cancel) == G_FILE_TYPE_DIRECTORY)
        throw std::runtime_error(
            "Replacing a directory is refused. Choose Keep both or Skip.");
    }
    if (type == G_FILE_TYPE_DIRECTORY) {
      GIO_CHECK(g_file_make_directory(dst.p, t->cancel, &e));
      e = nullptr;
      GFileEnumerator *en = g_file_enumerate_children(
          src.p, "standard::name", G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS,
          t->cancel, &e);
      if (!en)
        check(false, e);
      int skippedBefore = t->skipped.size();
      try {
        while (true) {
          cancelled();
          GFileInfo *i = g_file_enumerator_next_file(en, t->cancel, &e);
          if (!i) {
            if (e)
              check(false, e);
            break;
          }
          QString n = QString::fromUtf8(g_file_info_get_name(i));
          g_object_unref(i);
          transfer(childUri(s, n), childUri(d, n), moving);
        }
      } catch (...) {
        g_object_unref(en);
        throw;
      }
      g_object_unref(en);
      if (moving && t->skipped.size() == skippedBefore) {
        e = nullptr;
        GIO_CHECK(g_file_delete(src.p, t->cancel, &e));
      }
    } else {
      File parent(g_file_get_parent(dst.p));
      File temp(childUri(
          parent.uri(),
          ".etherfiles-" + QUuid::createUuid().toString(QUuid::WithoutBraces)));
      struct Progress {
        Operations *self;
        std::shared_ptr<Task> task;
        QString source;
        QElapsedTimer timer;
        qint64 last = 0;
      };
      Progress progress{this, t, s, {}, 0};
      progress.timer.start();
      auto cb = +[](goffset current, goffset total, gpointer p) {
        auto *c = static_cast<Progress *>(p);
        auto ms = c->timer.elapsed();
        if (ms - c->last < 100 && current != total)
          return;
        c->last = ms;
        const qint64 speed = ms > 0 ? current * 1000 / ms : 0;
        c->self->update(c->task->id,
                        {{"bytes", qlonglong(current)},
                         {"bytesTotal", qlonglong(total)},
                         {"speed", speed},
                         {"eta", speed > 0 ? (total - current) / speed : 0},
                         {"current", c->source}});
      };
      bool ok = g_file_copy(src.p, temp.p, G_FILE_COPY_NOFOLLOW_SYMLINKS,
                            t->cancel, cb, &progress, &e);
      if (!ok) {
        g_file_delete(temp.p, nullptr, nullptr);
        check(false, e);
      }
      e = nullptr;
      ok = g_file_move(temp.p, dst.p,
                       replace ? G_FILE_COPY_OVERWRITE : G_FILE_COPY_NONE,
                       t->cancel, nullptr, nullptr, &e);
      if (!ok) {
        g_file_delete(temp.p, nullptr, nullptr);
        check(false, e);
      }
      if (moving) {
        e = nullptr;
        GIO_CHECK(g_file_delete(src.p, t->cancel, &e));
      }
    }
  };
  std::function<void(const QString &)> remove;
  remove = [&](const QString &s) {
    cancelled();
    File f(s);
    GError *e = nullptr;
    if (g_file_query_file_type(f.p, G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS,
                               t->cancel) == G_FILE_TYPE_DIRECTORY) {
      GFileEnumerator *en = g_file_enumerate_children(
          f.p, "standard::name", G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS, t->cancel,
          &e);
      if (!en)
        check(false, e);
      try {
        while (true) {
          GFileInfo *i = g_file_enumerator_next_file(en, t->cancel, &e);
          if (!i) {
            if (e)
              check(false, e);
            break;
          }
          QString n = QString::fromUtf8(g_file_info_get_name(i));
          g_object_unref(i);
          remove(childUri(s, n));
        }
      } catch (...) {
        g_object_unref(en);
        throw;
      }
      g_object_unref(en);
    }
    e = nullptr;
    GIO_CHECK(g_file_delete(f.p, t->cancel, &e));
  };
  try {
    if (t->action == "mkdir" || t->action == "touch" ||
        t->action == "symlink") {
      if (!validName(t->name))
        throw std::runtime_error("Enter a single valid filename.");
      File dst(childUri(t->destination, t->name));
      GError *e = nullptr;
      if (t->action == "mkdir")
        GIO_CHECK(g_file_make_directory(dst.p, t->cancel, &e));
      else if (t->action == "symlink") {
        const QString target = t->sources.value(0);
        if (target.isEmpty() || target.contains(QChar(0)))
          throw std::runtime_error("Enter a valid link target.");
        GIO_CHECK(
            g_file_make_symbolic_link(dst.p, target.toUtf8(), t->cancel, &e));
      } else {
        GFileOutputStream *stream =
            g_file_create(dst.p, G_FILE_CREATE_NONE, t->cancel, &e);
        if (!stream)
          check(false, e);
        else {
          g_output_stream_close(G_OUTPUT_STREAM(stream), nullptr, nullptr);
          g_object_unref(stream);
        }
      }
      t->done = 1;
    }
    for (const QString &s :
         t->action == "symlink" ? QStringList() : t->sources) {
      cancelled();
      update(t->id, {{"current", s}});
      try {
        File src(s);
        GError *e = nullptr;
        if (t->action == "trash")
          GIO_CHECK(g_file_trash(src.p, t->cancel, &e));
        else if (t->action == "delete")
          remove(s);
        else if (t->action == "permissions") {
          bool ok = false;
          uint mode = t->name.toUInt(&ok, 8);
          if (!ok || mode > 0777 || localPath(s).isEmpty())
            throw std::runtime_error("Use local permissions 000–777.");
          if (QFileInfo(localPath(s)).isSymLink())
            throw std::runtime_error(
                "Permission changes on symlinks are refused.");
          const int fd = ::open(QFile::encodeName(localPath(s)).constData(),
                                O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
          if (fd < 0)
            throw std::runtime_error(
                "Cannot open this file safely for permission changes.");
          const int result = ::fchmod(fd, mode);
          ::close(fd);
          if (result != 0)
            throw std::runtime_error("Permission change failed.");
        } else if (t->action == "restore") {
          auto m = fileMetadata(s);
          const QString original = m["original"].toString();
          if (original.isEmpty())
            throw std::runtime_error("Original Trash path is unavailable.");
          File dst(original);
          if (exists(dst.p))
            throw std::runtime_error("Restore destination exists. Move the "
                                     "trashed item elsewhere first.");
          GIO_CHECK(g_file_move(src.p, dst.p, G_FILE_COPY_NOFOLLOW_SYMLINKS,
                                t->cancel, nullptr, nullptr, &e));
        } else {
          char *n = g_file_get_basename(src.p);
          QString name = QString::fromUtf8(n);
          g_free(n);
          QString dest = t->destination;
          if (t->action == "rename") {
            if (!validName(t->name))
              throw std::runtime_error("Enter a single valid filename.");
            File parent(g_file_get_parent(src.p));
            dest = parent.uri();
            name = t->name;
          }
          transfer(s, childUri(dest, name), t->action != "copy");
        }
        ++t->done;
      } catch (const std::exception &e) {
        t->errors.append(s + ": " + QString::fromUtf8(e.what()));
        if (g_cancellable_is_cancelled(t->cancel))
          throw;
      }
      update(
          t->id,
          {{"done", t->done}, {"errors", t->errors}, {"skipped", t->skipped}});
    }
  } catch (const std::exception &e) {
    t->errors.append(QString::fromUtf8(e.what()));
  }
  update(t->id, {{"state", g_cancellable_is_cancelled(t->cancel) ? "Cancelled"
                           : t->errors.isEmpty()
                               ? (t->skipped.isEmpty() ? "Complete"
                                                       : "Complete with skips")
                               : "Finished with errors"},
                 {"done", t->done},
                 {"errors", t->errors},
                 {"skipped", t->skipped}});
}
