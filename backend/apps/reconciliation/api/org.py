from ..models import Organization
from .errors import ServiceError


class MissingOrganizationError(ServiceError):
    status_code = 400
    default_code = "missing_organization"


class UnknownOrganizationError(ServiceError):
    status_code = 404
    default_code = "unknown_organization"


def resolve_organization(request) -> Organization:
    slug = (request.headers.get("X-Organization") or "").strip()
    if not slug:
        raise MissingOrganizationError("X-Organization header is required")
    try:
        return Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        raise UnknownOrganizationError(f"Unknown organization '{slug}'")
