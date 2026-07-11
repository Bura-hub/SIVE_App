import React from 'react';
import siveLogo from './sive-logo.svg';
import { IconHome, IconDashboard, IconGauge, IconInverter, IconCloudSun, IconGlobe, IconFileDown } from './icons';

function Sidebar({
  isSuperuser,
  isSidebarMinimized,
  setIsSidebarMinimized,
  navigateTo,
  currentPage
}) {
  const navItems = [
    {
      name: 'Inicio',
      page: 'home',
      icon: <IconHome className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-blue-600'
    },
    {
      name: 'Dashboard',
      page: 'dashboard',
      icon: <IconDashboard className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-blue-600'
    },
    {
      name: 'Medidores',
      page: 'electricalDetails',
      icon: <IconGauge className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-green-600 to-green-700 text-white shadow-lg shadow-green-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-green-600'
    },
    {
      name: 'Inversores',
      page: 'inverterDetails',
      icon: <IconInverter className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-red-600 to-red-700 text-white shadow-lg shadow-red-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-red-600'
    },
    {
      name: 'Estaciones',
      page: 'weatherDetails',
      icon: <IconCloudSun className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-orange-600 to-orange-700 text-white shadow-lg shadow-orange-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-orange-600'
    },
    {
      name: 'Datos Externos',
      page: 'externalEnergy',
      icon: <IconGlobe className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-teal-600 to-teal-700 text-white shadow-lg shadow-teal-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-teal-600'
    },
    {
      name: 'Exportar Reportes',
      page: 'exportReports',
      icon: <IconFileDown className="w-5 h-5 shrink-0" />,
      activeClasses: 'bg-gradient-to-r from-purple-600 to-purple-700 text-white shadow-lg shadow-purple-500/25',
      inactiveClasses: 'text-gray-600 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-purple-600'
    },
  ];

  return (
    <aside className={`bg-white border-r border-gray-200 shadow-lg flex flex-col justify-between ${isSidebarMinimized ? 'w-20' : 'w-72'}`}>
      {/* Header con logo y botón de toggle */}
      <div className="p-6 border-b border-gray-100">
        <div className={`flex items-center ${isSidebarMinimized ? 'justify-center' : 'justify-between'}`}>
          {!isSidebarMinimized && (
            <div className="flex items-center space-x-3 sidebar-fade-in">
              <img
                src={siveLogo}
                alt="SIVE Logo"
                className="max-w-[200px] h-auto object-contain"
              />
            </div>
          )}
          <button
            onClick={() => setIsSidebarMinimized(!isSidebarMinimized)}
            className="p-2 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors duration-150"
            title={isSidebarMinimized ? "Expandir menú" : "Minimizar menú"}
            aria-label={isSidebarMinimized ? "Expandir menú" : "Minimizar menú"}
            aria-expanded={!isSidebarMinimized}
          >
            {isSidebarMinimized ? (
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 5l7 7-7 7M6 5l7 7-7 7"></path>
              </svg>
            ) : (
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7"></path>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Navegación principal */}
      <div className="flex-1 px-4 py-6">
        <nav>
          <div className="space-y-2">
            {navItems.map((item) => {
              // Verificar si el elemento requiere permisos de administrador
              const requiresAdmin = item.page === 'externalEnergy' || item.page === 'exportReports';

              // Si requiere admin y el usuario no es superuser, no mostrar el elemento
              if (requiresAdmin && !isSuperuser) {
                return null;
              }

              return (
                <div key={item.page} className="relative">
                  <button
                    type="button"
                    title={item.name}
                    aria-label={item.name}
                    aria-current={currentPage === item.page ? 'page' : undefined}
                    className={`w-full flex items-center p-4 rounded-xl text-left transition-colors duration-150 ${isSidebarMinimized ? 'justify-center' : ''} ${
                      currentPage === item.page ? item.activeClasses : item.inactiveClasses
                    }`}
                    onClick={() => navigateTo(item.page)}
                  >
                    {item.icon}
                    {!isSidebarMinimized && (
                      <span className="font-medium ml-3 whitespace-nowrap sidebar-fade-in">
                        {item.name}
                      </span>
                    )}
                  </button>
                </div>
              );
            })}

            {/* Separador visual */}
            <div className="my-4 border-t border-gray-200"></div>
          </div>
        </nav>

        {/* About del sistema */}
        {!isSidebarMinimized && (
          <div className="px-3 py-3 border-t border-gray-100">
            <div className="text-center space-y-2">
              <p className="text-xs text-gray-600 font-medium leading-tight">
                Sistema de Visualización Energético
              </p>
              <div className="flex flex-col items-center space-y-1 text-xs text-gray-600">
                <div className="flex items-center space-x-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                  </svg>
                  <span className="text-xs">Universidad de Nariño</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}

export default Sidebar;
