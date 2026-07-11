from rest_framework.permissions import BasePermission


class IsSuperUser(BasePermission):
    """Permite el acceso únicamente a superusuarios autenticados.

    Se usa para endpoints "admin-only" (Datos Externos / Exportar Reportes) que en el
    frontend se gatean por `is_superuser`. Comprueba `is_superuser` (NO `is_staff`, que es
    lo que valida `IsAdminUser`), para que el control del servidor coincida con el del menú.
    """

    message = 'Se requieren privilegios de administrador.'

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_superuser)
