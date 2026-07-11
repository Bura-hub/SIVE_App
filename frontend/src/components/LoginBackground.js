import React from 'react';

/**
 * Fondo vectorial del login (solar / noche).
 *
 * Ilustración 100% SVG + CSS (sin imágenes): sol con ráfaga de rayos que rota,
 * arreglo fotovoltaico en perspectiva y líneas de energía que fluyen hacia el sol.
 * Es puramente decorativo (aria-hidden) y todas las animaciones se apagan con
 * `prefers-reduced-motion`. Los estilos y @keyframes viven en index.css (login-bg__*).
 */
function LoginBackground() {
  return (
    <div className="login-bg" aria-hidden="true">
      {/* Capa base: noche + glow solar cálido */}
      <div className="login-bg__base" />

      {/* Capa vectorial: sol, arreglo FV y líneas de energía */}
      <svg
        className="login-bg__svg"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        focusable="false"
      >
        <defs>
          <radialGradient id="loginSunCore" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ffe9bf" />
            <stop offset="45%" stopColor="#ffdf9e" />
            <stop offset="100%" stopColor="#f5b942" />
          </radialGradient>
          <radialGradient id="loginSunHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(245,185,66,.55)" />
            <stop offset="60%" stopColor="rgba(245,185,66,.14)" />
            <stop offset="100%" stopColor="rgba(245,185,66,0)" />
          </radialGradient>
          <linearGradient id="loginPanelFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0b1122" stopOpacity="0.95" />
            <stop offset="55%" stopColor="#0b1122" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="loginFlowGrad" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor="#38bdf8" />
            <stop offset="70%" stopColor="#7dd3fc" />
            <stop offset="100%" stopColor="#ffd77a" />
          </linearGradient>

          {/* Patrón de celda fotovoltaica: cuadro con busbars */}
          <pattern id="loginCells" width="66" height="66" patternUnits="userSpaceOnUse">
            <rect x="3" y="3" width="60" height="60" rx="7" fill="#1b2c50" stroke="rgba(125,180,255,.28)" strokeWidth="1.2" />
            <line x1="25" y1="6" x2="25" y2="60" stroke="rgba(125,180,255,.22)" strokeWidth="1" />
            <line x1="44" y1="6" x2="44" y2="60" stroke="rgba(125,180,255,.22)" strokeWidth="1" />
            <line x1="6" y1="33" x2="60" y2="33" stroke="rgba(125,180,255,.14)" strokeWidth="1" />
          </pattern>
        </defs>

        {/* SOL: halo + rayos + núcleo (arriba a la derecha) */}
        <g transform="translate(1140 190)">
          <circle className="login-bg__sunglow" r="230" fill="url(#loginSunHalo)" />
          <g className="login-bg__rays">
            <g stroke="#f5b942" strokeWidth="3" strokeLinecap="round" opacity="0.55">
              <line x1="0" y1="-96" x2="0" y2="-150" />
              <line x1="0" y1="96" x2="0" y2="150" />
              <line x1="-96" y1="0" x2="-150" y2="0" />
              <line x1="96" y1="0" x2="150" y2="0" />
              <line x1="-68" y1="-68" x2="-106" y2="-106" />
              <line x1="68" y1="-68" x2="106" y2="-106" />
              <line x1="-68" y1="68" x2="-106" y2="106" />
              <line x1="68" y1="68" x2="106" y2="106" />
            </g>
            <g stroke="#f5b942" strokeWidth="2" strokeLinecap="round" opacity="0.32" transform="rotate(22.5)">
              <line x1="0" y1="-100" x2="0" y2="-138" />
              <line x1="0" y1="100" x2="0" y2="138" />
              <line x1="-100" y1="0" x2="-138" y2="0" />
              <line x1="100" y1="0" x2="138" y2="0" />
              <line x1="-71" y1="-71" x2="-98" y2="-98" />
              <line x1="71" y1="-71" x2="98" y2="-98" />
              <line x1="-71" y1="71" x2="-98" y2="98" />
              <line x1="71" y1="71" x2="98" y2="98" />
            </g>
          </g>
          <circle r="66" fill="url(#loginSunCore)" />
          <circle r="66" fill="none" stroke="rgba(255,255,255,.25)" strokeWidth="1" />
        </g>

        {/* LÍNEAS DE ENERGÍA: fluyen desde los paneles hacia el sol */}
        <g fill="none" stroke="url(#loginFlowGrad)" strokeWidth="2.4" opacity="0.5" strokeLinecap="round">
          <path className="login-bg__flow" d="M 300 720 C 520 620, 760 640, 940 420 S 1080 250, 1120 210" />
          <path className="login-bg__flow login-bg__flow--b" d="M 470 770 C 640 700, 860 700, 1000 470 S 1090 300, 1120 220" />
          <path className="login-bg__flow login-bg__flow--c" d="M 150 690 C 380 660, 620 600, 900 430 S 1070 270, 1118 205" />
        </g>

        {/* ARREGLO FOTOVOLTAICO en perspectiva (abajo) */}
        <g opacity="0.9">
          <g transform="translate(210 700) skewX(-20) rotate(-3)">
            <rect x="0" y="0" width="330" height="150" rx="10" fill="url(#loginCells)" />
            <rect x="0" y="0" width="330" height="150" rx="10" fill="none" stroke="rgba(148,197,255,.35)" strokeWidth="2" />
            <rect className="login-bg__shine" x="0" y="0" width="330" height="150" rx="10" fill="#ffd77a" opacity="0.12" />
          </g>
          <g transform="translate(600 730) skewX(-20) rotate(-3)">
            <rect x="0" y="0" width="300" height="140" rx="10" fill="url(#loginCells)" />
            <rect x="0" y="0" width="300" height="140" rx="10" fill="none" stroke="rgba(148,197,255,.3)" strokeWidth="2" />
            <rect className="login-bg__shine login-bg__shine--b" x="0" y="0" width="300" height="140" rx="10" fill="#ffd77a" opacity="0.10" />
          </g>
          <g transform="translate(980 745) skewX(-20) rotate(-3)" opacity="0.6">
            <rect x="0" y="0" width="230" height="110" rx="8" fill="url(#loginCells)" />
            <rect x="0" y="0" width="230" height="110" rx="8" fill="none" stroke="rgba(148,197,255,.25)" strokeWidth="1.5" />
          </g>
        </g>

        {/* Desvanecido superior de los paneles para fundir con el fondo */}
        <rect x="0" y="640" width="1440" height="260" fill="url(#loginPanelFade)" />
      </svg>

      {/* Capa viñeta: mejora la legibilidad del card */}
      <div className="login-bg__vignette" />
    </div>
  );
}

export default LoginBackground;
