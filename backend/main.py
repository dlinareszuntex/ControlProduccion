from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
from decimal import Decimal

app = FastAPI(title="Sistema de Boteo - API de Productividad")

# Configuración CORS para permitir requests desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la base de datos
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "boteo_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "port": os.getenv("DB_PORT", "5432")
}

# Context manager para conexiones a la base de datos
@contextmanager
def get_db_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# Modelos Pydantic para validación de datos
class CicloRequest(BaseModel):
    id_operario: int = Field(..., description="ID del operario", example=3582)

class PausaRequest(BaseModel):
    id_operario: int = Field(..., description="ID del operario", example=3582)
    accion: Literal["INICIO", "FIN"] = Field(..., description="Tipo de acción")
    motivo: Optional[str] = Field(None, description="Motivo de la pausa (solo en INICIO)")

class CicloResponse(BaseModel):
    id_registro: int
    tiempo_ciclo_s: Optional[float]
    promedio_5_ciclos: Optional[float]
    estado: str
    mensaje: str
    ciclos_completados_hoy: int

class MetricasResponse(BaseModel):
    id_operario: int
    nombre: str
    tarea_actual: str
    tiempo_estandar_s: float
    ciclos_hoy: int
    promedio_dia: Optional[float]
    promedio_ultimos_5: Optional[float]
    estado_actual: str
    en_pausa: bool
    tiempo_pausa_actual_s: Optional[int]
    eficiencia_porcentaje: Optional[float]

class PausaResponse(BaseModel):
    id_pausa: int
    mensaje: str
    duracion_s: Optional[int]

# Modelos para endpoints de historial y reportes
class PausasPorMotivo(BaseModel):
    motivo: str
    total_pausas: int
    tiempo_total_min: float
    promedio_duracion_min: float
    operarios_afectados: int
    lineas_afectadas: list[str]

class HistorialDiaResponse(BaseModel):
    fecha: str
    ciclos_totales: int
    promedio_tiempo: Optional[float]
    ciclos_excelentes: int
    ciclos_normales: int
    ciclos_lentos: int
    total_pausas: int
    tiempo_total_pausas_min: float
    pausas_por_motivo: dict[str, int]
    eficiencia_porcentaje: Optional[float]
    horas_trabajadas: float

class ResumenPeriodoResponse(BaseModel):
    promedio_ciclos_dia: float
    promedio_eficiencia: Optional[float]
    dias_excelentes: int
    dias_normales: int
    dias_lentos: int

class HistorialCompletoResponse(BaseModel):
    operario: str
    id_operario: int
    dias: list[HistorialDiaResponse]
    resumen_periodo: ResumenPeriodoResponse

class OperarioDashboardDetalle(BaseModel):
    id_operario: int
    nombre: str
    ciclos: int
    promedio: Optional[float]
    estado: str
    eficiencia: Optional[float]
    pausas: int
    tiempo_pausas_min: float

class ProblemaDetectado(BaseModel):
    tipo: str
    operario: str
    detalle: str

class ResumenGeneral(BaseModel):
    operarios_activos: int
    operarios_excelentes: int
    operarios_lentos: int
    ciclos_totales: int
    eficiencia_promedio: Optional[float]

class DashboardResumenResponse(BaseModel):
    fecha: str
    resumen_general: ResumenGeneral
    operarios: list[OperarioDashboardDetalle]
    problemas_detectados: list[ProblemaDetectado]

class Recomendacion(BaseModel):
    mensaje: str

class ReportePausasResponse(BaseModel):
    periodo: str
    pausas_por_motivo: list[PausasPorMotivo]
    recomendaciones: list[Recomendacion]

class CuelloBotella(BaseModel):
    operario: str
    estacion: str
    linea: str
    tiempo_promedio: float
    tiempo_esperado: float
    retraso_porcentaje: float
    impacto_linea: str

class ReporteCuelloBotellaResponse(BaseModel):
    fecha: str
    cuellos_botella_detectados: list[CuelloBotella]

class OperarioComparativo(BaseModel):
    id_operario: int
    nombre: str
    ciclos_totales: int
    promedio_tiempo: Optional[float]
    eficiencia: Optional[float]
    dias_trabajados: int
    estado_general: str

class ReporteComparativoResponse(BaseModel):
    periodo: str
    operarios: list[OperarioComparativo]

