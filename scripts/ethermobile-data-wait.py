#!/usr/bin/python3
"""Wait for home-network packet service before starting the IPA data owner."""
import json
from pathlib import Path
import subprocess
import time
import ethermobile_data_status as status


class ConnectionFailure(RuntimeError):
    def __init__(self, code, detail):
        self.status_code = code
        self.safe_detail = detail
        super().__init__(code)


def main():
    status.update('modem', 'Próbuję połączyć: sprawdzam modem i kartę SIM…', reset=True)
    if Path('/etc/etherpocket/disk-identity').read_text().strip() != 'GM1920-548cb338-mobian-sda21':
        raise RuntimeError('Unsupported disk identity')
    deadline = time.monotonic() + 120
    reason = 'Nie wykryto modemu w ModemManager.'
    while time.monotonic() < deadline:
        result = subprocess.run(['mmcli', '-m', 'any', '-J'], capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            modem = json.loads(result.stdout)['modem']
            registration = modem.get('3gpp', {})
            generic = modem.get('generic', {})
            if generic.get('unlock-required') in ('sim-pin', 'sim-puk'):
                raise ConnectionFailure('SIM_LOCKED', 'Karta SIM wymaga kodu PIN lub PUK. Odblokuj ją w ustawieniach SIM.')
            if registration.get('registration-state') == 'roaming':
                raise ConnectionFailure('ROAMING_BLOCKED', 'Modem jest w roamingu. Adapter IPA nie zezwala na automatyczne połączenie w roamingu.')
            if registration.get('registration-state') == 'denied':
                raise ConnectionFailure('REGISTRATION_DENIED', 'Operator odmówił rejestracji modemu. Sprawdź kartę SIM i zasięg.')
            reason = 'Czekam na rejestrację w sieci operatora.'
            if registration.get('registration-state') == 'home' and registration.get('packet-service-state') == 'attached':
                state = subprocess.run(['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', 'qrtr0'], capture_output=True, text=True, timeout=10)
                if state.returncode == 0 and state.stdout.startswith('30 '):
                    status.update('ready', 'Modem zarejestrowany. Uruchamiam sesję danych IPA…')
                    print('Home-network packet service ready', flush=True)
                    return
                reason = 'NetworkManager zajmuje modem. Zakończ jego próbę połączenia; nie można uruchomić dwóch właścicieli danych.'
                status.update('network_owner', reason)
            elif registration.get('registration-state') == 'home':
                reason = 'Modem zarejestrowany, ale operator nie udostępnił jeszcze usługi pakietowej.'
                status.update('packet_service', reason)
            else:
                status.update('registration', reason)
        else:
            status.update('modem', reason)
        time.sleep(1)
    raise ConnectionFailure('REGISTRATION_TIMEOUT', 'Przekroczono limit 120 s. ' + reason)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(status.failure(error), flush=True)
        raise SystemExit(1)
