import React from 'react';

const TransitionOverlay = ({ show, type = 'success', message = '', onComplete }) => {
    if (!show) return null;

    const getColors = () => {
        switch (type) {
            case 'success':
                return {
                    bg: 'from-green-50 to-emerald-100',
                    text: 'text-green-700',
                    icon: 'text-green-600',
                    spinner: 'border-green-200 border-t-green-600'
                };
            case 'error':
                return {
                    bg: 'from-red-50 to-rose-100',
                    text: 'text-red-700',
                    icon: 'text-red-600',
                    spinner: 'border-red-200 border-t-red-600'
                };
            case 'warning':
                return {
                    bg: 'from-yellow-50 to-amber-100',
                    text: 'text-yellow-700',
                    icon: 'text-yellow-600',
                    spinner: 'border-yellow-200 border-t-yellow-600'
                };
            case 'info':
                return {
                    bg: 'from-blue-50 to-indigo-100',
                    text: 'text-blue-700',
                    icon: 'text-blue-600',
                    spinner: 'border-blue-200 border-t-blue-600'
                };
            case 'logout':
                return {
                    bg: 'from-gray-50 to-slate-100',
                    text: 'text-gray-700',
                    icon: 'text-gray-600',
                    spinner: 'border-gray-200 border-t-gray-600'
                };
            default:
                return {
                    bg: 'from-blue-50 to-indigo-100',
                    text: 'text-blue-700',
                    icon: 'text-blue-600',
                    spinner: 'border-blue-200 border-t-blue-600'
                };
        }
    };

    const getIcon = () => {
        switch (type) {
            case 'success':
                return (
                    <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                );
            case 'error':
                return (
                    <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                );
            case 'warning':
                return (
                    <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                );
            case 'info':
                return (
                    <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                );
            case 'logout':
                return (
                    <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                    </svg>
                );
            default:
                return (
                    <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                );
        }
    };

    const getMessage = () => {
        if (message) return message;
        
        switch (type) {
            case 'success':
                return 'Operación completada exitosamente';
            case 'error':
                return 'Ha ocurrido un error';
            case 'warning':
                return 'Advertencia';
            case 'info':
                return 'Procesando información';
            case 'logout':
                return 'Cerrando sesión...';
            default:
                return 'Procesando...';
        }
    };

    const colors = getColors();

    return (
        <div className={`fixed inset-0 bg-gradient-to-br ${colors.bg} bg-opacity-95 flex items-center justify-center z-50 backdrop-blur-sm`}>
            <div className="flex flex-col items-center space-y-6 p-8">
                <div className="relative">
                    {/* Spinner principal (único) */}
                    <div className={`animate-spin rounded-full h-20 w-20 border-4 ${colors.spinner}`}></div>

                    {/* Icono centrado */}
                    <div className="absolute inset-0 flex items-center justify-center">
                        {getIcon()}
                    </div>
                </div>
                
                <div className="text-center space-y-2">
                    <p className={`text-xl font-semibold ${colors.text} mb-2`}>
                        {getMessage()}
                    </p>
                    <p className={`text-sm ${colors.text} opacity-75`}>
                        Por favor espera un momento
                    </p>
                </div>
                
                {/* Barra de progreso (estática) */}
                <div className="w-64 bg-white bg-opacity-30 rounded-full h-2 overflow-hidden">
                    <div className={`h-full bg-gradient-to-r ${colors.bg.replace('from-', '').replace('to-', '')} rounded-full`}></div>
                </div>
            </div>
        </div>
    );
};

export default TransitionOverlay; 