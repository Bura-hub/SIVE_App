import React, { useState, useRef, useEffect } from 'react';
import { buildApiUrl } from '../config';

function ProfileImageUpload({ currentImageUrl, onImageUpdate, onImageDelete }) {
    const [selectedFile, setSelectedFile] = useState(null);
    const [previewUrl, setPreviewUrl] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    
    const fileInputRef = useRef(null);
    const dropZoneRef = useRef(null);

    // Configuración de archivos permitidos
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    const maxSize = 5 * 1024 * 1024; // 5MB
    const minDimensions = { width: 100, height: 100 };
    const maxDimensions = { width: 2000, height: 2000 };

    useEffect(() => {
        if (currentImageUrl) {
            setPreviewUrl(currentImageUrl);
        }
    }, [currentImageUrl]);

    // Función para validar archivo
    const validateFile = (file) => {
        setError('');
        
        // Verificar tipo de archivo
        if (!allowedTypes.includes(file.type)) {
            setError('Solo se permiten imágenes en formato JPG, PNG o WebP');
            return false;
        }
        
        // Verificar tamaño
        if (file.size > maxSize) {
            setError('La imagen no puede ser mayor a 5MB');
            return false;
        }
        
        return true;
    };

    // Función para validar dimensiones de imagen
    const validateImageDimensions = (file) => {
        return new Promise((resolve) => {
            const img = new Image();
            img.onload = () => {
                if (img.width < minDimensions.width || img.height < minDimensions.height) {
                    setError(`La imagen debe tener al menos ${minDimensions.width}x${minDimensions.height} píxeles`);
                    resolve(false);
                } else if (img.width > maxDimensions.width || img.height > maxDimensions.height) {
                    setError(`La imagen no puede ser mayor a ${maxDimensions.width}x${maxDimensions.height} píxeles`);
                    resolve(false);
                } else {
                    resolve(true);
                }
            };
            img.onerror = () => {
                setError('Error al cargar la imagen');
                resolve(false);
            };
            img.src = URL.createObjectURL(file);
        });
    };

    // Función para manejar selección de archivo
    const handleFileSelect = async (file) => {
        if (!validateFile(file)) return;
        
        const isValidDimensions = await validateImageDimensions(file);
        if (!isValidDimensions) return;
        
        setSelectedFile(file);
        setPreviewUrl(URL.createObjectURL(file));
        setError('');
    };

    // Función para manejar cambio en input de archivo
    const handleFileChange = (event) => {
        const file = event.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    };

    // Función para manejar drag and drop
    const handleDrag = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === "dragenter" || e.type === "dragover") {
            setDragActive(true);
        } else if (e.type === "dragleave") {
            setDragActive(false);
        }
    };

    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFileSelect(e.dataTransfer.files[0]);
        }
    };

    // Función para subir imagen
    const handleUpload = async () => {
        if (!selectedFile) return;
        
        setIsUploading(true);
        setError('');
        setSuccess('');
        
        try {
            const formData = new FormData();
            formData.append('profile_image', selectedFile);
            
            const response = await fetch(buildApiUrl('/auth/profile-image/'), {
                method: 'POST',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                },
                body: formData
            });
            
            if (response.ok) {
                const data = await response.json();
                setSuccess('Imagen de perfil actualizada exitosamente');
                setSelectedFile(null);
                if (onImageUpdate) {
                    onImageUpdate(data.profile_image_url);
                }
                
                // Limpiar mensaje de éxito después de 3 segundos
                setTimeout(() => setSuccess(''), 3000);
            } else {
                const errorData = await response.json();
                setError(errorData.error || 'Error al subir la imagen');
            }
        } catch (error) {
            setError('Error de conexión al subir la imagen');
        } finally {
            setIsUploading(false);
        }
    };

    // Función para eliminar imagen
    const handleDelete = async () => {
        if (!currentImageUrl) return;
        
        setIsUploading(true);
        setError('');
        
        try {
            const response = await fetch(buildApiUrl('/auth/profile-image/'), {
                method: 'DELETE',
                headers: {
                    'Authorization': `Token ${localStorage.getItem('authToken')}`,
                }
            });
            
            if (response.ok) {
                setSuccess('Imagen de perfil eliminada exitosamente');
                setPreviewUrl(null);
                if (onImageDelete) {
                    onImageDelete();
                }
                
                // Limpiar mensaje de éxito después de 3 segundos
                setTimeout(() => setSuccess(''), 3000);
            } else {
                const errorData = await response.json();
                setError(errorData.error || 'Error al eliminar la imagen');
            }
        } catch (error) {
            setError('Error de conexión al eliminar la imagen');
        } finally {
            setIsUploading(false);
        }
    };

    // Función para abrir selector de archivos
    const openFileSelector = () => {
        fileInputRef.current?.click();
    };

    return (
        <div className="space-y-6">
            {/* Título de la sección */}
            <div className="text-center">
                <h3 className="text-2xl font-bold text-slate-800 mb-2">Imagen de Perfil</h3>
                <p className="text-slate-600">Personaliza tu perfil con una imagen única</p>
            </div>

            {/* Zona de drag and drop */}
            <div
                ref={dropZoneRef}
                className={`relative border-2 border-dashed rounded-2xl p-8 text-center transition duration-300 ${
                    dragActive 
                        ? 'border-blue-500 bg-blue-50' 
                        : 'border-slate-300 hover:border-slate-400 hover:bg-slate-50'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
            >
                {/* Icono de imagen */}
                <div className="w-16 h-16 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                </div>

                {/* Texto de instrucciones */}
                <div className="space-y-2">
                    <p className="text-lg font-semibold text-slate-700">
                        {dragActive ? 'Suelta tu imagen aquí' : 'Arrastra tu imagen aquí o haz clic para seleccionar'}
                    </p>
                    <p className="text-sm text-slate-500">
                        Formatos: JPG, PNG, WebP • Máximo: 5MB • Dimensiones: 100x100 a 2000x2000 píxeles
                    </p>
                </div>

                {/* Botón de selección */}
                <button
                    onClick={openFileSelector}
                    className="mt-4 px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-indigo-700 transition duration-300 shadow-lg hover:shadow-xl"
                >
                    Seleccionar Imagen
                </button>

                {/* Input de archivo oculto */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    onChange={handleFileChange}
                    className="hidden"
                />
            </div>

            {/* Vista previa de la imagen */}
            {previewUrl && (
                <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-lg">
                    <h4 className="text-lg font-semibold text-slate-800 mb-4">Vista Previa</h4>
                    <div className="flex items-center space-x-6">
                        {/* Imagen */}
                        <div className="relative">
                            <img
                                src={previewUrl}
                                alt="Vista previa"
                                className="w-24 h-24 rounded-full object-cover border-4 border-slate-200 shadow-lg"
                            />
                            {selectedFile && (
                                <div className="absolute -top-2 -right-2 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
                                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                                    </svg>
                                </div>
                            )}
                        </div>

                        {/* Información del archivo */}
                        <div className="flex-1">
                            {selectedFile && (
                                <div className="space-y-2">
                                    <p className="text-sm text-slate-600">
                                        <span className="font-semibold">Archivo:</span> {selectedFile.name}
                                    </p>
                                    <p className="text-sm text-slate-600">
                                        <span className="font-semibold">Tamaño:</span> {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                    </p>
                                    <p className="text-sm text-slate-600">
                                        <span className="font-semibold">Tipo:</span> {selectedFile.type}
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Botones de acción */}
                        <div className="flex space-x-3">
                            {selectedFile && (
                                <button
                                    onClick={handleUpload}
                                    disabled={isUploading}
                                    className="px-4 py-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white rounded-lg font-semibold hover:from-emerald-700 hover:to-teal-700 transition duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {isUploading ? (
                                        <div className="flex items-center space-x-2">
                                            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                                            <span>Subiendo...</span>
                                        </div>
                                    ) : (
                                        'Subir Imagen'
                                    )}
                                </button>
                            )}
                            
                            {currentImageUrl && (
                                <button
                                    onClick={handleDelete}
                                    disabled={isUploading}
                                    className="px-4 py-2 bg-gradient-to-r from-red-600 to-pink-600 text-white rounded-lg font-semibold hover:from-red-700 hover:to-pink-700 transition duration-300 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    {isUploading ? 'Eliminando...' : 'Eliminar'}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Mensajes de estado */}
            {error && (
                <div className="bg-gradient-to-r from-red-50 to-pink-50 border border-red-200 rounded-xl p-4">
                    <div className="flex items-center">
                        <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center mr-4">
                            <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                            </svg>
                        </div>
                        <span className="text-red-800 font-semibold">{error}</span>
                    </div>
                </div>
            )}

            {success && (
                <div className="bg-gradient-to-r from-emerald-50 to-green-50 border border-emerald-200 rounded-xl p-4">
                    <div className="flex items-center">
                        <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center mr-4">
                            <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <span className="text-emerald-800 font-semibold">{success}</span>
                    </div>
                </div>
            )}
        </div>
    );
}

export default ProfileImageUpload;
