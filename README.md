# 🏭 Sistema de Boteo - Medición de Productividad en Maquila

Sistema de alta velocidad para medir la productividad individual de operarios en líneas de producción de confección. Diseñado para manejar miles de transacciones por hora con una interfaz de menos de 1 segundo de interacción.

## 📋 Características

- ✅ **Registro instantáneo de ciclos** (< 1 segundo)
- ⏸️ **Control de pausas** con seguimiento de tiempo
- 📊 **Cálculo automático de rendimiento** (Excelente/Normal/Lento)
- 🎯 **Alertas visuales en tiempo real**
- 📈 **Dashboard de métricas** por operario
- 🔄 **Alta concurrencia** - Maneja miles de requests/hora
- 📱 **Interfaz responsive** optimizada para tablets

## 🏗️ Arquitectura

```
┌─────────────────┐
│   Frontend      │  ← Interfaz de botones grandes
│   (HTML/JS)     │     Feedback visual instantáneo
└────────┬────────┘
         │
         │ HTTP REST
         │
┌────────▼────────┐
│   Backend API   │  ← FastAPI con lógica de cálculo
│   (Python)      │     Validación de datos
└────────┬────────┘
         │
         │ SQL
         │
┌────────▼────────┐
│   PostgreSQL    │  ← Base de datos optimizada
│   (Database)    │     Índices para alto volumen
└─────────────────┘
```

## 🚀 Instalación Rápida

### Requisitos Previos

- Python 3.9+
- PostgreSQL 12+
- Node.js (opcional, para servir el frontend)

### Paso 1: Configurar Base de Datos

```bash
# Crear base de datos
createdb boteo_db

# Ejecutar script de inicialización
psql -d boteo_db -f backend/init_db.sql
```

### Paso 2: Instalar Dependencias del Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate
# En Mac/Linux:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### Paso 3: Configurar Variables de Entorno

```bash
# Copiar el archivo de ejemplo
cp .env.example .env

# Editar .env con tus credenciales de PostgreSQL
nano .env
```

### Paso 4: Iniciar el Backend

```bash
# Desde el directorio backend
python main.py

# O con uvicorn directamente
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

El backend estará disponible en: `http://localhost:8000`

### Paso 5: Abrir el Frontend

Simplemente abre el archivo `frontend/index.html` en tu navegador, o sirve el frontend con un servidor HTTP:

```bash
# Con Python
cd frontend
python -m http.server 3000

# Luego abre: http://localhost:3000
```

## 📡 Endpoints de la API

### 1. POST `/api/ciclo` - Registrar Ciclo Terminado

**Request:**
```json
{
  "id_operario": 3582
}
```

**Response:**
```json
{
  "id_registro": 1234,
  "tiempo_ciclo_s": 12.5,
  "promedio_5_ciclos": 12.8,
  "estado": "Excelente",
  "mensaje": "Ciclo registrado. Estado: Excelente (Promedio: 12.8s)",
  "ciclos_completados_hoy": 45
}
```

### 2. POST `/api/pausa` - Registrar Pausa

**Request (INICIO):**
```json
{
  "id_operario": 3582,
  "accion": "INICIO",
  "motivo": "Baño"
}
```

**Request (FIN):**
```json
{
  "id_operario": 3582,
  "accion": "FIN"
}
```

**Response:**
```json
{
  "id_pausa": 567,
  "mensaje": "Pausa finalizada. Duración: 600s (10min)",
  "duracion_s": 600
}
```

### 3. GET `/api/metricas/{id_operario}` - Obtener Métricas

**Response:**
```json
{
  "id_operario": 3582,
  "nombre": "María González",
  "tarea_actual": "Coser Manga Derecha",
  "tiempo_estandar_s": 13.0,
  "ciclos_hoy": 45,
  "promedio_dia": 12.8,
  "promedio_ultimos_5": 12.5,
  "estado_actual": "Excelente",
  "en_pausa": false,
  "tiempo_pausa_actual_s": null,
  "eficiencia_porcentaje": 101.6
}
```

## 🎯 Lógica de Alertas

El sistema calcula el estado basado en el **promedio de los últimos 5 ciclos**:

| Estado | Criterio | Color | Acción |
|--------|----------|-------|--------|
| **🎉 Excelente** | ≤ 11.5 segundos | Verde | Reconocimiento/Bono |
| **👍 Normal** | 11.5 - 16.0 segundos | Azul | Continuar normalmente |
| **⚠️ Lento** | ≥ 16.0 segundos | Rojo | Supervisión/Apoyo |

### Valores Configurables (por tarea):

```sql
-- Ejemplo: Tarea "Coser Manga Derecha"
tiempo_estandar_s = 13.0    -- Meta objetivo
umbral_excelente_s = 11.5   -- Límite superior para "Excelente"
umbral_lento_s = 16.0       -- Límite inferior para "Lento"
```

## 💾 Esquema de Base de Datos

### Tablas Principales

#### `Operarios`
```sql
- id_operario (PK)
- nombre
- linea_produccion
- estacion
- activo
```

#### `Tareas`
```sql
- id_tarea (PK)
- nombre_tarea
- tiempo_estandar_s
- umbral_excelente_s
- umbral_lento_s
```

#### `Registros_Ciclos`
```sql
- id_registro (PK, BIGSERIAL)
- id_operario (FK)
- id_tarea (FK)
- marca_tiempo
- tiempo_ciclo_s (calculado)
- promedio_5_ciclos (calculado)
- estado ('Excelente'/'Normal'/'Lento')
- fecha_registro
```

