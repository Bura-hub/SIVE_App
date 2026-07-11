import React, { useState, useEffect } from 'react';
import siveLogo from './sive-logo.svg';
import background from './bg.webp';
import TransitionOverlay from './TransitionOverlay';
import { fetchWithAuth, handleApiResponse } from '../utils/apiConfig';
import { buildApiUrl, getEndpoint } from '../config';

function LoginPage({ onLoginSuccess }) {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [message, setMessage] = useState({ text: '', type: '' });
    const [loading, setLoading] = useState(false);
    const [isVisible, setIsVisible] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [focusedField, setFocusedField] = useState('');
    
    // Estados para la animación de transición
    const [showTransition, setShowTransition] = useState(false);
    const [transitionType, setTransitionType] = useState('info');
    const [transitionMessage, setTransitionMessage] = useState('');
    
    // Estados para rate limiting y seguridad
    const [failedAttempts, setFailedAttempts] = useState(0);
    const [isBlocked, setIsBlocked] = useState(false);
    const [blockUntil, setBlockUntil] = useState(null);
    const [showCaptcha, setShowCaptcha] = useState(false);
    const [captchaValue, setCaptchaValue] = useState('');
    const [generatedCaptcha, setGeneratedCaptcha] = useState('');
    
    // Estados para el modal de registro
    const [showRegisterModal, setShowRegisterModal] = useState(false);
    const [registerData, setRegisterData] = useState({
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        password: '',
        confirm_password: ''
    });
    const [registerLoading, setRegisterLoading] = useState(false);
    const [showRegisterPassword, setShowRegisterPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [registerSuccess, setRegisterSuccess] = useState(false);

    // Animación de entrada
    useEffect(() => {
        setIsVisible(true);
    }, []);
    
    // Efecto para rate limiting y bloqueo
    useEffect(() => {
        const savedAttempts = localStorage.getItem('loginFailedAttempts');
        const savedBlockUntil = localStorage.getItem('loginBlockUntil');
        
        if (savedAttempts) {
            setFailedAttempts(parseInt(savedAttempts));
        }
        
        if (savedBlockUntil) {
            const blockTime = new Date(savedBlockUntil);
            if (blockTime > new Date()) {
                setIsBlocked(true);
                setBlockUntil(blockTime);
            } else {
                // Limpiar bloqueo expirado
                localStorage.removeItem('loginFailedAttempts');
                localStorage.removeItem('loginBlockUntil');
                setFailedAttempts(0);
                setIsBlocked(false);
                setBlockUntil(null);
            }
        }
    }, []);
    
    // Generar captcha cuando se necesite
    useEffect(() => {
        if (showCaptcha) {
            generateCaptcha();
        }
    }, [showCaptcha]);
    
    // Función para generar captcha simple
    const generateCaptcha = () => {
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
        let result = '';
        for (let i = 0; i < 6; i++) {
            result += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        setGeneratedCaptcha(result);
    };
    
    // Función para verificar si debe mostrar captcha
    const shouldShowCaptcha = () => {
        return failedAttempts >= 3;
    };
    
    // Función para bloquear temporalmente
    const blockTemporarily = () => {
        const blockDuration = Math.min(30 * Math.pow(2, failedAttempts - 5), 300); // Máximo 5 minutos
        const blockUntil = new Date(Date.now() + blockDuration * 1000);
        
        setIsBlocked(true);
        setBlockUntil(blockUntil);
        localStorage.setItem('loginBlockUntil', blockUntil.toISOString());
    };

    // Función para validar contraseña
    const validatePassword = (password) => {
        const minLength = 8;
        const hasUpperCase = /[A-Z]/.test(password);
        const hasLowerCase = /[a-z]/.test(password);
        const hasNumbers = /\d/.test(password);
        const hasSpecialChar = /[!@#$%^&*(),.?":{}|<>]/.test(password);
        
        if (password.length < minLength) {
            return { isValid: false, message: `La contraseña debe tener al menos ${minLength} caracteres` };
        }
        if (!hasUpperCase) {
            return { isValid: false, message: 'La contraseña debe contener al menos una mayúscula' };
        }
        if (!hasLowerCase) {
            return { isValid: false, message: 'La contraseña debe contener al menos una minúscula' };
        }
        if (!hasNumbers) {
            return { isValid: false, message: 'La contraseña debe contener al menos un número' };
        }
        if (!hasSpecialChar) {
            return { isValid: false, message: 'La contraseña debe contener al menos un carácter especial' };
        }
        
        return { isValid: true, message: 'Contraseña válida' };
    };
    
    // Función para validar datos de registro
    const validateRegisterData = () => {
        if (!registerData.username || registerData.username.length < 3) {
            return { isValid: false, message: 'El nombre de usuario debe tener al menos 3 caracteres' };
        }
        if (!registerData.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registerData.email)) {
            return { isValid: false, message: 'Ingrese un email válido' };
        }
        if (!registerData.first_name || registerData.first_name.trim().length < 2) {
            return { isValid: false, message: 'El nombre debe tener al menos 2 caracteres' };
        }
        if (!registerData.last_name || registerData.last_name.trim().length < 2) {
            return { isValid: false, message: 'El apellido debe tener al menos 2 caracteres' };
        }
        
        const passwordValidation = validatePassword(registerData.password);
        if (!passwordValidation.isValid) {
            return passwordValidation;
        }
        
        if (registerData.password !== registerData.confirm_password) {
            return { isValid: false, message: 'Las contraseñas no coinciden' };
        }
        
        return { isValid: true, message: 'Datos válidos' };
    };
    
    // Función para manejar el registro
    const handleRegister = async (event) => {
        event.preventDefault();
        
        const validation = validateRegisterData();
        if (!validation.isValid) {
            setMessage({ text: validation.message, type: 'error' });
            return;
        }
        
        setRegisterLoading(true);
        setMessage({ text: '', type: '' });
        
        try {
            const response = await fetch(buildApiUrl(getEndpoint('REGISTER')), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: registerData.username,
                    email: registerData.email,
                    first_name: registerData.first_name,
                    last_name: registerData.last_name,
                    password: registerData.password,
                    confirm_password: registerData.confirm_password
                }),
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Error ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Mostrar estado de éxito
            setRegisterSuccess(true);
            setMessage({ text: 'Cuenta creada exitosamente. Ya puedes iniciar sesión.', type: 'success' });
            
            // Esperar 2 segundos para que el usuario vea el mensaje de éxito, luego cerrar
            setTimeout(() => {
                setShowRegisterModal(false);
                setRegisterSuccess(false);
            }, 2000);
            setRegisterData({
                username: '',
                email: '',
                first_name: '',
                last_name: '',
                password: '',
                confirm_password: ''
            });
            
            // Limpiar mensaje después de 3 segundos
            setTimeout(() => {
                setMessage({ text: '', type: '' });
            }, 3000);
            
        } catch (error) {
            // Mostrar error específico del backend o mensaje genérico
            let errorMessage = 'Error al crear la cuenta';
            
            if (error.message.includes('username already exists')) {
                errorMessage = 'El nombre de usuario ya existe. Intenta con otro.';
            } else if (error.message.includes('email already exists')) {
                errorMessage = 'El email ya está registrado. Intenta con otro.';
            } else if (error.message.includes('password')) {
                errorMessage = 'La contraseña no cumple con los requisitos de seguridad.';
            } else if (error.message) {
                errorMessage = error.message;
            }
            
            setMessage({ text: errorMessage, type: 'error' });
        } finally {
            setRegisterLoading(false);
        }
    };
    
    // Función para abrir modal de registro
    const openRegisterModal = () => {
        setShowRegisterModal(true);
        setMessage({ text: '', type: '' });
    };
    
    // Función para cerrar modal de registro
    const closeRegisterModal = () => {
        setShowRegisterModal(false);
        setRegisterData({
            username: '',
            email: '',
            first_name: '',
            last_name: '',
            password: '',
            confirm_password: ''
        });
        setMessage({ text: '', type: '' });
        setRegisterSuccess(false);
    };
    
    // Función para contactar soporte (olvidó contraseña)
    const contactSupport = () => {
        const supportEmail = 'bura.vent@gmail.com';
        const supportPhone = '+57 (312) 756-0677';
        
        const message = `Para recuperar tu contraseña, contacta a nuestro equipo de soporte:\n\n📧 Email: ${supportEmail}\n📞 Teléfono: ${supportPhone}\n\nHorario de atención: Lunes a Viernes 8:00 AM - 6:00 PM`;
        
        alert(message);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();
        
        // Verificar si está bloqueado
        if (isBlocked) {
            const remainingTime = Math.ceil((blockUntil - new Date()) / 1000);
            setMessage({ 
                text: `Demasiados intentos fallidos. Intenta de nuevo en ${Math.ceil(remainingTime / 60)} minutos`, 
                type: 'error' 
            });
            return;
        }
        
        // En el login no se valida complejidad de la contraseña: el backend
        // decide si las credenciales son válidas (la complejidad solo se
        // exige al registrar). Ver validateRegisterData para el registro.
        if (!password) {
            setMessage({ text: 'Ingresa tu contraseña', type: 'error' });
            return;
        }
        
        // Verificar captcha si es necesario
        if (showCaptcha && captchaValue !== generatedCaptcha) {
            setMessage({ text: 'Código de verificación incorrecto', type: 'error' });
            setCaptchaValue('');
            generateCaptcha();
            return;
        }
        
        setMessage({ text: '', type: '' });
        setLoading(true);
        setShowTransition(true);
        setTransitionType('info');
        setTransitionMessage('Iniciando sesión...');

        try {
            // Usar fetch directo para manejar errores de autenticación manualmente
            const response = await fetch(buildApiUrl(getEndpoint('LOGIN')), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ username, password }),
            });

            if (!response.ok) {
                let errorData = {};
                try { errorData = await response.json(); } catch (_) { /* respuesta no-JSON (p.ej. proxy/HTML) */ }
                const serverMsg = errorData.error || errorData.message || errorData.detail;
                const err = new Error(serverMsg || `HTTP ${response.status}`);
                err.status = response.status;   // para ramificar el mensaje en el catch
                err.serverMsg = serverMsg;
                throw err;
            }

            const data = await response.json();

            // Si llegamos aquí, el login fue exitoso
            // No logging por seguridad
            
            // Resetear intentos fallidos y bloqueos
            setFailedAttempts(0);
            setIsBlocked(false);
            setBlockUntil(null);
            setShowCaptcha(false);
            setCaptchaValue('');
            localStorage.removeItem('loginFailedAttempts');
            localStorage.removeItem('loginBlockUntil');
            
                setMessage({ text: 'Inicio exitoso. Redireccionando...', type: 'success' });
                setTransitionType('success');
                setTransitionMessage('Inicio exitoso. Redireccionando...');
                
                setTimeout(() => {
                    setShowTransition(false);
                // No logging por seguridad
                onLoginSuccess(data.access_token, data.username, data.is_superuser);
                }, 1500);

        } catch (error) {
            // No logging por seguridad
            
            // Mensaje claro según el tipo de fallo. error.status existe solo si hubo respuesta
            // HTTP; si no, fue un fallo de red real (sin conexión / servidor caído / CORS).
            const status = error.status;
            const serverMsg = error.serverMsg || '';
            let errorMessage;
            let shouldIncrementAttempts = false;

            if (status === undefined) {
                errorMessage = 'No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.';
            } else if (status === 401 || status === 400 || serverMsg.includes('Credenciales inválidas') || serverMsg.includes('Datos de entrada inválidos')) {
                errorMessage = 'Usuario o contraseña incorrectos.';
                shouldIncrementAttempts = true;
            } else if (status === 423 || serverMsg.includes('bloqueada')) {
                errorMessage = 'Tu cuenta está temporalmente bloqueada. Intenta más tarde.';
            } else if (serverMsg.includes('Cambio de contraseña')) {
                errorMessage = 'Debes cambiar tu contraseña antes de continuar.';
            } else if (serverMsg.includes('inactivo') || serverMsg.includes('desactivada')) {
                errorMessage = 'Tu cuenta ha sido desactivada. Contacta al administrador.';
            } else if (status === 403) {
                errorMessage = 'Acceso denegado. Si tienes abierta la sesión del panel de administración, ciérrala (o usa una ventana de incógnito) y vuelve a intentar.';
            } else if (status === 429) {
                errorMessage = 'Demasiados intentos. Espera un momento e inténtalo de nuevo.';
            } else if (status >= 500) {
                errorMessage = 'Error del servidor. Inténtalo de nuevo más tarde.';
            } else {
                errorMessage = serverMsg || `Error ${status}. Inténtalo de nuevo.`;
            }
            
            // Incrementar intentos fallidos si corresponde
            if (shouldIncrementAttempts) {
                const newFailedAttempts = failedAttempts + 1;
                setFailedAttempts(newFailedAttempts);
                localStorage.setItem('loginFailedAttempts', newFailedAttempts.toString());
                
                // Mostrar captcha después de 3 intentos
                if (newFailedAttempts >= 3 && !showCaptcha) {
                    setShowCaptcha(true);
                }
                
                // Bloquear después de 5 intentos
                if (newFailedAttempts >= 5) {
                    blockTemporarily();
                }
            }
            
                setMessage({ text: errorMessage, type: 'error' });
                setShowTransition(false);
            // No logging por seguridad
        } finally {
            setLoading(false);
        }
    };

    return (
        <div 
            className="min-h-screen flex items-center justify-center bg-cover bg-center bg-no-repeat p-4 font-inter relative overflow-hidden"
            style={{ backgroundColor: '#0f172a', backgroundImage: `url(${background})` }}
        >
            {/* Partículas flotantes animadas */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                {[...Array(6)].map((_, i) => (
                    <div
                        key={i}
                        className="absolute w-2 h-2 bg-blue-400 rounded-full opacity-20 animate-float"
                        style={{
                            left: `${Math.random() * 100}%`,
                            top: `${Math.random() * 100}%`,
                            animationDelay: `${Math.random() * 3}s`,
                            animationDuration: `${3 + Math.random() * 2}s`
                        }}
                    />
                ))}
            </div>

            {/* Card de login mejorado */}
            <div className={`login-card-enhanced transform transition duration-300 ease-out ${
                isVisible ? 'translate-y-0 opacity-100 scale-100' : 'translate-y-8 opacity-0 scale-95'
            }`}>
                {/* Logo con animación */}
                <div className="flex justify-center mb-6">
                    <div className="logo-container">
                        <img
                            src={siveLogo}
                            alt="SIVE Logo"
                            className="w-50 h-auto mx-auto transition-transform duration-300 hover:scale-105"
                        />
                    </div>
                </div>

                {/* Título y lema mejorados */}
                <div className="text-center mb-8">
                    <h1 className="text-2xl font-bold text-gray-800 mb-2">Bienvenido</h1>
                    <p className="text-sm text-gray-600 leading-relaxed">
                        Transparencia energética para un futuro descentralizado
                    </p>
                </div>

                {/* Formulario mejorado */}
                <form onSubmit={handleSubmit} className="space-y-6">
                    {/* Campo de usuario */}
                    <div className="input-group">
                        <label htmlFor="username" className="input-label">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                            </svg>
                            Usuario
                        </label>
                        <div className="input-wrapper">
                            <input
                                type="text"
                                id="username"
                                name="username"
                                placeholder="Introduce tu usuario"
                                className={`enhanced-input ${focusedField === 'username' ? 'focused' : ''}`}
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                onFocus={() => setFocusedField('username')}
                                onBlur={() => setFocusedField('')}
                                required
                            />
                        </div>
                    </div>

                    {/* Campo de contraseña */}
                    <div className="input-group">
                        <label htmlFor="password" className="input-label">
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                            </svg>
                            Contraseña
                        </label>
                        <div className="input-wrapper">
                            <input
                                type={showPassword ? "text" : "password"}
                                id="password"
                                name="password"
                                placeholder="Introduce tu contraseña"
                                className={`enhanced-input pr-12 ${focusedField === 'password' ? 'focused' : ''}`}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                onFocus={() => setFocusedField('password')}
                                onBlur={() => setFocusedField('')}
                                required
                            />
                            <button
                                type="button"
                                className="password-toggle"
                                aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                                aria-pressed={showPassword}
                                onClick={() => setShowPassword(!showPassword)}
                            >
                                {showPassword ? (
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

                    {/* Campo de captcha (se muestra después de 3 intentos fallidos) */}
                    {showCaptcha && (
                        <div className="input-group">
                            <label htmlFor="captcha" className="input-label">
                                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                Código de Verificación
                            </label>
                            <div className="captcha-container bg-gray-50 rounded-xl p-4 border border-gray-200">
                                <div className="captcha-display flex items-center justify-between mb-3">
                                    <div className="bg-white px-4 py-2 rounded-lg border-2 border-dashed border-gray-300">
                                        <span className="captcha-text text-2xl font-mono font-bold text-gray-800 tracking-widest select-none">
                                            {generatedCaptcha}
                                        </span>
                                    </div>
                                    <button
                                        type="button"
                                        onClick={generateCaptcha}
                                        className="captcha-refresh p-2 bg-blue-100 hover:bg-blue-200 rounded-lg transition-colors duration-150"
                                        title="Generar nuevo código"
                                    >
                                        <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                        </svg>
                                    </button>
                                </div>
                                <input
                                    type="text"
                                    id="captcha"
                                    name="captcha"
                                    placeholder="Ingresa el código de arriba"
                                    className="enhanced-input text-center text-lg font-mono tracking-widest"
                                    value={captchaValue}
                                    onChange={(e) => setCaptchaValue(e.target.value.toUpperCase())}
                                    maxLength={6}
                                    required
                                />
                            </div>
                        </div>
                    )}

                    {/* Botón de login mejorado */}
                    <button 
                        type="submit" 
                        className={`enhanced-login-button ${loading ? 'loading' : ''}`} 
                        disabled={loading}
                    >
                        <span className="button-content">
                            {loading ? (
                                <>
                                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Iniciando sesión...
                                </>
                            ) : (
                                <>
                                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                                    </svg>
                                    Iniciar sesión
                                </>
                            )}
                        </span>
                    </button>
                </form>

                {/* Indicadores de seguridad */}
                {failedAttempts > 0 && (
                    <div className="security-indicator bg-gradient-to-r from-orange-50 to-red-50 border border-orange-200 rounded-xl p-4 mb-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                                <div className={`w-3 h-3 rounded-full ${failedAttempts >= 5 ? 'bg-red-500' : failedAttempts >= 3 ? 'bg-orange-500' : 'bg-yellow-500'}`}></div>
                                <span className="text-orange-700 font-medium">
                                    <svg className="w-4 h-4 inline mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                                    </svg>
                                    Intentos fallidos: {failedAttempts}/5
                                </span>
                            </div>
                            {failedAttempts >= 3 && (
                                <span className="text-red-600 font-medium bg-red-100 px-3 py-1 rounded-full text-sm">
                                    Captcha requerido
                                </span>
                            )}
                            {failedAttempts >= 5 && (
                                <span className="text-red-600 font-medium bg-red-100 px-3 py-1 rounded-full text-sm">
                                    Cuenta bloqueada
                                </span>
                            )}
                        </div>
                        {isBlocked && blockUntil && (
                            <div className="mt-2 text-sm text-red-600">
                                <svg className="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                Bloqueado hasta: {blockUntil.toLocaleTimeString()}
                            </div>
                        )}
                    </div>
                )}

                {/* Mensaje de estado mejorado */}
                {message.text && (
                    <div className={`message-container ${message.type}`}>
                        <div className="message-icon">
                            {message.type === 'success' ? (
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                            ) : (
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            )}
                        </div>
                        <span>{message.text}</span>
                    </div>
                )}

                {/* Enlaces secundarios mejorados */}
                <div className="secondary-links">
                    <button 
                        onClick={contactSupport}
                        className="enhanced-secondary-link"
                    >
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.141 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
                        </svg>
                        ¿Olvidó su contraseña?
                    </button>
                    <button 
                        onClick={openRegisterModal}
                        className="enhanced-secondary-link"
                    >
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
                        </svg>
                        Crear una cuenta
                    </button>
                </div>

                {/* Footer profesional integrado */}
                <div className="mt-6 pt-4 border-t border-gray-200">
                    <div className="text-center space-y-2">
                        <p className="text-xs text-gray-600 leading-relaxed">
                            Sistema de Visualización Energético
                        </p>
                        <p className="text-xs text-gray-600">
                            SIVE para transparencia energética
                        </p>
                        <div className="flex items-center justify-center space-x-4 text-xs text-gray-600 pt-1">
                            <div className="flex items-center space-x-1">
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                                </svg>
                                <span>Universidad de Nariño</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Modal de Registro */}
            {showRegisterModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto">
                        {/* Header del modal */}
                        <div className="flex items-center justify-between p-6 border-b border-gray-200">
                            <h2 className="text-xl font-bold text-gray-800">Crear Nueva Cuenta</h2>
                            <button
                                onClick={closeRegisterModal}
                                className="text-gray-600 hover:text-gray-600 transition-colors"
                            >
                                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Mensaje de estado */}
                        {message.text && (
                            <div className={`mx-6 mb-4 p-4 rounded-lg ${
                                message.type === 'success' 
                                    ? 'bg-green-50 border border-green-200 text-green-800' 
                                    : 'bg-red-50 border border-red-200 text-red-800'
                            }`}>
                                <div className="flex items-center">
                                    {message.type === 'success' ? (
                                        <svg className="w-5 h-5 mr-2 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    ) : (
                                        <svg className="w-5 h-5 mr-2 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    )}
                                    <span className="font-medium">{message.text}</span>
                                </div>
                            </div>
                        )}

                        {/* Mensaje de éxito prominente */}
                        {registerSuccess && (
                            <div className="mx-6 mb-4 p-6 bg-gradient-to-r from-green-50 to-emerald-50 border-2 border-green-200 rounded-xl">
                                <div className="text-center">
                                    <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
                                        <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>
                                    <h3 className="text-lg font-bold text-green-800 mb-2">¡Cuenta Creada Exitosamente!</h3>
                                    <p className="text-green-700">Ya puedes cerrar esta ventana e iniciar sesión con tu nueva cuenta.</p>
                                </div>
                            </div>
                        )}

                        {/* Formulario de registro */}
                        {!registerSuccess && (
                            <form onSubmit={handleRegister} className="p-6 space-y-4">
                            {/* Username */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Nombre de Usuario *
                                </label>
                                <input
                                    type="text"
                                    value={registerData.username}
                                    onChange={(e) => setRegisterData({...registerData, username: e.target.value})}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    placeholder="Ingresa tu nombre de usuario"
                                    required
                                />
                            </div>

                            {/* Email */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Email *
                                </label>
                                <input
                                    type="email"
                                    value={registerData.email}
                                    onChange={(e) => setRegisterData({...registerData, email: e.target.value})}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                    placeholder="tu@email.com"
                                    required
                                />
                            </div>

                            {/* Nombre y Apellido */}
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Nombre *
                                    </label>
                                    <input
                                        type="text"
                                        value={registerData.first_name}
                                        onChange={(e) => setRegisterData({...registerData, first_name: e.target.value})}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        placeholder="Tu nombre"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                        Apellido *
                                    </label>
                                    <input
                                        type="text"
                                        value={registerData.last_name}
                                        onChange={(e) => setRegisterData({...registerData, last_name: e.target.value})}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        placeholder="Tu apellido"
                                        required
                                    />
                                </div>
                            </div>

                            {/* Contraseña */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Contraseña *
                                </label>
                                <div className="relative">
                                    <input
                                        type={showRegisterPassword ? "text" : "password"}
                                        value={registerData.password}
                                        onChange={(e) => setRegisterData({...registerData, password: e.target.value})}
                                        className="w-full px-3 py-2 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        placeholder="Mínimo 8 caracteres"
                                        required
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowRegisterPassword(!showRegisterPassword)}
                                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-600 hover:text-gray-600"
                                    >
                                        {showRegisterPassword ? (
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
                                <p className="text-xs text-gray-600 mt-1">
                                    Debe contener mayúsculas, minúsculas, números y caracteres especiales
                                </p>
                            </div>

                            {/* Confirmar Contraseña */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Confirmar Contraseña *
                                </label>
                                <div className="relative">
                                    <input
                                        type={showConfirmPassword ? "text" : "password"}
                                        value={registerData.confirm_password}
                                        onChange={(e) => setRegisterData({...registerData, confirm_password: e.target.value})}
                                        className="w-full px-3 py-2 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        placeholder="Repite tu contraseña"
                                        required
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                        className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-600 hover:text-gray-600"
                                    >
                                        {showConfirmPassword ? (
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

                            {/* Botón de registro */}
                            <button
                                type="submit"
                                disabled={registerLoading}
                                className={`w-full py-3 px-4 rounded-lg font-medium transition duration-150 ${
                                    registerLoading 
                                        ? 'bg-gray-400 text-gray-200 cursor-not-allowed' 
                                        : 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-4 focus:ring-blue-200'
                                }`}
                            >
                                {registerLoading ? (
                                    <div className="flex items-center justify-center">
                                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Creando cuenta...
                                    </div>
                                ) : (
                                    'Crear Cuenta'
                                )}
                            </button>
                            </form>
                        )}

                        {/* Footer del modal */}
                        <div className="px-6 py-4 bg-gray-50 rounded-b-2xl">
                            <p className="text-sm text-gray-600 text-center">
                                Al crear una cuenta, aceptas nuestros{' '}
                                <a href="#" className="text-blue-600 hover:underline">Términos de Servicio</a>
                                {' '}y{' '}
                                <a href="#" className="text-blue-600 hover:underline">Política de Privacidad</a>
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* Overlay de transición */}
            <TransitionOverlay 
                show={showTransition}
                type={transitionType}
                message={transitionMessage}
            />
        </div>
    );
}

export default LoginPage;