# ============================================================================
# ENDPOINT PRINCIPAL: POST /api/ciclo (Botón Verde - TERMINADO)
# ============================================================================
@app.post("/api/ciclo", response_model=CicloResponse, status_code=status.HTTP_201_CREATED)
async def registrar_ciclo(ciclo: CicloRequest):
    """
    Registra la finalización de un ciclo de trabajo.
    
    Este endpoint:
    1. Registra el timestamp actual
    2. Calcula el tiempo del ciclo (diferencia con el anterior)
    3. Calcula el promedio de los últimos 5 ciclos
    4. Determina el estado (Normal/Lento/Excelente)
    5. Retorna el estado al frontend
    """
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 1. Verificar que el operario existe y obtener su tarea actual
            cursor.execute("""
                SELECT ot.id_tarea, t.tiempo_estandar_s, t.umbral_excelente_s, t.umbral_lento_s
                FROM Operario_Tarea ot
                JOIN Tareas t ON ot.id_tarea = t.id_tarea
                WHERE ot.id_operario = %s AND ot.activa = TRUE
                LIMIT 1
            """, (ciclo.id_operario,))
            
            tarea_info = cursor.fetchone()
            
            if not tarea_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Operario {ciclo.id_operario} no encontrado o sin tarea asignada"
                )
            
            id_tarea = tarea_info['id_tarea']
            tiempo_estandar = float(tarea_info['tiempo_estandar_s'])
            umbral_excelente = float(tarea_info['umbral_excelente_s'])
            umbral_lento = float(tarea_info['umbral_lento_s'])
            
            # 2. Obtener el último ciclo registrado para calcular el tiempo transcurrido
            cursor.execute("""
                SELECT marca_tiempo
                FROM Registros_Ciclos
                WHERE id_operario = %s
                ORDER BY marca_tiempo DESC
                LIMIT 1
            """, (ciclo.id_operario,))
            
            ultimo_ciclo = cursor.fetchone()
            marca_tiempo_actual = datetime.now()
            tiempo_ciclo_s = None
            
            if ultimo_ciclo:
                tiempo_bruto = marca_tiempo_actual - ultimo_ciclo['marca_tiempo']
                tiempo_bruto_s = tiempo_bruto.total_seconds()
                
                # 2.1. Obtener pausas finalizadas que ocurrieron entre el último ciclo y el actual
                cursor.execute("""
                    SELECT COALESCE(SUM(duracion_s), 0) as tiempo_total_pausas
                    FROM Registros_Pausas
                    WHERE id_operario = %s
                      AND finalizada = TRUE
                      AND hora_inicio_pausa > %s
                      AND hora_inicio_pausa < %s
                """, (ciclo.id_operario, ultimo_ciclo['marca_tiempo'], marca_tiempo_actual))
                
                resultado_pausas = cursor.fetchone()
                tiempo_total_pausas_s = resultado_pausas['tiempo_total_pausas'] or 0
                
                # 2.2. Verificar si hay pausas sin finalizar en ese periodo
                cursor.execute("""
                    SELECT COUNT(*) as pausas_sin_finalizar
                    FROM Registros_Pausas
                    WHERE id_operario = %s
                      AND finalizada = FALSE
                      AND hora_inicio_pausa > %s
                      AND hora_inicio_pausa < %s
                """, (ciclo.id_operario, ultimo_ciclo['marca_tiempo'], marca_tiempo_actual))
                
                pausas_sin_finalizar = cursor.fetchone()['pausas_sin_finalizar']
                
                # 2.3. Calcular tiempo real excluyendo pausas
                if pausas_sin_finalizar > 0:
                    # Si hay pausas sin finalizar, marcar como NULL
                    tiempo_ciclo_s = None
                else:
                    tiempo_ciclo_s = tiempo_bruto_s - tiempo_total_pausas_s
                    
                    # Validación: ignorar ciclos muy largos o negativos (probablemente hubo un error)
                    if tiempo_ciclo_s > 300 or tiempo_ciclo_s < 0:  # Más de 5 minutos o negativo
                        tiempo_ciclo_s = None
            
            # 3. Obtener los últimos 4 ciclos para calcular el promedio de 5
            cursor.execute("""
                SELECT tiempo_ciclo_s
                FROM Registros_Ciclos
                WHERE id_operario = %s 
                  AND tiempo_ciclo_s IS NOT NULL
                  AND fecha_registro = CURRENT_DATE
                ORDER BY marca_tiempo DESC
                LIMIT 4
            """, (ciclo.id_operario,))
            
            ultimos_ciclos = cursor.fetchall()
            promedio_5_ciclos = None
            
            if tiempo_ciclo_s is not None:
                # Incluir el ciclo actual en el cálculo
                tiempos = [tiempo_ciclo_s] + [float(c['tiempo_ciclo_s']) for c in ultimos_ciclos]
                promedio_5_ciclos = sum(tiempos) / len(tiempos)
            
            # 4. Determinar el estado basado en el promedio
            estado = "Normal"
            if promedio_5_ciclos is not None:
                if promedio_5_ciclos <= umbral_excelente:
                    estado = "Excelente"
                elif promedio_5_ciclos >= umbral_lento:
                    estado = "Lento"
            
            # 5. Insertar el registro en la base de datos
            # Asegurar que fecha_registro se establece correctamente
            fecha_registro_actual = marca_tiempo_actual.date()
            cursor.execute("""
                INSERT INTO Registros_Ciclos 
                (id_operario, id_tarea, marca_tiempo, tiempo_ciclo_s, promedio_5_ciclos, estado, fecha_registro)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id_registro
            """, (
                ciclo.id_operario,
                id_tarea,
                marca_tiempo_actual,
                tiempo_ciclo_s,
                promedio_5_ciclos,
                estado,
                fecha_registro_actual
            ))
            
            id_registro = cursor.fetchone()['id_registro']
            
            # 6. Contar ciclos completados hoy
            cursor.execute("""
                SELECT COUNT(*) as total
                FROM Registros_Ciclos
                WHERE id_operario = %s AND fecha_registro = CURRENT_DATE
            """, (ciclo.id_operario,))
            
            ciclos_hoy = cursor.fetchone()['total']
            
            # 7. Preparar mensaje de respuesta
            mensaje = f"Ciclo registrado. Estado: {estado}"
            if promedio_5_ciclos:
                mensaje += f" (Promedio: {promedio_5_ciclos:.1f}s)"
            
            return CicloResponse(
                id_registro=id_registro,
                tiempo_ciclo_s=tiempo_ciclo_s,
                promedio_5_ciclos=promedio_5_ciclos,
                estado=estado,
                mensaje=mensaje,
                ciclos_completados_hoy=ciclos_hoy
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar ciclo: {str(e)}"
        )

