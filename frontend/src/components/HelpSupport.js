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
        }
    ];

    const helpContent = {
        overview: {
            title: 'Sistema de Visualización Energético (MTE)',
            description: 'Plataforma integral para el monitoreo y análisis de datos energéticos en tiempo real.',
            content: [
                {
                    subtitle: '¿Qué es MTE?',
                    text: 'MTE es una plataforma avanzada que permite visualizar, analizar y gestionar datos energéticos de múltiples fuentes incluyendo medidores eléctricos, inversores solares y estaciones meteorológicas.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Objetivo Principal',
                    text: 'Facilitar la toma de decisiones informadas sobre el consumo y generación de energía, optimizando la eficiencia energética y promoviendo el uso de energías renovables.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Beneficios',
                    text: 'Monitoreo en tiempo real, análisis histórico, reportes automatizados, alertas inteligentes y visualización intuitiva de datos complejos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                    )
                }
            ]
        },
        features: {
            title: 'Características Principales del Sistema',
            description: 'Descubre todas las funcionalidades disponibles en la plataforma MTE.',
            content: [
                {
                    subtitle: 'Dashboard Inteligente',
                    text: 'Panel principal con KPIs en tiempo real, gráficos interactivos y métricas de rendimiento energético.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Monitoreo de Medidores',
                    text: 'Seguimiento detallado del consumo eléctrico, potencia instantánea, factor de potencia y calidad de energía.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Gestión de Inversores',
                    text: 'Control y monitoreo de sistemas fotovoltaicos, eficiencia de conversión y generación de energía solar.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <rect x="3" y="5" width="18" height="14" rx="2" ry="2"></rect>
                            <path d="M7 12h2l1 2 2-4 1 2h2"></path>
                            <path d="M17 16h.01"></path>
                            <path d="M17 8h.01"></path>
                        </svg>
                    )
                },
                {
                    subtitle: 'Estaciones Meteorológicas',
                    text: 'Datos climáticos en tiempo real: temperatura, humedad, velocidad del viento, radiación solar y presión atmosférica.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Reportes Avanzados',
                    text: 'Generación automática de reportes personalizables, exportación en múltiples formatos y análisis comparativos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Seguridad Avanzada',
                    text: 'Autenticación robusta, control de acceso basado en roles, auditoría de acciones y encriptación de datos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                        </svg>
                    )
                }
            ]
        },
        navigation: {
            title: 'Guía de Navegación',
            description: 'Aprende a navegar eficientemente por la plataforma MTE.',
            content: [
                {
                    subtitle: 'Página de Inicio',
                    text: 'Accede al dashboard principal desde el menú lateral. Aquí encontrarás un resumen completo del sistema energético.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Medidores Eléctricos',
                    text: 'Navega a "Medidores" para ver el consumo eléctrico detallado, filtros por fecha y análisis de tendencias.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Inversores Solares',
                    text: 'Selecciona "Inversores" para monitorear la generación solar, eficiencia y estado de los sistemas fotovoltaicos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <rect x="3" y="5" width="18" height="14" rx="2" ry="2"></rect>
                            <path d="M7 12h2l1 2 2-4 1 2h2"></path>
                            <path d="M17 16h.01"></path>
                            <path d="M17 8h.01"></path>
                        </svg>
                    )
                },
                {
                    subtitle: 'Estaciones Meteorológicas',
                    text: 'Accede a "Estaciones" para consultar datos climáticos, pronósticos y correlaciones con la generación energética.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Reportes y Exportación',
                    text: 'Utiliza "Exportar Reportes" para generar informes personalizados y descargar datos en diferentes formatos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Configuración del Perfil',
                    text: 'Haz clic en tu nombre en la esquina superior derecha para acceder a la configuración de tu cuenta.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                    )
                }
            ]
        },
        troubleshooting: {
            title: 'Solución de Problemas Comunes',
            description: 'Resuelve rápidamente los problemas más frecuentes en la plataforma.',
            content: [
                {
                    subtitle: 'No puedo acceder al sistema',
                    text: 'Verifica que tu usuario y contraseña sean correctos. Si el problema persiste, contacta al administrador del sistema.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Los datos no se actualizan',
                    text: 'Refresca la página (F5) o verifica tu conexión a internet. Los datos se actualizan automáticamente cada 5 minutos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    )
                },
                {
                    subtitle: 'No veo mis medidores',
                    text: 'Asegúrate de tener los permisos necesarios. Contacta al administrador si necesitas acceso a dispositivos específicos.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Problemas en dispositivos móviles',
                    text: 'La plataforma es responsive. Si tienes problemas, intenta rotar la pantalla o usar la vista de escritorio.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Los reportes no se generan',
                    text: 'Verifica que hayas seleccionado un rango de fechas válido y que tengas permisos para generar reportes.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Problemas de sesión',
                    text: 'Si tu sesión expira, simplemente inicia sesión nuevamente. Las sesiones duran 24 horas por seguridad.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                    )
                }
            ]
        },
        contact: {
            title: 'Información de Contacto y Soporte',
            description: 'Obtén ayuda adicional y contacta al equipo de soporte técnico.',
            content: [
                {
                    subtitle: 'Universidad de Nariño',
                    text: 'Sistema desarrollado por la Universidad de Nariño para la gestión energética inteligente.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Equipo de Desarrollo',
                    text: 'Soporte técnico disponible para usuarios registrados del sistema MTE.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Canal de Comunicación',
                    text: 'Para reportar problemas o solicitar ayuda, contacta a tu administrador del sistema.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Documentación Técnica',
                    text: 'Consulta la documentación técnica disponible para obtener información detallada sobre la API y funcionalidades.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Actualizaciones del Sistema',
                    text: 'El sistema se actualiza regularmente. Las nuevas funcionalidades se anuncian a través de notificaciones.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                    )
                },
                {
                    subtitle: 'Sugerencias',
                    text: 'Tus comentarios y sugerencias son valiosos para mejorar la plataforma. Compártelos con el equipo de desarrollo.',
                    icon: (
                        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    )
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
                        <p className="text-slate-600 text-lg">Guía completa del Sistema MTE</p>
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
                                                Explora las diferentes secciones para familiarizarte con todas las funcionalidades del sistema MTE.
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
