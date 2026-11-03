"""Interactive management: credentials never appear in arguments or stdout."""
import argparse
import getpass
import json
import resource
from transport import call


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser(description='EtherCredentials protected management')
    parser.add_argument('operation', choices=['status', 'set', 'remove', 'prefer'])
    parser.add_argument('kind', nargs='?', choices=['system', 'pin', 'password'])
    args = parser.parse_args()
    request = dict(operation=args.operation, kind=args.kind)
    if args.operation != 'status':
        request['proof'] = getpass.getpass('Debian account password: ')
    if args.operation == 'set':
        request['new'] = getpass.getpass('New screen credential: ')
        request['confirmation'] = getpass.getpass('Confirm screen credential: ')
    if args.operation == 'remove' and input('Remove screen credential? Type REMOVE: ') != 'REMOVE':
        return
    try:
        print(json.dumps(call(request), indent=2))
    except (RuntimeError, OSError):
        parser.exit(1, 'Request rejected or backend unavailable; retain your recovery access.\n')


if __name__ == '__main__':
    main()
