/**
 * Módulo común de iconos SVG de SIVE (estilo Lucide: 24×24, trazo 2,
 * currentColor). Única fuente de verdad — no duplicar paths inline en los
 * componentes. El color se hereda del contexto (className con text-*).
 */
import React from 'react';

const base = (props, children) => {
  const { size = 24, className = '', ...rest } = props;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      {...rest}
    >
      {children}
    </svg>
  );
};

/* ============ Set del sidebar (identidad de cada pantalla) ============ */

export const IconHome = (p) => base(p, (
  <path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
));

// Dashboard: gráfico de barras (panorama mensual)
export const IconDashboard = (p) => base(p, (<>
  <path d="M3 21h18" />
  <path d="M7 21V11" />
  <path d="M12 21V4" />
  <path d="M17 21v-7" />
</>));

// Medidores: velocímetro (instrumento de medición)
export const IconGauge = (p) => base(p, (<>
  <path d="m12 14 4-4" />
  <path d="M3.34 19a10 10 0 1 1 17.32 0" />
</>));

// Inversores: caja con onda senoidal (salida AC)
export const IconInverter = (p) => base(p, (<>
  <rect x="3" y="5" width="18" height="14" rx="2" ry="2" />
  <path d="M6.5 13.5c1.2-3.2 2.6-3.2 3.7 0s2.6 3.2 3.7 0 2.5-3.2 3.6 0" />
</>));

// Estaciones: sol y nube (meteorología)
export const IconCloudSun = (p) => base(p, (<>
  <path d="M12 2v2" />
  <path d="m4.93 4.93 1.41 1.41" />
  <path d="M20 12h2" />
  <path d="m19.07 4.93-1.41 1.41" />
  <path d="M15.947 12.65a4 4 0 0 0-5.925-4.128" />
  <path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z" />
</>));

// Datos externos: globo (fuente externa / mercado XM)
export const IconGlobe = (p) => base(p, (<>
  <circle cx="12" cy="12" r="10" />
  <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
  <path d="M2 12h20" />
</>));

// Reportes: documento con flecha de descarga (exportar)
export const IconFileDown = (p) => base(p, (<>
  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
  <path d="M14 2v6h6" />
  <path d="M12 18v-6" />
  <path d="m9 15 3 3 3-3" />
</>));

/* ============ Tarjetas KPI del Dashboard ============ */

export const IconZap = (p) => base(p, (
  <path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z" />
));

export const IconSolarPanel = (p) => base(p, (<>
  <path d="M4 3h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
  <path d="M3 9h18" />
  <path d="M9 3v11" />
  <path d="M15 3v11" />
  <path d="M12 14v7" />
  <path d="M8 21h8" />
</>));

export const IconScale = (p) => base(p, (<>
  <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
  <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
  <path d="M7 21h10" />
  <path d="M12 3v18" />
  <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
</>));

export const IconPower = (p) => base(p, (<>
  <path d="M12 2v10" />
  <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
</>));

export const IconThermometer = (p) => base(p, (
  <path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z" />
));

export const IconDroplets = (p) => base(p, (<>
  <path d="M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05z" />
  <path d="M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97" />
</>));

export const IconWind = (p) => base(p, (<>
  <path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2" />
  <path d="M9.6 4.6A2 2 0 1 1 11 8H2" />
  <path d="M12.6 19.4A2 2 0 1 0 14 16H2" />
</>));

export const IconSun = (p) => base(p, (<>
  <circle cx="12" cy="12" r="4" />
  <path d="M12 2v2" />
  <path d="M12 20v2" />
  <path d="m4.93 4.93 1.41 1.41" />
  <path d="m17.66 17.66 1.41 1.41" />
  <path d="M2 12h2" />
  <path d="M20 12h2" />
  <path d="m6.34 17.66-1.41 1.41" />
  <path d="m19.07 4.93-1.41 1.41" />
</>));

/* ============ Comunes (duplicados por toda la app) ============ */

export const IconInfo = (p) => base(p, (<>
  <circle cx="12" cy="12" r="10" />
  <path d="M12 16v-4" />
  <path d="M12 8h.01" />
</>));

export const IconClose = (p) => base(p, (
  <path d="M18 6 6 18M6 6l12 12" />
));

export const IconDownload = (p) => base(p, (<>
  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
  <path d="m7 10 5 5 5-5" />
  <path d="M12 15V3" />
</>));

export const IconCheckCircle = (p) => base(p, (<>
  <path d="M21.801 10A10 10 0 1 1 17 3.335" />
  <path d="m9 11 3 3L22 4" />
</>));

export const IconAlertTriangle = (p) => base(p, (<>
  <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
  <path d="M12 9v4" />
  <path d="M12 17h.01" />
</>));

export const IconRefresh = (p) => base(p, (<>
  <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
  <path d="M21 3v5h-5" />
  <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
  <path d="M8 21H3v-5" />
</>));

/* ============ Específicos de pantallas ============ */

// Estabilidad / actividad (frecuencia)
export const IconActivity = (p) => base(p, (
  <path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2" />
));

// Distorsión armónica (THD): onda con marcas
export const IconWaveform = (p) => base(p, (<>
  <path d="M2 13a2 2 0 0 0 2-2V7a2 2 0 0 1 4 0v13a2 2 0 0 0 4 0V4a2 2 0 0 1 4 0v13a2 2 0 0 0 4 0v-4a2 2 0 0 1 2-2" />
</>));

// Gráfica de tendencia (mercado)
export const IconTrendingUp = (p) => base(p, (<>
  <path d="M3 3v16a2 2 0 0 0 2 2h16" />
  <path d="m7 14 3.5-3.5 3 3L19 8" />
  <path d="M15.5 8H19v3.5" />
</>));

/* ============ Menú de usuario flotante ============ */

// Configuración: engranaje Lucide (settings) — path fiel al mockup C aprobado
export const IconSettings = (p) => base(p, (<>
  <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
  <circle cx="12" cy="12" r="3" />
</>));

// Ayuda y soporte: círculo con interrogante (help-circle)
export const IconHelpCircle = (p) => base(p, (<>
  <circle cx="12" cy="12" r="10" />
  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
  <path d="M12 17h.01" />
</>));

// Cerrar sesión (log-out)
export const IconLogOut = (p) => base(p, (<>
  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
  <polyline points="16 17 21 12 16 7" />
  <line x1="21" y1="12" x2="9" y2="12" />
</>));

// Chevron hacia abajo (disparador del menú)
export const IconChevronDown = (p) => base(p, (
  <path d="m6 9 6 6 6-6" />
));

// Chevron hacia la derecha (indicador "ir a" de cada acción)
export const IconChevronRight = (p) => base(p, (
  <path d="m9 6 6 6-6 6" />
));

// Escudo (rol administrador)
export const IconShield = (p) => base(p, (
  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
));
