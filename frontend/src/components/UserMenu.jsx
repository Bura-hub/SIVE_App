import React, { useState, useEffect, useRef, useCallback } from 'react';
import { buildApiUrl } from '../config';
import TransitionOverlay from './TransitionOverlay';
import ProfileSettings from './ProfileSettings';
import HelpSupport from './HelpSupport';
import {
  IconSettings,
  IconHelpCircle,
  IconLogOut,
  IconChevronDown,
  IconChevronRight,
  IconShield,
} from './icons';

/**
 * Menú de usuario flotante (esquina superior derecha).
 * Chip de vidrio colapsado + dropdown sólido. Portado del mockup aprobado
 * final-widget-C.html. Contiene la lógica de perfil que antes vivía en el
 * Sidebar: imagen de perfil, modales (Configuración / Ayuda) y cierre de sesión.
 */
function UserMenu({ username, isSuperuser, onLogout }) {
  const [open, setOpen] = useState(false);
  const [profileImageUrl, setProfileImageUrl] = useState(null);
  const [showProfileSettings, setShowProfileSettings] = useState(false);
  const [showHelpSupport, setShowHelpSupport] = useState(false);

  // Estado de la animación de transición (usada por el cierre de sesión).
  const [showTransition, setShowTransition] = useState(false);
  const [transitionType, setTransitionType] = useState('info');
  const [transitionMessage, setTransitionMessage] = useState('');

  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  // Si el menú se abrió por teclado se enfoca la primera opción.
  const focusFirstRef = useRef(false);

  // Timeouts registrados para limpiarlos al desmontar (evita setState sobre
  // un componente desmontado si el usuario cierra sesión en medio de la animación).
  const timeoutsRef = useRef([]);
  useEffect(() => () => { timeoutsRef.current.forEach(clearTimeout); }, []);
  const scheduleTimeout = (fn, ms) => { timeoutsRef.current.push(setTimeout(fn, ms)); };

  const rol = isSuperuser ? 'Administrador' : 'Usuario Aliado';

  const getInitials = (name) => {
    if (!name) return 'G';
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
    return name.charAt(0).toUpperCase();
  };
  const initials = getInitials(username);

  // Cargar la imagen de perfil (misma lógica que tenía el Sidebar).
  const loadProfileImage = useCallback(async () => {
    try {
      const response = await fetch(buildApiUrl('/auth/profile-image/'), {
        headers: {
          'Authorization': `Token ${localStorage.getItem('authToken')}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setProfileImageUrl(data.profile_image_url);
      } else if (response.status === 404) {
        setProfileImageUrl(null);
      } else {
        console.error('Error cargando imagen de perfil:', response.status);
      }
    } catch (error) {
      console.error('Error cargando imagen de perfil:', error);
    }
  }, []);

  useEffect(() => {
    if (username) {
      loadProfileImage();
    }
  }, [username, loadProfileImage]);

  const closeMenu = useCallback((returnFocus) => {
    setOpen(false);
    if (returnFocus && triggerRef.current) {
      triggerRef.current.focus();
    }
  }, []);

  const openMenu = (focusFirst) => {
    focusFirstRef.current = !!focusFirst;
    setOpen(true);
  };

  // Al abrir: cerrar por click-fuera y, si procede, enfocar la primera opción.
  useEffect(() => {
    if (!open) return undefined;

    if (focusFirstRef.current && menuRef.current) {
      const first = menuRef.current.querySelector('.u-item');
      if (first) first.focus();
    }

    const onOutside = (e) => {
      if (
        menuRef.current && !menuRef.current.contains(e.target) &&
        triggerRef.current && !triggerRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onOutside, true);
    return () => document.removeEventListener('mousedown', onOutside, true);
  }, [open]);

  const menuItems = () =>
    menuRef.current ? Array.prototype.slice.call(menuRef.current.querySelectorAll('.u-item')) : [];

  const onMenuKeyDown = (e) => {
    const list = menuItems();
    const i = list.indexOf(document.activeElement);
    if (e.key === 'Escape') { e.preventDefault(); closeMenu(true); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); (list[i + 1] || list[0])?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); (list[i - 1] || list[list.length - 1])?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); list[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); list[list.length - 1]?.focus(); }
    else if (e.key === 'Tab') { setOpen(false); }
  };

  const onTriggerKeyDown = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      openMenu(true);
    }
  };

  const showTransitionAnimation = (type = 'info', message = '', duration = 2000) => {
    setTransitionType(type);
    setTransitionMessage(message);
    setShowTransition(true);
    scheduleTimeout(() => setShowTransition(false), duration);
  };

  const openProfileSettings = () => {
    setShowProfileSettings(true);
    closeMenu(false);
  };

  const openHelpSupport = () => {
    setShowHelpSupport(true);
    closeMenu(false);
  };

  const handleProfileImageUpdate = () => {
    loadProfileImage();
  };

  const handleLogoutClick = async () => {
    closeMenu(false);
    try {
      showTransitionAnimation('logout', 'Cerrando sesión...', 2000);

      const authToken = localStorage.getItem('authToken');
      if (authToken) {
        // fetch normal para no disparar la animación de carga de fetchWithAuth
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

      scheduleTimeout(() => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('isSuperuser');
        onLogout();
      }, 1500);
    } catch (error) {
      console.error('Error durante logout:', error);
      showTransitionAnimation('error', 'Error al cerrar sesión, pero se cerrará localmente', 2000);
      scheduleTimeout(() => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('username');
        localStorage.removeItem('isSuperuser');
        onLogout();
      }, 2000);
    }
  };

  const displayName = username || 'Invitado';

  const avatar = (
    <span className="u-ava" aria-hidden="true">
      {profileImageUrl ? (
        <img
          className="u-ava__img"
          src={profileImageUrl}
          alt=""
          onError={() => setProfileImageUrl(null)}
        />
      ) : (
        initials
      )}
      <span className="u-ava__dot" />
    </span>
  );

  return (
    <>
      <div className="u-float">
        <button
          ref={triggerRef}
          className="u-chip"
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls="user-menu-panel"
          onClick={() => (open ? closeMenu(false) : openMenu(false))}
          onKeyDown={onTriggerKeyDown}
        >
          {avatar}
          <span className="u-idn">
            <span className="u-idn__name">{displayName}</span>
            <span className="u-chiprole">
              {isSuperuser && <IconShield size={10} />}
              {rol}
            </span>
          </span>
          <IconChevronDown className="u-chev" size={15} />
          <span className="u-sr">
            {displayName}, {rol}. {open ? 'Cerrar' : 'Abrir'} menú de usuario
          </span>
        </button>

        <div
          ref={menuRef}
          className={open ? 'u-menu is-anim' : 'u-menu'}
          id="user-menu-panel"
          role="menu"
          aria-label={`Menú de usuario de ${displayName}`}
          hidden={!open}
          onKeyDown={onMenuKeyDown}
        >
          <div className="u-menu__head">
            {avatar}
            <span className="u-menu__id">
              <span className="u-menu__name">{displayName}</span>
              <span className="u-menu__role">
                {isSuperuser && <IconShield size={10} />}
                {rol}
              </span>
            </span>
          </div>

          <ul className="u-list">
            <li>
              <button className="u-item" type="button" role="menuitem" onClick={openProfileSettings}>
                <IconSettings size={17} />
                <span className="u-lbl">Configuración</span>
                <IconChevronRight className="u-go" size={14} />
              </button>
            </li>
            <li>
              <button className="u-item" type="button" role="menuitem" onClick={openHelpSupport}>
                <IconHelpCircle size={17} />
                <span className="u-lbl">Ayuda y Soporte</span>
                <IconChevronRight className="u-go" size={14} />
              </button>
            </li>
          </ul>

          <hr className="u-sep" aria-hidden="true" />

          <ul className="u-list">
            <li>
              <button
                className="u-item u-item--danger"
                type="button"
                role="menuitem"
                onClick={handleLogoutClick}
              >
                <IconLogOut size={17} />
                <span className="u-lbl">Cerrar Sesión</span>
              </button>
            </li>
          </ul>

          <div className="u-menu__foot">
            <b>SIVE</b>
            <span className="u-dot-sep" />
            Universidad de Nariño
          </div>
        </div>
      </div>

      <TransitionOverlay
        show={showTransition}
        type={transitionType}
        message={transitionMessage}
      />

      {showProfileSettings && (
        <ProfileSettings
          username={username}
          isSuperuser={isSuperuser}
          onClose={() => setShowProfileSettings(false)}
          onProfileImageUpdate={handleProfileImageUpdate}
        />
      )}

      {showHelpSupport && (
        <HelpSupport onClose={() => setShowHelpSupport(false)} />
      )}
    </>
  );
}

export default UserMenu;
