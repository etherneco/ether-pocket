"""Public, credential-free progress for the downstream IPA data owner."""
import json
import os
from pathlib import Path
import time

PATH = Path('/run/ethermobile-data-status.json')
BOOT = Path('/proc/sys/kernel/random/boot_id')


def read():
    try:
        data = json.loads(PATH.read_text())
        return data if data.get('boot') == BOOT.read_text().strip() else {}
    except (OSError, ValueError):
        return {}


def update(stage, message, state='connecting', code='', detail='', reset=False, **values):
    previous = {} if reset else read()
    now = time.time()
    history = previous.get('history', [])
    if not history or history[-1].get('stage') != stage or history[-1].get('message') != message:
        history = (history + [dict(stage=stage, message=message, time=now)])[-20:]
    data = dict(schema=1, boot=BOOT.read_text().strip(), state=state, stage=stage,
                message=message, code=code, detail=detail, updated=now,
                started=previous.get('started', now), history=history, **values)
    temporary = PATH.with_suffix('.new')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o644)
    with os.fdopen(descriptor, 'w') as output:
        json.dump(data, output, ensure_ascii=True)
        os.fchmod(output.fileno(), 0o644)
    temporary.replace(PATH)


def failure(error):
    previous = read()
    code = getattr(error, 'status_code', '') or type(error).__name__
    detail = getattr(error, 'safe_detail', '')
    numeric = getattr(error, 'code', None)
    if isinstance(numeric, int):
        code = 'QMI_' + str(numeric)
        reasons = {14: 'Modem odrzucił zestawienie sesji (CallFailed).',
                   48: 'Modem odrzucił format danych (InvalidArgument).'}
        detail = detail or reasons.get(numeric, 'Modem odrzucił żądanie; kod protokołu: ' + str(numeric))
    if not detail:
        detail = 'Sprawdź kartę SIM, zasięg, konfigurację APN i gotowość modemu. Nie ponowiono próby automatycznie.'
    message = 'Nie udało się połączyć: ' + previous.get('message', 'uruchamianie transmisji danych').rstrip('.')
    update(previous.get('stage', 'startup'), message, state='failed', code=code, detail=detail)
    return message + ' [' + code + '] ' + detail


def finish_unit():
    previous = read()
    result = os.environ.get('SERVICE_RESULT', 'success')
    if previous.get('state') == 'failed':
        return
    if result != 'success':
        update(previous.get('stage', 'startup'), 'Usługa transmisji danych zakończyła się błędem.',
               state='failed', code='SERVICE_' + result.upper().replace('-', '_'),
               detail='Etap: ' + previous.get('message', 'uruchamianie') + '. Sprawdź modem i spróbuj ponownie.')
    else:
        update('disconnected', 'Transmisja danych rozłączona.', state='disconnected')


if __name__ == '__main__':
    finish_unit()
