# Importación de la función 'path' para definir las rutas URL de la aplicación
from django.urls import path

# Importación de las vistas que gestionan las entidades SCADA
from .views import (
    ScadaConnectionStatusView,
    InstitutionsView,         # Vista para obtener información de instituciones asociadas
    DeviceCategoriesView,    # Vista para listar categorías de dispositivos disponibles
    DevicesView,             # Vista para listar dispositivos SCADA registrados
    MeasurementsView         # Vista para obtener mediciones asociadas a un dispositivo específico
)

# Definición de rutas URL para los recursos del sistema SCADA
urlpatterns = [
    # Estado de conexión con SCADA
    path('connection-status/', ScadaConnectionStatusView.as_view(), name='scada-connection-status'),
    # Endpoint para obtener las instituciones registradas en el sistema SCADA
    path('institutions/', InstitutionsView.as_view(), name='scada-institutions'),

    # Endpoint para listar las categorías de dispositivos existentes
    path('device-categories/', DeviceCategoriesView.as_view(), name='scada-device-categories'),

    # Endpoint para obtener la lista de dispositivos asociados a las instituciones o categorías
    path('devices/', DevicesView.as_view(), name='scada-devices'),

    # Endpoint para obtener mediciones históricas de un dispositivo en particular, referenciado por su ID
    path('measurements/<str:device_id>/', MeasurementsView.as_view(), name='scada-measurements'),
]