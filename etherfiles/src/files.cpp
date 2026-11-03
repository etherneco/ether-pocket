#include "files.h"
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QMimeDatabase>
#include <QRunnable>
#include <QStorageInfo>
#include <QUrl>
#include <algorithm>
#include <grp.h>
#include <pwd.h>
#include <sys/stat.h>
#undef signals
#include <gio/gio.h>

QString fileUri(const QString &input) {
  if (input.startsWith("/"))
    return QUrl::fromLocalFile(QDir::cleanPath(input))
        .toString(QUrl::FullyEncoded);
  QUrl url(input);
  if (url.isValid() && !url.scheme().isEmpty()) {
    url.setPassword(QString());
    return url.toString(QUrl::FullyEncoded);
  }
  return QUrl::fromLocalFile(QFileInfo(input).absoluteFilePath())
      .toString(QUrl::FullyEncoded);
}
QString localPath(const QString &uri) {
  return QUrl(uri).isLocalFile() ? QUrl(uri).toLocalFile() : QString();
}
static QString str(const char *s) { return QString::fromUtf8(s ? s : ""); }
static QVariantMap metadata(GFile *file, GFileInfo *info) {
  char *uri = g_file_get_uri(file);
  char *path = g_file_get_path(file);
  const QString mime = str(g_file_info_get_content_type(info));
  const bool dir = g_file_info_get_file_type(info) == G_FILE_TYPE_DIRECTORY;
  const bool symlink =
      g_file_info_has_attribute(info, G_FILE_ATTRIBUTE_STANDARD_IS_SYMLINK) &&
      g_file_info_get_is_symlink(info);
  const bool hasSize =
      g_file_info_has_attribute(info, G_FILE_ATTRIBUTE_STANDARD_SIZE);
  const qlonglong size = hasSize ? g_file_info_get_size(info) : 0;
  QVariantMap m{
      {"name", str(g_file_info_get_display_name(info))},
      {"uri", str(uri)},
      {"path", str(path)},
      {"directory", dir},
      {"symlink", symlink},
      {"target", (symlink && g_file_info_has_attribute(
                                 info, G_FILE_ATTRIBUTE_STANDARD_SYMLINK_TARGET)
                      ? str(g_file_info_get_symlink_target(info))
                      : QString())},
      {"size", size},
      {"mime", mime},
      {"modified",
       g_file_info_has_attribute(info, G_FILE_ATTRIBUTE_TIME_MODIFIED)
           ? QDateTime::fromSecsSinceEpoch(
                 g_file_info_get_attribute_uint64(
                     info, G_FILE_ATTRIBUTE_TIME_MODIFIED))
                 .toString(Qt::ISODate)
           : QString()},
      {"created", g_file_info_has_attribute(info, G_FILE_ATTRIBUTE_TIME_CREATED)
                      ? QDateTime::fromSecsSinceEpoch(
                            g_file_info_get_attribute_uint64(
                                info, G_FILE_ATTRIBUTE_TIME_CREATED))
                            .toString(Qt::ISODate)
                      : QString()},
      {"original", str(g_file_info_get_attribute_byte_string(
                       info, G_FILE_ATTRIBUTE_TRASH_ORIG_PATH))},
      {"filesystem", str(g_file_info_get_attribute_string(
                         info, G_FILE_ATTRIBUTE_ID_FILESYSTEM))}};
  QString icon = dir ? "folder" : "file";
  if (mime.startsWith("image/"))
    icon = "image";
  else if (mime.startsWith("video/"))
    icon = "video";
  else if (mime.startsWith("audio/"))
    icon = "audio";
  else if (mime.contains("pdf"))
    icon = "PDF";
  else if (mime.contains("zip") || mime.contains("tar") || mime.contains("7z"))
    icon = "archive";
  else if (mime.startsWith("text/") || mime.contains("json"))
    icon = "code";
  m["icon"] = icon;
  m["sizeLabel"] = dir       ? "Folder"
                   : hasSize ? QLocale().formattedDataSize(size)
                             : QString("Unavailable");
  if (path) {
    struct stat s{};
    if (lstat(path, &s) == 0) {
      m["uid"] = s.st_uid;
      m["gid"] = s.st_gid;
      m["permissions"] = QString::number(s.st_mode & 07777, 8);
      m["owner"] = str(
          g_file_info_get_attribute_string(info, G_FILE_ATTRIBUTE_OWNER_USER));
      m["group"] = str(
          g_file_info_get_attribute_string(info, G_FILE_ATTRIBUTE_OWNER_GROUP));
    }
  }
  g_free(uri);
  g_free(path);
  return m;
}
static constexpr auto attributes =
    "standard::*,time::*,unix::*,owner::*,id::filesystem,trash::*";