# ============================================================================
# ENDPOINT: POST /api/pausa (Botón Amarillo - PAUSA)
# ============================================================================
@app.post("/api/pausa", response_model=PausaResponse, status_code=status.HTTP_201_CREATED)
async def registrar_pausa(pausa: PausaRequest):
    """
    Registra el inicio o fin de una pausa.
    
    INICIO: Registra cuando el operario inicia una pausa
    FIN: Calcula la duración y cierra el registro de pausa
    """
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if pausa.accion == "INICIO":
                # Verificar que no hay una pausa abierta
                cursor.execute("""
                    SELECT id_pausa
                    FROM Registros_Pausas
                    WHERE id_operario = %s AND finalizada = FALSE
                """, (pausa.id_operario,))
                
                pausa_abierta = cursor.fetchone()
                
                if pausa_abierta:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Ya existe una pausa activa para este operario"
                    )
                
                # Insertar nueva pausa
                cursor.execute("""
                    INSERT INTO Registros_Pausas 
                    (id_operario, hora_inicio_pausa, motivo, finalizada)
                    VALUES (%s, %s, %s, FALSE)
                    RETURNING id_pausa
                """, (pausa.id_operario, datetime.now(), pausa.motivo))
                
                id_pausa = cursor.fetchone()['id_pausa']
                
                return PausaResponse(
                    id_pausa=id_pausa,
                    mensaje=f"Pausa iniciada: {pausa.motivo or 'Sin motivo'}",
                    duracion_s=None
                )
            
            else:  # accion == "FIN"
                # Buscar la pausa abierta
                cursor.execute("""
                    SELECT id_pausa, hora_inicio_pausa
                    FROM Registros_Pausas
                    WHERE id_operario = %s AND finalizada = FALSE
                    ORDER BY hora_inicio_pausa DESC
                    LIMIT 1
                """, (pausa.id_operario,))
                
                pausa_activa = cursor.fetchone()
                
                if not pausa_activa:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No hay pausas activas para este operario"
                    )
                
                # Calcular duración
                hora_fin = datetime.now()
                duracion = hora_fin - pausa_activa['hora_inicio_pausa']
                duracion_s = int(duracion.total_seconds())
                
                # Actualizar el registro
                cursor.execute("""
                    UPDATE Registros_Pausas
                    SET hora_fin_pausa = %s,
                        duracion_s = %s,
                        finalizada = TRUE
                    WHERE id_pausa = %s
                """, (hora_fin, duracion_s, pausa_activa['id_pausa']))
                
                return PausaResponse(
                    id_pausa=pausa_activa['id_pausa'],
                    mensaje=f"Pausa finalizada. Duración: {duracion_s}s ({duracion_s//60}min)",
                    duracion_s=duracion_s
                )
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al registrar pausa: {str(e)}"
        )

# ============================================================================
# ENDPOINT: GET /api/metricas/{id_operario} (Dashboard de Supervisión)
# ============================================================================
@app.get("/api/metricas/{id_operario}", response_model=MetricasResponse)
async def obtener_metricas(id_operario: int):
    """
    Obtiene las métricas actuales de un operario.
    
    Incluye:
    - Promedio del día
    - Promedio de los últimos 5 ciclos
    - Estado actual
    - Si está en pausa
    - Eficiencia
    """
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener información base del operario
            cursor.execute("""
                SELECT 
                    o.id_operario,
                    o.nombre,
                    t.nombre_tarea,
                    t.tiempo_estandar_s
                FROM Operarios o
                JOIN Operario_Tarea ot ON o.id_operario = ot.id_operario AND ot.activa = TRUE
                JOIN Tareas t ON ot.id_tarea = t.id_tarea
                WHERE o.id_operario = %s
            """, (id_operario,))
            
            operario_info = cursor.fetchone()
            
            if not operario_info:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Operario {id_operario} no encontrado"
                )
            
            # Obtener ciclos del día
            cursor.execute("""
                SELECT COUNT(*) as total,
                       AVG(tiempo_ciclo_s) as promedio
                FROM Registros_Ciclos
                WHERE id_operario = %s 
                  AND fecha_registro = CURRENT_DATE
                  AND tiempo_ciclo_s IS NOT NULL
            """, (id_operario,))
            
            ciclos_info = cursor.fetchone()
            
            # Obtener últimos 5 ciclos
            cursor.execute("""
                SELECT promedio_5_ciclos, estado
                FROM Registros_Ciclos
                WHERE id_operario = %s
                ORDER BY marca_tiempo DESC
                LIMIT 1
            """, (id_operario,))
            
            ultimo_registro = cursor.fetchone()
            
            # Verificar si está en pausa
            cursor.execute("""
                SELECT id_pausa, hora_inicio_pausa
                FROM Registros_Pausas
                WHERE id_operario = %s AND finalizada = FALSE
            """, (id_operario,))
            
            pausa_activa = cursor.fetchone()
            en_pausa = pausa_activa is not None
            tiempo_pausa_s = None
            
            if en_pausa:
                tiempo_transcurrido = datetime.now() - pausa_activa['hora_inicio_pausa']
                tiempo_pausa_s = int(tiempo_transcurrido.total_seconds())
            
            # Calcular eficiencia
            promedio_dia = float(ciclos_info['promedio']) if ciclos_info['promedio'] else None
            eficiencia = None
            if promedio_dia:
                tiempo_estandar = float(operario_info['tiempo_estandar_s'])
                eficiencia = (tiempo_estandar / promedio_dia) * 100
            
            return MetricasResponse(
                id_operario=operario_info['id_operario'],
                nombre=operario_info['nombre'],
                tarea_actual=operario_info['nombre_tarea'],
                tiempo_estandar_s=float(operario_info['tiempo_estandar_s']),
                ciclos_hoy=ciclos_info['total'],
                promedio_dia=promedio_dia,
                promedio_ultimos_5=float(ultimo_registro['promedio_5_ciclos']) if ultimo_registro and ultimo_registro['promedio_5_ciclos'] else None,
                estado_actual=ultimo_registro['estado'] if ultimo_registro else "Sin datos",
                en_pausa=en_pausa,
                tiempo_pausa_actual_s=tiempo_pausa_s,
                eficiencia_porcentaje=eficiencia
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener métricas: {str(e)}"
        )

