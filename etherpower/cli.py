#!/usr/bin/python3
"""etherpower state|history HOURS|processes|profile NAME [CUSTOM_JSON]|configure JSON|refresh|restore|action NAME|report"""
import dbus,json,sys
api=dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherPower1','/com/etherneco/EtherPower1'),'com.etherneco.EtherPower1')
args=sys.argv[1:] or ['state']
if args[0]=='state':print(str(api.GetState()))
elif args[0]=='history':print(str(api.GetHistory(dbus.UInt32(int(args[1])))))
elif args[0]=='processes':print(str(api.GetProcessImpact(timeout=30)))
elif args[0]=='profile':api.ApplyProfile(args[1],args[2] if len(args)>2 else '',timeout=90)
elif args[0]=='configure':api.Configure(args[1],timeout=90)
elif args[0]=='refresh':api.Refresh()
elif args[0]=='restore':api.RestoreOriginal(timeout=90)
elif args[0]=='action':api.PowerAction(args[1],timeout=90)
elif args[0]=='report':
 print(json.dumps({'schemaVersion':1,'state':json.loads(str(api.GetState())),
  'limitations':'Battery terminal and USB input estimates are separate; physical suspend remains gated by verified recovery'},indent=2))
else:raise SystemExit(__doc__)
