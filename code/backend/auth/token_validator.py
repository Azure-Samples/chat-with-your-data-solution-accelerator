from jose import jwt
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
        audience = "00000003-0000-0000-c000-000000000000"

        jwks = json.loads(urlopen(jwks_url).read())
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = self.find_rsa_key(jwks, unverified_header)

        return jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer_url,
            options={"verify_signature": False},
        )

    def find_rsa_key(self, jwks, unverified_header):
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