# ============================================================================
# ENDPOINTS ADICIONALES
# ============================================================================

class OperarioInfo(BaseModel):
    id_operario: int
    nombre: str
    linea_produccion: str
    estacion: str

class DashboardOperario(BaseModel):
    id_operario: int
    nombre: str
    ciclos_hoy: int
    promedio_dia: Optional[float]
    estado_actual: str
    en_pausa: bool

@app.get("/api/operarios", response_model=list[OperarioInfo])
async def listar_operarios():
    """
    Lista todos los operarios activos para la pantalla de selección
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT id_operario, nombre, linea_produccion, estacion
                FROM Operarios
                WHERE activo = TRUE
                ORDER BY nombre
            """)
            
            operarios = cursor.fetchall()
            
            return [OperarioInfo(**op) for op in operarios]
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al listar operarios: {str(e)}"
        )

@app.get("/api/dashboard", response_model=list[DashboardOperario])
async def obtener_dashboard():
    """
    Obtiene información de todos los operarios para el dashboard IT
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    o.id_operario,
                    o.nombre,
                    COALESCE(COUNT(rc.id_registro), 0) as ciclos_hoy,
                    AVG(rc.tiempo_ciclo_s) as promedio_dia,
                    COALESCE(
                        (SELECT estado FROM Registros_Ciclos 
                         WHERE id_operario = o.id_operario 
                         ORDER BY marca_tiempo DESC LIMIT 1),
                        'Sin datos'
                    ) as estado_actual,
                    EXISTS(
                        SELECT 1 FROM Registros_Pausas 
                        WHERE id_operario = o.id_operario 
                        AND finalizada = FALSE
                    ) as en_pausa
                FROM Operarios o
                LEFT JOIN Registros_Ciclos rc ON o.id_operario = rc.id_operario 
                    AND rc.fecha_registro = CURRENT_DATE
                    AND rc.tiempo_ciclo_s IS NOT NULL
                WHERE o.activo = TRUE
                GROUP BY o.id_operario, o.nombre
                ORDER BY o.nombre
            """)
            
            operarios = cursor.fetchall()
            
            return [DashboardOperario(**op) for op in operarios]
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener dashboard: {str(e)}"
        )

# ============================================================================
# NUEVOS ENDPOINTS DE HISTORIAL Y REPORTES
# ============================================================================

