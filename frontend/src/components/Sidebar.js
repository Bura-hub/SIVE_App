import React, { useState, useEffect, useRef } from 'react';
import siveLogo from './sive-logo.svg';
import TransitionOverlay from './TransitionOverlay';
import { IconHome, IconGauge, IconInverter, IconCloudSun, IconGlobe, IconFileDown } from './icons';
import { fetchWithAuth } from '../utils/apiConfig';
import ProfileSettings from './ProfileSettings';
import HelpSupport from './HelpSupport';
import { buildApiUrl } from '../config';

function Sidebar({
  username,
  isSuperuser,
  isSidebarMinimized,
  setIsSidebarMinimized,
  navigateTo,
  onLogout,
  currentPage
}) {
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const profileMenuRef = useRef(null);

  // Estado para la animación de transición
  const [showTransition, setShowTransition] = useState(false);
  const [transitionType, setTransitionType] = useState('info');
  const [transitionMessage, setTransitionMessage] = useState('');
  
  // Estado para el modal de configuración del perfil
  const [showProfileSettings, setShowProfileSettings] = useState(false);
  
  // Estado para el modal de ayuda y soporte
  const [showHelpSupport, setShowHelpSupport] = useState(false);
  
  // Estado para la imagen de perfil
  const [profileImageUrl, setProfileImageUrl] = useState(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target)) {
        setShowProfileMenu(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [profileMenuRef]);
  
  // Cargar imagen de perfil al montar el componente
  useEffect(() => {
    if (username) {
      loadProfileImage();
    }
  }, [username]);

  // Función para mostrar transición
  // Timeouts registrados para limpiarlos al desmontar (evita setState sobre
  // componente desmontado si el usuario navega en medio de una animación).
  const timeoutsRef = React.useRef([]);
  React.useEffect(() => () => { timeoutsRef.current.forEach(clearTimeout); }, []);
  const scheduleTimeout = (fn, ms) => { timeoutsRef.current.push(setTimeout(fn, ms)); };

  const showTransitionAnimation = (type = 'info', message = '', duration = 2000) => {
    setTransitionType(type);
    setTransitionMessage(message);
    setShowTransition(true);
    
    scheduleTimeout(() => {
      setShowTransition(false);
    }, duration);
  };
  
  // Función para abrir configuración del perfil
  const openProfileSettings = () => {
    setShowProfileSettings(true);
    setShowProfileMenu(false);
  };
  
  // Función para abrir ayuda y soporte
  const openHelpSupport = () => {
    setShowHelpSupport(true);
    setShowProfileMenu(false);
  };
  
  // Función para actualizar la imagen de perfil
  const handleProfileImageUpdate = () => {
    loadProfileImage(); // Recargar la imagen
  };
  
  // Función para cargar la imagen de perfil
  const loadProfileImage = async () => {
    try {
      const response = await fetch(buildApiUrl('/auth/profile-image/'), {
        headers: {
          'Authorization': `Token ${localStorage.getItem('authToken')}`,
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setProfileImageUrl(data.profile_image_url);
      } else if (response.status === 404) {
        // No hay imagen de perfil configurada
        setProfileImageUrl(null);
      } else {
        console.error('Error cargando imagen de perfil:', response.status);
      }
    } catch (error) {
      console.error('Error cargando imagen de perfil:', error);
    }
  };

  const navItems = [
    { 
      name: 'Inicio', 
      page: 'dashboard', 
      icon: <IconHome className="w-5 h-5 shrink-0" />,
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

  const handleLogoutClick = async () => {
    try {
      // Mostrar animación de logout
      showTransitionAnimation('logout', 'Cerrando sesión...', 2000);
      
      // Obtener el token actual del localStorage
      const authToken = localStorage.getItem('authToken');
      
      if (authToken) {
        // Llamar al endpoint de logout del backend para revocar tokens
        // Usar fetch normal para evitar la animación de carga de fetchWithAuth
        const response = await fetch(buildApiUrl('/auth/logout/'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Token ${authToken}`,
          },
        });
        
        if (!response.ok) {
          console.warn('Error en logout del backend:', response.status);
        }
      }
      
      // Esperar un momento para mostrar la animación
      scheduleTimeout(() => {
        // Limpiar datos locales
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('isSuperuser');
        
        // Llamar a la función de logout del componente padre
        onLogout();
      }, 1500);
      
    } catch (error) {
      console.error('Error durante logout:', error);
      // Continuar con logout local en caso de error
      showTransitionAnimation('error', 'Error al cerrar sesión, pero se cerrará localmente', 2000);
      
      scheduleTimeout(() => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('isSuperuser');
        onLogout();
      }, 2000);
    }
  };

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
            
            {/* Administración del Perfil */}
            <div
              ref={profileMenuRef}
              className={`relative flex items-center p-4 rounded-2xl bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 cursor-pointer hover:from-blue-100 hover:via-indigo-100 hover:to-purple-100 hover:shadow-lg hover:shadow-blue-500/20 transition-colors duration-150 border border-slate-200/50 hover:border-blue-300/50 ${isSidebarMinimized ? 'justify-center p-3' : ''}`}
              onClick={() => setShowProfileMenu(!showProfileMenu)}
            >
                             <div className="relative">
                 {profileImageUrl ? (
                   // Mostrar imagen de perfil real
                   <div className={'rounded-2xl overflow-hidden shadow-lg shadow-blue-500/30 w-12 h-12'}>
                     <img
                       src={profileImageUrl}
                       alt={`Perfil de ${username}`}
                       className="w-full h-full object-cover"
                       onError={() => setProfileImageUrl(null)} // Fallback si la imagen falla
                     />
                   </div>
                 ) : (
                   // Mostrar avatar con iniciales (diseño actual)
                   <div className={'rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/30 w-12 h-12'}>
                     <span className="text-white font-bold text-lg">
                       {(username || 'G').charAt(0).toUpperCase()}
                     </span>
                   </div>
                 )}
                 <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-400 border-2 border-white rounded-full shadow-sm"></div>
               </div>
              {!isSidebarMinimized && (
              <div className="ml-4 overflow-hidden sidebar-fade-in">
                <p className="font-bold text-slate-800 whitespace-nowrap text-sm">
                  {username || 'Invitado'}
                </p>
                <p className="text-xs text-slate-600 whitespace-nowrap font-medium flex items-center">
                  <span className={`w-2 h-2 rounded-full mr-2 ${isSuperuser ? 'bg-purple-500' : 'bg-blue-500'}`}></span>
                  {isSuperuser ? 'Administrador' : 'Usuario Aliado'}
                </p>
              </div>
              )}
              {!isSidebarMinimized && (
                <svg
                  className={`w-5 h-5 ml-auto text-slate-500 transition-transform duration-150 ${showProfileMenu ? 'rotate-180 text-blue-600' : ''}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              )}

              {showProfileMenu && (
                <div
                  className={`absolute top-full mt-4 ${
                    isSidebarMinimized ? 'left-1/2 -translate-x-1/2 w-64' : 'left-0 w-full'
                  } bg-white/95 backdrop-blur-xl rounded-3xl shadow-2xl shadow-slate-900/20 py-4 z-20 border border-slate-200/50`}
                >
                                     {/* Header elegante */}
                   <div className="px-6 py-4 border-b border-slate-100/50">
                     <div className="flex items-center">
                       {profileImageUrl ? (
                         // Mostrar imagen de perfil real en el menú
                         <div className="w-12 h-12 rounded-2xl overflow-hidden shadow-lg shadow-blue-500/30 mr-4">
                           <img
                             src={profileImageUrl}
                             alt={`Perfil de ${username}`}
                             className="w-full h-full object-cover"
                             onError={() => setProfileImageUrl(null)}
                           />
                         </div>
                       ) : (
                         // Mostrar avatar con iniciales en el menú
                         <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/30 mr-4">
                           <span className="text-white font-bold text-lg">
                             {(username || 'G').charAt(0).toUpperCase()}
                           </span>
                         </div>
                       )}
                      <div>
                        <p className="text-sm font-bold text-slate-800">{username || 'Invitado'}</p>
                        <p className="text-xs text-slate-600 font-medium flex items-center">
                          <span className={`w-2 h-2 rounded-full mr-2 ${isSuperuser ? 'bg-purple-500' : 'bg-blue-500'}`}></span>
                          {isSuperuser ? 'Administrador' : 'Usuario Aliado'}
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Opciones del menú */}
                  <div className="py-2">
                    <button 
                      onClick={openProfileSettings}
                      className="group flex items-center w-full text-left px-6 py-3 text-sm text-slate-700 hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50 transition duration-300"
                    >
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-100 to-blue-200 rounded-xl flex items-center justify-center mr-4 group-hover:from-blue-200 group-hover:to-blue-300 transition duration-300 shadow-sm">
                        <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                        </svg>
                      </div>
                      <span className="font-semibold">Configuración</span>
                    </button>
                    
                    <button 
                      onClick={openHelpSupport}
                      className="group flex items-center w-full text-left px-6 py-3 text-sm text-slate-700 hover:bg-gradient-to-r hover:from-emerald-50 hover:to-teal-50 transition duration-300"
                    >
                      <div className="w-10 h-10 bg-gradient-to-br from-emerald-100 to-emerald-200 rounded-xl flex items-center justify-center mr-4 group-hover:from-emerald-200 group-hover:to-emerald-300 transition duration-300 shadow-sm">
                        <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                      </div>
                      <span className="font-semibold">Ayuda y Soporte</span>
                    </button>
                    
                    <div className="border-t border-slate-200/50 my-3 mx-6"></div>
                    
                    <button 
                      onClick={handleLogoutClick} 
                      className="group flex items-center w-full text-left px-6 py-3 text-sm text-red-600 hover:bg-gradient-to-r hover:from-red-50 hover:to-pink-50 transition duration-300"
                    >
                      <div className="w-10 h-10 bg-gradient-to-br from-red-100 to-red-200 rounded-xl flex items-center justify-center mr-4 group-hover:from-red-200 group-hover:to-red-300 transition duration-300 shadow-sm">
                        <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path>
                        </svg>
                      </div>
                      <span className="font-semibold">Cerrar Sesión</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
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

      {/* Overlay de transición */}
      <TransitionOverlay 
        show={showTransition}
        type={transitionType}
        message={transitionMessage}
      />
      
             {/* Modal de configuración del perfil */}
       {showProfileSettings && (
         <ProfileSettings
           username={username}
           isSuperuser={isSuperuser}
           onClose={() => setShowProfileSettings(false)}
           onProfileImageUpdate={handleProfileImageUpdate}
         />
       )}
      
      {/* Modal de ayuda y soporte */}
      {showHelpSupport && (
        <HelpSupport
          onClose={() => setShowHelpSupport(false)}
        />
      )}
    </aside>
  );
}

export default Sidebar;