"""Bounded read-only libqmi Voice query; never starts or modifies a call."""
from pathlib import Path
import json,runpy
ROOT=Path(__file__).resolve().parent.parent
remote=runpy.run_path(str(ROOT/'scripts/check-etherphone-device.py'))['remote']
SOURCE=r'''
import gi,json,time
gi.require_version('Qmi','1.0');gi.require_version('Qrtr','1.0')
from gi.repository import Qmi,Qrtr,GLib
loop=GLib.MainLoop();refs={};report={'readOnly':True,'query':'QMI Voice Get All Call Info','callNumbersExported':False,'timestamp':time.time()}
def error(e):
 report['error']=str(e);loop.quit()
def released(dev,res):
 try:dev.release_client_finish(res)
 except GLib.Error:pass
 loop.quit()
def queried(client,res):
 try:
  out=client.get_all_call_info_finish(res);out.get_result();report['querySucceeded']=True
  try:report['callCount']=len(out.get_call_information())
  except GLib.Error:report['callCount']=None;report['callInfoFieldPresent']=False
 except GLib.Error as e:report['querySucceeded']=False;report['error']=str(e)
 refs['device'].release_client(client,Qmi.DeviceReleaseClientFlags.RELEASE_CID,3,None,released)
def allocated(dev,res):
 try:
  client=dev.allocate_client_finish(res);refs['client']=client
  client.get_all_call_info(None,5,None,queried)
 except GLib.Error as e:error(e)
def opened(dev,res):
 try:
  dev.open_finish(res);dev.allocate_client(Qmi.Service.VOICE,Qmi.CID_NONE,5,None,allocated)
 except GLib.Error as e:error(e)
def device_ready(obj,res):
 try:
  dev=Qmi.Device.new_from_node_finish(res);refs['device']=dev
  dev.open(Qmi.DeviceOpenFlags.NONE,5,None,opened)
 except GLib.Error as e:error(e)
def bus_ready(obj,res):
 try:
  bus=Qrtr.Bus.new_finish(res);refs['bus']=bus;node=bus.get_node(0)
  if node is None:raise RuntimeError('QRTR node 0 unavailable')
  Qmi.Device.new_from_node(node,None,device_ready)
 except (GLib.Error,RuntimeError) as e:error(e)
def timeout():report['error']='Bounded read-only query timed out';loop.quit();return False
GLib.timeout_add_seconds(25,timeout);Qrtr.Bus.new(2000,None,bus_ready);loop.run()
print(json.dumps(report,indent=2))
'''
if __name__=='__main__':
    report=json.loads(remote(SOURCE,timeout=35))
    (ROOT/'evidence/etherphone-voice-query.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