@app.get("/api/metricas/{id_operario}/historial", response_model=HistorialCompletoResponse)
async def obtener_historial_operario(
    id_operario: int,
    fecha_inicio: str,
    fecha_fin: str
):
    """
    Obtiene el historial de métricas de un operario en un rango de fechas.
    
    Parámetros:
    - fecha_inicio: Fecha de inicio en formato YYYY-MM-DD
    - fecha_fin: Fecha de fin en formato YYYY-MM-DD
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Verificar que el operario existe
            cursor.execute("""
                SELECT nombre FROM Operarios WHERE id_operario = %s
            """, (id_operario,))
            
            operario = cursor.fetchone()
            if not operario:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Operario {id_operario} no encontrado"
                )
            
            # Obtener datos por día
            cursor.execute("""
                SELECT 
                    fecha_registro::text as fecha,
                    COUNT(*) as ciclos_totales,
                    AVG(tiempo_ciclo_s) as promedio_tiempo,
                    COUNT(*) FILTER (WHERE estado = 'Excelente') as ciclos_excelentes,
                    COUNT(*) FILTER (WHERE estado = 'Normal') as ciclos_normales,
                    COUNT(*) FILTER (WHERE estado = 'Lento') as ciclos_lentos
                FROM Registros_Ciclos
                WHERE id_operario = %s
                  AND fecha_registro >= %s::date
                  AND fecha_registro <= %s::date
                GROUP BY fecha_registro
                ORDER BY fecha_registro
            """, (id_operario, fecha_inicio, fecha_fin))
            
            dias_ciclos = cursor.fetchall()
            
            # Obtener pausas por día
            cursor.execute("""
                SELECT 
                    fecha_registro::text as fecha,
                    COUNT(*) as total_pausas,
                    COALESCE(SUM(duracion_s), 0) / 60.0 as tiempo_total_pausas_min,
                    motivo,
                    COUNT(*) as pausas_motivo
                FROM Registros_Pausas
                WHERE id_operario = %s
                  AND finalizada = TRUE
                  AND fecha_registro >= %s::date
                  AND fecha_registro <= %s::date
                GROUP BY fecha_registro, motivo
            """, (id_operario, fecha_inicio, fecha_fin))
            
            pausas_por_dia = cursor.fetchall()
            
            # Obtener tiempo estándar para calcular eficiencia
            cursor.execute("""
                SELECT tiempo_estandar_s
                FROM Operario_Tarea ot
                JOIN Tareas t ON ot.id_tarea = t.id_tarea
                WHERE ot.id_operario = %s AND ot.activa = TRUE
                LIMIT 1
            """, (id_operario,))
            
            tarea_info = cursor.fetchone()
            tiempo_estandar = float(tarea_info['tiempo_estandar_s']) if tarea_info else None
            
            # Combinar datos
            dias_dict = {}
            for dia in dias_ciclos:
                fecha = dia['fecha']
                dias_dict[fecha] = HistorialDiaResponse(
                    fecha=fecha,
                    ciclos_totales=dia['ciclos_totales'],
                    promedio_tiempo=float(dia['promedio_tiempo']) if dia['promedio_tiempo'] else None,
                    ciclos_excelentes=dia['ciclos_excelentes'],
                    ciclos_normales=dia['ciclos_normales'],
                    ciclos_lentos=dia['ciclos_lentos'],
                    total_pausas=0,
                    tiempo_total_pausas_min=0.0,
                    pausas_por_motivo={},
                    eficiencia_porcentaje=None,
                    horas_trabajadas=8.0  # Valor por defecto, se puede calcular mejor
                )
            
            # Agregar información de pausas
            for pausa in pausas_por_dia:
                fecha = pausa['fecha']
                if fecha not in dias_dict:
                    continue
                
                dias_dict[fecha].total_pausas += pausa['total_pausas']
                dias_dict[fecha].tiempo_total_pausas_min += pausa['tiempo_total_pausas_min']
                
                motivo = pausa['motivo'] or 'Sin motivo'
                dias_dict[fecha].pausas_por_motivo[motivo] = pausa['pausas_motivo']
            
            # Calcular eficiencia y horas trabajadas
            for dia in dias_dict.values():
                if dia.promedio_tiempo and tiempo_estandar:
                    dia.eficiencia_porcentaje = (tiempo_estandar / dia.promedio_tiempo) * 100
                
                # Calcular horas trabajadas (8 horas - tiempo de pausas)
                dia.horas_trabajadas = max(0, 8.0 - (dia.tiempo_total_pausas_min / 60.0))
            
            # Calcular resumen del periodo
            dias_list = list(dias_dict.values())
            total_dias = len(dias_list)
            
            if total_dias > 0:
                promedio_ciclos = sum(d.ciclos_totales for d in dias_list) / total_dias
                eficiencias = [d.eficiencia_porcentaje for d in dias_list if d.eficiencia_porcentaje]
                promedio_eficiencia = sum(eficiencias) / len(eficiencias) if eficiencias else None
                
                dias_excelentes = sum(1 for d in dias_list if d.eficiencia_porcentaje and d.eficiencia_porcentaje >= 100)
                dias_normales = sum(1 for d in dias_list if d.eficiencia_porcentaje and 80 <= d.eficiencia_porcentaje < 100)
                dias_lentos = sum(1 for d in dias_list if d.eficiencia_porcentaje and d.eficiencia_porcentaje < 80)
            else:
                promedio_ciclos = 0
                promedio_eficiencia = None
                dias_excelentes = 0
                dias_normales = 0
                dias_lentos = 0
            
            return HistorialCompletoResponse(
                operario=operario['nombre'],
                id_operario=id_operario,
                dias=dias_list,
                resumen_periodo=ResumenPeriodoResponse(
                    promedio_ciclos_dia=promedio_ciclos,
                    promedio_eficiencia=promedio_eficiencia,
                    dias_excelentes=dias_excelentes,
                    dias_normales=dias_normales,
                    dias_lentos=dias_lentos
                )
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener historial: {str(e)}"
        )

@app.get("/api/dashboard/resumen", response_model=DashboardResumenResponse)
async def obtener_dashboard_resumen(fecha: str):
    """
    Obtiene el resumen del dashboard IT para una fecha específica.
    
    Parámetros:
    - fecha: Fecha en formato YYYY-MM-DD
    """
    try:
        # Validar formato de fecha
        try:
            datetime.strptime(fecha, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de fecha inválido. Use YYYY-MM-DD. Recibido: {fecha}"
            )
        
        # Log para debug
        print(f"🔍 [DEBUG] Buscando datos para fecha: {fecha}")
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Verificar qué fechas hay en la base de datos
            cursor.execute("""
                SELECT DISTINCT fecha_registro, COUNT(*) as total
                FROM Registros_Ciclos
                GROUP BY fecha_registro
                ORDER BY fecha_registro DESC
                LIMIT 5
            """)
            fechas_disponibles = cursor.fetchall()
            print(f"📅 [DEBUG] Fechas disponibles en BD: {[str(f['fecha_registro']) for f in fechas_disponibles]}")
            
            # Obtener resumen general
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT o.id_operario) as operarios_activos,
                    COUNT(DISTINCT CASE 
                        WHEN (
                            SELECT estado FROM Registros_Ciclos rc
                            WHERE rc.id_operario = o.id_operario
                              AND rc.fecha_registro = %s::date
                            ORDER BY rc.marca_tiempo DESC
                            LIMIT 1
                        ) = 'Excelente' THEN o.id_operario 
                    END) as operarios_excelentes,
                    COUNT(DISTINCT CASE 
                        WHEN (
                            SELECT estado FROM Registros_Ciclos rc
                            WHERE rc.id_operario = o.id_operario
                              AND rc.fecha_registro = %s::date
                            ORDER BY rc.marca_tiempo DESC
                            LIMIT 1
                        ) = 'Lento' THEN o.id_operario 
                    END) as operarios_lentos,
                    COALESCE((
                        SELECT COUNT(*) FROM Registros_Ciclos
                        WHERE fecha_registro = %s::date
                    ), 0) as ciclos_totales
                FROM Operarios o
                WHERE o.activo = TRUE
            """, (fecha, fecha, fecha))
            
            resumen_general = cursor.fetchone()
            
            if not resumen_general:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al obtener resumen general"
                )
            
            # Obtener eficiencia promedio
            cursor.execute("""
                SELECT 
                    AVG(t.tiempo_estandar_s / rc.tiempo_ciclo_s * 100) as eficiencia_promedio
                FROM Registros_Ciclos rc
                JOIN Operario_Tarea ot ON rc.id_operario = ot.id_operario AND ot.activa = TRUE
                JOIN Tareas t ON ot.id_tarea = t.id_tarea
                WHERE rc.fecha_registro = %s::date
                  AND rc.tiempo_ciclo_s IS NOT NULL
            """, (fecha,))
            
            eficiencia_result = cursor.fetchone()
            eficiencia_promedio = float(eficiencia_result['eficiencia_promedio']) if eficiencia_result['eficiencia_promedio'] else None
            
            # Obtener detalle de operarios
            cursor.execute("""
                SELECT 
                    o.id_operario,
                    o.nombre,
                    COALESCE((
                        SELECT COUNT(*) FROM Registros_Ciclos
                        WHERE id_operario = o.id_operario
                          AND fecha_registro = %s::date
                    ), 0) as ciclos,
                    (
                        SELECT AVG(tiempo_ciclo_s) FROM Registros_Ciclos
                        WHERE id_operario = o.id_operario
                          AND fecha_registro = %s::date
                          AND tiempo_ciclo_s IS NOT NULL
                    ) as promedio,
                    COALESCE((
                        SELECT estado FROM Registros_Ciclos
                        WHERE id_operario = o.id_operario
                          AND fecha_registro = %s::date
                        ORDER BY marca_tiempo DESC
                        LIMIT 1
                    ), 'Sin datos') as estado,
                    (
                        SELECT 
                            t.tiempo_estandar_s / AVG(rc2.tiempo_ciclo_s) * 100
                        FROM Registros_Ciclos rc2
                        JOIN Operario_Tarea ot2 ON rc2.id_operario = ot2.id_operario AND ot2.activa = TRUE
                        JOIN Tareas t ON ot2.id_tarea = t.id_tarea
                        WHERE rc2.id_operario = o.id_operario
                          AND rc2.fecha_registro = %s::date
                          AND rc2.tiempo_ciclo_s IS NOT NULL
                        GROUP BY t.tiempo_estandar_s
                    ) as eficiencia,
                    COALESCE((
                        SELECT COUNT(*) FROM Registros_Pausas
                        WHERE id_operario = o.id_operario
                          AND fecha_registro = %s::date
                          AND finalizada = TRUE
                    ), 0) as pausas,
                    COALESCE((
                        SELECT SUM(duracion_s) / 60.0 FROM Registros_Pausas
                        WHERE id_operario = o.id_operario
                          AND fecha_registro = %s::date
                          AND finalizada = TRUE
                    ), 0) as tiempo_pausas_min
                FROM Operarios o
                WHERE o.activo = TRUE
                ORDER BY o.nombre
            """, (fecha, fecha, fecha, fecha, fecha, fecha))
            
            operarios_data = cursor.fetchall()
            
            print(f"👥 [DEBUG] Operarios encontrados: {len(operarios_data)}")
            for op in operarios_data[:3]:  # Mostrar solo los primeros 3 para debug
                print(f"   - {op['nombre']}: {op['ciclos']} ciclos, promedio: {op['promedio']}")
            
            operarios = []
            problemas = []
            
            for op in operarios_data:
                operarios.append(OperarioDashboardDetalle(
                    id_operario=op['id_operario'],
                    nombre=op['nombre'],
                    ciclos=op['ciclos'],
                    promedio=float(op['promedio']) if op['promedio'] else None,
                    estado=op['estado'],
                    eficiencia=float(op['eficiencia']) if op['eficiencia'] else None,
                    pausas=op['pausas'],
                    tiempo_pausas_min=float(op['tiempo_pausas_min'])
                ))
                
                # Detectar problemas
                if op['estado'] == 'Lento' and op['promedio']:
                    tiempo_esperado = 13.0  # Valor por defecto, se puede obtener de la tarea
                    if op['promedio'] > tiempo_esperado:
                        problemas.append(ProblemaDetectado(
                            tipo="Operario Lento",
                            operario=op['nombre'],
                            detalle=f"Promedio de {op['promedio']:.1f}s vs meta de {tiempo_esperado}s"
                        ))
                
                if op['pausas'] > 5:
                    problemas.append(ProblemaDetectado(
                        tipo="Pausas Excesivas",
                        operario=op['nombre'],
                        detalle=f"{op['pausas']} pausas ({op['tiempo_pausas_min']:.0f} min total)"
                    ))
            
            return DashboardResumenResponse(
                fecha=fecha,
                resumen_general=ResumenGeneral(
                    operarios_activos=resumen_general['operarios_activos'] or 0,
                    operarios_excelentes=resumen_general['operarios_excelentes'] or 0,
                    operarios_lentos=resumen_general['operarios_lentos'] or 0,
                    ciclos_totales=resumen_general['ciclos_totales'] or 0,
                    eficiencia_promedio=eficiencia_promedio
                ),
                operarios=operarios,
                problemas_detectados=problemas
            )
            
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"Error al obtener resumen: {str(e)}\n{traceback.format_exc()}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )

