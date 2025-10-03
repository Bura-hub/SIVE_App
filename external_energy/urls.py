from django.urls import path
from . import views

app_name = 'external_energy'

urlpatterns = [
    # Endpoints para datos externos de energía
    path('prices/', views.energy_prices, name='energy_prices'),
    path('savings/', views.energy_savings, name='energy_savings'),
    path('sync/', views.sync_external_data, name='sync_external_data'),
    path('market-overview/', views.market_overview, name='market_overview'),
    
    # Nuevos endpoints para datos de XM
    path('generation/', views.generation_data, name='generation_data'),
    path('demand/', views.demand_data, name='demand_data'),
    path('emissions/', views.emissions_data, name='emissions_data'),
    path('exports/', views.exports_data, name='exports_data'),
    path('imports/', views.imports_data, name='imports_data'),
]
