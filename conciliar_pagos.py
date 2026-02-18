# conciliar_pagos.py
import os
import django
from django.db.models import Q, Sum, F

# Configurar el entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controltarjetas.settings')
django.setup()

from tarjetas_app.models import Movimiento
from django.db.models import Q, Sum

def conciliar_pagos():
    # Buscar pagos sin compra_origen
    pagos_sin_asignar = Movimiento.objects.filter(tipo='PAGO', compra_origen__isnull=True)
    
    for pago in pagos_sin_asignar:
        # Buscar compras de la misma persona y tarjeta con el mismo monto
        # y que no estén ya pagadas (saldo pendiente > 0) o que el pago cubra exactamente
        compras_candidatas = Movimiento.objects.filter(
            persona=pago.persona,
            tarjeta=pago.tarjeta,
            tipo__in=['COMPRA', 'COMISION', 'INTERES'],
            monto=pago.monto  # Mismo monto
        ).annotate(
            total_pagado=Sum('pagos__monto')
        ).filter(
            Q(total_pagado__isnull=True) | Q(total_pagado__lt=F('monto'))
        )
        
        # Si hay una sola compra candidata, la asignamos
        if compras_candidatas.count() == 1:
            compra = compras_candidatas.first()
            pago.compra_origen = compra
            pago.save()
            print(f"✅ Pago {pago.id} asignado a compra {compra.id} (monto {pago.monto})")
        elif compras_candidatas.count() > 1:
            print(f"⚠️ Pago {pago.id} tiene múltiples compras candidatas del mismo monto. Revisar manualmente.")
        else:
            print(f"❌ Pago {pago.id} no tiene compra candidata del mismo monto.")

if __name__ == '__main__':
    print("Iniciando conciliación de pagos...")
    conciliar_pagos()
    print("Conciliación finalizada.")