@app.get("/api/reportes/pausas", response_model=ReportePausasResponse)
async def obtener_reporte_pausas(fecha_inicio: str, fecha_fin: str):
    """
    Obtiene un análisis de pausas por motivo en un rango de fechas.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    motivo,
                    COUNT(*) as total_pausas,
                    COALESCE(SUM(duracion_s), 0) / 60.0 as tiempo_total_min,
                    COALESCE(AVG(duracion_s), 0) / 60.0 as promedio_duracion_min,
                    COUNT(DISTINCT id_operario) as operarios_afectados,
                    ARRAY_AGG(DISTINCT o.linea_produccion) FILTER (WHERE o.linea_produccion IS NOT NULL) as lineas_afectadas
                FROM Registros_Pausas rp
                JOIN Operarios o ON rp.id_operario = o.id_operario
                WHERE rp.fecha_registro >= %s::date
                  AND rp.fecha_registro <= %s::date
                  AND rp.finalizada = TRUE
                GROUP BY motivo
                ORDER BY total_pausas DESC
            """, (fecha_inicio, fecha_fin))
            
            pausas_data = cursor.fetchall()
            
            pausas_por_motivo = []
            recomendaciones = []
            
            for pausa in pausas_data:
                motivo = pausa['motivo'] or 'Sin motivo'
                lineas = pausa['lineas_afectadas'] or []
                
                pausas_por_motivo.append(PausasPorMotivo(
                    motivo=motivo,
                    total_pausas=pausa['total_pausas'],
                    tiempo_total_min=float(pausa['tiempo_total_min']),
                    promedio_duracion_min=float(pausa['promedio_duracion_min']),
                    operarios_afectados=pausa['operarios_afectados'],
                    lineas_afectadas=list(lineas) if lineas else []
                ))
                
                # Generar recomendaciones
                if motivo == 'Sin Materiales' and pausa['total_pausas'] > 20:
                    recomendaciones.append(Recomendacion(
                        mensaje="Revisar cadena de suministro de materiales"
                    ))
                elif motivo == 'Falla Técnica - Máquina' and pausa['total_pausas'] > 10:
                    lineas_str = ', '.join(lineas) if lineas else 'las líneas afectadas'
                    recomendaciones.append(Recomendacion(
                        mensaje=f"Mantenimiento preventivo en {lineas_str}"
                    ))
            
            return ReportePausasResponse(
                periodo=f"{fecha_inicio} a {fecha_fin}",
                pausas_por_motivo=pausas_por_motivo,
                recomendaciones=recomendaciones
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reporte de pausas: {str(e)}"
        )

