import { applyStatusToExport } from './ExportReports';

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
