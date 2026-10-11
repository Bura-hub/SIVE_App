from rest_framework.permissions import SAFE_METHODS, BasePermission


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


class IsAuthenticatedOrPublicRead(BasePermission):
    """Lectura pública (modo invitado) en las pantallas de datos.

    Los métodos seguros (GET/HEAD/OPTIONS) se permiten sin autenticar para que un invitado
    vea los datos ya calculados en solo lectura; cualquier otro método (POST/PUT/PATCH/DELETE:
    recalcular, sincronizar, escribir) exige un usuario autenticado. Solo se aplica a vistas
    que leen datos ya sincronizados o calculados: auth/perfil, reportes, tareas, el proxy
    remoto /scada/ y la administración siguen con `IsAuthenticated`/`IsSuperUser`.

    El tráfico anónimo que entra por aquí se limita con
    `core.throttling.GuestAwareAnonRateThrottle` (alcance `anon_read`).
    """

    message = 'Inicia sesión para realizar esta acción.'
    # Marca leída por el throttle de invitados para elegir el alcance `anon_read`.
    public_read = True

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        u = request.user
        return bool(u and u.is_authenticated)