@app.get("/api/reportes/cuellos-botella", response_model=ReporteCuelloBotellaResponse)
async def obtener_reporte_cuellos_botella(fecha: str):
    """
    Detecta cuellos de botella (operarios lentos) en una fecha específica.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT 
                    o.id_operario,
                    o.nombre,
                    o.estacion,
                    o.linea_produccion,
                    AVG(rc.tiempo_ciclo_s) as tiempo_promedio,
                    t.tiempo_estandar_s as tiempo_esperado,
                    (AVG(rc.tiempo_ciclo_s) / t.tiempo_estandar_s - 1) * 100 as retraso_porcentaje
                FROM Operarios o
                JOIN Registros_Ciclos rc ON o.id_operario = rc.id_operario
                JOIN Operario_Tarea ot ON o.id_operario = ot.id_operario AND ot.activa = TRUE
                JOIN Tareas t ON ot.id_tarea = t.id_tarea
                WHERE rc.fecha_registro = %s::date
                  AND rc.tiempo_ciclo_s IS NOT NULL
                GROUP BY o.id_operario, o.nombre, o.estacion, o.linea_produccion, t.tiempo_estandar_s
                HAVING AVG(rc.tiempo_ciclo_s) > t.tiempo_estandar_s * 1.1
                ORDER BY retraso_porcentaje DESC
            """, (fecha,))
            
            cuellos_data = cursor.fetchall()
            
            cuellos_botella = []
            for cuello in cuellos_data:
                # Determinar impacto en la línea
                impacto = "Afecta a estaciones siguientes"
                if cuello['estacion']:
                    num_estacion = int(cuello['estacion'].split()[-1]) if cuello['estacion'] else 0
                    if num_estacion > 0:
                        impacto = f"Afecta a {num_estacion} estaciones siguientes"
                
                cuellos_botella.append(CuelloBotella(
                    operario=cuello['nombre'],
                    estacion=cuello['estacion'] or 'N/A',
                    linea=cuello['linea_produccion'] or 'N/A',
                    tiempo_promedio=float(cuello['tiempo_promedio']),
                    tiempo_esperado=float(cuello['tiempo_esperado']),
                    retraso_porcentaje=float(cuello['retraso_porcentaje']),
                    impacto_linea=impacto
                ))
            
            return ReporteCuelloBotellaResponse(
                fecha=fecha,
                cuellos_botella_detectados=cuellos_botella
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reporte de cuellos de botella: {str(e)}"
        )

