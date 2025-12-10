-- ============================================================================
-- Script de Inicialización de Base de Datos
-- Sistema de Boteo - Medición de Productividad
-- ============================================================================

-- Limpiar tablas existentes (solo para desarrollo/testing)
DROP TABLE IF EXISTS Registros_Pausas CASCADE;
DROP TABLE IF EXISTS Registros_Ciclos CASCADE;
DROP TABLE IF EXISTS Operario_Tarea CASCADE;
DROP TABLE IF EXISTS Tareas CASCADE;
DROP TABLE IF EXISTS Operarios CASCADE;
DROP VIEW IF EXISTS Vista_Metricas_Operario;

-- ============================================================================
-- CREACIÓN DE TABLAS
-- ============================================================================

-- Tabla de Operarios
CREATE TABLE Operarios (
    id_operario INTEGER PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    linea_produccion VARCHAR(50),
    estacion VARCHAR(50),
    activo BOOLEAN DEFAULT TRUE,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabla de Tareas/Operaciones
CREATE TABLE Tareas (
    id_tarea INTEGER PRIMARY KEY,
    nombre_tarea VARCHAR(100) NOT NULL,
    descripcion TEXT,
    tiempo_estandar_s DECIMAL(6,2) NOT NULL,
    umbral_excelente_s DECIMAL(6,2) NOT NULL,
    umbral_lento_s DECIMAL(6,2) NOT NULL,
    activa BOOLEAN DEFAULT TRUE
);

-- Tabla de Asignación Operario-Tarea
CREATE TABLE Operario_Tarea (
    id_operario INTEGER REFERENCES Operarios(id_operario),
    id_tarea INTEGER REFERENCES Tareas(id_tarea),
    fecha_asignacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    activa BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (id_operario, id_tarea)
);

-- Tabla de Registros de Ciclos (OPTIMIZADA para alto volumen)
CREATE TABLE Registros_Ciclos (
    id_registro BIGSERIAL PRIMARY KEY,
    id_operario INTEGER NOT NULL REFERENCES Operarios(id_operario),
    id_tarea INTEGER NOT NULL REFERENCES Tareas(id_tarea),
    marca_tiempo TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tiempo_ciclo_s DECIMAL(6,2),
    promedio_5_ciclos DECIMAL(6,2),
    estado VARCHAR(20),
    turno VARCHAR(20),
    fecha_registro DATE DEFAULT CURRENT_DATE
);

-- Índices para optimizar consultas de alto volumen
CREATE INDEX idx_registros_operario_tiempo ON Registros_Ciclos(id_operario, marca_tiempo DESC);
CREATE INDEX idx_registros_fecha ON Registros_Ciclos(fecha_registro);
CREATE INDEX idx_registros_operario_fecha ON Registros_Ciclos(id_operario, fecha_registro);

-- Tabla de Registros de Pausas
CREATE TABLE Registros_Pausas (
    id_pausa BIGSERIAL PRIMARY KEY,
    id_operario INTEGER NOT NULL REFERENCES Operarios(id_operario),
    hora_inicio_pausa TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    hora_fin_pausa TIMESTAMP,
    duracion_s INTEGER,
    motivo VARCHAR(50),
    turno VARCHAR(20),
    fecha_registro DATE DEFAULT CURRENT_DATE,
    finalizada BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_pausas_operario ON Registros_Pausas(id_operario, finalizada);
CREATE INDEX idx_pausas_fecha ON Registros_Pausas(fecha_registro);

-- Vista para métricas en tiempo real
CREATE VIEW Vista_Metricas_Operario AS
SELECT 
    o.id_operario,
    o.nombre,
    o.linea_produccion,
    o.estacion,
    ot.id_tarea,
    t.nombre_tarea,
    t.tiempo_estandar_s,
    t.umbral_excelente_s,
    t.umbral_lento_s,
    (SELECT COUNT(*) FROM Registros_Ciclos rc 
     WHERE rc.id_operario = o.id_operario 
     AND rc.fecha_registro = CURRENT_DATE) as ciclos_hoy,
    (SELECT AVG(tiempo_ciclo_s) FROM Registros_Ciclos rc 
     WHERE rc.id_operario = o.id_operario 
     AND rc.fecha_registro = CURRENT_DATE
     AND rc.tiempo_ciclo_s IS NOT NULL) as promedio_dia,
    (SELECT estado FROM Registros_Ciclos rc 
     WHERE rc.id_operario = o.id_operario 
     ORDER BY marca_tiempo DESC LIMIT 1) as estado_actual,
    (SELECT COUNT(*) FROM Registros_Pausas rp
     WHERE rp.id_operario = o.id_operario
     AND rp.finalizada = FALSE) as en_pausa
FROM Operarios o
JOIN Operario_Tarea ot ON o.id_operario = ot.id_operario AND ot.activa = TRUE
JOIN Tareas t ON ot.id_tarea = t.id_tarea
WHERE o.activo = TRUE;

-- ============================================================================
-- DATOS DE PRUEBA
-- ============================================================================

-- Insertar Tareas
INSERT INTO Tareas (id_tarea, nombre_tarea, descripcion, tiempo_estandar_s, umbral_excelente_s, umbral_lento_s) VALUES
(1, 'Coser Manga Derecha', 'Costura de manga derecha en camisa', 13.0, 11.5, 16.0),
(2, 'Coser Manga Izquierda', 'Costura de manga izquierda en camisa', 13.0, 11.5, 16.0),
(3, 'Pegar Botones', 'Colocación de botones en parte frontal', 18.0, 15.0, 22.0),
(4, 'Hacer Ojales', 'Creación de ojales para botones', 20.0, 17.0, 24.0),
(5, 'Coser Cuello', 'Costura de cuello a cuerpo de camisa', 25.0, 22.0, 30.0);

-- Insertar Operarios
INSERT INTO Operarios (id_operario, nombre, linea_produccion, estacion, activo) VALUES
(3582, 'María González', 'Línea A', 'Estación 1', TRUE),
(3583, 'Juan Pérez', 'Línea A', 'Estación 2', TRUE),
(3584, 'Ana Martínez', 'Línea A', 'Estación 3', TRUE),
(3585, 'Carlos López', 'Línea B', 'Estación 1', TRUE),
(3586, 'Rosa Hernández', 'Línea B', 'Estación 2', TRUE),
(3587, 'Pedro Ramírez', 'Línea B', 'Estación 3', TRUE),
(3588, 'Laura Torres', 'Línea C', 'Estación 1', TRUE),
(3589, 'Miguel Flores', 'Línea C', 'Estación 2', TRUE),
(3590, 'Carmen Díaz', 'Línea C', 'Estación 3', TRUE),
(3591, 'José Morales', 'Línea A', 'Estación 4', TRUE);

-- Asignar Tareas a Operarios
INSERT INTO Operario_Tarea (id_operario, id_tarea, activa) VALUES
(3582, 1, TRUE),
(3583, 2, TRUE),
(3584, 3, TRUE),
(3585, 4, TRUE),
(3586, 5, TRUE),
(3587, 1, TRUE),
(3588, 2, TRUE),
(3589, 3, TRUE),
(3590, 4, TRUE),
(3591, 5, TRUE);

-- ============================================================================
-- DATOS DE SIMULACIÓN (Ciclos de ejemplo)
-- ============================================================================

-- Generar algunos ciclos de ejemplo para el día actual
-- Operario 3582 (María) - Rendimiento Excelente
INSERT INTO Registros_Ciclos (id_operario, id_tarea, marca_tiempo, tiempo_ciclo_s, promedio_5_ciclos, estado)
VALUES 
    (3582, 1, NOW() - INTERVAL '60 minutes', NULL, NULL, 'Normal'),
    (3582, 1, NOW() - INTERVAL '59 minutes', 11.2, 11.2, 'Excelente'),
    (3582, 1, NOW() - INTERVAL '58 minutes', 10.8, 11.0, 'Excelente'),
    (3582, 1, NOW() - INTERVAL '57 minutes', 11.5, 11.17, 'Excelente'),
    (3582, 1, NOW() - INTERVAL '56 minutes', 10.9, 11.1, 'Excelente'),
    (3582, 1, NOW() - INTERVAL '55 minutes', 11.3, 11.14, 'Excelente');

-- Operario 3583 (Juan) - Rendimiento Normal
INSERT INTO Registros_Ciclos (id_operario, id_tarea, marca_tiempo, tiempo_ciclo_s, promedio_5_ciclos, estado)
VALUES 
    (3583, 2, NOW() - INTERVAL '60 minutes', NULL, NULL, 'Normal'),
    (3583, 2, NOW() - INTERVAL '59 minutes', 13.5, 13.5, 'Normal'),
    (3583, 2, NOW() - INTERVAL '58 minutes', 12.8, 13.15, 'Normal'),
    (3583, 2, NOW() - INTERVAL '57 minutes', 14.2, 13.5, 'Normal'),
    (3583, 2, NOW() - INTERVAL '56 minutes', 13.1, 13.4, 'Normal'),
    (3583, 2, NOW() - INTERVAL '55 minutes', 13.8, 13.48, 'Normal');

-- Operario 3584 (Ana) - Rendimiento Lento (necesita atención)
INSERT INTO Registros_Ciclos (id_operario, id_tarea, marca_tiempo, tiempo_ciclo_s, promedio_5_ciclos, estado)
VALUES 
    (3584, 3, NOW() - INTERVAL '60 minutes', NULL, NULL, 'Normal'),
    (3584, 3, NOW() - INTERVAL '59 minutes', 17.2, 17.2, 'Lento'),
    (3584, 3, NOW() - INTERVAL '58 minutes', 16.8, 17.0, 'Lento'),
    (3584, 3, NOW() - INTERVAL '57 minutes', 17.5, 17.17, 'Lento'),
    (3584, 3, NOW() - INTERVAL '56 minutes', 16.3, 16.95, 'Lento'),
    (3584, 3, NOW() - INTERVAL '55 minutes', 17.1, 16.98, 'Lento');

-- Pausas de ejemplo
INSERT INTO Registros_Pausas (id_operario, hora_inicio_pausa, hora_fin_pausa, duracion_s, motivo, finalizada)
VALUES 
    (3582, NOW() - INTERVAL '45 minutes', NOW() - INTERVAL '35 minutes', 600, 'Baño', TRUE),
    (3583, NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '20 minutes', 600, 'Descanso', TRUE);

-- ============================================================================
-- FUNCIONES ÚTILES
-- ============================================================================

-- Función para obtener el resumen del día de un operario
CREATE OR REPLACE FUNCTION obtener_resumen_dia(p_id_operario INTEGER)
RETURNS TABLE (
    total_ciclos INTEGER,
    promedio_tiempo DECIMAL,
    ciclos_excelentes INTEGER,
    ciclos_normales INTEGER,
    ciclos_lentos INTEGER,
    total_pausas INTEGER,
    tiempo_total_pausas INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*)::INTEGER 
         FROM Registros_Ciclos 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE) as total_ciclos,
        
        (SELECT AVG(tiempo_ciclo_s)
         FROM Registros_Ciclos 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE
         AND tiempo_ciclo_s IS NOT NULL) as promedio_tiempo,
        
        (SELECT COUNT(*)::INTEGER 
         FROM Registros_Ciclos 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE
         AND estado = 'Excelente') as ciclos_excelentes,
        
        (SELECT COUNT(*)::INTEGER 
         FROM Registros_Ciclos 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE
         AND estado = 'Normal') as ciclos_normales,
        
        (SELECT COUNT(*)::INTEGER 
         FROM Registros_Ciclos 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE
         AND estado = 'Lento') as ciclos_lentos,
        
        (SELECT COUNT(*)::INTEGER 
         FROM Registros_Pausas 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE
         AND finalizada = TRUE) as total_pausas,
        
        (SELECT COALESCE(SUM(duracion_s), 0)::INTEGER 
         FROM Registros_Pausas 
         WHERE id_operario = p_id_operario 
         AND fecha_registro = CURRENT_DATE
         AND finalizada = TRUE) as tiempo_total_pausas;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- CONSULTAS ÚTILES PARA VERIFICACIÓN
-- ============================================================================

-- Ver todos los operarios con sus tareas asignadas
-- SELECT * FROM Vista_Metricas_Operario;

-- Ver resumen del día de un operario específico
-- SELECT * FROM obtener_resumen_dia(3582);

-- Ver últimos 10 ciclos de un operario
-- SELECT * FROM Registros_Ciclos WHERE id_operario = 3582 ORDER BY marca_tiempo DESC LIMIT 10;

-- Ver pausas activas
-- SELECT * FROM Registros_Pausas WHERE finalizada = FALSE;

COMMIT;