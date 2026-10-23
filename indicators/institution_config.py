"""
Configuración energética por institución: qué medidor da la demanda, de qué tipo es, qué inversor da la
generación, capacidad FV, estación meteorológica y comercializador.

Es la misma convención del módulo de mercado P2P con blockchain (`mercado-p2p/motor_p2p/semillas/agentes.json`),
para que SIVE, el Control Panel y el mercado den las mismas cifras. Ver indicators/indicators.md.

Las claves son el `scada_id` del conector (UUID), que es estable; el `id` de Django no lo es entre instalaciones.

- tipo_medidor:
    'gross'       el medidor mide la carga: D = max(0, P_M1)
    'net'         el medidor está en el punto de conexión y la FV queda aguas abajo: D = max(0, P_M1 + Σ inversores)
    'net_partial' igual que 'net' (solo parte de la FV queda aguas abajo; se reconstruye igual)
- inversores_generacion: inversores cuya suma es G. Un inversor solo cuenta hasta su fecha de retiro (exclusiva).
- respaldo_generacion: antes de `desde`, G = inversor de respaldo × factor (el Inversor MTE de Udenar
  existe desde el 2025-09-03; antes se escala el Fronius 1 por la razón de energías, k ≈ 1,2054, r = 0,997).
- estacion_apta_pr: False si la estación no sirve para el PR (Udenar: 7–12 kWh/m²/día, físicamente imposible).
- Validación cruzada del PR: un día de la estación de una institución solo cuenta si su irradiación queda a ±25 % de
  la de la estación de referencia (ESTACION_REFERENCIA_PR, Alvernia) ese mismo día. La del HUDN, por ejemplo, marcaba
  un 50–75 % más que Alvernia en abr–jun 2025 y un 20 % menos en feb–mar 2026, y solo coincidía en jul–nov 2025.
  Además, un mes solo vale si la mediana de la razón diaria estación/referencia queda a ±10 % (con ≥ 5 días para
  contrastar): el filtro diario deja pasar un sesgo sistemático del 20 % que infla el PR en 1/0,8.
"""
from datetime import date

KWP_POR_PLANTA = 17.55            # 30 módulos Jinko de 585 Wp
DISENO_KWH_DIA = 59.4             # Informe Técnico 2: producción de diseño por sistema
DISENO_IRRADIACION_KWH_M2_DIA = 4.5
DISENO_PERDIDAS = 0.20
FACTOR_CO2_KG_KWH = 0.112         # Factor del SIN, UPME Res. 0705/2024
ARBOLES_POR_TONELADA_CO2 = 545 / 12   # Informe Técnico 2: 545 árboles por 12 t

# Estación de referencia para validar la irradiación de las demás (la de Alvernia, Universidad Mariana: completa
# y coherente con la de Cesmag) y tolerancia diaria admitida.
INSTITUCION_REFERENCIA_PR = '0357e3a6-ebdd-45f2-bd1a-0c384c522df3'
TOLERANCIA_REFERENCIA_PR = 0.25        # por día (las nubes difieren entre sedes)
TOLERANCIA_SESGO_MENSUAL_PR = 0.10     # mediana mensual de la razón estación / referencia
MIN_DIAS_SESGO_MENSUAL_PR = 5          # días emparejados mínimos para juzgar el sesgo del mes