@app.get("/api/reportes/comparativo", response_model=ReporteComparativoResponse)
async def obtener_reporte_comparativo(
    operarios: str,
    fecha_inicio: str,
    fecha_fin: str
):
    """
    Compara el rendimiento de múltiples operarios en un rango de fechas.
    
    Parámetros:
    - operarios: Lista de IDs separados por comas (ej: "3582,3583,3584")
    - fecha_inicio: Fecha de inicio en formato YYYY-MM-DD
    - fecha_fin: Fecha de fin en formato YYYY-MM-DD
    """
    try:
        operarios_list = [int(id.strip()) for id in operarios.split(',')]
        
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            operarios_comparativo = []
            
            for id_operario in operarios_list:
                # Obtener información del operario
                cursor.execute("""
                    SELECT nombre FROM Operarios WHERE id_operario = %s
                """, (id_operario,))
                
                operario = cursor.fetchone()
                if not operario:
                    continue
                
                # Obtener métricas del periodo
                cursor.execute("""
                    SELECT 
                        COUNT(*) as ciclos_totales,
                        AVG(tiempo_ciclo_s) as promedio_tiempo,
                        COUNT(DISTINCT fecha_registro) as dias_trabajados
                    FROM Registros_Ciclos
                    WHERE id_operario = %s
                      AND fecha_registro >= %s::date
                      AND fecha_registro <= %s::date
                      AND tiempo_ciclo_s IS NOT NULL
                """, (id_operario, fecha_inicio, fecha_fin))
                
                metricas = cursor.fetchone()
                
                # Obtener tiempo estándar y calcular eficiencia
                cursor.execute("""
                    SELECT tiempo_estandar_s
                    FROM Operario_Tarea ot
                    JOIN Tareas t ON ot.id_tarea = t.id_tarea
                    WHERE ot.id_operario = %s AND ot.activa = TRUE
                    LIMIT 1
                """, (id_operario,))
                
                tarea = cursor.fetchone()
                tiempo_estandar = float(tarea['tiempo_estandar_s']) if tarea else None
                
                eficiencia = None
                if metricas['promedio_tiempo'] and tiempo_estandar:
                    eficiencia = (tiempo_estandar / float(metricas['promedio_tiempo'])) * 100
                
                # Determinar estado general
                estado_general = "Sin datos"
                if eficiencia:
                    if eficiencia >= 100:
                        estado_general = "Excelente"
                    elif eficiencia >= 80:
                        estado_general = "Normal"
                    else:
                        estado_general = "Lento"
                
                operarios_comparativo.append(OperarioComparativo(
                    id_operario=id_operario,
                    nombre=operario['nombre'],
                    ciclos_totales=metricas['ciclos_totales'],
                    promedio_tiempo=float(metricas['promedio_tiempo']) if metricas['promedio_tiempo'] else None,
                    eficiencia=eficiencia,
                    dias_trabajados=metricas['dias_trabajados'],
                    estado_general=estado_general
                ))
            
            return ReporteComparativoResponse(
                periodo=f"{fecha_inicio} a {fecha_fin}",
                operarios=operarios_comparativo
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener reporte comparativo: {str(e)}"
        )

@app.get("/")
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "nombre": "Sistema de Boteo - API de Productividad",
        "version": "3.0.0",
        "endpoints": {
            "GET /api/operarios": "Listar operarios activos",
            "POST /api/ciclo": "Registrar finalización de ciclo (excluye pausas)",
            "POST /api/pausa": "Registrar inicio/fin de pausa",
            "GET /api/metricas/{id_operario}": "Obtener métricas del operario",
            "GET /api/metricas/{id_operario}/historial": "Obtener historial de métricas (con filtros de fecha)",
            "GET /api/dashboard": "Dashboard IT con todos los operarios",
            "GET /api/dashboard/resumen": "Dashboard IT con resumen por fecha",
            "GET /api/reportes/pausas": "Análisis de pausas por motivo",
            "GET /api/reportes/cuellos-botella": "Detectar cuellos de botella",
            "GET /api/reportes/comparativo": "Comparar múltiples operarios"
        }
    }

@app.get("/health")
async def health_check():
    """Verificar el estado de la API y la conexión a la base de datos"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/api/debug/fechas")
async def debug_fechas():
    """Endpoint de debug para verificar fechas en la base de datos"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener fechas únicas de ciclos
            cursor.execute("""
                SELECT 
                    fecha_registro,
                    COUNT(*) as total_ciclos,
                    MIN(marca_tiempo) as primer_ciclo,
                    MAX(marca_tiempo) as ultimo_ciclo
                FROM Registros_Ciclos
                GROUP BY fecha_registro
                ORDER BY fecha_registro DESC
                LIMIT 10
            """)
            
            fechas_ciclos = cursor.fetchall()
            
            # Obtener fecha actual del servidor
            cursor.execute("SELECT CURRENT_DATE as fecha_actual, NOW() as timestamp_actual")
            fecha_actual = cursor.fetchone()
            
            return {
                "fecha_actual_servidor": str(fecha_actual['fecha_actual']),
                "timestamp_actual": str(fecha_actual['timestamp_actual']),
                "fechas_con_datos": [
                    {
                        "fecha": str(f['fecha_registro']),
                        "total_ciclos": f['total_ciclos'],
                        "primer_ciclo": str(f['primer_ciclo']),
                        "ultimo_ciclo": str(f['ultimo_ciclo'])
                    }
                    for f in fechas_ciclos
                ]
            }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)