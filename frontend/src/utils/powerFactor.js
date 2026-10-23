// Clasificación del factor de potencia con los umbrales de su ficha (utils/kpiInfo.js):
// ≥0,95 óptimo; de 0,90 a 0,95 bueno; <0,90 mejorable (umbral regulatorio en Colombia).
export const powerFactorLevel = (value) => {
  const v = Number(value) || 0;
  if (v >= 0.95) return 'optimo';
  if (v >= 0.90) return 'bueno';
  return 'mejorable';
};

export const POWER_FACTOR_LABEL = { optimo: 'Óptimo', bueno: 'Bueno', mejorable: 'Mejorable' };
export const POWER_FACTOR_DOT = { optimo: 'bg-green-500', bueno: 'bg-yellow-500', mejorable: 'bg-red-500' };
