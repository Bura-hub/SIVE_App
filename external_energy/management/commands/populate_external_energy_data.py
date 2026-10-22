from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import random

from external_energy.models import (
    EnergyPrice, 
    EnergySavings, 
    EnergyPriceForecast, 
    EnergyMarketData, 
    EnergyAlert
)


class Command(BaseCommand):
    help = 'Pobla la base de datos con datos simulados de energía externa'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Número de días para generar datos (por defecto: 90)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Limpiar datos existentes antes de poblar'
        )
        parser.add_argument(
            '--location',
            type=str,
            default='Pasto',
            help='Ubicación para datos solares (por defecto: Pasto)'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        clear_existing = options['clear']
        location = options['location']
        
        if clear_existing:
            self.stdout.write('Limpiando datos existentes...')
            EnergyPrice.objects.all().delete()
            EnergyMarketData.objects.all().delete()
            EnergySavings.objects.all().delete()
            EnergyPriceForecast.objects.all().delete()
            EnergyAlert.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Datos existentes eliminados'))
        
        self.stdout.write(f'Generando datos simulados para {days} días en {location}...')
        
        # Generar datos de precios
        self.generate_energy_prices(days)
        
        # Generar datos del mercado
        self.generate_market_data(days)
        
        # Generar ahorros de energía
        self.generate_energy_savings(days)
        
        # Generar pronósticos
        self.generate_price_forecasts(days)
        
        # Generar alertas
        self.generate_energy_alerts()
        
        # Generar datos solares simulados
        self.generate_solar_data(days, location)
        
        self.stdout.write(self.style.SUCCESS('Datos simulados generados exitosamente'))
    
    def generate_energy_prices(self, days):
        """Genera datos simulados de precios de energía"""
        self.stdout.write('Generando precios de energía...')
        
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=days)
        current_date = start_date
        
        prices_created = 0
        base_price = 450.0  # Precio base en COP/kWh
        
        while current_date <= end_date:
            # Simular variaciones diarias
            variation = random.uniform(-0.05, 0.05)  # ±5%
            daily_price = base_price * (1 + variation)
            
            # Simular patrones semanales (precios más altos en días laborales)
            if current_date.weekday() < 5:  # Lunes a viernes
                daily_price *= 1.1
            
            # Simular patrones estacionales específicos de Colombia
            if current_date.month in [12, 1, 2]:  # Diciembre a febrero (verano)
                daily_price *= 1.15
            elif current_date.month in [6, 7, 8]:  # Junio a agosto (invierno)
                daily_price *= 0.95
            
            EnergyPrice.objects.create(
                date=current_date,
                price_per_kwh=Decimal(str(round(daily_price, 2))),
                source='ElectricityMaps',
                region='Colombia'
            )
            
            prices_created += 1
            current_date += timedelta(days=1)
        
        self.stdout.write(f'  - {prices_created} precios creados')
    
    def generate_market_data(self, days):
        """Genera datos simulados del mercado de energía"""
        self.stdout.write('Generando datos del mercado...')
        
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=days)
        current_date = start_date
        
        market_data_created = 0
        
        while current_date <= end_date:
            EnergyMarketData.objects.create(
                date=current_date,
                demand_mw=Decimal(str(round(random.uniform(8000, 12000), 2))),
                supply_mw=Decimal(str(round(random.uniform(8500, 12500), 2))),
                hydro_percentage=Decimal(str(round(random.uniform(60, 80), 2))),
                thermal_percentage=Decimal(str(round(random.uniform(15, 25), 2))),
                renewable_percentage=Decimal(str(round(random.uniform(5, 15), 2))),
                market_price_cop_mwh=Decimal(str(round(random.uniform(150000, 250000), 2)))
            )
            
            market_data_created += 1
            current_date += timedelta(days=1)
        
        self.stdout.write(f'  - {market_data_created} registros del mercado creados')
    
    def generate_energy_savings(self, days):
        """Genera datos simulados de ahorro de energía"""
        self.stdout.write('Generando datos de ahorro...')
        
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=days)
        current_date = start_date
        
        savings_created = 0
        
        while current_date <= end_date:
            # Simular consumo y generación
            consumed = random.uniform(100, 200)
            generated = random.uniform(80, 180)
            price = random.uniform(400, 500)
            
            EnergySavings.objects.create(
                date=current_date,
                total_consumed_kwh=Decimal(str(round(consumed, 2))),
                total_generated_kwh=Decimal(str(round(generated, 2))),
                average_price_kwh=Decimal(str(round(price, 2)))
            )
            
            savings_created += 1
            current_date += timedelta(days=1)
        
        self.stdout.write(f'  - {savings_created} registros de ahorro creados')
    
    def generate_price_forecasts(self, days):
        """Genera pronósticos simulados de precios"""
        self.stdout.write('Generando pronósticos...')
        
        end_date = timezone.localdate()
        start_date = end_date + timedelta(days=1)  # Pronósticos futuros
        current_date = start_date
        
        forecasts_created = 0
        base_price = 450.0
        
        for i in range(days):
            # Simular tendencia con ruido
            trend = 0.001 * i  # Tendencia ligeramente creciente
            noise = random.uniform(-0.02, 0.02)  # ±2% de ruido
            predicted_price = base_price * (1 + trend + noise)
            
            EnergyPriceForecast.objects.create(
                date=current_date,
                predicted_price_kwh=Decimal(str(round(predicted_price, 2))),
                confidence_level=Decimal(str(round(random.uniform(70, 95), 1))),
                source='ElectricityMaps',
                algorithm='ML_Model'
            )
            
            forecasts_created += 1
            current_date += timedelta(days=1)
        
        self.stdout.write(f'  - {forecasts_created} pronósticos creados')
    
    def generate_energy_alerts(self):
        """Genera alertas simuladas de energía"""
        self.stdout.write('Generando alertas...')
        
        alert_types = ['price_spike', 'demand_surge', 'generation_drop', 'market_volatility']
        severities = ['low', 'medium', 'high']
        
        alerts_created = 0
        
        for i in range(10):  # Crear 10 alertas
            alert_type = random.choice(alert_types)
            severity = random.choice(severities)
            
            if alert_type == 'price_spike':
                title = 'Incremento significativo en precios de energía'
                description = 'Se ha detectado un incremento del 15% en los precios del mercado'
            elif alert_type == 'demand_surge':
                title = 'Pico de demanda energética'
                description = 'La demanda de energía ha aumentado un 20% en las últimas horas'
            elif alert_type == 'generation_drop':
                title = 'Caída en la generación renovable'
                description = 'Se ha observado una reducción del 25% en la generación solar'
            else:
                title = 'Volatilidad del mercado energético'
                description = 'El mercado muestra alta volatilidad en los precios'
            
            EnergyAlert.objects.create(
                alert_type=alert_type,
                severity=severity,
                title=title,
                description=description,
                affected_date=timezone.localdate(),
                is_active=random.choice([True, False])
            )
            
            alerts_created += 1
        
        self.stdout.write(f'  - {alerts_created} alertas creadas')
    
    def generate_solar_data(self, days, location):
        """Genera datos solares simulados basados en la ubicación"""
        self.stdout.write(f'Generando datos solares para {location}...')
        
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=days)
        current_date = start_date
        
        solar_data_created = 0
        
        # Configurar parámetros según la ubicación
        if location.lower() == 'pasto':
            # Pasto: clima templado de montaña, altiplano nariñense
            base_radiation = 750  # W/m² base (altitud alta compensa latitud)
            base_clouds = 65  # Alta nubosidad típica de Pasto
            temp_range = (8, 22)  # Clima templado de montaña
            rainy_seasons = [3, 4, 5, 10, 11, 12]  # Marzo-Mayo y Octubre-Diciembre
            dry_seasons = [6, 7, 8, 9]  # Junio-Septiembre
        elif location.lower() == 'bogota':
            # Bogotá: clima templado, nuboso
            base_radiation = 700
            base_clouds = 60
            temp_range = (10, 25)
            rainy_seasons = [4, 5, 10, 11]
            dry_seasons = [12, 1, 2, 7, 8]
        elif location.lower() == 'medellin':
            # Medellín: clima templado, menos nuboso
            base_radiation = 800
            base_clouds = 40
            temp_range = (15, 30)
            rainy_seasons = [4, 5, 10, 11]
            dry_seasons = [12, 1, 2, 7, 8]
        elif location.lower() == 'cali':
            # Cali: clima cálido, menos nuboso
            base_radiation = 900
            base_clouds = 30
            temp_range = (20, 35)
            rainy_seasons = [4, 5, 10, 11]
            dry_seasons = [12, 1, 2, 7, 8]
        else:
            # Ubicación genérica
            base_radiation = 750
            base_clouds = 50
            temp_range = (15, 30)
            rainy_seasons = [4, 5, 10, 11]
            dry_seasons = [12, 1, 2, 7, 8]
        
        while current_date <= end_date:
            # Simular variaciones estacionales
            month = current_date.month
            if month in rainy_seasons:  # Temporada de lluvias
                seasonal_radiation = base_radiation * 0.7
                seasonal_clouds = base_clouds * 1.3
            elif month in dry_seasons:  # Temporada seca
                seasonal_radiation = base_radiation * 1.2
                seasonal_clouds = base_clouds * 0.7
            else:  # Transiciones
                seasonal_radiation = base_radiation
                seasonal_clouds = base_clouds
            
            # Simular variaciones diarias
            daily_variation = random.uniform(-0.15, 0.15)
            daily_radiation = seasonal_radiation * (1 + daily_variation)
            daily_clouds = seasonal_clouds * (1 + random.uniform(-0.1, 0.1))
            
            # Simular temperatura
            daily_temp = random.uniform(temp_range[0], temp_range[1])
            
            # Simular humedad (inversamente proporcional a la temperatura)
            daily_humidity = max(30, min(95, 100 - (daily_temp - 20) * 2))
            
            # Simular velocidad del viento
            daily_wind = random.uniform(0, 20)
            
            # Crear registro de datos solares (esto se puede expandir en el futuro)
            # Por ahora, solo mostramos la información en el log
            solar_data_created += 1
            current_date += timedelta(days=1)
        
        self.stdout.write(f'  - {solar_data_created} registros de datos solares simulados para {location}')
        self.stdout.write(f'    - Radiación base: {base_radiation} W/m²')
        self.stdout.write(f'    - Cobertura de nubes base: {base_clouds}%')
        self.stdout.write(f'    - Rango de temperatura: {temp_range[0]}°C - {temp_range[1]}°C')
        
        # Información específica de Pasto
        if location.lower() == 'pasto':
            self.stdout.write(f'    - Altitud: 2,527 msnm (altiplano nariñense)')
            self.stdout.write(f'    - Clima: Templado de montaña tropical')
            self.stdout.write(f'    - Temporadas de lluvia: Marzo-Mayo y Octubre-Diciembre')
            self.stdout.write(f'    - Temporada seca: Junio-Septiembre')
