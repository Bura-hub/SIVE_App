from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ConsumptionSummaryView, 
    ChartDataView, 
    CalculateKPIsView, 
    CalculateDailyDataView,
    InstitutionsListView,
    ElectricMetersListView,
    ElectricMeterIndicatorsViewSet,
    # Nuevas vistas para inversores
    InverterIndicatorsView,
    InverterChartDataView,
    CalculateInverterDataView,
    InvertersListView,
    # Nueva vista para cálculo eléctrico
    CalculateElectricalDataView,
    # Nuevas vistas para estaciones meteorológicas
    WeatherStationIndicatorsView,
    WeatherStationChartDataView,
    CalculateWeatherStationDataView,
    WeatherStationsListView,
    # =========================
    # ENDPOINTS PARA GENERACIÓN DE REPORTES
    # =========================
    GenerateReportView,
    ReportStatusView,
    DownloadReportView,
    ReportHistoryView,
    DeleteReportView
)
from .views_availability import DataAvailabilityView

router = DefaultRouter()
router.register(r'electric-meter-indicators', ElectricMeterIndicatorsViewSet, basename='electric-meter-indicators')

# Definición de las rutas de URL asociadas a esta aplicación
urlpatterns = [
    # Endpoints existentes
    path('dashboard/summary/', ConsumptionSummaryView.as_view(), name='consumption-summary'),
    path('dashboard/chart-data/', ChartDataView.as_view(), name='chart-data'),
    path('dashboard/calculate-kpis/', CalculateKPIsView.as_view(), name='calculate-kpis'),
    path('dashboard/calculate-daily-data/', CalculateDailyDataView.as_view(), name='calculate-daily-data'),
    
    # Endpoints para medidores eléctricos
    path('electric-meters/list/', ElectricMetersListView.as_view(), name='electric-meters-list'),
    path('institutions/', InstitutionsListView.as_view(), name='institutions-list'),
    path('electric-meters/calculate-new/', CalculateElectricalDataView.as_view(), name='calculate-electrical-data'),
    
    # Nuevos endpoints para inversores
    path('inverter-indicators/', InverterIndicatorsView.as_view(), name='inverter-indicators'),
    path('inverter-chart-data/', InverterChartDataView.as_view(), name='inverter-chart-data'),
    path('inverters/calculate/', CalculateInverterDataView.as_view(), name='calculate-inverter-data'),
    path('inverters/list/', InvertersListView.as_view(), name='inverters-list'),
    
    # Nuevos endpoints para estaciones meteorológicas
    path('weather-station-indicators/', WeatherStationIndicatorsView.as_view(), name='weather-station-indicators'),
    path('weather-station-chart-data/', WeatherStationChartDataView.as_view(), name='weather-station-chart-data'),
    path('weather-stations/calculate/', CalculateWeatherStationDataView.as_view(), name='calculate-weather-station-data'),
    path('weather-stations/list/', WeatherStationsListView.as_view(), name='weather-stations-list'),

    # =========================
    # ENDPOINTS PARA GENERACIÓN DE REPORTES
    # =========================
    path('reports/generate/', GenerateReportView.as_view(), name='generate-report'),
    path('reports/status/', ReportStatusView.as_view(), name='report-status'),
    path('reports/download/', DownloadReportView.as_view(), name='download-report'),
    path('reports/history/', ReportHistoryView.as_view(), name='report-history'),
    path('reports/delete/', DeleteReportView.as_view(), name='delete-report'),
    
    path('data-availability/', DataAvailabilityView.as_view(), name='data-availability'),

    path('', include(router.urls)),
]