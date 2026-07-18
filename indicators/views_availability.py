# indicators/views_availability.py
from django.db.models import Min, Max
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from indicators.models import (
    ElectricMeterIndicators, HourlyMeterIndicators,
    InverterIndicators, HourlyInverterIndicators,
    WeatherStationIndicators, HourlyWeatherIndicators,
)

# Mapea category -> (modelo daily/monthly, modelo horario)
_CATEGORY_MODELS = {
    'electricMeter': (ElectricMeterIndicators, HourlyMeterIndicators),
    'inverter': (InverterIndicators, HourlyInverterIndicators),
    'weatherStation': (WeatherStationIndicators, HourlyWeatherIndicators),
}


class DataAvailabilityView(APIView):
    """Reporta el rango real de datos disponibles por sede y categoría."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Disponibilidad de datos'],
        parameters=[
            OpenApiParameter('institution_id', int, required=True,
                             description='ID de la sede/institución'),
            OpenApiParameter('category', str, required=True,
                             description='electricMeter | inverter | weatherStation'),
        ],
    )
    def get(self, request, *args, **kwargs):
        institution_id = request.query_params.get('institution_id')
        category = request.query_params.get('category')

        if not institution_id or not category:
            return Response(
                {'detail': "Los parámetros 'institution_id' y 'category' son obligatorios."},
                status=status.HTTP_400_BAD_REQUEST)

        if category not in _CATEGORY_MODELS:
            return Response(
                {'detail': "category debe ser 'electricMeter', 'inverter' o 'weatherStation'."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            institution_id = int(institution_id)
        except ValueError:
            return Response(
                {"detail": "institution_id debe ser un número entero válido"},
                status=status.HTTP_400_BAD_REQUEST)

        daily_model, hourly_model = _CATEGORY_MODELS[category]

        dm = (daily_model.objects.filter(institution_id=institution_id)
              .aggregate(min_date=Min('date'), max_date=Max('date')))
        hr = (hourly_model.objects.filter(institution_id=institution_id)
              .aggregate(min_date=Min('hour'), max_date=Max('hour')))

        return Response({
            'institution_id': int(institution_id),
            'category': category,
            'daily_monthly': {'min_date': dm['min_date'], 'max_date': dm['max_date']},
            'hourly': {'min_date': hr['min_date'], 'max_date': hr['max_date']},
            'last_updated': dm['max_date'],
        })
