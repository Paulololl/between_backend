from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'admin'

class IsCoordinator(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, 'user_role') and request.user.user_role == 'coordinator'


class IsReadOnly(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS





