
from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization
import base64

vapid = Vapid()
vapid.generate_keys()

# Generate private key in PEM format
private_key = vapid.private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Generate public key in PEM format
public_key = vapid.public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Convert private key to Base64
private_key_b64 = base64.b64encode(
    private_key
).decode("utf-8")

# Convert public key to Base64
public_key_b64 = base64.b64encode(
    public_key
).decode("utf-8")

# Display both keys
print("\nPRIVATE KEY BASE64:")
print(private_key_b64)

print("\nPUBLIC KEY BASE64:")
print(public_key_b64)