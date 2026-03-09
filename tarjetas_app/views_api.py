# tarjetas_app/views_api.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Tarjeta, Movimiento
from django.db.models import Sum


@login_required
def api_personas_tarjeta(request, tarjeta_id):
    try:
        tarjeta = Tarjeta.objects.get(id=tarjeta_id, activa=True)
    except Tarjeta.DoesNotExist:
        return JsonResponse({'error': 'Tarjeta no encontrada'}, status=404)
    
    personas = tarjeta.usuarios.filter(activo=True)
    movimientos_count = Movimiento.objects.filter(tarjeta=tarjeta).count()
    
    cashback_total = Movimiento.objects.filter(
        tarjeta=tarjeta,
        tipo='COMPRA'
    ).aggregate(total=Sum('monto_cashback'))['total'] or 0

    personas_data = []
    for persona in personas:
        movimientos = Movimiento.objects.filter(
            tarjeta=tarjeta,
            persona=persona
        )
        
        deuda_total = 0
        
        for mov in movimientos:
            if mov.tipo in ['COMPRA', 'COMISION', 'INTERES'] and not mov.es_a_meses:
                deuda_total += mov.monto
            elif mov.tipo == 'MENSUALIDAD':
                deuda_total += mov.monto
            elif mov.tipo in ['PAGO', 'CASHBACK']:
                deuda_total -= mov.monto
        
        
        cashback_persona = movimientos.filter(tipo='COMPRA').aggregate(
            total=Sum('monto_cashback')
        )['total'] or 0
        
        personas_data.append({
            'id': persona.id,
            'nombre': persona.nombre,
            'activo': persona.activo,
            'deuda_total': float(deuda_total),
            'total_movimientos': movimientos.count(),
            'cashback_generado': float(cashback_persona),
        })
    
    response_data = {
        'tarjeta_id': tarjeta.id,
        'disponible_total': float(tarjeta.saldo_disponible()),
        'personas_count': personas.count(),
        'movimientos_count': movimientos_count,
        'cashback_total': float(cashback_total),
        'personas': personas_data
    }
    
    return JsonResponse(response_data)