#pragma once
#include "media.h"
#include <QQuickWindow>
#include <QGuiApplication>
#include <QScreen>
#include <QDir>
#include <QJsonDocument>
#include <QFile>
#include <QTimer>
#include <QDebug>
#include <X11/Xlib.h>
#include <X11/XF86keysym.h>
#include <X11/extensions/XTest.h>

// Explicit opt-in test against the real desktop. Restores the original volume.
class MediaTest : public QObject {
public:
    MediaTest(Media *media,QQuickWindow *root):QObject(media),media(media),root(root){
        d=XOpenDisplay(nullptr);dir=QDir::homePath()+"/ethershell-validation";QDir().mkpath(dir);
        connect(media,&Media::saved,this,[this](const QString &path){paths<<path;});
        QTimer::singleShot(1800,this,[this]{oldVolume=this->media->volume();this->media->setVolume(50);next(700,[this]{volume();});});
    }
private:
    Media *media;QQuickWindow *root;QQuickWindow marker;Display *d=nullptr;QString dir;QStringList paths;QVariantMap results;int oldVolume=50;
    void next(int ms,std::function<void()> action){QTimer::singleShot(ms,this,action);}
    void key(KeySym key,bool down){XTestFakeKeyEvent(d,XKeysymToKeycode(d,key),down,CurrentTime);XFlush(d);}
    void volume(){
        results["volume_set"]=media->volume()==50;
        key(XF86XK_AudioLowerVolume,true);next(60,[this]{key(XF86XK_AudioLowerVolume,false);next(700,[this]{
            qInfo()<<"Volume down actual"<<media->volume();results["volume_down_one_step"]=media->volume()==45;
            key(XF86XK_AudioRaiseVolume,true);next(60,[this]{key(XF86XK_AudioRaiseVolume,false);next(700,[this]{
                results["volume_up_one_step"]=media->volume()==50;firstChord();
            });});
        });});
    }
    void firstChord(){
        marker.setTitle("EtherShell media test marker");marker.setColor(QColor("#ed17ca"));marker.setGeometry(150,350,160,160);marker.show();marker.raise();marker.requestActivate();
        next(350,[this]{
            key(XF86XK_PowerOff,true);next(60,[this]{key(XF86XK_AudioLowerVolume,true);next(180,[this]{
                bool visible=false;for(auto *w:QGuiApplication::allWindows())if(w->title()=="EtherShell Screenshot Flash"&&w->isVisible())visible=true;
                results["flash_after_save"]=visible;
                next(700,[this]{key(XF86XK_PowerOff,false);key(XF86XK_AudioLowerVolume,false);next(350,[this]{
                    results["power_down_one_capture"]=paths.size()==1;
                    qInfo()<<"Chord actual"<<media->volume()<<paths.size();results["chord_keeps_volume"]=media->volume()==50;
                    if(!paths.isEmpty()){
                        QImage image(paths.first());XWindowAttributes attr{};XGetWindowAttributes(d,DefaultRootWindow(d),&attr);
                        results["whole_root_dimensions"]=image.size()==QSize(attr.width,attr.height);
                        QPoint center=marker.geometry().center()*marker.devicePixelRatio();results["captures_other_window"]=image.valid(center)&&image.pixelColor(center)==QColor("#ed17ca");
                        QFile::remove(dir+"/media-full-screen.png");QFile::copy(paths.first(),dir+"/media-full-screen.png");
                    }
                    secondChord();
                });});
            });});
        });
    }
    void secondChord(){
        key(XF86XK_AudioLowerVolume,true);next(60,[this]{key(XF86XK_PowerOff,true);next(800,[this]{
            key(XF86XK_AudioLowerVolume,false);next(80,[this]{key(XF86XK_PowerOff,false);next(350,[this]{
                results["reverse_chord_one_capture"]=paths.size()==2;
                qInfo()<<"Reverse chord actual"<<media->volume()<<paths.size();results["reverse_chord_keeps_volume"]=media->volume()==50;
                marker.hide();key(XF86XK_AudioLowerVolume,true);next(1000,[this]{key(XF86XK_AudioLowerVolume,false);next(600,[this]{
                    results["held_volume_repeats"]=media->volume()<=35&&media->volume()>=0;
                    media->setVolume(100);next(500,[this]{key(XF86XK_AudioRaiseVolume,true);next(60,[this]{key(XF86XK_AudioRaiseVolume,false);next(500,[this]{results["volume_capped_at_100"]=media->volume()==100;gallery();});});});
                });});
            });});
        });});
    }
    void gallery(){
        root->showNormal();root->raise();root->requestActivate();root->setProperty("page","gallery");media->scan();
        next(800,[this]{
            results["gallery_includes_new_capture"]=false;
            for(auto image:media->images())if(paths.contains(image.toMap()["path"].toString()))results["gallery_includes_new_capture"]=true;
            results["gallery_render"]=root->grabWindow().save(dir+"/media-gallery.png");
            auto *view=root->findChild<QObject*>("gallery");results["gallery_page_exists"]=view!=nullptr;
            if(view)view->setProperty("selected",0);
            next(900,[this]{
                auto *image=root->findChild<QObject*>("galleryImage");results["gallery_preview_loaded"]=image&&image->property("status").toInt()==1;
                root->grabWindow().save(dir+"/media-preview.png");media->setVolume(oldVolume);
                next(500,[this]{
                    results["volume_restored"]=media->volume()==oldVolume;
                    for(const auto &path:paths)QFile::remove(path);media->scan();
                    bool passed=true;for(auto value:results)passed=passed&&value.toBool();results["passed"]=passed;
                    QFile file(dir+"/media-results.json");file.open(QIODevice::WriteOnly);file.write(QJsonDocument::fromVariant(results).toJson());file.close();
                    XCloseDisplay(d);QGuiApplication::exit(passed?0:6);
                });
            });
        });
    }
};
