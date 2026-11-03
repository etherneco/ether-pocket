#!/usr/bin/python3
"""Public registry client: etherhardware state|capabilities|capability ID|refresh
|diagnose CATEGORY|report json|text|history [QUERY [COMPONENT]]|clear-history.
Reports are written to stdout; shell redirection chooses the user's destination.
"""
import sys
import dbus


def main():
    args = sys.argv[1:] or ['state']
    api = dbus.Interface(dbus.SystemBus().get_object('com.etherneco.EtherHardware1', '/com/etherneco/EtherHardware1'), 'com.etherneco.EtherHardware1')
    actions = {'state': ('GetState', []), 'capabilities': ('GetCapabilities', []),
        'capability': ('GetCapability', args[1:2]), 'refresh': ('Refresh', args[1:2] or ['all']),
        'diagnose': ('RunDiagnostics', args[1:2] or ['all']), 'report': ('ExportReport', args[1:2] or ['json']),
        'history': ('GetHistory', [(args + ['', ''])[1], (args + ['', ''])[2]]),
        'clear-history': ('ClearHistory', [])}
    if args[0] not in actions:
        raise SystemExit(__doc__)
    method, values = actions[args[0]]
    result = getattr(api, method)(*values, timeout=65)
    if result is not None:
        print(str(result))


if __name__ == '__main__':
    main()
