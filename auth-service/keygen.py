"""Write a new Ed25519 signing key for the auth service: `make auth-key`.

Runs in the auth image as root, with no network, so the only requirement is
Docker. The file belongs to the service's user (uid 10001) with mode 0400:
Compose mounts file secrets as they are and ignores uid, gid and mode, so the
file must already suit the container (ADR 0033). It refuses to overwrite an
existing key; rotating is a deliberate step (ADR 0033's runbook).
"""

import os
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SERVICE_UID = 10001


def main(path: str) -> None:
    pem = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    # O_EXCL: never replace a key by accident. 0o400 from the first byte, so
    # the key is never briefly readable by anyone else.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    try:
        os.write(fd, pem)
        os.fchown(fd, SERVICE_UID, SERVICE_UID)
    finally:
        os.close(fd)
    print(f"Wrote {path}, readable only by uid {SERVICE_UID}.")


if __name__ == "__main__":
    main(sys.argv[1])
