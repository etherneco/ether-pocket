#pragma once
#include <QMutex>
#include <QObject>
#include <QThreadPool>
#include <QVariantList>
#include <QWaitCondition>
#include <atomic>
#include <memory>

class Operations : public QObject {
  Q_OBJECT
  Q_PROPERTY(QVariantList jobs READ jobs NOTIFY changed)
  Q_PROPERTY(QVariantMap conflict READ conflict NOTIFY conflictChanged)
public:
  explicit Operations(QObject *parent = nullptr);
  ~Operations() override;
  QVariantList jobs() const { return m_jobs; }
  QVariantMap conflict() const { return m_conflict; }
  Q_INVOKABLE int submit(const QString &action, const QStringList &sources,
                         const QString &destination = QString(),
                         const QString &name = QString());
  Q_INVOKABLE void cancel(int id);
  Q_INVOKABLE void resolve(const QString &decision, bool remaining);
signals:
  void changed();
  void conflictChanged();
  void completed();

private:
  struct Task;
  QThreadPool m_pool;
  QVariantList m_jobs;
  QVariantMap m_conflict;
  QHash<int, std::shared_ptr<Task>> m_tasks;
  int m_next = 0;
  QMutex m_mutex;
  QWaitCondition m_answer;
  QString m_decision;
  bool m_remaining = false;
  void update(int id, const QVariantMap &values);
  QString ask(const QString &source, const QString &destination,
              const std::shared_ptr<Task> &);
  void run(const std::shared_ptr<Task> &);
  void saveJobs();
};
