#pragma once
#include <QAbstractListModel>
#include <QFileSystemWatcher>
#include <QThreadPool>
#include <QTimer>
#include <QVariantMap>
#include <atomic>
#include <memory>

// URI-valued paths keep GIO local, Trash and GVfs backends interchangeable.
QString fileUri(const QString &input);
QString localPath(const QString &uri);
QVariantMap fileMetadata(const QString &uri);

class DirectoryModel : public QAbstractListModel {
  Q_OBJECT
  Q_PROPERTY(QString location READ location WRITE setLocation NOTIFY changed)
  Q_PROPERTY(QString query READ query WRITE setQuery NOTIFY changed)
  Q_PROPERTY(bool hidden READ hidden WRITE setHidden NOTIFY changed)
  Q_PROPERTY(bool recursive READ recursive WRITE setRecursive NOTIFY changed)
  Q_PROPERTY(int sort READ sort WRITE setSort NOTIFY changed)
  Q_PROPERTY(bool descending READ descending WRITE setDescending NOTIFY changed)
  Q_PROPERTY(QVariantMap filters READ filters WRITE setFilters NOTIFY changed)
  Q_PROPERTY(bool busy READ busy NOTIFY changed)
  Q_PROPERTY(QString error READ error NOTIFY changed)
  Q_PROPERTY(int count READ rowCount NOTIFY changed)
public:
  enum Roles { Entry = Qt::UserRole + 1 };
  explicit DirectoryModel(QObject *parent = nullptr);
  ~DirectoryModel() override;
  int rowCount(const QModelIndex &parent = {}) const override {
    return parent.isValid() ? 0 : m_entries.size();
  }
  QVariant data(const QModelIndex &, int role) const override;
  QHash<int, QByteArray> roleNames() const override {
    return {{Entry, "entry"}};
  }
  QString location() const { return m_location; }
  QString query() const { return m_query; }
  QString error() const { return m_error; }
  bool hidden() const { return m_hidden; }
  bool recursive() const { return m_recursive; }
  bool descending() const { return m_descending; }
  bool busy() const { return m_busy; }
  QVariantMap filters() const { return m_filters; }
  int sort() const { return m_sort; }
  void setLocation(const QString &);
  void setQuery(const QString &);
  void setHidden(bool);
  void setRecursive(bool);
  void setSort(int);
  void setDescending(bool);
  void setFilters(const QVariantMap &v) {
    m_filters = v;
    refresh();
  }
  Q_INVOKABLE void refresh();
  Q_INVOKABLE void cancel();
  Q_INVOKABLE QVariantMap get(int row) const;
  Q_INVOKABLE QString parentLocation() const;
signals:
  void changed();

private:
  QList<QVariantMap> m_entries;
  QVariantMap m_filters;
  QString m_location, m_query, m_error;
  bool m_hidden = false, m_recursive = false, m_descending = false,
       m_busy = false;
  int m_sort = 0;
  quint64 m_generation = 0;
  QThreadPool m_pool;
  QFileSystemWatcher m_watcher;
  QTimer m_debounce;
  QTimer m_deadline;
  std::shared_ptr<void> m_ioCancel;
  std::shared_ptr<std::atomic_bool> m_cancel;
};
