"""Small control/diagnostic client. Raw samples require approved subscriptions."""
import argparse,json
import dbus
NAME='com.etherneco.EtherSensors1'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('command',choices=['state','list','capabilities','orientation','motion','diagnostics'])
 args=parser.parse_args()
 methods=dict(state='GetState',list='ListSensors',capabilities='GetCapabilities',orientation='GetOrientation',motion='GetMotionState',diagnostics='ExportDiagnostics')
 try:
  api=dbus.Interface(dbus.SessionBus().get_object(NAME,'/com/etherneco/EtherSensors1'),NAME)
  print(json.dumps(json.loads(str(getattr(api,methods[args.command])())),indent=2))
 except dbus.DBusException as e:parser.exit(1,str(e)+'\n')
if __name__=='__main__':main()
