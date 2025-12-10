-- ============================================================================
-- Script de Optimización de Base de Datos
-- Agregar índices adicionales para mejorar el rendimiento de las nuevas consultas
-- ============================================================================

-- Índice para consultas de pausas por rango de tiempo (usado en cálculo de tiempo_ciclo)
CREATE INDEX IF NOT EXISTS idx_pausas_operario_tiempo 
ON Registros_Pausas(id_operario, hora_inicio_pausa, finalizada);

-- Índice para consultas de pausas por motivo y fecha (usado en reportes)
CREATE INDEX IF NOT EXISTS idx_pausas_motivo_fecha 
ON Registros_Pausas(motivo, fecha_registro, finalizada);

-- Índice para consultas de ciclos por operario y fecha (ya existe, pero verificamos)
-- CREATE INDEX IF NOT EXISTS idx_registros_operario_fecha ON Registros_Ciclos(id_operario, fecha_registro);

-- Índice compuesto para consultas de estado de operarios
CREATE INDEX IF NOT EXISTS idx_ciclos_operario_fecha_estado 
ON Registros_Ciclos(id_operario, fecha_registro, estado);

COMMIT;

