import { useState, useEffect } from 'react';

/**
 * Suscribe a una media query CSS y devuelve si coincide actualmente.
 * Defensivo ante entornos sin `matchMedia` (p. ej. jsdom en tests): devuelve false.
 *
 * @param {string} query - media query, p. ej. '(max-width: 1023.98px)'
 * @returns {boolean}
 */
export function useMediaQuery(query) {
  const getMatch = () => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return false;
    }
    return window.matchMedia(query).matches;
  };

  const [matches, setMatches] = useState(getMatch);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
      return undefined;
    }
    const mql = window.matchMedia(query);
    const onChange = (e) => setMatches(e.matches);
    // Sincroniza por si cambió entre el render inicial y el efecto.
    setMatches(mql.matches);
    mql.addEventListener('change', onChange);
    return () => mql.removeEventListener('change', onChange);
  }, [query]);

  return matches;
}

/** true por debajo del breakpoint `lg` (1024px), coherente con el CSS de UserMenu. */
export function useIsMobile() {
  return useMediaQuery('(max-width: 1023.98px)');
}

/** true en dispositivos de puntero grueso (táctil), para ajustar gestos de zoom. */
export function useIsCoarsePointer() {
  return useMediaQuery('(pointer: coarse)');
}
