from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'admin'


class IsApplicant(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'applicant'


class IsCompany(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'company'


class IsCEA(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'cea'


class IsCoordinator(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'coordinator'


class IsReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS





