import { render } from '@testing-library/react';
import UserMenu from './UserMenu';

// El menú flotante publica su ancho en --u-float-reserve para que las cabeceras le dejen sitio
// (como invitado lleva además «Iniciar sesión» y no cabía en los 16rem fijos: tapaba «XM Conectado»).
test('publica el ancho del menú flotante en --u-float-reserve y lo retira al desmontar', () => {
  let callback = null;
  const original = global.ResizeObserver;
  global.ResizeObserver = class { constructor(cb) { callback = cb; } observe() {} disconnect() {} };
  try {
    const { unmount } = render(<UserMenu isGuest onLogin={() => {}} onLogout={() => {}} />);
    callback([{ contentRect: { width: 380 } }]);
    expect(document.documentElement.style.getPropertyValue('--u-float-reserve')).toBe('428px');
    unmount();
    expect(document.documentElement.style.getPropertyValue('--u-float-reserve')).toBe('');
  } finally {
    global.ResizeObserver = original;
  }
});