QVariantMap fileMetadata(const QString &uri) {
  GFile *f = g_file_new_for_uri(fileUri(uri).toUtf8().constData());
  GError *e = nullptr;
  GFileInfo *i = g_file_query_info(
      f, attributes, G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS, nullptr, &e);
  QVariantMap m =
      i ? metadata(f, i)
        : QVariantMap{{"error", str(e ? e->message : "Metadata unavailable")}};
  if (i)
    g_object_unref(i);
  if (e)
    g_error_free(e);
  g_object_unref(f);
  return m;
}
DirectoryModel::DirectoryModel(QObject *p) : QAbstractListModel(p) {
  m_pool.setMaxThreadCount(2);
  m_debounce.setSingleShot(true);
  m_debounce.setInterval(220);
  m_deadline.setSingleShot(true);
  m_deadline.setInterval(30000);
  connect(&m_deadline, &QTimer::timeout, this, &DirectoryModel::cancel);
  connect(&m_debounce, &QTimer::timeout, this, &DirectoryModel::refresh);
  connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this,
          [this] { m_debounce.start(); });
}
DirectoryModel::~DirectoryModel() {
  cancel();
  m_pool.clear();
  m_pool.waitForDone();
}
QVariant DirectoryModel::data(const QModelIndex &i, int role) const {
  return role == Entry && i.row() >= 0 && i.row() < m_entries.size()
             ? QVariant(m_entries[i.row()])
             : QVariant();
}
QVariantMap DirectoryModel::get(int row) const {
  return row >= 0 && row < m_entries.size() ? m_entries[row] : QVariantMap();
}
void DirectoryModel::setLocation(const QString &s) {
  auto u = fileUri(s);
  if (u == m_location)
    return;
  m_location = u;
  m_query.clear();
  refresh();
}
void DirectoryModel::setQuery(const QString &s) {
  if (s == m_query)
    return;
  m_query = s;
  m_debounce.start();
  emit changed();
}
void DirectoryModel::setHidden(bool b) {
  if (b != m_hidden) {
    m_hidden = b;
    refresh();
  }
}
void DirectoryModel::setRecursive(bool b) {
  if (b != m_recursive) {
    m_recursive = b;
    refresh();
  }
}
void DirectoryModel::setSort(int v) {
  if (v != m_sort) {
    m_sort = v;
    refresh();
  }
}
void DirectoryModel::setDescending(bool b) {
  if (b != m_descending) {
    m_descending = b;
    refresh();
  }
}
void DirectoryModel::cancel() {
  if (m_cancel)
    *m_cancel = true;
  if (m_ioCancel)
    g_cancellable_cancel(G_CANCELLABLE(m_ioCancel.get()));
}
QString DirectoryModel::parentLocation() const {
  GFile *f = g_file_new_for_uri(m_location.toUtf8());
  GFile *p = g_file_get_parent(f);
  char *u = p ? g_file_get_uri(p) : nullptr;
  QString result = u ? str(u) : m_location;
  g_free(u);
  if (p)
    g_object_unref(p);
  g_object_unref(f);
  return result;
}
void DirectoryModel::refresh() {
  m_debounce.stop();
  cancel();
  m_pool.clear();
  const auto generation = ++m_generation;
  m_cancel = std::make_shared<std::atomic_bool>(false);
  auto stop = m_cancel;
  m_ioCancel = std::shared_ptr<void>(g_cancellable_new(),
                                     [](void *p) { g_object_unref(p); });
  auto io = m_ioCancel;
  m_deadline.start();
  if (!m_watcher.directories().isEmpty())
    m_watcher.removePaths(m_watcher.directories());
  if (!localPath(m_location).isEmpty() &&
      !m_watcher.addPath(localPath(m_location)))
    m_error = "Live monitoring unavailable; use Refresh.";
  else
    m_error.clear();
  const QString uri = m_location, query = m_query;
  const bool hidden = m_hidden, recursive = m_recursive, desc = m_descending;
  const int sort = m_sort;
  const auto filters = m_filters;
  m_busy = true;
  emit changed();
  m_pool.start(QRunnable::create([this, generation, stop, io, uri, query,
                                  hidden, recursive, desc, sort, filters] {
    QList<QVariantMap> entries;
    QString error;
    QStringList pending{uri};
    int visited = 0;
    while (!pending.isEmpty() && !stop->load() && visited++ < 100000) {
      const QString current = pending.takeLast();
      GFile *f = g_file_new_for_uri(current.toUtf8());
      GError *e = nullptr;
      GFileEnumerator *en = g_file_enumerate_children(
          f, attributes, G_FILE_QUERY_INFO_NOFOLLOW_SYMLINKS,
          G_CANCELLABLE(io.get()), &e);
      if (!en) {
        if (e) {
          error = str(e->message);
          g_error_free(e);
        }
        g_object_unref(f);
        continue;
      }
      while (!stop->load()) {
        GFileInfo *i =
            g_file_enumerator_next_file(en, G_CANCELLABLE(io.get()), &e);
        if (!i)
          break;
        const bool isHidden =
            g_file_info_has_attribute(i, G_FILE_ATTRIBUTE_STANDARD_IS_HIDDEN)
                ? g_file_info_get_is_hidden(i)
                : str(g_file_info_get_name(i)).startsWith('.');
        if (!hidden && isHidden) {
          g_object_unref(i);
          continue;
        }
        GFile *child = g_file_get_child(f, g_file_info_get_name(i));
        auto m = metadata(child, i);
        if (recursive && m["directory"].toBool() && !m["symlink"].toBool())
          pending.append(m["uri"].toString());
        bool matches =
            query.isEmpty() ||
            m["name"].toString().contains(query, Qt::CaseInsensitive) ||
            m["mime"].toString().contains(query, Qt::CaseInsensitive);
        if (!filters.value("extension").toString().isEmpty())
          matches =
              matches &&
              QFileInfo(m["name"].toString())
                      .suffix()
                      .compare(filters["extension"].toString().remove('.'),
                               Qt::CaseInsensitive) == 0;
        if (!filters.value("mime").toString().isEmpty())
          matches = matches &&
                    m["mime"].toString().startsWith(filters["mime"].toString(),
                                                    Qt::CaseInsensitive);
        if (filters.contains("minimum"))
          matches = matches &&
                    m["size"].toLongLong() >= filters["minimum"].toLongLong();
        if (filters.contains("maximum"))
          matches = matches &&
                    m["size"].toLongLong() <= filters["maximum"].toLongLong();
        const QString modified = m["modified"].toString().left(10);
        if (!filters.value("after").toString().isEmpty())
          matches = matches && modified >= filters["after"].toString();
        if (!filters.value("before").toString().isEmpty())
          matches = matches && modified <= filters["before"].toString();
        if (matches)
          entries.append(m);
        g_object_unref(child);
        g_object_unref(i);
        if (entries.size() >= 100000) {
          error = "Result limit reached (100,000). Narrow the search.";
          *stop = true;
          break;
        }
      }
      if (e) {
        error = str(e->message);
        g_error_free(e);
      }
      g_object_unref(en);
      g_object_unref(f);
    }
    std::stable_sort(
        entries.begin(), entries.end(),
        [sort, desc](const auto &a, const auto &b) {
          if (a["directory"].toBool() != b["directory"].toBool())
            return a["directory"].toBool();
          int c = 0;
          if (sort == 1) {
            auto x = a["size"].toLongLong(), y = b["size"].toLongLong();
            c = x < y ? -1 : x > y ? 1 : 0;
          } else
            c = QString::compare(a[sort == 2   ? "mime"
                                   : sort == 3 ? "modified"
                                               : "name"]
                                     .toString(),
                                 b[sort == 2   ? "mime"
                                   : sort == 3 ? "modified"
                                               : "name"]
                                     .toString(),
                                 Qt::CaseInsensitive);
          if (!c)
            c = QString::compare(a["uri"].toString(), b["uri"].toString());
          return desc ? c > 0 : c < 0;
        });
    if (stop->load() && error.isEmpty())
      error = "Listing cancelled or timed out; results may be partial.";
    QMetaObject::invokeMethod(
        this,
        [this, generation, entries = std::move(entries), error]() mutable {
          if (generation != m_generation)
            return;
          m_deadline.stop();
          beginResetModel();
          m_entries = std::move(entries);
          endResetModel();
          m_busy = false;
          m_error = error;
          emit changed();
        },
        Qt::QueuedConnection);
  }));
}
