/**
 * Home.js — Pestaña «Inicio» (presentación del proyecto MTE / SIVE).
 *
 * Port fiel del <main> del mockup aprobado (híbrido A + C):
 *   hero (C) + franja de cifras (hc-stat) + «qué es SIVE» (#proyecto) +
 *   índice de módulos + glosario/sedes + bloque institucional (hc-inst).
 *
 * Los estilos viven en index.css (clases c-* y hc-*). Este componente solo
 * aporta el marcado y el cableado de navegación.
 *
 * Integración de layout: se monta dentro del <main className="... p-8 ..."> de
 * App.js. La clase `home-bleed` (margin:-2rem) anula ese padding para que el
 * hero y las franjas de sección lleguen a todo el ancho (full-bleed), mientras
 * el contenido interno recupera su aire lateral vía .c-wrap / .hc-wrap.
 *
 * Props (de commonProps en App.js):
 *   - navigateTo(page): cambia de vista dentro de la app.
 *   - isSuperuser: si es false, oculta los módulos restringidos (Datos
 *     Externos y Exportar Reportes), igual que el Sidebar.
 */
import React from 'react';

// Icono flecha reutilizado en las filas del índice de módulos.
const ArrowIcon = () => (
  <svg
    className="c-arrow"
    width="18"
    height="18"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

function Home({ navigateTo, isSuperuser }) {
  // Definición de los módulos del índice. `restricted` marca los que solo
  // se muestran a administradores (coherente con el gate del Sidebar).
  const modules = [
    {
      page: 'dashboard',
      color: '#2563eb',
      name: 'Dashboard',
      sub: 'Panorama mensual',
      icon: (
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 17V9m4 8V5m4 12v-6M3 21h18" />
        </svg>
      ),
      desc: (
        <>
          Resumen mensual de <b>consumo, generación y balance</b> energético, acompañado de las variables
          climáticas del periodo.
        </>
      ),
    },
    {
      page: 'electricalDetails',
      color: '#16a34a',
      name: 'Medidores',
      sub: 'Demanda eléctrica',
      icon: (
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      desc: (
        <>
          <b>Energía importada</b> de la red, demanda pico, factor de carga y factor de potencia por sede.
        </>
      ),
    },
    {
      page: 'inverterDetails',
      color: '#dc2626',
      name: 'Inversores',
      sub: 'Generación FV',
      icon: (
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="M7 12h2l1 2 2-4 1 2h2" />
        </svg>
      ),
      desc: (
        <>
          <b>Generación fotovoltaica</b>, potencia máxima, factor de potencia y desbalance de los inversores
          solares.
        </>
      ),
    },
    {
      page: 'weatherDetails',
      color: '#ea580c',
      name: 'Estaciones',
      sub: 'Recurso y clima',
      icon: (
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"
          />
        </svg>
      ),
      desc: (
        <>
          <b>Irradiancia y HSP</b>, temperatura, viento (rosa de vientos) y precipitación desde las estaciones
          meteorológicas.
        </>
      ),
    },
    {
      page: 'externalEnergy',
      color: '#0d9488',
      name: 'Datos Externos',
      sub: 'Mercado XM',
      restricted: true,
      icon: (
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M21 12a9 9 0 11-18 0 9 9 0 0118 0zM3.6 9h16.8M3.6 15h16.8M12 3a15 15 0 010 18a15 15 0 010-18z"
          />
        </svg>
      ),
      desc: (
        <>
          Mercado eléctrico <b>XM</b>: precios de bolsa, ahorros, demanda del sistema y emisiones asociadas.
        </>
      ),
    },
    {
      page: 'exportReports',
      color: '#7c3aed',
      name: 'Exportar Reportes',
      sub: 'Entregables',
      restricted: true,
      icon: (
        <svg fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24" aria-hidden="true">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5 5-5M12 15V3"
          />
        </svg>
      ),
      desc: (
        <>
          Informes en <b>PDF, Excel y CSV</b> con resumen ejecutivo, listos para presentar a los agentes del
          proyecto.
        </>
      ),
    },
  ];

  // Permite activar las filas de módulo (divs) también con teclado.
  const handleRowKey = (event, page) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      navigateTo(page);
    }
  };

  return (
    <article className="c-doc home-bleed">
      {/* ============ HERO (C) + franja de cifras ============ */}
      <header className="hc-hero">
        <div className="hc-wrap">
          <div className="hc-hero__grid">
            <div className="hc-hero__copy">
              <span className="hc-eyebrow">
                <span className="tick"></span>Proyecto MTE · Universidad de Nariño
              </span>
              <h1>
                SI<span>V</span>E
              </h1>
              <p className="hc-sub">Sistema de Visualización Energético</p>
              <p className="hc-lema">
                Transparencia energética para un futuro descentralizado. Datos históricos e indicadores de
                consumo, generación y clima, de la fuente a la lectura.
              </p>
              <div className="hc-cta">
                <button type="button" className="hc-btn pri" onClick={() => navigateTo('dashboard')}>
                  Ir al Dashboard
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6l6 6-6 6" />
                  </svg>
                </button>
                <a className="hc-btn gho" href="#proyecto">
                  Conocer el proyecto
                </a>
              </div>
            </div>

            {/* Ilustración vectorial: sol + arreglo fotovoltaico en capas */}
            <div className="hc-art" aria-hidden="true">
              <svg viewBox="0 0 520 452" role="img">
                <defs>
                  <radialGradient id="cSun" cx="42%" cy="38%" r="65%">
                    <stop offset="0%" stopColor="#fff6dc" />
                    <stop offset="42%" stopColor="#f5b942" />
                    <stop offset="100%" stopColor="#e08a24" />
                  </radialGradient>
                  <radialGradient id="cGlow" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="rgba(245,185,66,.55)" />
                    <stop offset="60%" stopColor="rgba(245,185,66,.12)" />
                    <stop offset="100%" stopColor="rgba(245,185,66,0)" />
                  </radialGradient>
                  <linearGradient id="cPanelF" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#4c63d8" />
                    <stop offset="100%" stopColor="#28347f" />
                  </linearGradient>
                  <linearGradient id="cPanelB" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#33409a" />
                    <stop offset="100%" stopColor="#1c2560" />
                  </linearGradient>
                  <linearGradient id="cRay" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ffe4a0" />
                    <stop offset="100%" stopColor="rgba(245,185,66,.15)" />
                  </linearGradient>
                </defs>

                {/* halo */}
                <circle cx="352" cy="150" r="150" fill="url(#cGlow)" />
                {/* órbitas tenues (capas de profundidad) */}
                <g fill="none" stroke="rgba(255,255,255,.16)">
                  <ellipse cx="352" cy="150" rx="118" ry="118" />
                  <ellipse cx="352" cy="150" rx="150" ry="150" stroke="rgba(255,255,255,.09)" />
                </g>

                {/* rayos: 8 largos + 8 cortos */}
                <g stroke="url(#cRay)" strokeWidth="5" strokeLinecap="round" className="cRays">
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(0 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(45 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(90 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(135 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(180 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(225 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(270 352 150)" />
                  <line x1="352" y1="86" x2="352" y2="60" transform="rotate(315 352 150)" />
                </g>
                <g stroke="rgba(255,228,160,.55)" strokeWidth="3.4" strokeLinecap="round" className="cRays2">
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(22.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(67.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(112.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(157.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(202.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(247.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(292.5 352 150)" />
                  <line x1="352" y1="88" x2="352" y2="74" transform="rotate(337.5 352 150)" />
                </g>

                {/* sol */}
                <circle cx="352" cy="150" r="52" fill="url(#cSun)" />
                <circle cx="352" cy="150" r="52" fill="none" stroke="rgba(255,255,255,.35)" strokeWidth="1.5" />
                <path
                  d="M330 128a30 30 0 0 1 40 6"
                  fill="none"
                  stroke="rgba(255,255,255,.5)"
                  strokeWidth="3"
                  strokeLinecap="round"
                />

                {/* arcos de energía sol -> arreglo */}
                <g fill="none" strokeLinecap="round" opacity=".9">
                  <path
                    d="M300 188 C 240 250, 175 250, 150 316"
                    stroke="rgba(245,185,66,.55)"
                    strokeWidth="2"
                    strokeDasharray="2 8"
                  />
                  <path
                    d="M338 202 C 300 280, 260 300, 236 336"
                    stroke="rgba(255,255,255,.4)"
                    strokeWidth="1.6"
                    strokeDasharray="2 8"
                  />
                </g>
                <circle cx="150" cy="316" r="3.5" fill="#f5b942" />
                <circle cx="236" cy="336" r="3" fill="#ffe4a0" />

                {/* arreglo FV posterior (capa de fondo) */}
                <g>
                  <polygon
                    points="300,286 452,268 470,318 316,338"
                    fill="url(#cPanelB)"
                    stroke="rgba(255,255,255,.14)"
                    strokeWidth="1.5"
                  />
                  <g stroke="rgba(255,255,255,.13)" strokeWidth="1">
                    <line x1="338" y1="282" x2="354" y2="333" />
                    <line x1="376" y1="277" x2="393" y2="329" />
                    <line x1="414" y1="272" x2="432" y2="324" />
                    <line x1="308" y1="308" x2="462" y2="290" />
                  </g>
                  <line x1="385" y1="333" x2="385" y2="356" stroke="#1c2560" strokeWidth="4" />
                </g>

                {/* arreglo FV frontal (capa principal) */}
                <g>
                  <polygon
                    points="86,318 300,292 324,368 100,392"
                    fill="url(#cPanelF)"
                    stroke="rgba(245,185,66,.55)"
                    strokeWidth="2"
                  />
                  <line x1="86" y1="318" x2="300" y2="292" stroke="#f7c65f" strokeWidth="2.4" />
                  <g stroke="rgba(255,255,255,.18)" strokeWidth="1.1">
                    <line x1="139" y1="311" x2="157" y2="386" />
                    <line x1="192" y1="305" x2="212" y2="380" />
                    <line x1="245" y1="298" x2="266" y2="374" />
                    <line x1="98" y1="342" x2="315" y2="317" />
                  </g>
                  <line x1="150" y1="382" x2="150" y2="412" stroke="#28347f" strokeWidth="5" />
                  <line x1="262" y1="368" x2="262" y2="398" stroke="#28347f" strokeWidth="5" />
                  <ellipse cx="205" cy="418" rx="120" ry="12" fill="rgba(9,12,48,.35)" />
                </g>
              </svg>
            </div>
          </div>
        </div>

        {/* franja de cifras (hc-stat de C) */}
        <div className="hc-strip">
          <div className="hc-stat">
            <b>
              <em>05</em> sedes
            </b>
            <span>Monitoreadas en Pasto, Nariño</span>
          </div>
          <div className="hc-stat">
            <b>
              <em>06</em> módulos
            </b>
            <span>Analítica de energía y clima</span>
          </div>
          <div className="hc-stat">
            <b>
              SCADA <em>+</em> XM
            </b>
            <span>Datos locales y mercado eléctrico</span>
          </div>
        </div>
      </header>

      {/* ============ abstract: qué es SIVE / proyecto MTE (A) ============ */}
      <section className="c-block c-block--white" id="proyecto">
        <div className="c-wrap">
          <div className="c-abstract">
            <div>
              <span className="c-kick">Qué es SIVE</span>
              <p className="lead">
                Un <b>observatorio del pulso energético</b> de la región: reúne datos históricos e indicadores
                de consumo y generación junto a las variables climáticas que los explican, y los presenta de
                forma <span className="hl">comparable y auditable</span>.
              </p>
              <p className="body">
                La información llega desde el conector <b>SCADA</b> que sincroniza la medición local de cada
                sede, y desde el mercado eléctrico colombiano <b>XM</b>, que aporta precios, demanda y
                emisiones del sistema. Todo se consolida en un único marco de lectura.
              </p>
            </div>
            <aside className="c-mte">
              <div className="cap">
                <i></i>El proyecto MTE
              </div>
              <div className="bd">
                <p className="q">
                  Desarrollo de un modelo transaccional de energía no convencional de múltiples agentes para el
                  departamento de Nariño
                </p>
                <p>
                  Pilota un mecanismo de intercambio de energía eléctrica que incorpora Fuentes No
                  Convencionales de Energía (FNCE), articulando a los agentes que consumen y generan dentro de
                  una misma red.
                </p>
                <div className="tags">
                  <span className="c-tag">Múltiples agentes</span>
                  <span className="c-tag">
                    Registro SIGP <b>89530</b>
                  </span>
                  <span className="c-tag">Nariño · FNCE</span>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>

      {/* ============ module index (A) ============ */}
      <section className="c-block c-block--paper">
        <div className="c-wrap">
          <div className="c-shead">
            <div>
              <span className="c-kick b">La plataforma</span>
              <h2 className="c-htitle">Seis módulos, una lectura integral</h2>
            </div>
            <p className="aside">
              Cada módulo conserva el color con el que vive en el menú lateral, para orientarte sin fricción
              entre secciones.
            </p>
          </div>

          <div className="c-index">
            <div className="head" role="presentation">
              <span></span>
              <span>Módulo</span>
              <span>Qué analiza</span>
              <span></span>
            </div>

            {modules
              .filter((mod) => !mod.restricted || isSuperuser)
              .map((mod) => (
                <div
                  key={mod.page}
                  className="c-row"
                  role="button"
                  tabIndex={0}
                  aria-label={mod.name}
                  style={{ '--c': mod.color, cursor: 'pointer' }}
                  onClick={() => navigateTo(mod.page)}
                  onKeyDown={(event) => handleRowKey(event, mod.page)}
                >
                  <span className="c-ico">{mod.icon}</span>
                  <span className="c-mod">
                    <span className="name">{mod.name}</span>
                    <span className="sub">{mod.sub}</span>
                  </span>
                  <span className="c-desc">{mod.desc}</span>
                  <ArrowIcon />
                </div>
              ))}
          </div>
        </div>
      </section>

      {/* ============ glosario + sedes (A) ============ */}
      <section className="c-block c-block--white">
        <div className="c-wrap">
          <div className="c-split">
            <div>
              <div className="c-sub2">
                <h3>Conceptos clave</h3>
                <span className="rule"></span>
              </div>
              <dl className="c-gloss">
                <div className="term">
                  <dt>FNCE</dt>
                  <dd>
                    Fuentes No Convencionales de Energía: renovables como la <b>solar, eólica o biomasa</b>.
                  </dd>
                </div>
                <div className="term">
                  <dt>Prosumidor</dt>
                  <dd>
                    Usuario que <b>consume y a la vez genera</b>, inyectando sus excedentes a la red.
                  </dd>
                </div>
                <div className="term">
                  <dt>Energía transactiva</dt>
                  <dd>
                    Mecanismos económicos y de control que <b>equilibran oferta y demanda</b> usando el precio
                    como señal.
                  </dd>
                </div>
                <div className="term">
                  <dt>Microrred</dt>
                  <dd>
                    Red de distribución de baja tensión con recursos distribuidos; opera{' '}
                    <b>conectada o en isla</b>.
                  </dd>
                </div>
              </dl>
            </div>

            <div>
              <div className="c-sub2">
                <h3>Sedes monitoreadas</h3>
                <span className="rule"></span>
              </div>
              <ul className="c-sedes">
                <li style={{ '--c': '#2563eb' }}>
                  <span className="mk"></span>
                  <span>
                    <span className="nm">Universidad de Nariño</span>
                    <span className="role">Universidad pública · proponente del proyecto</span>
                  </span>
                </li>
                <li style={{ '--c': '#16a34a' }}>
                  <span className="mk"></span>
                  <span>
                    <span className="nm">Universidad CESMAG</span>
                    <span className="role">Universidad privada</span>
                  </span>
                </li>
                <li style={{ '--c': '#0d9488' }}>
                  <span className="mk"></span>
                  <span>
                    <span className="nm">Universidad Cooperativa de Colombia</span>
                    <span className="role">Sede Pasto</span>
                  </span>
                </li>
                <li style={{ '--c': '#7c3aed' }}>
                  <span className="mk"></span>
                  <span>
                    <span className="nm">Universidad Mariana</span>
                    <span className="role">Universidad privada</span>
                  </span>
                </li>
                <li style={{ '--c': '#ea580c' }}>
                  <span className="mk"></span>
                  <span>
                    <span className="nm">Hospital Universitario Departamental de Nariño</span>
                    <span className="role">Hospital universitario de referencia</span>
                  </span>
                </li>
              </ul>
              <p className="c-note">
                Las cinco instituciones cuentan con generación FV y medición inteligente en Pasto, y conforman
                la red de agentes del modelo transaccional.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ============ INSTITUCIONAL (C) ============ */}
      <footer className="hc-inst">
        <div className="hc-wrap hc-sec">
          <span className="hc-kicker">Quién lo hace posible</span>
          <h2 className="hc-h2">Investigación pública, energía de la región</h2>

          <div className="hc-icols">
            <div className="hc-icol">
              <h4>Desarrollo</h4>
              <div className="big">GIIEE</div>
              <p className="sm">
                Grupo de Investigación en Ingeniería Eléctrica y Electrónica. Dpto. de Ingeniería Electrónica,
                Universidad de Nariño.
              </p>
            </div>
            <div className="hc-icol">
              <h4>Investigador principal</h4>
              <div className="big">Wilson Achicanoy, Ph.D.</div>
              <p className="sm">
                <a href="mailto:wilachic@udenar.edu.co">wilachic@udenar.edu.co</a>
              </p>
            </div>
            <div className="hc-icol hc-fund">
              <h4>Financiación</h4>
              <div className="big">Sistema General de Regalías</div>
              <p className="sm">
                CTeI ambiental · Registro SIGP <b>89530</b>.<br />
                Proponente: Universidad de Nariño.
              </p>
            </div>
            <div className="hc-icol">
              <h4>Instituciones monitoreadas</h4>
              <ul className="hc-orgs">
                <li>Universidad de Nariño</li>
                <li>Universidad CESMAG</li>
                <li>Universidad Cooperativa de Colombia · sede Pasto</li>
                <li>Universidad Mariana</li>
                <li>Hospital Universitario Departamental de Nariño</li>
              </ul>
            </div>
          </div>

          <div className="hc-close">
            <p className="lm">
              <span>Transparencia energética</span> para un futuro descentralizado — cinco sedes con generación
              FV y medición inteligente en Pasto.
            </p>
            <div className="sig">
              <svg width="22" height="22" viewBox="0 0 34 34" aria-hidden="true">
                <circle cx="17" cy="17" r="7.5" fill="#f5b942" />
                <g stroke="#f5b942" strokeWidth="2.4" strokeLinecap="round">
                  <line x1="17" y1="1.5" x2="17" y2="6" />
                  <line x1="17" y1="28" x2="17" y2="32.5" />
                  <line x1="1.5" y1="17" x2="6" y2="17" />
                  <line x1="28" y1="17" x2="32.5" y2="17" />
                  <line x1="5.8" y1="5.8" x2="9" y2="9" />
                  <line x1="25" y1="25" x2="28.2" y2="28.2" />
                  <line x1="28.2" y1="5.8" x2="25" y2="9" />
                  <line x1="9" y1="25" x2="5.8" y2="28.2" />
                </g>
              </svg>
              SIVE · Universidad de Nariño
            </div>
          </div>
        </div>
      </footer>
    </article>
  );
}

export default Home;
