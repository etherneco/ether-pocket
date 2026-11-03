#include "files.h"
#include "operations.h"
#include "services.h"
#include <QCache>
#include <QCommandLineParser>
#include <QFileInfo>
#include <QGuiApplication>
#include <QImageReader>
#include <QMutex>
#include <QMutexLocker>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QTimer>
#include <QUrl>
#include <unistd.h>

class ThumbnailProvider : public QQuickImageProvider {
  QMutex mutex;
  QCache<QString, QImage> cache{32768};

public:
  ThumbnailProvider()
      : QQuickImageProvider(
            QQuickImageProvider::Image,
            QQmlImageProviderBase::ForceAsynchronousImageLoading) {}
  QImage requestImage(const QString &id, QSize *size,
                      const QSize &requested) override {
    QString path = QUrl::fromPercentEncoding(id.toUtf8());
    QFileInfo f(path);
    QSize wanted = requested.isValid() ? requested : QSize(256, 192);
    wanted = wanted.boundedTo(QSize(1024, 1024));
    const QString key = path +
                        QString::number(f.lastModified().toMSecsSinceEpoch()) +
                        QString::number(wanted.width()) + "x" +
                        QString::number(wanted.height());
    {
      QMutexLocker lock(&mutex);
      if (auto *img = cache.object(key)) {
        if (size)
          *size = img->size();
        return *img;
      }
    }
    if (f.isSymLink() || !f.isFile() || f.size() > 32 * 1024 * 1024)
      return {};
    QImageReader reader(path);
    reader.setAutoTransform(true);
    const QSize original = reader.size();
    if (!original.isValid() ||
        qint64(original.width()) * original.height() > 64000000)
      return {};
    reader.setScaledSize(original.scaled(wanted, Qt::KeepAspectRatio));
    QImage img = reader.read();
    if (size)
      *size = img.size();
    if (!img.isNull()) {
      QMutexLocker lock(&mutex);
      cache.insert(key, new QImage(img), int(img.sizeInBytes() / 1024) + 1);
    }
    return img;
  }
};
int main(int argc, char **argv) {
  if (geteuid() == 0) {
    fprintf(stderr, "Run EtherFiles as your normal desktop user.\n");
    return 1;
  }
  QQuickStyle::setStyle("Basic");
  QGuiApplication app(argc, argv);
  app.setOrganizationName("Etherneco");
  app.setApplicationName("EtherFiles");
  app.setApplicationVersion("0.1.1");
  app.setDesktopFileName("etherfiles");
  QCommandLineParser parser;
  parser.setApplicationDescription("Native touch-first Linux file manager");
  parser.addHelpOption();
  parser.addVersionOption();
  parser.addPositionalArgument("location", "Directory path or GIO URI to open",
                               "[location]");
  parser.addOption({"screenshot", "Save an isolated render and exit", "png"});
  parser.addOption({"pocket", "Use Pocket layout"});
  parser.addOption({"desktop", "Use EtherAir desktop layout"});
  parser.addOption({"dark", "Use dark theme"});
  parser.addOption({"split", "Show both panes"});
  parser.process(app);
  Operations operations;
  Services services;
  qmlRegisterType<DirectoryModel>("EtherFiles", 1, 0, "DirectoryModel");
  QQmlApplicationEngine engine;
  engine.rootContext()->setContextProperty("Operations", &operations);
  engine.rootContext()->setContextProperty("Services", &services);
  const QString initial = parser.positionalArguments().isEmpty()
                              ? QString()
                              : fileUri(parser.positionalArguments().first());
  engine.rootContext()->setContextProperty("InitialLocation", initial);
  engine.addImageProvider("thumb", new ThumbnailProvider);
  engine.load(QUrl("qrc:/qml/Main.qml"));
  if (engine.rootObjects().isEmpty())
    return 2;
  auto *root = engine.rootObjects()[0];
  if (parser.isSet("pocket")) {
    root->setProperty("presentation", "pocket");
    root->setProperty("width", 430);
    root->setProperty("height", 860);
  }
  if (parser.isSet("desktop"))
    root->setProperty("presentation", "desktop");
  if (parser.isSet("dark"))
    root->setProperty("dark", true);
  if (parser.isSet("split"))
    root->setProperty("split", true);
  // Isolated render smoke mode uses the real filesystem and exits without
  // performing operations.
  if (parser.isSet("screenshot")) {
    QString output = parser.value("screenshot");
    QTimer::singleShot(1800, &app, [&engine, &app, output] {
      auto *w = qobject_cast<QQuickWindow *>(engine.rootObjects()[0]);
      app.exit(w && w->grabWindow().save(output) ? 0 : 3);
    });
  }
  return app.exec();
}
