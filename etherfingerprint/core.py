"""Fail-closed fingerprint provider. Never opens sensor or secure-world devices."""
from abc import ABC, abstractmethod
from pathlib import Path
import datetime


class BackendUnavailable(RuntimeError):
    pass


class HardwareProvider(ABC):
    """Only trusted adapters may implement operations; callers cannot inject results.

    A future adapter needs reviewed local-session authorization, recent primary
    authentication for management, operation ownership/cancellation, nonce-bound
    trusted assertions and bounded retries before EtherLock can consume it.
    """
    @abstractmethod
    def status(self):
        raise NotImplementedError

    def enroll(self, *args, **kwargs):
        raise BackendUnavailable('Secure enrollment backend unavailable; use PIN/password')

    def verify(self, *args, **kwargs):
        raise BackendUnavailable('Secure verification backend unavailable; use PIN/password')

    def manage(self, *args, **kwargs):
        raise BackendUnavailable('Biometric identity management is disabled')

    def cancel(self):
        # No hardware resources or illumination are acquired by this provider.
        return None


class DiagnosticProvider(HardwareProvider):
    def __init__(self, root='/'):
        self.root = Path(root)

    def path(self, name):
        return self.root / name.lstrip('/')

    def status(self):
        device = self.path('/sys/bus/platform/devices/soc:goodix_fp')
        try:
            compatible = (device/'of_node/compatible').read_bytes()[:256].split(b'\0')
        except OSError:
            compatible = []
        detected = b'goodix,fingerprint' in compatible
        driver = None
        try:
            link = device/'driver'
            if link.is_symlink():
                driver = link.resolve(strict=True).name
        except OSError:
            pass
        return dict(schemaVersion=1, ready=True,
            observedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            state='Blocked' if detected else 'Not tested', detected=detected,
            vendor='Goodix' if detected else 'Unknown', model='Not verified',
            deviceInterface='/dev/goodix_fp' if self.path('/dev/goodix_fp').exists() else None,
            driver=driver, firmwareStatus='Not verified', backend='Diagnostics only',
            secureServiceAvailable=False, secureTransportNodePresent=self.path('/dev/qseecom').exists(),
            illuminationSupported=False, illuminationStatus='Not verified; no display writes',
            sensorGeometry=None, operational=False, enabled=False,
            canEnroll=False, canVerify=False, canManage=False, hardwareTestSupported=False,
            canList=False, enrolledCount=None, enrollments=None,
            securityPolicy={'primaryCredentialRequired': True, 'fingerprintUnlockAvailable': False,
                'managementAvailable': False, 'timeoutConfigurable': False,
                'privilegedAuthorizationAvailable': False},
            enrollmentState='Unknown; protected storage is not inspected',
            primaryAuthenticationRequired=True,
            lastError='No verified trusted biometric adapter; PIN/password required',
            powerState='Inactive; no sensor handles, illumination or polling')
