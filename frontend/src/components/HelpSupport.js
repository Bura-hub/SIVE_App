import React, { useState, useEffect } from 'react';

function HelpSupport({ onClose }) {
    const [activeSection, setActiveSection] = useState('overview');

    // Accesibilidad: cerrar el modal con la tecla Escape.
    useEffect(() => {
        const onKey = (e) => { if (e.key === 'Escape') onClose(); };
        document.addEventListener('keydown', onKey);
        return () => document.removeEventListener('keydown', onKey);
    }, [onClose]);

    const sections = [
        { 
            id: 'overview', 
            name: 'Vista General', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
            )
        },
        { 
            id: 'features', 
            name: 'Características', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                </svg>
            )
        },
        { 
            id: 'navigation', 
            name: 'Navegación', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
            )
        },
        { 
            id: 'troubleshooting', 
            name: 'Solución de Problemas', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
            )
        },
        {
            id: 'contact',
            name: 'Contacto',
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                </svg>
            )
        },
        {
            id: 'about',
            name: 'Acerca del Proyecto',
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
            )
        }
    ];

    // Iconos reutilizables (Heroicons outline)
    const IconBolt = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>);
    const IconTarget = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>);
    const IconChart = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>);
    const IconSolar = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2" ry="2"></rect><path d="M7 12h2l1 2 2-4 1 2h2"></path></svg>);
    const IconWeather = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" /></svg>);
    const IconReport = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>);
    const IconShield = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></svg>);
    const IconHome = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>);
    const IconMarket = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3v18h18M9 17V9m4 8V5m4 12v-6" /></svg>);
    const IconWarn = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" /></svg>);
    const IconRefresh = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>);
    const IconKey = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>);
    const IconBuilding = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" /></svg>);
    const IconMail = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>);
    const IconDoc = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg>);
    const IconBook = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>);
    const IconCash = (<svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" /></svg>);

    const helpContent = {
        overview: {
            title: 'SIVE, Sistema de Visualización Energético',
            description: 'Plataforma web de visualización del proyecto MTE de la Universidad de Nariño.',
            content: [
                {
                    subtitle: '¿Qué es SIVE?',
                    text: 'SIVE muestra los datos históricos y los indicadores de consumo, generación y clima de las cinco instituciones del proyecto MTE, junto con los datos del mercado eléctrico colombiano (XM). Las mediciones de las sedes llegan del conector SCADA cada hora, y SIVE las guarda y las concilia cada noche con las del conector.',
                    icon: IconBolt
                },
                {
                    subtitle: 'El proyecto MTE',
                    text: 'SIVE hace parte del proyecto MTE de la Universidad de Nariño, que instaló en cada una de las cinco instituciones una planta solar de 17,55 kWp y medición inteligente, para pilotar un modelo transaccional de energía con fuentes no convencionales (FNCE).',
                    icon: IconTarget
                },
                {
                    subtitle: 'Consulta sin cuenta (modo invitado)',
                    text: 'Cualquier persona puede consultar SIVE sin iniciar sesión, como «Invitado», en solo lectura: el Dashboard, Medidores, Inversores, Estaciones, Indicadores Solares y Datos Externos. Con una cuenta se puede además sincronizar y recalcular los datos. Exportar reportes es solo para administradores. El botón «Iniciar sesión» abre el acceso cuando hace falta.',
                    icon: IconKey
                },
                {
                    subtitle: 'Para qué sirve',
                    text: 'Permite seguir el comportamiento energético (demanda, generación y balance) y climático de cada sede, y el desempeño de cada planta solar, como apoyo a las decisiones de eficiencia energética y al seguimiento de la transición hacia las energías renovables.',
                    icon: IconChart
                }
            ]
        },
        features: {
            title: 'Características del Sistema',
            description: 'Lo que puedes hacer en SIVE.',
            content: [
                {
                    subtitle: 'Dashboard',
                    text: 'Resumen del mes en curso: demanda de los circuitos medidos (el Medidor 1 de cada institución), generación de las cinco plantas solares, balance entre las dos, potencia media de la flota y clima. Cada cifra se compara con el mes anterior en el mismo tiempo transcurrido. La tarjeta de inversores cuenta los que enviaron datos en las últimas 24 horas.',
                    icon: IconChart
                },
                {
                    subtitle: 'Medidores',
                    text: 'Para un medidor o para todos juntos: energía importada de la red, demanda pico (la mayor media de 15 minutos), factor de carga y factor de potencia, en la institución y el rango de fechas que elijas.',
                    icon: IconBolt
                },
                {
                    subtitle: 'Inversores',
                    text: 'Generación, potencia máxima, factor de potencia y frecuencia mientras el inversor genera, desbalance de fases y de corriente, y Performance Ratio con la estación de la institución. Cuando un dato no se puede calcular, la tarjeta dice «No disponible» y el motivo, nunca 0. La eficiencia DC/AC no se calcula, porque el inversor solo reporta una de sus entradas de corriente continua.',
                    icon: IconSolar
                },
                {
                    subtitle: 'Estaciones',
                    text: 'Irradiancia acumulada y horas solares pico (HSP), temperatura, velocidad y dirección del viento (con rosa de los vientos), precipitación y potencia fotovoltaica teórica. Si la estación no tiene un sensor, su tarjeta dice «No disponible».',
                    icon: IconWeather
                },
                {
                    subtitle: 'Indicadores Solares',
                    text: 'El desempeño de la planta de cada institución: energía generada, rendimiento específico, factor de capacidad, producción frente a lo esperado, Performance Ratio, demanda del circuito, cobertura solar, autoconsumo, ahorro estimado, CO₂ evitado y disponibilidad de datos, con gráficas y una tabla por periodo.',
                    icon: IconTarget
                },
                {
                    subtitle: 'Datos Externos (XM)',
                    text: 'Datos del mercado eléctrico colombiano publicados por XM: precios de la energía, generación y demanda nacional, factor de emisión de CO₂ y comercio internacional de energía.',
                    icon: IconMarket
                },
                {
                    subtitle: 'Exportar Reportes',
                    text: 'Los administradores generan y descargan informes en PDF, Excel y CSV por institución y período.',
                    icon: IconReport
                },
                {
                    subtitle: 'En el teléfono',
                    text: 'SIVE se adapta a pantallas pequeñas: el menú se abre con el botón de tres líneas de la barra superior, y los filtros y las gráficas ocupan todo el ancho.',
                    icon: IconHome
                }
            ]
        },
        navigation: {
            title: 'Guía de Navegación',
            description: 'Cómo moverte por SIVE.',
            content: [
                {
                    subtitle: 'Menú y tarjetas',
                    text: 'El menú lateral lleva a cada pantalla. El botón de información (i) de cada tarjeta explica qué mide, cómo se calcula y cómo leerla.',
                    icon: IconHome
                },
                {
                    subtitle: 'Filtros y rango de fechas',
                    text: 'En Medidores, Inversores, Estaciones e Indicadores Solares elige la institución, el dispositivo y el rango de fechas. La vista horaria admite hasta 31 días, y la diaria y la mensual, hasta un año (doce meses). El aviso «Datos disponibles» indica desde y hasta cuándo hay mediciones para la selección.',
                    icon: IconBolt
                },
                {
                    subtitle: 'Cálculo de los indicadores',
                    text: 'SIVE calcula los indicadores cada hora y los vuelve a calcular cuando la conciliación nocturna recupera mediciones atrasadas, así que no hace falta pedirlos. Con sesión iniciada, los botones de cálculo de cada pantalla y «Sincronizar datos y calcular KPIs» del Dashboard fuerzan el recálculo del periodo elegido.',
                    icon: IconRefresh
                },
                {
                    subtitle: 'Exportar reportes',
                    text: 'En «Exportar Reportes» (solo administradores) elige categoría, institución, tipo de reporte, formato y rango. El archivo se genera en segundo plano y queda disponible para descargar.',
                    icon: IconReport
                },
                {
                    subtitle: 'Perfil y sesión',
                    text: 'Con sesión iniciada, tu perfil está en el menú de usuario. Por seguridad la sesión expira tras un tiempo de inactividad, y al cerrarla SIVE vuelve al modo invitado.',
                    icon: IconKey
                }
            ]
        },
        troubleshooting: {
            title: 'Solución de Problemas',
            description: 'Respuestas a las dudas más frecuentes.',
            content: [
                {
                    subtitle: 'No puedo iniciar sesión',
                    text: 'Verifica usuario y contraseña. Tras varios intentos fallidos la cuenta se bloquea temporalmente por seguridad; espera unos minutos o contacta al administrador. Mientras tanto puedes seguir consultando como invitado.',
                    icon: IconWarn
                },
                {
                    subtitle: '¿Por qué los datos no son en tiempo real?',
                    text: 'SIVE muestra datos históricos. Las mediciones de las sedes llegan cada hora, y las que una sede envía con retraso se recuperan en la conciliación con el conector, a las 00:40, a las 01:30 y a las 06:40, 12:40 y 18:40. Por eso el último día puede completarse al día siguiente. Ninguna tarjeta muestra valores en vivo.',
                    icon: IconRefresh
                },
                {
                    subtitle: 'Una tarjeta dice «No disponible»',
                    text: 'El dato no se midió en el rango o no se puede calcular con lo medido, por ejemplo un sensor que la estación no tiene o un Performance Ratio sin días válidos. La tarjeta explica el motivo. SIVE no muestra 0 en lugar de un dato que falta.',
                    icon: IconWarn
                },
                {
                    subtitle: 'No aparece una institución o dispositivo',
                    text: 'Puede que no haya reportado datos en el rango elegido. Revisa el aviso de disponibilidad de datos, ajusta las fechas o consulta con el administrador el estado de ese dispositivo.',
                    icon: IconBolt
                },
                {
                    subtitle: 'Un mes se ve muy distinto de otro',
                    text: 'Suele deberse a la cobertura de datos, por ejemplo un dispositivo que dejó de reportar parte del período, y no a un error de cálculo. Compara la disponibilidad de datos de los dos meses.',
                    icon: IconChart
                },
                {
                    subtitle: 'El reporte no se genera o no descarga',
                    text: 'Exportar reportes requiere una cuenta de administrador. Selecciona institución y un rango de fechas válido. El reporte se procesa en segundo plano; si tarda, espera unos segundos y vuelve a intentar la descarga.',
                    icon: IconReport
                },
                {
                    subtitle: 'Mi sesión se cerró',
                    text: 'Por seguridad las sesiones caducan. SIVE sigue en modo invitado; vuelve a iniciar sesión para recalcular datos o exportar reportes.',
                    icon: IconKey
                }
            ]
        },
        contact: {
            title: 'Contacto y Soporte',
            description: 'Quién desarrolla SIVE y cómo obtener ayuda.',
            content: [
                {
                    subtitle: 'Universidad de Nariño, GIIEE',
                    text: 'Sistema desarrollado por el Grupo de Investigación en Ingeniería Eléctrica y Electrónica (GIIEE), Departamento de Ingeniería Electrónica de la Universidad de Nariño.',
                    icon: IconBuilding
                },
                {
                    subtitle: 'Investigador principal',
                    text: 'Wilson Achicanoy, Ph.D. Correo institucional: wilachic@udenar.edu.co',
                    icon: IconMail
                },
                {
                    subtitle: 'Soporte y accesos',
                    text: 'Para reportar problemas, solicitar una cuenta o restablecer credenciales, contacta al administrador del sistema o al grupo GIIEE.',
                    icon: IconShield
                },
                {
                    subtitle: 'Documentación técnica (API)',
                    text: 'Los administradores pueden consultar la documentación de la API en /sive/docs (Swagger) y /sive/redocs (Redoc), tras iniciar sesión en el panel de administración.',
                    icon: IconDoc
                }
            ]
        },
        about: {
            title: 'Acerca del Proyecto',
            description: 'El proyecto MTE detrás de SIVE.',
            content: [
                {
                    subtitle: 'Nombre del proyecto',
                    text: '«Desarrollo de un modelo transaccional de energía no convencional de múltiples agentes para el departamento de Nariño» (MTE). Palabras clave: energía renovable no convencional, transición energética y mercado transaccional de energía.',
                    icon: IconBook
                },
                {
                    subtitle: 'Objetivo del proyecto',
                    text: 'Desarrollar un piloto de un modelo transaccional de energía eléctrica, incluyendo fuentes no convencionales (FNCE), aplicado al contexto del departamento de Nariño.',
                    icon: IconTarget
                },
                {
                    subtitle: 'Instituciones monitoreadas',
                    text: 'Generación fotovoltaica y medición inteligente en la Universidad de Nariño (Udenar), la Universidad Mariana (Unimar), la Universidad Cooperativa de Colombia, campus Pasto (UCC), la Universidad CESMAG (Unicesmag) y el Hospital Universitario Departamental de Nariño (HUDN), todas en el municipio de Pasto.',
                    icon: IconBuilding
                },
                {
                    subtitle: 'Financiación',
                    text: 'Proyecto financiado por la Asignación para la Ciencia, Tecnología e Innovación (CTeI) del Sistema General de Regalías (SGR), código BPIN 2021000100499 (registro SIGP 89530). Entidad proponente: Universidad de Nariño.',
                    icon: IconCash
                },
                {
                    subtitle: 'Glosario: FNCE',
                    text: 'Fuentes No Convencionales de Energía: fuentes renovables como la solar, eólica, biomasa, geotérmica e hidroeléctrica de pequeña escala.',
                    icon: IconBolt
                },
                {
                    subtitle: 'Glosario: Prosumidor',
                    text: 'Usuario conectado a la red que además genera su propia energía (por ejemplo, con paneles solares), y que puede consumir energía de la red o inyectarle sus excedentes.',
                    icon: IconSolar
                },
                {
                    subtitle: 'Glosario: Energía transactiva',
                    text: 'Conjunto de mecanismos económicos y de control que equilibran de forma dinámica la oferta y la demanda usando el valor (precio) como parámetro operativo clave.',
                    icon: IconMarket
                },
                {
                    subtitle: 'Glosario: Microrred',
                    text: 'Sistema de distribución de baja tensión con recursos energéticos distribuidos y cargas, que puede operar conectado a la red principal o de forma aislada (modo isla).',
                    icon: IconChart
                }
            ]
        }
    };

    return (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            role="dialog" aria-modal="true" aria-label="Ayuda y soporte">
            <div className="bg-white rounded-3xl shadow-2xl max-w-7xl w-full max-h-[95vh] overflow-hidden border border-gray-100">
                {/* Header */}
                <div className="flex items-center justify-between p-8 border-b border-gray-100 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
                    <div className="space-y-2">
                        <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-700 to-purple-700 bg-clip-text text-transparent">
                            Ayuda y Soporte
                        </h2>
                        <p className="text-slate-600 text-lg">Guía de uso de SIVE</p>
                    </div>
                    <button
                        onClick={onClose}
                        aria-label="Cerrar"
                        className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition duration-150 p-3 rounded-full"
                    >
                        <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="flex h-[calc(95vh-200px)]">
                    {/* Sidebar de navegación */}
                    <div className="w-80 bg-gradient-to-b from-slate-50 to-blue-50 border-r border-slate-200 p-6">
                        <nav className="space-y-3">
                            {sections.map((section) => (
                                <button
                                    key={section.id}
                                    onClick={() => setActiveSection(section.id)}
                                    className={`w-full flex items-center px-6 py-4 rounded-2xl text-left transition duration-300 ${
                                        activeSection === section.id
                                            ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg shadow-blue-500/25 transform scale-105'
                                            : 'text-slate-600 hover:bg-white hover:text-slate-800 hover:shadow-md hover:scale-105 border border-transparent hover:border-slate-200'
                                    }`}
                                >
                                    <div className="mr-4 text-slate-600">{section.icon}</div>
                                    <span className="font-semibold text-lg">{section.name}</span>
                                </button>
                            ))}
                        </nav>
                    </div>

                    {/* Contenido principal */}
                    <div className="flex-1 p-8 overflow-y-auto bg-gradient-to-br from-white to-slate-50/30">
                        {activeSection && helpContent[activeSection] && (
                            <div className="space-y-8">
                                <div className="text-center mb-8">
                                    <h3 className="text-3xl font-bold text-slate-800 mb-4">
                                        {helpContent[activeSection].title}
                                    </h3>
                                    <p className="text-slate-600 text-lg max-w-3xl mx-auto">
                                        {helpContent[activeSection].description}
                                    </p>
                                </div>

                                <div className="max-w-4xl mx-auto space-y-6">
                                    {helpContent[activeSection].content.map((item, index) => (
                                        <div key={index} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-lg hover:shadow-xl transition duration-300">
                                            <div className="flex items-start space-x-4">
                                                <div className="w-12 h-12 bg-gradient-to-br from-blue-100 to-purple-100 rounded-xl flex items-center justify-center flex-shrink-0 shadow-md">
                                                    <span className="text-2xl">{item.icon}</span>
                                                </div>
                                                <div className="flex-1">
                                                    <h4 className="text-xl font-bold text-slate-800 mb-3">
                                                        {item.subtitle}
                                                    </h4>
                                                    <p className="text-slate-600 text-lg leading-relaxed">
                                                        {item.text}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                {/* Información adicional según la sección */}
                                {activeSection === 'overview' && (
                                    <div className="mt-8 bg-gradient-to-r from-blue-50 to-purple-50 rounded-3xl p-8 border border-blue-200">
                                        <div className="text-center">
                                            <h4 className="text-2xl font-bold text-blue-800 mb-4">
                                                ¿Listo para comenzar?
                                            </h4>
                                            <p className="text-blue-700 text-lg mb-6">
                                                Explora las diferentes secciones para conocer todo lo que puedes hacer en SIVE.
                                            </p>
                                            <div className="flex justify-center space-x-4">
                                                <button
                                                    onClick={() => setActiveSection('features')}
                                                    className="bg-gradient-to-r from-blue-600 to-purple-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-blue-700 hover:to-purple-700 transition duration-300 shadow-lg hover:shadow-xl"
                                                >
                                                    Ver Características
                                                </button>
                                                <button
                                                    onClick={() => setActiveSection('navigation')}
                                                    className="bg-white text-blue-600 px-6 py-3 rounded-xl font-semibold border-2 border-blue-200 hover:bg-blue-50 transition duration-300"
                                                >
                                                    Guía de Navegación
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {activeSection === 'troubleshooting' && (
                                    <div className="mt-8 bg-gradient-to-r from-amber-50 to-orange-50 rounded-3xl p-8 border border-amber-200">
                                        <div className="text-center">
                                            <h4 className="text-2xl font-bold text-amber-800 mb-4">
                                                ¿No encontraste la solución?
                                            </h4>
                                            <p className="text-amber-700 text-lg mb-6">
                                                Si tu problema no está listado aquí, no dudes en contactar al equipo de soporte técnico.
                                            </p>
                                            <button
                                                onClick={() => setActiveSection('contact')}
                                                className="bg-gradient-to-r from-amber-600 to-orange-600 text-white px-6 py-3 rounded-xl font-semibold hover:from-amber-700 hover:to-orange-700 transition duration-300 shadow-lg hover:shadow-xl"
                                            >
                                                Ver Información de Contacto
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

export default HelpSupport;