INSTITUCIONES = {
    '04abaa1c-9f61-4ae4-8b53-44f66cce93c6': {
        'nombre': 'Udenar',
        'medidor_demanda': '7ba9fa00-7ef9-4246-8c30-85ea56088e0d',     # Bloque Sur - Medidor 1
        'tipo_medidor': 'net',
        'inversores_generacion': ['c03a5f4a-f78e-47d7-8818-b50544b3f531'],   # Inversor MTE
        'respaldo_generacion': {
            'inversor': 'ada64a56-331c-4489-a02c-7aac55d54111',        # inverter1 (Fronius)
            'factor': 1.2054,
            'desde': date(2025, 9, 3),
        },
        # Para reconstruir D en el medidor neto se suman todos los inversores aguas abajo, mientras existan.
        'inversores_reconstruccion': [
            'ada64a56-331c-4489-a02c-7aac55d54111',
            '37f796af-7caa-459f-bc86-3e2f7936a879',
            'c03a5f4a-f78e-47d7-8818-b50544b3f531',
        ],
        'retirados': {
            'ada64a56-331c-4489-a02c-7aac55d54111': date(2026, 4, 11),
            '37f796af-7caa-459f-bc86-3e2f7936a879': date(2026, 4, 11),
        },
        'estacion': '46094855-4fe6-4c10-afe3-444a101719e2',
        'estacion_apta_pr': False,
        'comercializador': 'asc',
        'kwp': KWP_POR_PLANTA,
    },
    '0357e3a6-ebdd-45f2-bd1a-0c384c522df3': {
        'nombre': 'Mariana',
        'medidor_demanda': 'b06d770e-ec25-49a0-949d-60c9e169f2bb',     # Medidor 1 - Alvernia
        'tipo_medidor': 'net_partial',
        'inversores_generacion': ['0f962572-fab3-4c09-bffc-465b56a22d8d'],
        'respaldo_generacion': None,
        'inversores_reconstruccion': ['0f962572-fab3-4c09-bffc-465b56a22d8d'],
        'retirados': {},
        'estacion': '1fb6c4ae-2e7c-4758-80bf-156c7826fead',
        'estacion_apta_pr': True,
        'comercializador': 'asc',
        'kwp': KWP_POR_PLANTA,
    },
    'efe7b26b-4c1e-480f-b736-678ed7aedfb5': {
        'nombre': 'UCC',
        'medidor_demanda': '86b9c020-4645-4c39-891a-d1e8a7048c12',     # Medidor 1 - UCC
        'tipo_medidor': 'net_partial',
        'inversores_generacion': ['29630827-0242-492f-9ed0-a48d120da2ac'],
        'respaldo_generacion': None,
        'inversores_reconstruccion': ['29630827-0242-492f-9ed0-a48d120da2ac'],
        'retirados': {},
        'estacion': '74154481-3f6c-4827-a8d7-ea6fbae62fd9',
        'estacion_apta_pr': True,
        'comercializador': 'asc',
        'kwp': KWP_POR_PLANTA,
    },
    '40a047f8-295a-4b8a-8d2c-649ddc18e600': {
        'nombre': 'HUDN',
        'medidor_demanda': '628cf5fd-e92b-4f4b-b5eb-a62ccb1bdec9',     # Medidor 1 - HUDN (subestación piso 3)
        'tipo_medidor': 'gross',
        'inversores_generacion': ['f6893ba9-7175-44ea-8624-a47bf55158c9'],
        'respaldo_generacion': None,
        'inversores_reconstruccion': [],
        'retirados': {},
        'estacion': '49435c0b-ada3-4ced-ad15-9418013a30d1',
        'estacion_apta_pr': True,
        'comercializador': 'asc',
        'kwp': KWP_POR_PLANTA,
    },
    'c4be3013-b100-4fca-8ecc-54a5b728a28c': {
        'nombre': 'Cesmag',
        'medidor_demanda': '4c57e1a2-08e5-4ab4-b37a-c09f4b8d2c02',     # Medidor 1 - Cesmag
        'tipo_medidor': 'gross',
        'inversores_generacion': ['e96986a9-a127-4139-975d-1a711ae25327'],
        'respaldo_generacion': None,
        'inversores_reconstruccion': [],
        'retirados': {},
        'estacion': '819dfc27-fe61-42e6-9413-0f8820bea03e',
        'estacion_apta_pr': True,
        'comercializador': 'cedenar',
        'kwp': KWP_POR_PLANTA,
    },
}

# Dispositivos que no son de las plantas del proyecto: no cuentan en «inversores activos» ni en la flota.
DISPOSITIVOS_EXCLUIDOS_FLOTA = {
    '3a5eca15-cd03-4a83-8981-b432d2217344',   # Prueba (Udenar)
    '0306b653-9f11-4f80-a687-1e35daf336ce',   # prueba (Udenar)
}


def config_institucion(scada_id):
    """Devuelve la configuración de la institución o None si no es una planta del proyecto (p. ej. CEDENAR)."""
    return INSTITUCIONES.get(str(scada_id))


def inversor_vigente(config, inversor_scada_id, dia):
    """True si el inversor cuenta el día `dia` (no está retirado o se retiró después)."""
    retiro = config['retirados'].get(str(inversor_scada_id))
    return retiro is None or dia < retiro
