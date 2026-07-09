import os
import requests
import logging
import concurrent.futures
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
import json

logger = logging.getLogger(__name__)

# Verificación SSL para las llamadas a la API de XM.
# En .env: PYDATAXM_VERIFY_SSL=false (por defecto true).
#
# NOTA DE SEGURIDAD: pydataxm usa el módulo `requests` global internamente y NO expone
# un parámetro `verify` ni acepta una `requests.Session` propia. Por eso NO es posible
# desactivar la verificación SSL solo para este módulo sin parchear el `requests.post`
# global del proceso, lo que afectaría a TODO el backend (incluido el cliente SCADA que
# envía credenciales). En consecuencia, aquí NUNCA se altera el `requests` global: si
# PYDATAXM_VERIFY_SSL=false solo se registra una advertencia y se ignora. Para entornos
# con una CA propia use la variable de entorno estándar REQUESTS_CA_BUNDLE.
_ssl_verify = os.environ.get('PYDATAXM_VERIFY_SSL', 'true').lower() not in ('0', 'false', 'no')


class XMRealAPIService:
    """Servicio para obtener datos reales de la API de XM (Sistema Interconectado Nacional)"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Timeout duro (segundos) para acotar las llamadas a XM y no bloquear el ciclo
        # request/response de Django. Configurable vía settings.XM_API_TIMEOUT.
        self.request_timeout = int(getattr(settings, 'XM_API_TIMEOUT', 30) or 30)
        self.api_available = self._check_api_availability()

    def _check_api_availability(self):
        """Verifica si la librería pydataxm está disponible (sin tocar el `requests` global)."""
        if not _ssl_verify:
            # No se parchea el `requests` global (ver nota de seguridad al inicio del módulo).
            self.logger.warning(
                "PYDATAXM_VERIFY_SSL=false se ignora: no es posible desactivar la "
                "verificación SSL solo para pydataxm sin afectar al resto del backend. "
                "Use REQUESTS_CA_BUNDLE si necesita registrar una CA propia."
            )
        try:
            from pydataxm import pydataxm  # noqa: F401
            return True
        except ImportError:
            self.logger.warning("pydataxm no está disponible. Usando datos simulados.")
            return False

    def _request_data_with_timeout(self, api_client, metric_id, entity, start, end):
        """Ejecuta `api_client.request_data` con un timeout duro.

        pydataxm no expone un parámetro de timeout, por lo que la llamada se ejecuta en un
        hilo aparte y se acota el tiempo máximo de espera del ciclo request/response de Django.
        """
        # NO usar `with ThreadPoolExecutor(...)`: su __exit__ hace shutdown(wait=True)
        # y bloquearía hasta que el hilo colgado termine, anulando el timeout. Se
        # cierra con wait=False para devolver el control de inmediato (el hilo huérfano
        # terminará por su cuenta; Python no permite matarlo).
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(api_client.request_data, metric_id, entity, start, end)
        try:
            result = future.result(timeout=self.request_timeout)
            executor.shutdown(wait=False)
            return result
        except concurrent.futures.TimeoutError:
            future.cancel()
            executor.shutdown(wait=False)
            raise TimeoutError(
                f"La consulta a XM '{metric_id}' superó el timeout de "
                f"{self.request_timeout}s"
            )

    def _extract_series(self, df, date_column='Date'):
        """Normaliza un DataFrame de la API de XM a una lista de registros {'datetime', 'value'}.

        Soporta los dos formatos que devuelve pydataxm:
        - Métricas HORARIAS: 24 columnas 'Values_HourXX' por fila (una fila por día).
        - Métricas DIARIAS: una única columna 'Value' (o 'Values') por fila.

        No silencia errores de formato/fecha: los propaga en lugar de devolver datos vacíos
        ocultando el fallo real.
        """
        import pandas as pd

        if df is None or df.empty:
            return []

        # La API de XM devuelve la fecha en formato ISO (YYYY-MM-DD); se infiere el formato
        # automáticamente en lugar de forzar '%d/%m/%Y', que no coincidía y lanzaba ValueError.
        df[date_column] = pd.to_datetime(df[date_column])

        hour_columns = [col for col in df.columns if 'Values_Hour' in col]
        records = []

        if hour_columns:
            # Métrica horaria: expandir las 24 horas de cada día en registros individuales.
            for _, row in df.iterrows():
                base_date = row[date_column]
                for i, col in enumerate(hour_columns):
                    value = row[col]
                    records.append({
                        'datetime': base_date + pd.Timedelta(hours=i),
                        'value': None if pd.isna(value) else float(value),
                    })
            return records

        # Métrica diaria: buscar la columna de valor único ('Value' o 'Values').
        daily_col = None
        for candidate in ('Value', 'Values'):
            if candidate in df.columns:
                daily_col = candidate
                break

        if daily_col is not None:
            for _, row in df.iterrows():
                value = row[daily_col]
                records.append({
                    'datetime': row[date_column],
                    'value': None if pd.isna(value) else float(value),
                })
            return records

        raise ValueError(
            f"Formato de DataFrame de XM no reconocido (columnas: {list(df.columns)})"
        )

    def _records_to_daily_average(self, records, value_key='price'):
        """Agrega registros (horarios o diarios) a nivel DIARIO usando el promedio.

        Ignora valores None/NaN. Devuelve una lista ordenada por fecha:
        [{'date': 'YYYY-MM-DD', value_key: <promedio>}]. Se usa para precios, cuya serie de
        XM es horaria (24 valores/día) pero el modelo EnergyPrice guarda un valor por fecha.
        """
        sums = {}
        counts = {}
        for rec in records:
            value = rec['value']
            if value is None:
                continue
            dt = rec['datetime']
            day = dt.date() if hasattr(dt, 'date') else dt
            sums[day] = sums.get(day, 0.0) + float(value)
            counts[day] = counts.get(day, 0) + 1

        daily = []
        for day in sorted(sums.keys()):
            if counts[day] > 0:
                daily.append({
                    'date': day.strftime('%Y-%m-%d'),
                    value_key: sums[day] / counts[day],
                })
        return daily

    def _records_to_list(self, records):
        """Convierte registros normalizados a la lista {'date', 'value'} que esperan las vistas.

        Conserva None para valores faltantes: las vistas filtran None/NaN pero conservan los
        ceros legítimos (demanda/generación/importación/exportación 0 son datos reales).

        Si la serie es HORARIA (varios registros por día, p. ej. Gene/DemaCome/emisiones),
        se incluye la hora en la etiqueta para no colapsar las 24 muestras diarias a una
        sola clave de fecha. Si es DIARIA, se mantiene solo 'YYYY-MM-DD' (sin cambios).
        """
        days = [rec['datetime'].date() if hasattr(rec['datetime'], 'date') else rec['datetime']
                for rec in records]
        hourly = len(days) != len(set(days))  # hay más de un registro por día
        fmt = '%Y-%m-%d %H:%M' if hourly else '%Y-%m-%d'
        return [
            {
                'date': rec['datetime'].strftime(fmt),
                'value': rec['value'],
            }
            for rec in records
        ]

    def fetch_energy_prices(self, start_date, end_date):
        """Obtiene precios de energía (bolsa nacional) desde XM, agregados a nivel DIARIO."""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")

            from pydataxm import pydataxm
            import datetime as dt

            # Crear objeto de conexión a la API
            api_client = pydataxm.ReadDB()

            # Consultar precios de bolsa nacional (serie horaria)
            df_prices = self._request_data_with_timeout(
                api_client,
                "PrecBolsNaci",  # Precio Bolsa Nacional
                "Sistema",       # Entidad Sistema
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day),
            )

            if df_prices is None or df_prices.empty:
                raise Exception("No se obtuvieron datos de precios desde la API de XM")

            # La serie de precios es HORARIA (24 valores/día). Se agrega a promedio DIARIO
            # para que coincida con el modelo EnergyPrice (una fila por fecha) y no se pierdan
            # 23 de cada 24 registros por el `unique` de la fecha.
            records = self._extract_series(df_prices)
            prices = self._records_to_daily_average(records, value_key='price')

            if not prices:
                raise Exception("Error al procesar datos de precios desde XM")

            return prices

        except Exception as e:
            self.logger.error(f"Error obteniendo precios de XM API: {str(e)}")
            raise e

    def fetch_generation_data(self, start_date, end_date):
        """Obtiene datos de generación desde la API de XM (serie horaria)"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")

            from pydataxm import pydataxm
            import datetime as dt

            api_client = pydataxm.ReadDB()

            # Consultar generación real total (serie horaria)
            df_generation = self._request_data_with_timeout(
                api_client,
                "Gene",  # Generación
                "Sistema",
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day),
            )

            if df_generation is None or df_generation.empty:
                raise Exception("No se obtuvieron datos de generación desde la API de XM")

            return self._records_to_list(self._extract_series(df_generation))

        except Exception as e:
            self.logger.error(f"Error obteniendo generación de XM API: {str(e)}")
            raise e

    def fetch_demand_data(self, start_date, end_date):
        """Obtiene datos de demanda desde la API de XM (serie horaria)"""
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")

            from pydataxm import pydataxm
            import datetime as dt

            api_client = pydataxm.ReadDB()

            # Consultar demanda comercial (serie horaria)
            df_demand = self._request_data_with_timeout(
                api_client,
                "DemaCome",  # Demanda Comercial
                "Sistema",
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day),
            )

            if df_demand is None or df_demand.empty:
                raise Exception("No se obtuvieron datos de demanda desde la API de XM")

            return self._records_to_list(self._extract_series(df_demand))

        except Exception as e:
            self.logger.error(f"Error obteniendo demanda de XM API: {str(e)}")
            raise e

    def fetch_emissions_data(self, start_date, end_date):
        """Obtiene datos de emisiones desde la API de XM.

        `factorEmisionCO2e` (Entity=Sistema, gCO2e/kWh) es una métrica HORARIA
        (Type=HourlyEntities, columnas 'Values_HourXX') confirmada contra el catálogo real de
        XM; `_extract_series` la normaliza por la rama horaria.
        """
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")

            from pydataxm import pydataxm
            import datetime as dt

            api_client = pydataxm.ReadDB()

            # Consultar factor de emisión de CO2 equivalente (métrica horaria)
            df_emissions = self._request_data_with_timeout(
                api_client,
                "factorEmisionCO2e",  # Factor de emisión CO2 equivalente
                "Sistema",
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day),
            )

            if df_emissions is None or df_emissions.empty:
                raise Exception("No se obtuvieron datos de emisiones desde la API de XM")

            return self._records_to_list(self._extract_series(df_emissions))

        except Exception as e:
            self.logger.error(f"Error obteniendo emisiones de XM API: {str(e)}")
            raise e

    def fetch_exports_data(self, start_date, end_date):
        """Obtiene datos de exportaciones de energía desde la API de XM.

        'ExpoEner' (Entity=Sistema, kWh, Type=HourlyEntities) queda CONFIRMADO contra el
        catálogo real de XM (get_collections). `_extract_series` soporta series horarias y diarias.
        """
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")

            from pydataxm import pydataxm
            import datetime as dt

            api_client = pydataxm.ReadDB()

            # Consultar exportaciones de energía
            df_exports = self._request_data_with_timeout(
                api_client,
                "ExpoEner",           # Exportaciones de energía (confirmado en catálogo XM, kWh)
                "Sistema",            # Entidad Sistema
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day),
            )

            if df_exports is None or df_exports.empty:
                raise Exception("No se obtuvieron datos de exportaciones desde la API de XM")

            return self._records_to_list(self._extract_series(df_exports))

        except Exception as e:
            self.logger.error(f"Error obteniendo exportaciones de XM API: {str(e)}")
            raise e

    def fetch_imports_data(self, start_date, end_date):
        """Obtiene datos de importaciones de energía desde la API de XM.

        'ImpoEner' (Entity=Sistema, kWh, Type=HourlyEntities) queda CONFIRMADO contra el
        catálogo real de XM (get_collections). `_extract_series` soporta series horarias y diarias.
        """
        try:
            if not self.api_available:
                raise Exception("API de XM no disponible: pydataxm no está instalado")

            from pydataxm import pydataxm
            import datetime as dt

            api_client = pydataxm.ReadDB()

            # Consultar importaciones de energía
            df_imports = self._request_data_with_timeout(
                api_client,
                "ImpoEner",           # Importaciones de energía (confirmado en catálogo XM, kWh)
                "Sistema",            # Entidad Sistema
                dt.date(start_date.year, start_date.month, start_date.day),
                dt.date(end_date.year, end_date.month, end_date.day),
            )

            if df_imports is None or df_imports.empty:
                raise Exception("No se obtuvieron datos de importaciones desde la API de XM")

            return self._records_to_list(self._extract_series(df_imports))

        except Exception as e:
            self.logger.error(f"Error obteniendo importaciones de XM API: {str(e)}")
            raise e


