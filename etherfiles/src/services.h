#pragma once
#include <QDBusArgument>
#include <QDBusObjectPath>
#include <QObject>
#include <QThreadPool>
#include <QVariantList>
#include <QVariantMap>
#include <atomic>
#include <functional>
#include <memory>
using StorageInterfaces = QMap<QString, QVariantMap>;
using StorageObjects = QMap<QDBusObjectPath, StorageInterfaces>;
Q_DECLARE_METATYPE(StorageInterfaces)
Q_DECLARE_METATYPE(StorageObjects)

class Services : public QObject {
  Q_OBJECT
  Q_PROPERTY(QString home READ home CONSTANT)
  Q_PROPERTY(QVariantList places READ places CONSTANT)
  Q_PROPERTY(QVariantList devices READ devices NOTIFY devicesChanged)
  Q_PROPERTY(QVariantList bookmarks READ bookmarks NOTIFY bookmarksChanged)
  Q_PROPERTY(QVariantList removable READ removable NOTIFY devicesChanged)
  Q_PROPERTY(QVariantMap preview READ preview NOTIFY previewChanged)
  Q_PROPERTY(QString message READ message NOTIFY messageChanged)
public:
  explicit Services(QObject *p = nullptr);
  ~Services() override;
  QString home() const;
  QVariantList places() const;
  QVariantList devices() const;
  QVariantList bookmarks() const;
  QVariantList removable() const { return m_removable; }
  QVariantMap preview() const { return m_preview; }
  QString message() const { return m_message; }
  Q_INVOKABLE void inspect(const QString &uri);
  Q_INVOKABLE void hash(const QString &uri, bool sha512 = false);
  Q_INVOKABLE void open(const QString &uri);
  Q_INVOKABLE QVariantList applications(const QString &uri) const;
  Q_INVOKABLE void openWith(const QString &uri, const QString &applicationId);
  Q_INVOKABLE void terminal(const QString &uri);
  Q_INVOKABLE void clipboard(const QStringList &uris, bool cut);
  Q_INVOKABLE QVariantMap paste() const;
  Q_INVOKABLE void copyText(const QString &text);
  Q_INVOKABLE void bookmark(const QString &uri);
  Q_INVOKABLE void refreshDevices();
  Q_INVOKABLE void storageAction(const QString &block, const QString &action);
  Q_INVOKABLE void connectNetwork(const QString &uri, const QString &username,
                                  const QString &password);
  Q_INVOKABLE void extract(const QString &uri, const QString &destination);
  Q_INVOKABLE void createArchive(const QStringList &uris,
                                 const QString &destination,
                                 const QString &name);
  Q_INVOKABLE void cancelPreview();
  Q_INVOKABLE void cancelTask();
  void notify(const QString &text);
signals:
  void previewChanged();
  void messageChanged();
  void devicesChanged();
  void bookmarksChanged();
  void networkReady(QString uri);
private slots:
  void storageChanged();

private:
  QThreadPool m_pool;
  QThreadPool m_tasks;
  QVariantMap m_preview;
  QVariantList m_devices;
  QVariantList m_removable;
  QString m_message;
  quint64 m_generation = 0;
  std::shared_ptr<std::atomic_bool> m_previewCancel, m_taskCancel;
  void task(std::function<QString(std::atomic_bool &)> work);
};
