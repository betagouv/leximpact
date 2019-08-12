from models.user import find_user
from models.jwt import JWT, encode_jwt, decode_jwt
from jwt.exceptions import (  # type: ignore
    InvalidSignatureError,
    ExpiredSignatureError,
    DecodeError,
)
from datetime import datetime
from typing import Dict, Optional, Any


# Now returns a dict : {"success" : boolean stating if the token is valid,
# "email" : {if success, email of user},
# "error" : {if not success, reason for error}}
def check_user(session, tokenencoded: str) -> Dict[str, Any]:
    checkjwt = JWT()
    checkjwt.encoded = tokenencoded
    resultat = {}  # type: Dict[str, Any]
    try:
        decode_jwt(checkjwt)
        user = find_user(session, checkjwt.decoded["sub"])
        if user is None:
            resultat["success"] = False
            resultat["error"] = "User not found in email database"
            return resultat
        if datetime.utcnow().timestamp() > checkjwt.decoded["exp"]:
            resultat["success"] = False
            resultat["error"] = "Token has expired!"
        resultat["success"] = True
        resultat["email"] = checkjwt.decoded["sub"]
        return resultat
    except InvalidSignatureError:
        resultat["success"] = False
        resultat["error"] = "Token signature was invalid"
        return resultat
    except ExpiredSignatureError:
        resultat["success"] = False
        resultat["error"] = "Token has expired"
        return resultat
    except DecodeError:
        resultat["success"] = False
        resultat["error"] = "Token invalid : not Decodable"
        return resultat


def login_user(session, email: str) -> Optional[JWT]:  # Optional[User]:
    user = find_user(session, email)

    if not user:
        return None
    return encode_jwt(JWT(), user.email)