#### `Registros_Pausas`
```sql
- id_pausa (PK, BIGSERIAL)
- id_operario (FK)
- hora_inicio_pausa
- hora_fin_pausa
- duracion_s (calculado)
- motivo
- finalizada
```

## 🎨 Interfaz de Usuario

### Pantalla Principal del Operario

```
┌──────────────────────────────────────┐
│     🏭 Sistema de Boteo              │
├──────────────────────────────────────┤
│  María González                      │
│  ID: 3582 | Línea A - Estación 1    │
│  Tarea: Coser Manga Derecha         │
├──────────────────────────────────────┤
│  Ciclos Hoy: 45    Promedio: 12.8s  │
│  Meta: 13.0s       Eficiencia: 102% │
├──────────────────────────────────────┤
│  🎉 ¡EXCELENTE! Promedio: 12.8s     │
├──────────────────────────────────────┤
│                                      │
│      [ ✓ TERMINADO ]                │
│                                      │
│      [ ⏸ PAUSA ]                    │
│                                      │
└──────────────────────────────────────┘
```

### Atajos de Teclado

- **ESPACIO**: Registrar ciclo terminado
- **P**: Toggle pausa

## 🔧 Configuración Avanzada

### Optimización para Alto Volumen

```python
# En producción, considera usar un pool de conexiones
from psycopg2 import pool

connection_pool = pool.SimpleConnectionPool(
    minconn=10,
    maxconn=100,
    **DB_CONFIG
)
```

### Índices de Base de Datos

El sistema incluye índices optimizados:

```sql
-- Índice compuesto para consultas frecuentes
CREATE INDEX idx_registros_operario_tiempo 
ON Registros_Ciclos(id_operario, marca_tiempo DESC);

-- Índice para filtros por fecha
CREATE INDEX idx_registros_fecha 
ON Registros_Ciclos(fecha_registro);
```

### Configuración de CORS

Por defecto, el backend acepta requests desde cualquier origen. En producción, limita esto:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tu-dominio.com"],  # Solo tu dominio
    allow_credentials=True,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
```

## 📊 Consultas Útiles

### Ver resumen del día de un operario

```sql
SELECT * FROM obtener_resumen_dia(3582);
```

### Ver operarios con rendimiento bajo

```sql
SELECT 
    o.nombre,
    AVG(rc.tiempo_ciclo_s) as promedio_dia,
    COUNT(*) as ciclos
FROM Registros_Ciclos rc
JOIN Operarios o ON rc.id_operario = o.id_operario
WHERE rc.fecha_registro = CURRENT_DATE
  AND rc.tiempo_ciclo_s IS NOT NULL
GROUP BY o.id_operario, o.nombre
HAVING AVG(rc.tiempo_ciclo_s) >= 16.0
ORDER BY promedio_dia DESC;
```

### Ver pausas excesivas

```sql
SELECT 
    o.nombre,
    COUNT(*) as total_pausas,
    SUM(rp.duracion_s) / 60 as minutos_pausa
FROM Registros_Pausas rp
JOIN Operarios o ON rp.id_operario = o.id_operario
WHERE rp.fecha_registro = CURRENT_DATE
  AND rp.finalizada = TRUE
GROUP BY o.id_operario, o.nombre
HAVING SUM(rp.duracion_s) > 3600  -- Más de 1 hora
ORDER BY minutos_pausa DESC;
```

## 🧪 Testing

### Probar el Backend con curl

```bash
# Registrar un ciclo
curl -X POST http://localhost:8000/api/ciclo \
  -H "Content-Type: application/json" \
  -d '{"id_operario": 3582}'

# Iniciar pausa
curl -X POST http://localhost:8000/api/pausa \
  -H "Content-Type: application/json" \
  -d '{"id_operario": 3582, "accion": "INICIO", "motivo": "Baño"}'

# Obtener métricas
curl http://localhost:8000/api/metricas/3582
```

### Simulación de Carga

```python
import asyncio
import aiohttp

async def simular_operario(session, id_operario):
    for _ in range(100):
        async with session.post(
            'http://localhost:8000/api/ciclo',
            json={'id_operario': id_operario}
        ) as response:
            print(f"Operario {id_operario}: {response.status}")
        await asyncio.sleep(13)  # Simular tiempo de ciclo

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [simular_operario(session, i) for i in range(3582, 3592)]
        await asyncio.gather(*tasks)

asyncio.run(main())
```

## 🐛 Troubleshooting

### Error: "No module named 'psycopg2'"

```bash
pip install psycopg2-binary
```

### Error: "Connection refused" en PostgreSQL

Verifica que PostgreSQL esté corriendo:
```bash
sudo systemctl status postgresql
```

### Frontend no se conecta al Backend

Verifica CORS y que ambos servicios estén en los puertos correctos:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`

## 📈 Escalabilidad

### Para 1000+ operarios simultáneos:

1. **Usar un balanceador de carga** (Nginx/HAProxy)
2. **Multiple instancias del backend** con Gunicorn:
   ```bash
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```
3. **Connection pooling** en PostgreSQL
4. **Caché de Redis** para métricas frecuentes
5. **Particionamiento de tablas** por fecha

## 📝 Próximos Pasos / Mejoras

- [ ] Agregar autenticación JWT
- [ ] Implementar WebSockets para actualizaciones en tiempo real
- [ ] Dashboard de supervisión general
- [ ] Reportes PDF diarios/semanales
- [ ] Integración con sistemas de nómina
- [ ] App móvil nativa
- [ ] Modo offline con sincronización


---

**Desarrollado para mejorar la productividad y el bienestar de los operarios en la industria de confección** 🏭✨