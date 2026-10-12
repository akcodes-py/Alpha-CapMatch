from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class ServiceError(APIException):
    status_code = 400
    default_code = "bad_request"

    def __init__(self, message: str, code: str = "", status_code: int = 0):
        super().__init__(detail=message)
        if code:
            self.default_code = code
        if status_code:
            self.status_code = status_code


class ConflictError(ServiceError):
    status_code = 409
    default_code = "conflict"


class NotFoundError(ServiceError):
    status_code = 404
    default_code = "not_found"


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict) and "error" in detail:
        return response
    code = getattr(exc, "default_code", "error")
    if isinstance(detail, list):
        message = "; ".join(str(d) for d in detail)
    elif isinstance(detail, dict):
        parts = []
        for key, value in detail.items():
            parts.append(f"{key}: {value}")
        message = "; ".join(parts)
    else:
        message = str(detail) if detail is not None else str(exc)
    response.data = {"error": {"code": str(code), "message": message}}
    return response
