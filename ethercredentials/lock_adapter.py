"""EtherLock conversation protocol adapter; only the existing locker can unlock."""
import json
import resource
import sys
from transport import call


def emit(value):
    print(json.dumps(value), flush=True)


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        state = call(dict(operation='status'))
        kind = 'system' if sys.argv[1:] == ['--system'] else state['preferred']
        emit(dict(event='prompt', echo=False, method=kind))
        line = sys.stdin.buffer.readline(131073)
        if len(line) > 131072 or not line.endswith(b'\n'):
            raise ValueError('Invalid input')
        response = json.loads(line)['response']
        result = call(dict(operation='verify', kind=kind, proof=response))
        success = result.get('authenticated') is True
    except (OSError, RuntimeError, ValueError, KeyError):
        success = False
    emit(dict(event='result', success=success))
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
