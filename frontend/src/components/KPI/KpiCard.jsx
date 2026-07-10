// KpiCard.jsx
import React from 'react';

// Diccionario que asigna clases de color de texto según el estado del KPI
const statusColors = {
  positivo: "text-emerald-600",
  negativo: "text-red-600",
  critico: "text-orange-600",
  estable: "text-slate-600",
  normal: "text-emerald-600",
  optimo: "text-emerald-600",
  moderado: "text-amber-600",
  loading: "text-blue-600",
  success: "text-emerald-600",
  error: "text-red-600",
};

// Diccionario que asigna gradientes de fondo según el estado
const statusGradients = {
  positivo: "from-emerald-50 to-green-50 border-emerald-200",
  negativo: "from-red-50 to-pink-50 border-red-200",
  critico: "from-orange-50 to-amber-50 border-orange-200",
  estable: "from-slate-50 to-gray-50 border-slate-200",
  normal: "from-emerald-50 to-green-50 border-emerald-200",
  optimo: "from-emerald-50 to-green-50 border-emerald-200",
  moderado: "from-amber-50 to-yellow-50 border-amber-200",
  loading: "from-blue-50 to-indigo-50 border-blue-200",
  success: "from-emerald-50 to-green-50 border-emerald-200",
  error: "from-red-50 to-pink-50 border-red-200",
};

// Diccionario que asigna iconos de estado
const statusIcons = {
  positivo: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  ),
  negativo: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
  critico: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  ),
  estable: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  normal: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  ),
  optimo: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  ),
  moderado: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
    </svg>
  ),
  loading: (
    <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  ),
  success: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  error: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
};

// Componente funcional que representa una tarjeta KPI mejorada
export const KpiCard = ({ title, value, unit, change, status, description, icon, onClick }) => {
  const cardClasses = onClick 
    ? "relative overflow-hidden bg-white rounded-2xl shadow-lg hover:shadow-xl transition duration-300 cursor-pointer hover:scale-105 active:scale-95 group"
    : "relative overflow-hidden bg-white rounded-2xl shadow-lg hover:shadow-xl transition duration-300 group";

  const statusGradient = statusGradients[status] || "from-slate-50 to-gray-50 border-slate-200";
  const statusColor = statusColors[status] || "text-slate-600";
  const statusIcon = statusIcons[status];

  return (
    <div className={cardClasses} onClick={onClick}>
      {/* Fondo decorativo con gradiente sutil */}
      <div className={`absolute inset-0 bg-gradient-to-br ${statusGradient} opacity-50`}></div>
      
      {/* Línea decorativa superior */}
      <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${statusGradient.split(' ')[0]} ${statusGradient.split(' ')[1]}`}></div>
      
      {/* Contenido principal */}
      <div className="relative p-6">
        {/* Header con título e icono */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            {title}
          </h3>
          <div className="relative">
            {/* Icono principal con efecto de brillo */}
            <div className="p-3 bg-gradient-to-br from-gray-50 to-white rounded-xl shadow-sm border border-gray-100 group-hover:shadow-md transition duration-300">
              <div className="text-gray-600 group-hover:text-gray-800 transition-colors duration-300">
                {icon}
              </div>
            </div>
            {/* Efecto de brillo en hover */}
            <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          </div>
        </div>

        {/* Valor principal con animación */}
        <div className="mb-4">
          <div className="flex items-baseline space-x-2">
            <span className="text-3xl font-bold text-gray-900 group-hover:text-gray-800 transition-colors duration-300">
              {value}
            </span>
            {unit && (
              <span className="text-lg font-medium text-gray-500">
                {unit}
              </span>
            )}
          </div>
        </div>

        {/* Footer con estado y descripción */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            {/* Icono de estado */}
            <div className={`p-1.5 rounded-full ${statusColor.replace('text-', 'bg-')} bg-opacity-10`}>
              {statusIcon}
            </div>
            
            {/* Texto de descripción */}
            <p className={`text-sm font-medium ${statusColor}`}>
              {change || description || "Estado actual"}
            </p>
          </div>

          {/* Indicador de estado animado */}
          <div className="relative">
            <div className={`w-3 h-3 rounded-full ${statusColor.replace('text-', 'bg-')} animate-pulse`}></div>
            <div className={`absolute inset-0 w-3 h-3 rounded-full ${statusColor.replace('text-', 'bg-')} animate-ping opacity-75`}></div>
          </div>
        </div>

        {/* Efecto de brillo en hover */}
        <div className="absolute inset-0 bg-gradient-to-br from-white/10 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
      </div>

      {/* Indicador de click para botones */}
      {onClick && (
        <div className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
        </div>
      )}
    </div>
  );
};