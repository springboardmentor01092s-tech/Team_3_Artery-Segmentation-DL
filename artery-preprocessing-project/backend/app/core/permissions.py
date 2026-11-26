from enum import Enum


class UserRole(str, Enum):
    ADMINISTRATOR = "administrator"
    RADIOLOGIST = "radiologist"
    RESEARCHER = "researcher"
    DATA_SCIENTIST = "data_scientist"


class Permission(str, Enum):
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"
    CASE_CREATE = "case:create"
    CASE_READ_OWN = "case:read_own"
    CASE_READ_ALL = "case:read_all"
    CASE_UPDATE_OWN = "case:update_own"
    CASE_DELETE_OWN = "case:delete_own"
    IMAGE_UPLOAD = "image:upload"
    IMAGE_PREPROCESS = "image:preprocess"
    DATASET_INSPECT = "dataset:inspect"
    CASE_ASSIGN = "case:assign"
    CASE_SHARE = "case:share"



ACCESS_TYPE_ASSIGNED = "assigned"
ACCESS_TYPE_SHARED = "shared"
VALID_ACCESS_TYPES = {ACCESS_TYPE_ASSIGNED, ACCESS_TYPE_SHARED}


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMINISTRATOR: set(Permission),
    UserRole.RADIOLOGIST: {
        Permission.CASE_CREATE,
        Permission.CASE_READ_OWN,
        Permission.CASE_UPDATE_OWN,
        Permission.CASE_DELETE_OWN,
        Permission.CASE_SHARE,
        Permission.IMAGE_UPLOAD,
        Permission.IMAGE_PREPROCESS,
    },
    UserRole.RESEARCHER: {
        Permission.CASE_CREATE,
        Permission.CASE_READ_OWN,
        Permission.CASE_UPDATE_OWN,
        Permission.CASE_DELETE_OWN,
        Permission.CASE_SHARE,
        Permission.IMAGE_UPLOAD,
        Permission.IMAGE_PREPROCESS,
    },
    UserRole.DATA_SCIENTIST: {
        Permission.CASE_CREATE,
        Permission.CASE_READ_OWN,
        Permission.CASE_UPDATE_OWN,
        Permission.CASE_DELETE_OWN,
        Permission.CASE_SHARE,
        Permission.IMAGE_UPLOAD,
        Permission.IMAGE_PREPROCESS,
        Permission.DATASET_INSPECT,
    },
}

DEFAULT_REGISTRATION_ROLE = UserRole.RESEARCHER


def has_permission(role: UserRole | str, permission: Permission) -> bool:
    try:
        resolved = UserRole(role)
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(resolved, set())


def permissions_for_role(role: UserRole | str) -> list[str]:
    try:
        resolved = UserRole(role)
    except ValueError:
        return []
    return sorted(permission.value for permission in ROLE_PERMISSIONS.get(resolved, set()))
