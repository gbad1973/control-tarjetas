# tarjetas_app/views_api.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Tarjeta, Movimiento

@login_required
def api_personas_tarjeta(request, tarjeta_id):
    """API para obtener personas y estadísticas de una tarjeta específica"""
    try:
        tarjeta = Tarjeta.objects.get(id=tarjeta_id, activa=True)
    except Tarjeta.DoesNotExist:
        return JsonResponse({'error': 'Tarjeta no encontrada'}, status=404)
    
    # Obtener personas de la tarjeta
    personas = tarjeta.usuarios.filter(activo=True)
    
    # Contar movimientos totales de la tarjeta
    movimientos_count = Movimiento.objects.filter(tarjeta=tarjeta).count()
    
    # Preparar datos de personas
    personas_data = []
    for persona in personas:
        # Movimientos de esta persona en ESTA tarjeta
        movimientos = Movimiento.objects.filter(
            tarjeta=tarjeta,
            persona=persona
        )
        
        # Calcular deuda específica de esta tarjeta
        deuda_total = 0
        for mov in movimientos:
            if mov.tipo in ['COMPRA', 'COMISION', 'INTERES']:
                deuda_total += mov.monto
            elif mov.tipo in ['PAGO', 'CASHBACK']:
                deuda_total -= mov.monto
        
        personas_data.append({
            'id': persona.id,
            'nombre': persona.nombre,
            'activo': persona.activo,
            'deuda_total': float(deuda_total),
            'total_movimientos': movimientos.count()
        })
    
    response_data = {
        'tarjeta_id': tarjeta.id,
        'disponible_total': float(tarjeta.saldo_disponible()),
        'personas_count': personas.count(),
        'movimientos_count': movimientos_count,
        'personas': personas_data
    }
    
    return JsonResponse(response_data)