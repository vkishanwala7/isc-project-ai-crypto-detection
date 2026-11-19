"""Development-only key material.

* A local "VERIFRAME Local Demo Root CA" (ECDSA P-256) that issues
* a C2PA signing certificate "VERIFRAME Demo Signer" (ES256, EKU emailProtection), and
* an Ed25519 key pair for the supplementary detached-signature educational envelope.

All private keys live in `keys/` (git-ignored), are written with 0600 permissions and are never
returned by the API, stored in the database, or bundled into the frontend.
The root CA is NOT on the official C2PA trust list; it is trusted only by this verifier's local
demo trust policy.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.core.config import settings

ROOT_CERT = "demo_root_ca.pem"
ROOT_KEY = "demo_root_ca.key"
SIGNER_CHAIN = "demo_signer_chain.pem"
SIGNER_KEY = "demo_signer.key"
ED_PRIV = "ed25519_private.pem"
ED_PUB = "ed25519_public.pem"

_lock = threading.RLock()


def _write(path: Path, data: bytes, private: bool) -> None:
    path.write_bytes(data)
    os.chmod(path, 0o600 if private else 0o644)


def _pem_key(key) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def generate_demo_keys(keys_dir: Path | None = None, overwrite: bool = False) -> Path:
    keys_dir = keys_dir or settings.keys_dir
    keys_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(keys_dir, 0o700)
    if (keys_dir / SIGNER_KEY).exists() and not overwrite:
        return keys_dir
    now = dt.datetime.now(dt.timezone.utc)
    root_key = ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "VERIFRAME Local Demo Root CA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VERIFRAME Demo (ISC Team 16) - NOT PUBLICLY TRUSTED"),
    ])
    root = (
        x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name)
        .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    signer_key = ec.generate_private_key(ec.SECP256R1())
    signer_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "VERIFRAME Demo Signer"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Browser capture & signing service (demo)"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "VERIFRAME Demo (ISC Team 16)"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
    ])
    signer = (
        x509.CertificateBuilder().subject_name(signer_name).issuer_name(root_name)
        .public_key(signer_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(signer_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
        .sign(root_key, hashes.SHA256())
    )
    pem = lambda c: c.public_bytes(serialization.Encoding.PEM)  # noqa: E731
    _write(keys_dir / ROOT_CERT, pem(root), private=False)
    _write(keys_dir / ROOT_KEY, _pem_key(root_key), private=True)
    _write(keys_dir / SIGNER_CHAIN, pem(signer) + pem(root), private=False)
    _write(keys_dir / SIGNER_KEY, _pem_key(signer_key), private=True)
    ed = ed25519.Ed25519PrivateKey.generate()
    _write(keys_dir / ED_PRIV, _pem_key(ed), private=True)
    _write(keys_dir / ED_PUB, ed.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo), private=False)
    return keys_dir


@dataclass
class KeyMaterial:
    signer_chain_pem: bytes
    signer_key_pem: bytes
    root_cert_pem: bytes
    signer_cert: x509.Certificate
    root_cert: x509.Certificate
    ed_private: ed25519.Ed25519PrivateKey
    ed_public_raw: bytes

    @property
    def ed_key_id(self) -> str:
        return "vf-ed25519-" + hashlib.sha256(self.ed_public_raw).hexdigest()[:16]

    def signer_summary(self) -> dict:
        c = self.signer_cert
        cn = c.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        org = c.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
        return {
            "subject": f"{cn} — {org}",
            "subject_dn": c.subject.rfc4514_string(),
            "issuer": c.issuer.rfc4514_string(),
            "serial": format(c.serial_number, "x"),
            "not_before": c.not_valid_before_utc.isoformat(),
            "not_after": c.not_valid_after_utc.isoformat(),
            "sha256_fingerprint": c.fingerprint(hashes.SHA256()).hex(),
            "algorithm": "ES256 (ECDSA P-256 / SHA-256)",
            "type": "Local development signer (self-issued demo CA, not on the C2PA trust list)",
        }

    def root_summary(self) -> dict:
        c = self.root_cert
        return {"subject": c.subject.rfc4514_string(), "sha256_fingerprint": c.fingerprint(hashes.SHA256()).hex(),
                "not_after": c.not_valid_after_utc.isoformat()}


_cache: KeyMaterial | None = None


def load_keys(reload: bool = False) -> KeyMaterial:
    global _cache
    with _lock:
        if _cache is not None and not reload:
            return _cache
        d = settings.keys_dir
        if not (d / SIGNER_KEY).exists() or not (d / ED_PRIV).exists():
            generate_demo_keys(d)
        chain = (d / SIGNER_CHAIN).read_bytes()
        certs = x509.load_pem_x509_certificates(chain)
        ed_priv = serialization.load_pem_private_key((d / ED_PRIV).read_bytes(), password=None)
        _cache = KeyMaterial(
            signer_chain_pem=chain,
            signer_key_pem=(d / SIGNER_KEY).read_bytes(),
            root_cert_pem=(d / ROOT_CERT).read_bytes(),
            signer_cert=certs[0],
            root_cert=x509.load_pem_x509_certificate((d / ROOT_CERT).read_bytes()),
            ed_private=ed_priv,
            ed_public_raw=ed_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw),
        )
        return _cache