# Mantener compatibilidad con el código existente
class XMEnergyService:
    """Servicio principal que usa la API real de XM"""

    def __init__(self):
        self.xm_service = XMRealAPIService()

    def fetch_energy_prices(self, start_date, end_date):
        return self.xm_service.fetch_energy_prices(start_date, end_date)

    def sync_all_data(self):
        """Sincroniza y PERSISTE datos de XM en la base de datos.

        Los precios se agregan a nivel DIARIO (promedio de las 24 horas) y se guardan con
        `update_or_create` para no depender de un IntegrityError (por el `unique` de la fecha)
        para deduplicar. A diferencia de la versión anterior, aquí sí se persiste de verdad.
        """
        # Import diferido para evitar dependencias circulares al cargar el módulo.
        from .models import EnergyPrice

        try:
            today = timezone.now().date()
            start_date = today - timedelta(days=30)

            # Obtener precios desde XM (ya vienen agregados a nivel diario)
            prices = self.fetch_energy_prices(start_date, today)

            created = 0
            updated = 0
            for price_data in prices:
                price_date = price_data['date']
                if isinstance(price_date, str):
                    price_date = datetime.strptime(price_date, '%Y-%m-%d').date()

                _, was_created = EnergyPrice.objects.update_or_create(
                    date=price_date,
                    defaults={
                        'price_per_kwh': Decimal(str(round(float(price_data['price']), 4))),
                        'source': 'XM',
                        'region': 'Colombia',
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

            return {
                'prices_synced': len(prices),
                'prices_created': created,
                'prices_updated': updated,
                'last_sync': timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error en sync_all_data: {str(e)}")
            return {
                'error': str(e),
                'last_sync': timezone.now().isoformat(),
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
