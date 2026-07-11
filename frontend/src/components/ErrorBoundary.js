import React from 'react';

/**
 * Error Boundary global. Antes, un error de render en cualquier pantalla/gráfico tumbaba TODA
 * la app (pantalla en blanco). Este límite captura esos errores y muestra un fallback amable,
 * dejando el resto de la app (barra lateral, navegación) funcionando.
 *
 * Se usa con `key={currentPage}` en App.js para que al navegar a otra pantalla el límite se
 * remonte y se resetee automáticamente.
 */
class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, info) {
        // Queda en la consola del navegador para diagnóstico.
        console.error('ErrorBoundary capturó un error de render:', error, info);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: null });
    };

    handleReload = () => {
        window.location.reload();
    };

    render() {
        if (!this.state.hasError) {
            return this.props.children;
        }

        return (
            <div className="flex items-center justify-center min-h-[60vh] p-6" role="alert">
                <div className="max-w-lg w-full bg-white rounded-2xl shadow-xl border border-gray-100 p-8 text-center">
                    <div className="mx-auto w-14 h-14 rounded-full bg-red-50 flex items-center justify-center mb-4">
                        <svg className="w-7 h-7 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                    </div>
                    <h2 className="text-xl font-bold text-gray-800 mb-2">Algo salió mal en esta sección</h2>
                    <p className="text-gray-600 mb-6">
                        Ocurrió un error al mostrar este contenido. El resto de la aplicación sigue
                        funcionando: puedes reintentar, ir a otra sección o recargar la página.
                    </p>
                    <div className="flex justify-center gap-3">
                        <button
                            onClick={this.handleReset}
                            className="px-5 py-2.5 rounded-xl font-semibold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 transition duration-150 shadow-md hover:shadow-lg"
                        >
                            Reintentar
                        </button>
                        <button
                            onClick={this.handleReload}
                            className="px-5 py-2.5 rounded-xl font-semibold text-blue-600 bg-white border-2 border-blue-200 hover:bg-blue-50 transition duration-150"
                        >
                            Recargar página
                        </button>
                    </div>
                    {this.state.error && (
                        <details className="mt-5 text-left">
                            <summary className="text-xs text-gray-400 cursor-pointer">Detalle técnico</summary>
                            <pre className="mt-2 text-xs text-red-600 bg-red-50 rounded-lg p-3 overflow-auto max-h-40 whitespace-pre-wrap">
                                {String((this.state.error && this.state.error.message) || this.state.error)}
                            </pre>
                        </details>
                    )}
                </div>
            </div>
        );
    }
}

export default ErrorBoundary;
