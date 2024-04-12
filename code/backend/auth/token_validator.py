import jwt
import base64
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import json
from urllib.request import urlopen


class TokenValidator:
    def __init__(self, tenant_id, client_id):
        self.tenant_id = tenant_id
        self.client_id = client_id

    def validate(self, token):
        jwks_url = (
            f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        )
        issuer_url = f"https://sts.windows.net/{self.tenant_id}/"
        audience = f"api://{self.client_id}"

        jwks = json.loads(urlopen(jwks_url).read())
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = self.find_rsa_key(jwks, unverified_header)
        public_key = self.rsa_pem_from_jwk(rsa_key)

        return jwt.decode(
            token,
            public_key,
            verify=True,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer_url,
        )

    def find_rsa_key(jwks, unverified_header):
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }

    def ensure_bytes(key):
        if isinstance(key, str):
            key = key.encode("utf-8")
        return key

    def decode_value(self, val):
        decoded = base64.urlsafe_b64decode(self.ensure_bytes(val) + b"==")
        return int.from_bytes(decoded, "big")

    def rsa_pem_from_jwk(self, jwk):
        return (
            RSAPublicNumbers(
                n=self.decode_value(jwk["n"]), e=self.decode_value(jwk["e"])
            )
            .public_key(default_backend())
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
