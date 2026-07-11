// Importación de hooks y componentes de React
import React, { useState, useEffect, lazy, Suspense } from 'react';
import LoginPage from './components/LoginPage'; // Eager: la pantalla de login debe cargar de inmediato
import Sidebar from './components/Sidebar'; // Componente de barra lateral
import ErrorBoundary from './components/ErrorBoundary'; // Límite de error global de pantallas

// Code-splitting: cada pantalla se carga bajo demanda en su propio chunk
const Dashboard = lazy(() => import('./components/Dashboard'));
const ElectricalDetails = lazy(() => import('./components/ElectricalDetails'));
const InverterDetails = lazy(() => import('./components/InverterDetails'));
const WeatherStationDetails = lazy(() => import('./components/WeatherStationDetails'));
const ExternalEnergyData = lazy(() => import('./components/ExternalEnergyData'));
const ExportReports = lazy(() => import('./components/ExportReports'));

// Fallback discreto mientras se descarga el chunk de una pantalla
// (mismo estilo que el spinner de carga del Dashboard)
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-screen bg-gray-100">
    <div className="flex flex-col items-center">
      <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-blue-500"></div>
      <p className="mt-4 text-lg text-gray-700">Cargando...</p>
    </div>
  </div>
);

function App() {
  // Estados para gestionar la sesión del usuario
  const [authToken, setAuthToken] = useState(localStorage.getItem('authToken')); // Token de autenticación
  const [username, setUsername] = useState(localStorage.getItem('username')); // Nombre de usuario
  const [isSuperuser, setIsSuperuser] = useState(localStorage.getItem('isSuperuser') === 'true'); // Rol de superusuario

  // Estado para determinar la vista actual (login, dashboard, etc.)
  // Persistir la página actual en localStorage
  const [currentPage, setCurrentPage] = useState(() => {
    const savedPage = localStorage.getItem('currentPage');
    return authToken ? (savedPage || 'dashboard') : 'login';
  });

  // Estado para controlar si la barra lateral está minimizada
  // Persistir el estado de la sidebar en localStorage
  const [isSidebarMinimized, setIsSidebarMinimized] = useState(() => {
    const savedSidebarState = localStorage.getItem('isSidebarMinimized');
    return savedSidebarState ? JSON.parse(savedSidebarState) : false;
  });



  // Maneja el éxito en el login: guarda los datos en el estado y en localStorage
  const handleLoginSuccess = (token, user, superuser) => {
    setAuthToken(token);
    setUsername(user);
    setIsSuperuser(superuser);
    localStorage.setItem('authToken', token);
    localStorage.setItem('username', user);
    localStorage.setItem('isSuperuser', superuser);
    setCurrentPage('dashboard'); // Redirige al dashboard
    localStorage.setItem('currentPage', 'dashboard'); // Persistir la página
  };

  // Cierra sesión limpiando los datos de sesión y redirigiendo al login
  const performLogout = () => {
    setAuthToken(null);
    setUsername(null);
    setIsSuperuser(false);
    localStorage.removeItem('authToken');
    localStorage.removeItem('username');
    localStorage.removeItem('isSuperuser');
    localStorage.removeItem('currentPage'); // Limpiar la página persistida
    setCurrentPage('login'); // Redirige a la vista de login
  };

  // Cierra sesión directamente
  const handleLogoutWithAnimation = () => {
    performLogout(); // Ejecuta el cierre de sesión directamente
  };

  // Cambia de vista dentro de la aplicación
  const navigateTo = (page) => {
    setCurrentPage(page);
    localStorage.setItem('currentPage', page); // Persistir la nueva página
  };

  // Efecto que asegura que si no hay token, se redirige a login
  useEffect(() => {
    if (!authToken) {
      setCurrentPage('login');
      localStorage.removeItem('currentPage'); // Limpiar la página persistida
    }
  }, [authToken]);

  // Función que decide qué componente renderizar según la vista actual
  const renderPageContent = () => {
    const commonProps = {
      authToken,
      onLogout: handleLogoutWithAnimation,
      username,
      isSuperuser,
      navigateTo,
      isSidebarMinimized,
      setIsSidebarMinimized: (minimized) => {
        setIsSidebarMinimized(minimized);
        localStorage.setItem('isSidebarMinimized', JSON.stringify(minimized)); // Persistir el estado
      },
    };

    switch (currentPage) {
      case 'login':
        return <LoginPage onLoginSuccess={handleLoginSuccess} />;
      case 'dashboard':
        return <Dashboard {...commonProps} />;
      case 'electricalDetails':
        return <ElectricalDetails {...commonProps} />;
      case 'inverterDetails':
        return <InverterDetails {...commonProps} />;
      case 'weatherDetails':
        return <WeatherStationDetails {...commonProps} />;
      case 'externalEnergy':
        return <ExternalEnergyData {...commonProps} />;
      case 'exportReports':
        return <ExportReports {...commonProps} />;
      default:
        return <LoginPage onLoginSuccess={handleLoginSuccess} />; // Fallback en caso de error
    }
  };

  // Si el usuario está en la página de login, no muestra la barra lateral ni animaciones
  if (currentPage === 'login') {
    return (
      <div className="App">
        {renderPageContent()}
        {/* La animación de logout no aplica en login */}
      </div>
    );
  }

  // Para el resto de vistas, muestra la barra lateral, el contenido y la animación si aplica
  return (
    <div className="flex min-h-screen bg-gray-100 w-full font-inter">
      <Sidebar
        username={username}
        isSuperuser={isSuperuser}
        isSidebarMinimized={isSidebarMinimized}
        setIsSidebarMinimized={(minimized) => {
          setIsSidebarMinimized(minimized);
          localStorage.setItem('isSidebarMinimized', JSON.stringify(minimized)); // Persistir el estado
        }}
        navigateTo={navigateTo}
        onLogout={handleLogoutWithAnimation}
        currentPage={currentPage}
      />
      {/* Contenedor principal de la página */}
      <main className="flex-1 p-8 bg-gray-100 rounded-tl-3xl shadow-inner">
        {/* Suspense muestra el fallback mientras se descarga el chunk de la pantalla */}
        <Suspense fallback={<PageLoader />}>
          {/* Si una pantalla lanza un error de render, el ErrorBoundary muestra un fallback
              en vez de tumbar toda la app; key={currentPage} lo resetea al navegar. */}
          <ErrorBoundary key={currentPage}>
            {renderPageContent()} {/* Renderiza el componente correspondiente */}
          </ErrorBoundary>
        </Suspense>
      </main>


    </div>
  );
}

export default App;