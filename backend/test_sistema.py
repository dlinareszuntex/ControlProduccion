#!/usr/bin/env python3
"""
Script de Testing para el Sistema de Boteo
Simula el comportamiento de operarios en una línea de producción
"""

import requests
import time
import random
from datetime import datetime
from typing import List, Dict

# Configuración
API_URL = "http://localhost:8000"
OPERARIOS = [3582, 3583, 3584]  # IDs de operarios a simular
CICLOS_POR_OPERARIO = 10

# Colores para output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text: str):
    """Imprime un encabezado decorado"""
    print(f"\n{'='*60}")
    print(f"{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{'='*60}\n")

def print_success(text: str):
    """Imprime mensaje de éxito"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_warning(text: str):
    """Imprime mensaje de advertencia"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text: str):
    """Imprime mensaje de error"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def verificar_conexion() -> bool:
    """Verifica que el backend esté disponible"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("Conexión con el backend establecida")
            return True
        else:
            print_error(f"Backend respondió con código {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"No se pudo conectar al backend: {e}")
        return False

def obtener_metricas(id_operario: int) -> Dict:
    """Obtiene las métricas actuales de un operario"""
    try:
        response = requests.get(f"{API_URL}/api/metricas/{id_operario}")
        if response.status_code == 200:
            return response.json()
        else:
            print_error(f"Error al obtener métricas: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        print_error(f"Error de conexión: {e}")
        return {}

def registrar_ciclo(id_operario: int) -> Dict:
    """Registra un ciclo completado"""
    try:
        response = requests.post(
            f"{API_URL}/api/ciclo",
            json={"id_operario": id_operario},
            timeout=5
        )
        
        if response.status_code == 201:
            data = response.json()
            return data
        else:
            print_error(f"Error al registrar ciclo: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        print_error(f"Error de conexión: {e}")
        return {}

def registrar_pausa(id_operario: int, accion: str, motivo: str = None) -> Dict:
    """Registra inicio o fin de pausa"""
    try:
        payload = {
            "id_operario": id_operario,
            "accion": accion
        }
        if motivo and accion == "INICIO":
            payload["motivo"] = motivo
        
        response = requests.post(
            f"{API_URL}/api/pausa",
            json=payload,
            timeout=5
        )
        
        if response.status_code == 201:
            return response.json()
        else:
            print_error(f"Error al registrar pausa: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        print_error(f"Error de conexión: {e}")
        return {}

def simular_operario_perfil_excelente(id_operario: int, num_ciclos: int):
    """Simula un operario con rendimiento excelente"""
    print(f"\n{Colors.GREEN}► Simulando operario EXCELENTE (ID: {id_operario}){Colors.END}")
    
    for i in range(num_ciclos):
        # Tiempo entre 10-11.5 segundos (excelente)
        tiempo_espera = random.uniform(10.0, 11.5)
        time.sleep(tiempo_espera)
        
        result = registrar_ciclo(id_operario)
        if result:
            estado_color = Colors.GREEN if result['estado'] == 'Excelente' else Colors.YELLOW
            print(f"  Ciclo {i+1}/{num_ciclos}: {estado_color}{result['estado']}{Colors.END} "
                  f"(Tiempo: {tiempo_espera:.1f}s, "
                  f"Promedio: {result.get('promedio_5_ciclos', 0):.1f}s)")

def simular_operario_perfil_normal(id_operario: int, num_ciclos: int):
    """Simula un operario con rendimiento normal"""
    print(f"\n{Colors.BLUE}► Simulando operario NORMAL (ID: {id_operario}){Colors.END}")
    
    for i in range(num_ciclos):
        # Tiempo entre 12-15 segundos (normal)
        tiempo_espera = random.uniform(12.0, 15.0)
        time.sleep(tiempo_espera)
        
        result = registrar_ciclo(id_operario)
        if result:
            estado_color = Colors.BLUE if result['estado'] == 'Normal' else Colors.YELLOW
            print(f"  Ciclo {i+1}/{num_ciclos}: {estado_color}{result['estado']}{Colors.END} "
                  f"(Tiempo: {tiempo_espera:.1f}s, "
                  f"Promedio: {result.get('promedio_5_ciclos', 0):.1f}s)")

def simular_operario_perfil_lento(id_operario: int, num_ciclos: int):
    """Simula un operario con rendimiento bajo"""
    print(f"\n{Colors.RED}► Simulando operario LENTO (ID: {id_operario}){Colors.END}")
    
    for i in range(num_ciclos):
        # Tiempo entre 16-20 segundos (lento)
        tiempo_espera = random.uniform(16.0, 20.0)
        time.sleep(tiempo_espera)
        
        result = registrar_ciclo(id_operario)
        if result:
            estado_color = Colors.RED if result['estado'] == 'Lento' else Colors.YELLOW
            print(f"  Ciclo {i+1}/{num_ciclos}: {estado_color}{result['estado']}{Colors.END} "
                  f"(Tiempo: {tiempo_espera:.1f}s, "
                  f"Promedio: {result.get('promedio_5_ciclos', 0):.1f}s)")

def simular_pausas(id_operario: int):
    """Simula pausas de un operario"""
    print(f"\n{Colors.YELLOW}► Simulando PAUSAS (ID: {id_operario}){Colors.END}")
    
    # Iniciar pausa
    result = registrar_pausa(id_operario, "INICIO", "Baño")
    if result:
        print_warning(f"Pausa iniciada: {result['mensaje']}")
    
    # Simular tiempo de pausa (5-10 segundos en la demo)
    tiempo_pausa = random.uniform(5, 10)
    print(f"  Esperando {tiempo_pausa:.1f} segundos...")
    time.sleep(tiempo_pausa)
    
    # Finalizar pausa
    result = registrar_pausa(id_operario, "FIN")
    if result:
        print_success(f"Pausa finalizada: {result['mensaje']}")

def mostrar_resumen_final(operarios: List[int]):
    """Muestra un resumen final de todos los operarios"""
    print_header("RESUMEN FINAL")
    
    for id_operario in operarios:
        metricas = obtener_metricas(id_operario)
        if metricas:
            print(f"\n{Colors.BLUE}Operario: {metricas['nombre']} (ID: {id_operario}){Colors.END}")
            print(f"  Tarea: {metricas['tarea_actual']}")
            print(f"  Ciclos hoy: {metricas['ciclos_hoy']}")
            print(f"  Promedio del día: {metricas.get('promedio_dia', 0):.1f}s")
            print(f"  Promedio últimos 5: {metricas.get('promedio_ultimos_5', 0):.1f}s")
            print(f"  Eficiencia: {metricas.get('eficiencia_porcentaje', 0):.1f}%")
            
            # Color según estado
            estado = metricas['estado_actual']
            if estado == 'Excelente':
                print(f"  Estado: {Colors.GREEN}🎉 {estado}{Colors.END}")
            elif estado == 'Normal':
                print(f"  Estado: {Colors.BLUE}👍 {estado}{Colors.END}")
            elif estado == 'Lento':
                print(f"  Estado: {Colors.RED}⚠️  {estado}{Colors.END}")

def test_completo():
    """Ejecuta una prueba completa del sistema"""
    print_header("🏭 SISTEMA DE BOTEO - TEST AUTOMATIZADO")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Verificar conexión
    if not verificar_conexion():
        print_error("No se puede continuar sin conexión al backend")
        return
    
    # 2. Simular diferentes perfiles de operarios
    print_header("FASE 1: Simulación de Perfiles de Rendimiento")
    
    # Operario excelente
    simular_operario_perfil_excelente(OPERARIOS[0], 5)
    
    # Operario normal
    simular_operario_perfil_normal(OPERARIOS[1], 5)
    
    # Operario lento
    simular_operario_perfil_lento(OPERARIOS[2], 5)
    
    # 3. Simular pausas
    print_header("FASE 2: Simulación de Pausas")
    simular_pausas(OPERARIOS[0])
    
    # 4. Algunos ciclos más después de la pausa
    print_header("FASE 3: Continuación Después de Pausa")
    simular_operario_perfil_excelente(OPERARIOS[0], 3)
    
    # 5. Resumen final
    mostrar_resumen_final(OPERARIOS)
    
    print_header("TEST COMPLETADO ✓")
    print(f"{Colors.GREEN}Todos los tests se ejecutaron exitosamente{Colors.END}\n")

def test_rapido():
    """Ejecuta un test rápido de funcionalidad básica"""
    print_header("TEST RÁPIDO")
    
    if not verificar_conexion():
        return
    
    id_operario = 3582
    
    # Registrar algunos ciclos
    print("\nRegistrando 3 ciclos...")
    for i in range(3):
        time.sleep(2)
        result = registrar_ciclo(id_operario)
        if result:
            print_success(f"Ciclo {i+1}: {result['estado']}")
    
    # Obtener métricas
    print("\nObteniendo métricas...")
    metricas = obtener_metricas(id_operario)
    if metricas:
        print_success(f"Métricas obtenidas: {metricas['ciclos_hoy']} ciclos hoy")
    
    print_success("\nTest rápido completado")

def menu_interactivo():
    """Muestra un menú interactivo para elegir el tipo de test"""
    print_header("MENÚ DE TESTING")
    print("1. Test Completo (simulación de múltiples operarios)")
    print("2. Test Rápido (verificación básica)")
    print("3. Simulación Continua (infinito hasta Ctrl+C)")
    print("4. Salir")
    
    opcion = input("\nSeleccione una opción (1-4): ").strip()
    
    if opcion == '1':
        test_completo()
    elif opcion == '2':
        test_rapido()
    elif opcion == '3':
        print_header("SIMULACIÓN CONTINUA")
        print("Presione Ctrl+C para detener\n")
        try:
            while True:
                for id_op in OPERARIOS:
                    tiempo = random.uniform(10, 18)
                    time.sleep(tiempo)
                    result = registrar_ciclo(id_op)
                    if result:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                              f"Op {id_op}: {result['estado']}")
        except KeyboardInterrupt:
            print("\n\nSimulación detenida por el usuario")
    elif opcion == '4':
        print_success("¡Hasta luego!")
    else:
        print_error("Opción no válida")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "completo":
            test_completo()
        elif sys.argv[1] == "rapido":
            test_rapido()
        else:
            print("Uso: python test_sistema.py [completo|rapido]")
    else:
        menu_interactivo()