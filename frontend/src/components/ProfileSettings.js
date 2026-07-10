import React, { useState, useEffect } from 'react';
import { buildApiUrl, getEndpoint } from '../config';
import ProfileImageUpload from './ProfileImageUpload';

function ProfileSettings({ username, isSuperuser, onClose, onProfileImageUpdate }) {
    const [activeTab, setActiveTab] = useState('profile');
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState({ text: '', type: '' });
    
    // Estados para información del perfil
    const [profileData, setProfileData] = useState({
        first_name: '',
        last_name: '',
        email: '',
        phone_number: '',
        bio: '',
        date_of_birth: '',
        language: 'es'
    });
    
    // Estados para cambio de contraseña
    const [passwordData, setPasswordData] = useState({
        current_password: '',
        new_password: '',
        confirm_password: ''
    });
    const [showPasswords, setShowPasswords] = useState({
        current: false,
        new: false,
        confirm: false
    });
    
    // Estados para seguridad
    const [securitySettings, setSecuritySettings] = useState({
        two_factor_enabled: false,
        session_timeout: 30,
        require_password_change: false
    });
    
    // Estados para sesiones activas
    const [activeSessions, setActiveSessions] = useState([]);
    const [loadingSessions, setLoadingSessions] = useState(false);
    
    // Estados para tokens de acceso
    const [accessTokens, setAccessTokens] = useState([]);
    const [loadingTokens, setLoadingTokens] = useState(false);
    
    // Estado para imagen de perfil
    const [profileImageUrl, setProfileImageUrl] = useState(null);

    useEffect(() => {
        loadProfileData();
        loadActiveSessions();
        loadAccessTokens();
        loadProfileImage();
    }, []);

    const loadProfileData = async () => {
        try {
            const response = await fetch(buildApiUrl(getEndpoint('USER_PROFILE')), {
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                // Mapear los datos del backend al estado local
                setProfileData({
                    first_name: data.first_name || '',
                    last_name: data.last_name || '',
                    phone_number: data.phone_number || '',
                    bio: data.bio || '',
                    date_of_birth: data.date_of_birth || '',
                    language: data.language || 'es'
                });
            } else {
                console.error('Error cargando perfil:', response.status);
            }
        } catch (error) {
            console.error('Error cargando perfil:', error);
        }
    };

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

    const handleImageUpdate = (newImageUrl) => {
        setProfileImageUrl(newImageUrl);
        // Notificar a la sidebar que se actualizó la imagen
        if (onProfileImageUpdate) {
            onProfileImageUpdate();
        }
    };

    const handleImageDelete = () => {
        setProfileImageUrl(null);
        // Notificar a la sidebar que se eliminó la imagen
        if (onProfileImageUpdate) {
            onProfileImageUpdate();
        }
    };



    const loadActiveSessions = async () => {
        setLoadingSessions(true);
        try {
            const response = await fetch(buildApiUrl(getEndpoint('SESSIONS')), {
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                setActiveSessions(data.active_devices || []);
            } else {
                console.error('Error cargando sesiones:', response.status);
            }
        } catch (error) {
            console.error('Error cargando sesiones:', error);
        } finally {
            setLoadingSessions(false);
        }
    };

    const loadAccessTokens = async () => {
        setLoadingTokens(true);
        try {
            const response = await fetch(buildApiUrl(getEndpoint('USER_PROFILE')), {
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                setAccessTokens(data.active_tokens || []);
            }
        } catch (error) {
            console.error('Error cargando tokens:', error);
        } finally {
            setLoadingTokens(false);
        }
    };

    const handleProfileUpdate = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage({ text: '', type: '' });

        try {
            // Preparar datos para enviar (solo campos del perfil)
            const updateData = {
                first_name: profileData.first_name,
                last_name: profileData.last_name,
                email: profileData.email,
                phone_number: profileData.phone_number,
                bio: profileData.bio,
                date_of_birth: profileData.date_of_birth,
                language: profileData.language
            };

            const response = await fetch(buildApiUrl(getEndpoint('USER_PROFILE')), {
                method: 'PUT',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });

            if (response.ok) {
                setMessage({ text: 'Perfil actualizado exitosamente', type: 'success' });
                setTimeout(() => setMessage({ text: '', type: '' }), 3000);
            } else {
                const errorData = await response.json();
                setMessage({ text: errorData.error || 'Error al actualizar perfil', type: 'error' });
            }
        } catch (error) {
            setMessage({ text: 'Error de conexión', type: 'error' });
        } finally {
            setLoading(false);
        }
    };



    const handlePasswordChange = async (e) => {
        e.preventDefault();
        setLoading(true);
        setMessage({ text: '', type: '' });

        if (passwordData.new_password !== passwordData.confirm_password) {
            setMessage({ text: 'Las contraseñas no coinciden', type: 'error' });
            setLoading(false);
            return;
        }

        try {
            console.log('🔄 Enviando solicitud de cambio de contraseña...');
            const response = await fetch(buildApiUrl(getEndpoint('CHANGE_PASSWORD')), {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    current_password: passwordData.current_password,
                    new_password: passwordData.new_password,
                    confirm_password: passwordData.confirm_password
                })
            });

            console.log('📡 Respuesta recibida:', response.status, response.statusText);

            if (response.ok) {
                const responseData = await response.json();
                console.log('✅ Respuesta exitosa:', responseData);
                setMessage({ text: 'Contraseña cambiada exitosamente', type: 'success' });
                setPasswordData({ current_password: '', new_password: '', confirm_password: '' });
                setTimeout(() => setMessage({ text: '', type: '' }), 3000);
            } else {
                const errorData = await response.json();
                console.log('❌ Error en respuesta:', errorData);
                setMessage({ text: errorData.error || 'Error al cambiar contraseña', type: 'error' });
            }
        } catch (error) {
            console.error('💥 Error de conexión:', error);
            setMessage({ text: 'Error de conexión', type: 'error' });
        } finally {
            setLoading(false);
        }
    };

    const handleLogoutDevice = async (tokenId) => {
        try {
            const response = await fetch(buildApiUrl(getEndpoint('LOGOUT')), {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ token_id: tokenId })
            });

            if (response.ok) {
                setMessage({ text: 'Dispositivo cerrado exitosamente', type: 'success' });
                loadActiveSessions();
                loadAccessTokens();
                setTimeout(() => setMessage({ text: '', type: '' }), 3000);
            } else {
                const errorData = await response.json();
                setMessage({ text: errorData.error || 'Error al cerrar dispositivo', type: 'error' });
            }
        } catch (error) {
            setMessage({ text: 'Error de conexión al cerrar dispositivo', type: 'error' });
        }
    };

    const handleLogoutAllDevices = async () => {
        if (!window.confirm('¿Estás seguro de que quieres cerrar sesión en todos los dispositivos? Esto cerrará tu sesión actual.')) {
            return;
        }

        try {
            const response = await fetch(buildApiUrl(getEndpoint('LOGOUT_ALL')), {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                setMessage({ text: 'Sesión cerrada en todos los dispositivos', type: 'success' });
                setTimeout(() => {
                    localStorage.clear();
                    window.location.reload();
                }, 2000);
            } else {
                const errorData = await response.json();
                setMessage({ text: errorData.error || 'Error al cerrar todas las sesiones', type: 'error' });
            }
        } catch (error) {
            setMessage({ text: 'Error de conexión al cerrar todas las sesiones', type: 'error' });
        }
    };



    const tabs = [
        { 
            id: 'profile', 
            name: 'Perfil', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
            )
        },
        { 
            id: 'security', 
            name: 'Seguridad', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
            )
        },
        { 
            id: 'sessions', 
            name: 'Sesiones', 
            icon: (
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <rect x="3" y="5" width="18" height="14" rx="2" ry="2"></rect>
                    <path d="M7 12h2l1 2 2-4 1 2h2"></path>
                    <path d="M17 16h.01"></path>
                    <path d="M17 8h.01"></path>
                </svg>
            )
        }
    ];

    return (
        <div className="fixed inset-0 bg-black bg-opacity-60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-3xl shadow-2xl max-w-7xl w-full max-h-[95vh] overflow-hidden border border-gray-100">
                {/* Header */}
                <div className="flex items-center justify-between p-8 border-b border-gray-100 bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
                    <div className="space-y-2">
                        <h2 className="text-3xl font-bold bg-gradient-to-r from-slate-800 to-blue-700 bg-clip-text text-transparent">
                            Configuración del Perfil
                        </h2>
                        <p className="text-slate-600 text-lg">Gestiona tu cuenta y preferencias de seguridad</p>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition duration-150 p-3 rounded-full"
                    >
                        <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Mensaje de estado */}
                {message.text && (
                    <div className={`mx-8 mt-6 p-5 rounded-2xl shadow-lg border-l-4 ${
                        message.type === 'success' 
                            ? 'bg-gradient-to-r from-emerald-50 to-green-50 border-emerald-400 text-emerald-800' 
                            : 'bg-gradient-to-r from-red-50 to-rose-50 border-red-400 text-red-800'
                    }`}>
                        <div className="flex items-center">
                            {message.type === 'success' ? (
                                <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center mr-4">
                                    <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                </div>
                            ) : (
                                <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mr-4">
                                    <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </div>
                            )}
                            <span className="font-semibold text-lg">{message.text}</span>
                        </div>
                    </div>
                )}

                <div className="flex h-[calc(95vh-280px)]">
                    {/* Sidebar de navegación */}
                    <div className="w-72 bg-gradient-to-b from-slate-50 to-blue-50 border-r border-slate-200 p-6">
                        <nav className="space-y-3">
                            {tabs.map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`w-full flex items-center px-6 py-4 rounded-2xl text-left transition duration-300 ${
                                        activeTab === tab.id
                                            ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white shadow-lg shadow-blue-500/25 transform scale-105'
                                            : 'text-slate-600 hover:bg-white hover:text-slate-800 hover:shadow-md hover:scale-105 border border-transparent hover:border-slate-200'
                                    }`}
                                >
                                    <div className="mr-4 text-slate-600">{tab.icon}</div>
                                    <span className="font-semibold text-lg">{tab.name}</span>
                                </button>
                            ))}
                        </nav>
                    </div>

                    {/* Contenido principal */}
                    <div className="flex-1 p-8 overflow-y-auto bg-gradient-to-br from-white to-slate-50/30">
                        {/* Pestaña: Perfil */}
                        {activeTab === 'profile' && (
                            <div className="space-y-8">
                                <div className="text-center mb-8">
                                    <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg overflow-hidden">
                                        {profileImageUrl ? (
                                            <img
                                                src={profileImageUrl}
                                                alt="Imagen de perfil"
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                                            </svg>
                                        )}
                                    </div>
                                    <h3 className="text-3xl font-bold text-slate-800 mb-2">Información Personal</h3>
                                    <p className="text-slate-600 text-lg">Actualiza tu información personal y de contacto</p>
                                </div>
                                
                                <form onSubmit={handleProfileUpdate} className="max-w-4xl mx-auto space-y-6">
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <label className="block text-sm font-semibold text-slate-700 mb-3">
                                                Nombre *
                                            </label>
                                            <input
                                                type="text"
                                                value={profileData.first_name}
                                                onChange={(e) => setProfileData({...profileData, first_name: e.target.value})}
                                                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                                required
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="block text-sm font-semibold text-slate-700 mb-3">
                                                Apellido *
                                            </label>
                                            <input
                                                type="text"
                                                value={profileData.last_name}
                                                onChange={(e) => setProfileData({...profileData, last_name: e.target.value})}
                                                className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                                required
                                            />
                                        </div>
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <label className="block text-sm font-semibold text-slate-700 mb-3">
                                            Email *
                                        </label>
                                        <input
                                            type="email"
                                            value={profileData.email}
                                            onChange={(e) => setProfileData({...profileData, email: e.target.value})}
                                            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                            required
                                        />
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <label className="block text-sm font-semibold text-slate-700 mb-3">
                                            Número de Teléfono
                                        </label>
                                        <input
                                            type="tel"
                                            value={profileData.phone_number}
                                            onChange={(e) => setProfileData({...profileData, phone_number: e.target.value})}
                                            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                            placeholder="+1 (555) 123-4567"
                                        />
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <label className="block text-sm font-semibold text-slate-700 mb-3">
                                            Biografía
                                        </label>
                                        <textarea
                                            value={profileData.bio}
                                            onChange={(e) => setProfileData({...profileData, bio: e.target.value})}
                                            rows={4}
                                            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 bg-white shadow-sm hover:shadow-md resize-none"
                                            placeholder="Cuéntanos sobre ti..."
                                        />
                                    </div>
                                    
                                    <div className="space-y-2">
                                        <label className="block text-sm font-semibold text-slate-700 mb-3">
                                            Fecha de Nacimiento
                                        </label>
                                        <input
                                            type="date"
                                            value={profileData.date_of_birth}
                                            onChange={(e) => setProfileData({...profileData, date_of_birth: e.target.value})}
                                            className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                        />
                                    </div>
                                    
                                    <div className="pt-6">
                                        <button
                                            type="submit"
                                            disabled={loading}
                                            className={`w-full py-4 px-6 rounded-2xl font-semibold text-lg transition duration-300 ${
                                                loading
                                                    ? 'bg-slate-400 text-slate-200 cursor-not-allowed'
                                                    : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:from-blue-700 hover:to-indigo-700 focus:ring-4 focus:ring-blue-500/25 shadow-lg hover:shadow-xl transform hover:scale-[1.02]'
                                            }`}
                                        >
                                            {loading ? (
                                                <div className="flex items-center justify-center">
                                                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                                                    Actualizando...
                                                </div>
                                            ) : (
                                                'Actualizar Perfil'
                                            )}
                                        </button>
                                    </div>
                                </form>
                                
                                {/* Componente de Imagen de Perfil */}
                                <div className="max-w-4xl mx-auto">
                                    <ProfileImageUpload
                                        currentImageUrl={profileImageUrl}
                                        onImageUpdate={handleImageUpdate}
                                        onImageDelete={handleImageDelete}
                                    />
                                </div>
                            </div>
                        )}

                        {/* Pestaña: Seguridad */}
                        {activeTab === 'security' && (
                            <div className="space-y-8">
                                <div className="text-center mb-8">
                                    <div className="w-20 h-20 bg-gradient-to-br from-emerald-500 to-green-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
                                        <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                        </svg>
                                    </div>
                                    <h3 className="text-3xl font-bold text-slate-800 mb-2">Configuración de Seguridad</h3>
                                    <p className="text-slate-600 text-lg">Gestiona la seguridad de tu cuenta y contraseñas</p>
                                </div>
                                
                                {/* Cambio de Contraseña */}
                                <div className="max-w-2xl mx-auto">
                                    <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-3xl p-8 border border-emerald-200 shadow-lg">
                                        <div className="flex items-center mb-6">
                                            <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mr-4">
                                                <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                                                </svg>
                                            </div>
                                            <h4 className="text-2xl font-bold text-emerald-800">Cambiar Contraseña</h4>
                                        </div>
                                        
                                        <form onSubmit={handlePasswordChange} className="space-y-6">
                                            <div className="space-y-2">
                                                <label className="block text-sm font-semibold text-emerald-700 mb-3">
                                                    Contraseña Actual
                                                </label>
                                                <div className="relative">
                                                    <input
                                                        type={showPasswords.current ? "text" : "password"}
                                                        value={passwordData.current_password}
                                                        onChange={(e) => setPasswordData({...passwordData, current_password: e.target.value})}
                                                        className="w-full px-4 py-3 pr-14 border border-emerald-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                                        required
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => setShowPasswords({...showPasswords, current: !showPasswords.current})}
                                                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-emerald-400 hover:text-emerald-600 p-1 rounded-lg hover:bg-emerald-50 transition-colors"
                                                    >
                                                        {showPasswords.current ? (
                                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                                                            </svg>
                                                        ) : (
                                                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                                            </svg>
                                                        )}
                                                    </button>
                                                </div>
                                            </div>
                                            
                                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                                <div className="space-y-2">
                                                    <label className="block text-sm font-semibold text-emerald-700 mb-3">
                                                        Nueva Contraseña
                                                    </label>
                                                    <div className="relative">
                                                        <input
                                                            type={showPasswords.new ? "text" : "password"}
                                                            value={passwordData.new_password}
                                                            onChange={(e) => setPasswordData({...passwordData, new_password: e.target.value})}
                                                            className="w-full px-4 py-3 pr-14 border border-emerald-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                                            required
                                                        />
                                                        <button
                                                            type="button"
                                                            onClick={() => setShowPasswords({...showPasswords, new: !showPasswords.new})}
                                                            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-emerald-400 hover:text-emerald-600 p-1 rounded-lg hover:bg-emerald-50 transition-colors"
                                                        >
                                                            {showPasswords.new ? (
                                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                                                                </svg>
                                                            ) : (
                                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                                                </svg>
                                                            )}
                                                        </button>
                                                    </div>
                                                </div>
                                                
                                                <div className="space-y-2">
                                                    <label className="block text-sm font-semibold text-emerald-700 mb-3">
                                                        Confirmar Contraseña
                                                    </label>
                                                    <div className="relative">
                                                        <input
                                                            type={showPasswords.confirm ? "text" : "password"}
                                                            value={passwordData.confirm_password}
                                                            onChange={(e) => setPasswordData({...passwordData, confirm_password: e.target.value})}
                                                            className="w-full px-4 py-3 pr-14 border border-emerald-200 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition duration-150 bg-white shadow-sm hover:shadow-md"
                                                            required
                                                        />
                                                        <button
                                                            type="button"
                                                            onClick={() => setShowPasswords({...showPasswords, confirm: !showPasswords.confirm})}
                                                            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-emerald-400 hover:text-emerald-600 p-1 rounded-lg hover:bg-emerald-50 transition-colors"
                                                        >
                                                            {showPasswords.confirm ? (
                                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L21 21" />
                                                                </svg>
                                                            ) : (
                                                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                                                </svg>
                                                            )}
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                            
                                            <div className="pt-4">
                                                <button
                                                    type="submit"
                                                    disabled={loading}
                                                    className={`w-full py-4 px-6 rounded-2xl font-semibold text-lg transition duration-300 ${
                                                        loading
                                                            ? 'bg-slate-400 text-slate-200 cursor-not-allowed'
                                                            : 'bg-gradient-to-r from-emerald-600 to-green-600 text-white hover:from-emerald-700 hover:to-green-700 focus:ring-4 focus:ring-emerald-500/25 shadow-lg hover:shadow-xl transform hover:scale-[1.02]'
                                                    }`}
                                                >
                                                    {loading ? (
                                                        <div className="flex items-center justify-center">
                                                            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white mr-3"></div>
                                                            Cambiando...
                                                        </div>
                                                    ) : (
                                                        'Cambiar Contraseña'
                                                    )}
                                                </button>
                                            </div>
                                        </form>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Pestaña: Sesiones */}
                        {activeTab === 'sessions' && (
                            <div className="space-y-8">
                                <div className="text-center mb-8">
                                    <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg">
                                        <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    <h3 className="text-3xl font-bold text-slate-800 mb-2">Sesiones Activas</h3>
                                    <p className="text-slate-600 text-lg">Gestiona tus dispositivos y sesiones activas</p>
                                </div>
                                
                                <div className="max-w-4xl mx-auto">
                                    <div className="flex items-center justify-between mb-6">
                                        <h4 className="text-xl font-semibold text-slate-700">Dispositivos Conectados</h4>
                                        <button
                                            onClick={handleLogoutAllDevices}
                                            className="bg-gradient-to-r from-red-500 to-rose-600 text-white px-6 py-3 rounded-xl hover:from-red-600 hover:to-rose-700 transition duration-300 shadow-lg hover:shadow-xl transform hover:scale-105 font-semibold"
                                        >
                                            Cerrar Todas las Sesiones
                                        </button>
                                    </div>
                                    
                                    {loadingSessions ? (
                                        <div className="text-center py-12">
                                            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-purple-600 mx-auto mb-6"></div>
                                            <p className="text-lg text-slate-600 font-medium">Cargando sesiones...</p>
                                        </div>
                                    ) : activeSessions.length > 0 ? (
                                        <div className="grid gap-4">
                                            {activeSessions.map((session, index) => (
                                                <div key={index} className="bg-gradient-to-r from-white to-slate-50 rounded-2xl p-6 border border-slate-200 shadow-lg hover:shadow-xl transition duration-300 hover:scale-[1.02]">
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center space-x-6">
                                                            <div className="w-14 h-14 bg-gradient-to-br from-purple-100 to-indigo-100 rounded-2xl flex items-center justify-center shadow-md">
                                                                <svg className="w-8 h-8 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                                                </svg>
                                                            </div>
                                                            <div className="space-y-2">
                                                                <p className="font-bold text-lg text-slate-800">{session.name || 'Dispositivo'}</p>
                                                                <p className="text-slate-600 font-medium">IP: {session.ip_address}</p>
                                                                <p className="text-sm text-slate-500">
                                                                    Último uso: {new Date(session.last_used).toLocaleString()}
                                                                </p>
                                                            </div>
                                                        </div>
                                                        <button
                                                            onClick={() => handleLogoutDevice(session.id)}
                                                            className="text-red-500 hover:text-red-700 hover:bg-red-50 p-3 rounded-xl transition duration-150"
                                                        >
                                                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                                                            </svg>
                                                        </button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="text-center py-16">
                                            <div className="w-24 h-24 bg-gradient-to-br from-slate-100 to-slate-200 rounded-full flex items-center justify-center mx-auto mb-6">
                                                <svg className="w-12 h-12 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                                </svg>
                                            </div>
                                            <p className="text-xl text-slate-500 font-medium">No hay sesiones activas</p>
                                            <p className="text-slate-400 mt-2">Todos los dispositivos han sido desconectados</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}




                    </div>
                </div>
            </div>
        </div>
    );
}

export default ProfileSettings;
