"""
Indicadores del sistema fotovoltaico por institución (pantalla «Indicadores solares»).

GET /api/solar-indicators/?institution_id=<id>&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&granularity=day|month|year
GET /api/solar-indicators/institutions/   instituciones con sistema FV configurado
"""
import logging
from datetime import datetime

from django.core.cache import cache
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from indicators.institution_config import INSTITUCIONES
from indicators.services import solar_kpis
from indicators.services.date_ranges import get_colombia_date
from scada_proxy.models import Institution

logger = logging.getLogger(__name__)

CACHE_SEGUNDOS = 10 * 60


def _fecha(valor, nombre):
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError(f'{nombre} debe tener el formato YYYY-MM-DD.')


class SolarInstitutionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary='Instituciones con sistema fotovoltaico configurado', tags=['Indicadores solares'])
    def get(self, request):
        filas = Institution.objects.filter(scada_id__in=list(INSTITUCIONES)).values('id', 'name', 'scada_id')
        return Response([{**f, 'kwp': INSTITUCIONES[f['scada_id']]['kwp']} for f in filas])


class SolarIndicatorsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Indicadores del sistema fotovoltaico de una institución',
        description=(
            'Generación, rendimiento específico, factor de capacidad, producción frente al diseño, Performance '
            'Ratio, demanda del circuito medido, cobertura solar, autoconsumo y exportación, ahorro estimado, CO₂ '
            'evitado y disponibilidad de datos, por día, mes o año, con los supuestos de cada cifra.'
        ),
        parameters=[
            OpenApiParameter('institution_id', int, required=True),
            OpenApiParameter('start_date', str, description='YYYY-MM-DD (por defecto 2025-04-04)'),
            OpenApiParameter('end_date', str, description='YYYY-MM-DD (por defecto hoy, hora de Bogotá)'),
            OpenApiParameter('granularity', str, enum=list(solar_kpis.GRANULARIDADES), description='por defecto month'),
        ],
        tags=['Indicadores solares'],
    )
    def get(self, request):
        try:
            institution_id = int(request.query_params.get('institution_id', ''))
        except ValueError:
            return Response({'detail': 'institution_id es obligatorio y debe ser un entero.'},
                            status=status.HTTP_400_BAD_REQUEST)
        desde_def, hasta_def = solar_kpis.rango_por_defecto(get_colombia_date())
        granularidad = request.query_params.get('granularity', 'month')
        try:
            desde = _fecha(request.query_params['start_date'], 'start_date') \
                if request.query_params.get('start_date') else desde_def
            hasta = _fecha(request.query_params['end_date'], 'end_date') \
                if request.query_params.get('end_date') else hasta_def
            solar_kpis.validar_rango(desde, hasta)
            if granularidad not in solar_kpis.GRANULARIDADES:
                raise ValueError(f'granularity debe ser una de {", ".join(solar_kpis.GRANULARIDADES)}.')
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        institucion = Institution.objects.filter(id=institution_id).first()
        if institucion is None:
            return Response({'detail': 'Institución no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        clave = f'solar-indicators:{institution_id}:{desde}:{hasta}:{granularidad}'
        datos = cache.get(clave)
        if datos is None:
            try:
                datos = solar_kpis.calcular(institucion, desde, hasta, granularidad)
            except ValueError as e:
                return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            cache.set(clave, datos, CACHE_SEGUNDOS)
        return Response(datos)
