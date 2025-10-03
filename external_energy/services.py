import requests
import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import json

logger = logging.getLogger(__name__)

class XMRealAPIService:
    """Servicio para obtener datos reales de la API de XM (Sistema Interconectado Nacional)"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_available = self._check_api_availability()
    
    def _check_api_availability(self):
        """Verifica si la librería pydataxm está disponible"""
        try:
            from pydataxm import pydataxm
            return True
        except ImportError:
            self.logger.warning("pydataxm no está disponible. Usando datos simulados.")
            return False
    
    def _convert_to_hourly_series(self, df, date_column='Date', value_prefix='Values_Hour'):
        """Convierte DataFrame de XM API a serie horaria"""
        try:
            import pandas as pd
            
            # Asegurar que la fecha esté en formato datetime
            df[date_column] = pd.to_datetime(df[date_column], format='%d/%m/%Y')
            
            # Obtener columnas de valores por hora
            hour_columns = [col for col in df.columns if value_prefix in col]
            
            # Convertir a serie horaria
            hourly_data = []
            for idx, row in df.iterrows():
                base_date = row[date_column]
                for i, col in enumerate(hour_columns):
                    hour_datetime = base_date + pd.Timedelta(hours=i)
                    hourly_data.append({
                        'datetime': hour_datetime,
                        'value': row[col]
                    })
            
            return pd.DataFrame(hourly_data)
            
        except Exception as e:
            self.logger.error(f"Error convirtiendo a serie horaria: {str(e)}")
            return pd.DataFrame()
    
    def fetch_energy_prices(self, start_date, end_date):
        """Obtiene precios de energía desde la API de XM"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            from pydataxm import pydataxm
            import datetime as dt
            
            # Crear objeto de conexión a la API
            api_client = pydataxm.ReadDB()
            
            # Consultar precios de bolsa nacional
            df_prices = api_client.request_data(
                "PrecBolsNaci",  # Precio Bolsa Nacional
                "Sistema",       # Entidad Sistema
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day)
            )
            
            if df_prices.empty:
                raise Exception("No se obtuvieron datos de precios desde la API de XM")
            
            # Convertir a serie horaria
            hourly_data = self._convert_to_hourly_series(df_prices)
            
            if hourly_data.empty:
                raise Exception("Error al procesar datos de precios desde XM")
            
            # Procesar datos para el formato esperado
            import pandas as pd
            prices = []
            for _, row in hourly_data.iterrows():
                prices.append({
                    'date': row['datetime'].strftime('%Y-%m-%d'),
                    'price': float(row['value']) if pd.notna(row['value']) else 0.0
                })
            
            return prices
            
        except Exception as e:
            self.logger.error(f"Error obteniendo precios de XM API: {str(e)}")
            raise e
    
    def fetch_generation_data(self, start_date, end_date):
        """Obtiene datos de generación desde la API de XM"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            from pydataxm import pydataxm
            import datetime as dt
            
            api_client = pydataxm.ReadDB()
            
            # Consultar generación real total
            df_generation = api_client.request_data(
                "Gene",  # Generación
                "Sistema",
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day)
            )
            
            if df_generation.empty:
                raise Exception("No se obtuvieron datos de generación desde la API de XM")
            
            # Convertir a serie horaria
            hourly_data = self._convert_to_hourly_series(df_generation)
            
            if hourly_data.empty:
                raise Exception("Error al procesar datos de generación desde XM")
            
            # Procesar datos
            import pandas as pd
            generation = []
            for _, row in hourly_data.iterrows():
                generation.append({
                    'date': row['datetime'].strftime('%Y-%m-%d'),
                    'value': float(row['value']) if pd.notna(row['value']) else 0.0
                })
            
            return generation
            
        except Exception as e:
            self.logger.error(f"Error obteniendo generación de XM API: {str(e)}")
            raise e
    
    def fetch_demand_data(self, start_date, end_date):
        """Obtiene datos de demanda desde la API de XM"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            from pydataxm import pydataxm
            import datetime as dt
            
            api_client = pydataxm.ReadDB()
            
            # Consultar demanda comercial
            df_demand = api_client.request_data(
                "DemaCome",  # Demanda Comercial
                "Sistema",
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day)
            )
            
            if df_demand.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Convertir a serie horaria
            hourly_data = self._convert_to_hourly_series(df_demand)
            
            if hourly_data.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Procesar datos
            import pandas as pd
            demand = []
            for _, row in hourly_data.iterrows():
                demand.append({
                    'date': row['datetime'].strftime('%Y-%m-%d'),
                    'value': float(row['value']) if pd.notna(row['value']) else 0.0
                })
            
            return demand
            
        except Exception as e:
            self.logger.error(f"Error obteniendo demanda de XM API: {str(e)}")
            raise Exception("No se obtuvieron datos de demanda desde la API de XM")
    
    def fetch_emissions_data(self, start_date, end_date):
        """Obtiene datos de emisiones desde la API de XM"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            from pydataxm import pydataxm
            import datetime as dt
            
            api_client = pydataxm.ReadDB()
            
            # Consultar factor de emisión CO2
            df_emissions = api_client.request_data(
                "factorEmisionCO2e",  # Factor de emisión CO2 equivalente
                "Sistema",
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day)
            )
            
            if df_emissions.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Convertir a serie horaria
            hourly_data = self._convert_to_hourly_series(df_emissions)
            
            if hourly_data.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Procesar datos
            import pandas as pd
            emissions = []
            for _, row in hourly_data.iterrows():
                emissions.append({
                    'date': row['datetime'].strftime('%Y-%m-%d'),
                    'value': float(row['value']) if pd.notna(row['value']) else 0.0
                })
            
            return emissions
            
        except Exception as e:
            self.logger.error(f"Error obteniendo emisiones de XM API: {str(e)}")
            raise Exception("No se obtuvieron datos de emisiones desde la API de XM")

    def fetch_exports_data(self, start_date, end_date):
        """Obtiene datos de exportaciones de energía desde la API de XM"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            from pydataxm import pydataxm
            import datetime as dt
            
            api_client = pydataxm.ReadDB()
            
            # Consultar exportaciones de energía
            df_exports = api_client.request_data(
                "ExpoEner",           # Exportaciones de energía
                "Sistema",            # Entidad Sistema
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day)
            )
            
            if df_exports.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Convertir a serie horaria
            hourly_data = self._convert_to_hourly_series(df_exports)
            
            if hourly_data.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Procesar datos
            import pandas as pd
            exports = []
            for _, row in hourly_data.iterrows():
                exports.append({
                    'date': row['datetime'].strftime('%Y-%m-%d'),
                    'value': float(row['value']) if pd.notna(row['value']) else 0.0
                })
            
            return exports
            
        except Exception as e:
            self.logger.error(f"Error obteniendo exportaciones de XM API: {str(e)}")
            raise Exception("No se obtuvieron datos de exportaciones desde la API de XM")

    def fetch_imports_data(self, start_date, end_date):
        """Obtiene datos de importaciones de energía desde la API de XM"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            from pydataxm import pydataxm
            import datetime as dt
            
            api_client = pydataxm.ReadDB()
            
            # Consultar importaciones de energía
            df_imports = api_client.request_data(
                "ImpoEner",           # Importaciones de energía
                "Sistema",            # Entidad Sistema
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day)
            )
            
            if df_imports.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Convertir a serie horaria
            hourly_data = self._convert_to_hourly_series(df_imports)
            
            if hourly_data.empty:
                raise Exception("API de XM no disponible: pydataxm no está instalado")
            
            # Procesar datos
            import pandas as pd
            imports = []
            for _, row in hourly_data.iterrows():
                imports.append({
                    'date': row['datetime'].strftime('%Y-%m-%d'),
                    'value': float(row['value']) if pd.notna(row['value']) else 0.0
                })
            
            return imports
            
        except Exception as e:
            self.logger.error(f"Error obteniendo importaciones de XM API: {str(e)}")
            raise Exception("No se obtuvieron datos de importaciones desde la API de XM")
    


# Mantener compatibilidad con el código existente
class XMEnergyService:
    """Servicio principal que usa la API real de XM"""
    
    def __init__(self):
        self.xm_service = XMRealAPIService()
    
    def fetch_energy_prices(self, start_date, end_date):
        return self.xm_service.fetch_energy_prices(start_date, end_date)
    
    def sync_all_data(self):
        try:
            today = timezone.now().date()
            start_date = today - timedelta(days=30)
            
            # Obtener precios desde XM
            prices = self.fetch_energy_prices(start_date, today)
            
            return {
                'prices_synced': len(prices),
                'last_sync': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en sync_all_data: {str(e)}")
            return {
                'error': str(e),
                'last_sync': timezone.now().isoformat()
            }
    
    def fetch_generation_data(self, start_date, end_date):
        return self.xm_service.fetch_generation_data(start_date, end_date)
    
    def fetch_demand_data(self, start_date, end_date):
        return self.xm_service.fetch_demand_data(start_date, end_date)
    
    def fetch_emissions_data(self, start_date, end_date):
        return self.xm_service.fetch_emissions_data(start_date, end_date)
    
    def fetch_exports_data(self, start_date, end_date):
        return self.xm_service.fetch_exports_data(start_date, end_date)
    
    def fetch_imports_data(self, start_date, end_date):
        return self.xm_service.fetch_imports_data(start_date, end_date)
