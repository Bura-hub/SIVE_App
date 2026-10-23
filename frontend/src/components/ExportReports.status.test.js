import { applyStatusToExport, displayFileSize } from './ExportReports';

const fila = { id: 't-1', status: 'Pendiente', fileSize: 'Generando...', recordCount: 0 };

test('completado: toma el tamaño y los registros del estado, no de la descarga', () => {
  const r = applyStatusToExport(fila, { status: 'completed', file_size: '1.5 KB', record_count: 31 });
  expect(r).toEqual({ ...fila, status: 'Completado', fileSize: '1.5 KB', recordCount: 31 });
});

test('fallido: marca el error', () => {
  const r = applyStatusToExport(fila, { status: 'failed', error: 'x' });
  expect(r.status).toBe('Fallido');
  expect(r.fileSize).toBe('Error');
});

test('pendiente y en proceso se reflejan en la fila', () => {
  expect(applyStatusToExport(fila, { status: 'pending' }).status).toBe('Pendiente');
  expect(applyStatusToExport(fila, { status: 'processing' }).status).toBe('Procesando');
});

// Los reportes guardados antes de la coma decimal conservan «1.5 KB»: la tabla los muestra con coma.
test('el tamaño de un reporte se muestra con coma decimal', () => {
  expect(displayFileSize('1.5 KB')).toBe('1,5 KB');
  expect(displayFileSize('411,3 KB')).toBe('411,3 KB');
  expect(displayFileSize('Generando...')).toBe('Generando...');
  expect(displayFileSize(undefined)).toBe('');
});
