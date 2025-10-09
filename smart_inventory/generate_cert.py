
import os, datetime, ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

IP = os.environ.get("IP_LAN","192.168.1.72")

# 1) clave privada
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2) sujeto/issuer (autofirmado)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"ES"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"SmartInventory Dev"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"{}".format(IP)),
])

# 3) SAN: localhost + 192.168.1.72 + tu IP
alt = x509.SubjectAlternativeName([
    x509.DNSName(u"localhost"),
    x509.IPAddress(ipaddress.IPv4Address(u"192.168.1.72")),
    x509.IPAddress(ipaddress.IPv4Address(IP)),
])

cert = (x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .add_extension(alt, critical=False)
    .sign(key, hashes.SHA256())
)

# 4) escribir ficheros
with open("certs/key.pem","wb") as f:
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()
    ))
with open("certs/cert.pem","wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

# 5) PEM combinado (cert primero, luego key)
with open("certs/dev.pem","wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
    f.write(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption()
    ))
print("OK: generados certs/cert.pem, certs/key.pem y certs/dev.pem")

