from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from datetime import date, datetime, timedelta
from .models import Persona, Tarjeta, Establecimiento, Movimiento, PagoCompra, LiberacionMensualidad
from .forms import PersonaForm, TarjetaForm, EstablecimientoForm, MovimientoForm, PagoCompraFormSet
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from itertools import chain
from operator import attrgetter
from decimal import Decimal


# ========== AUTENTICACIÓN ==========
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'tarjetas_app/login.html', {'error': 'Usuario o contraseña incorrectos'})
    
    return render(request, 'tarjetas_app/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def crear_usuario_admin(request):
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        return render(request, 'tarjetas_app/crear_admin.html', {'mensaje': 'Usuario admin creado'})
    return render(request, 'tarjetas_app/crear_admin.html')

# ========== DASHBOARD Y PRINCIPALES ==========
@login_required
def dashboard(request):
    tarjetas = Tarjeta.objects.filter(activa=True)
    tarjeta_seleccionada = tarjetas.first() if tarjetas.exists() else None
    
    if tarjeta_seleccionada:
        personas = tarjeta_seleccionada.usuarios.filter(activo=True)
        for persona in personas:
            movimientos_persona = Movimiento.objects.filter(
                persona=persona, 
                tarjeta=tarjeta_seleccionada
            )
            
            deuda_total = 0
            for movimiento in movimientos_persona:
                if movimiento.tipo in ['COMPRA', 'COMISION', 'INTERES']:
                    if not movimiento.es_a_meses:
                        deuda_total += movimiento.monto
                elif movimiento.tipo == 'MENSUALIDAD':
                    deuda_total += movimiento.monto
                elif movimiento.tipo in ['PAGO', 'CASHBACK']:
                    deuda_total -= movimiento.monto
            
            persona.deuda_total = deuda_total
            persona.total_movimientos = movimientos_persona.count()
    else:
        personas = []
    
    total_limite = tarjetas.aggregate(total=Sum('limite_credito'))['total'] or 0
    total_saldo = tarjetas.aggregate(total=Sum('saldo_actual'))['total'] or 0
    total_disponible = total_limite - total_saldo
    total_cashback = Movimiento.objects.filter(
        tipo__in=['COMPRA', 'MENSUALIDAD']
    ).aggregate(total=Sum('monto_cashback'))['total'] or 0
    
    for persona in personas:
        cashback_persona = Movimiento.objects.filter(
            persona=persona,
            tarjeta=tarjeta_seleccionada,
            tipo__in=['COMPRA', 'MENSUALIDAD']
        ).aggregate(total=Sum('monto_cashback'))['total'] or 0
        persona.cashback = cashback_persona
    
    context = {
        'personas': personas,
        'tarjetas': tarjetas,
        'tarjeta_seleccionada': tarjeta_seleccionada,
        'total_limite': total_limite,
        'total_saldo': total_saldo,
        'total_disponible': total_disponible,
        'total_movimientos': Movimiento.objects.count(),
        'total_cashback': total_cashback,
    }
    return render(request, 'tarjetas_app/dashboard.html', context)

# ========== FORMULARIOS NUEVOS ==========
@login_required
def nueva_persona(request):
    if request.method == 'POST':
        form = PersonaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Persona creada exitosamente!')
            return redirect('lista_personas')
    else:
        form = PersonaForm()
    return render(request, 'tarjetas_app/nueva_persona.html', {'form': form})

# ========== FUNCIÓN AUXILIAR ==========
def convertir_fecha_vencimiento(valor_mm_aa):
    if not valor_mm_aa:
        return date.today() + timedelta(days=365*3)
    try:
        valor_mm_aa = valor_mm_aa.strip().replace(' ', '')
        if isinstance(valor_mm_aa, date):
            return valor_mm_aa
        if '/' in valor_mm_aa:
            partes = valor_mm_aa.split('/')
            if len(partes) == 2:
                mes = int(partes[0])
                anio_str = partes[1]
                if len(anio_str) == 2:
                    anio = 2000 + int(anio_str)
                else:
                    anio = int(anio_str)
                if mes == 12:
                    return date(anio, mes, 31)
                else:
                    ultimo_dia = (date(anio, mes + 1, 1) - timedelta(days=1)).day
                    return date(anio, mes, ultimo_dia)
    except:
        pass
    return date.today() + timedelta(days=365*3)

# ========== NUEVA TARJETA ==========
@login_required
def nueva_tarjeta(request):
    todas_las_personas = Persona.objects.filter(activo=True)
    if request.method == 'POST':
        form = TarjetaForm(request.POST)
        fecha_mm_aa = request.POST.get('fecha_vencimiento_tarjeta_mm_aa', '')
        fecha_convertida = convertir_fecha_vencimiento(fecha_mm_aa)
        post_data = request.POST.copy()
        post_data['fecha_vencimiento_tarjeta'] = fecha_convertida
        form = TarjetaForm(post_data)
        if form.is_valid():
            tarjeta = form.save(commit=False)
            tarjeta.fecha_vencimiento_tarjeta = fecha_convertida
            usuarios_ids = request.POST.get('usuarios_ids', '')
            if usuarios_ids:
                usuarios_ids = [int(id) for id in usuarios_ids.split(',') if id.isdigit()]
                usuarios = Persona.objects.filter(id__in=usuarios_ids)
                tarjeta.save()
                tarjeta.usuarios.set(usuarios)
            else:
                tarjeta.save()
                if tarjeta.titular:
                    tarjeta.usuarios.add(tarjeta.titular)
            messages.success(request, '¡Tarjeta creada exitosamente!')
            return redirect('lista_tarjetas')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = TarjetaForm()
    return render(request, 'tarjetas_app/nueva_tarjeta.html', {
        'form': form,
        'todas_las_personas': todas_las_personas,
        'es_edicion': False,
        'usuarios_asignados': [],
        'tarjeta': None
    })

# ========== NUEVO MOVIMIENTO (COMPLETO CON COMPRAS A MESES) ==========
# ========== NUEVO MOVIMIENTO (CORREGIDO CON CASHBACK) ==========
@login_required
def nuevo_movimiento(request):
    if request.method == 'POST':
        print("🔍 POST recibido en nuevo_movimiento")
        print(f"Datos POST: {request.POST}")
        
        form = MovimientoForm(request.POST)
        if form.is_valid():
            print("✅ Formulario válido")
            movimiento = form.save(commit=False)
            print(f"Tipo de movimiento: {movimiento.tipo}")
            
            # ===== CÁLCULO DE CASHBACK PARA COMPRAS (NORMALES Y A MESES) =====
            if movimiento.tipo == 'COMPRA':
                # Verificar si es a meses desde el POST
                es_a_meses = request.POST.get('es_a_meses') == 'on'
                
                if es_a_meses:
                    movimiento.es_a_meses = True
                    movimiento.numero_meses = request.POST.get('numero_meses')
                    if movimiento.numero_meses:
                        movimiento.numero_meses = int(movimiento.numero_meses)
                        movimiento.monto_mensual = movimiento.monto / movimiento.numero_meses
                        movimiento.meses_pagados = 0
                else:
                    movimiento.es_a_meses = False
                    movimiento.numero_meses = None
                    movimiento.monto_mensual = None
                
                # ===== CALCULAR CASHBACK PARA TODAS LAS COMPRAS =====
                if movimiento.establecimiento and movimiento.establecimiento.porcentaje_cashback > 0:
                    porcentaje = movimiento.establecimiento.porcentaje_cashback / 100
                    movimiento.monto_cashback = movimiento.monto * porcentaje
                    print(f"💰 Cashback calculado: ${movimiento.monto_cashback} ({movimiento.establecimiento.porcentaje_cashback}%)")
                else:
                    movimiento.monto_cashback = 0
                    print("ℹ️ Establecimiento sin cashback")
            
            if movimiento.tipo != 'COMPRA':
                movimiento.establecimiento = None
            
            movimiento.save()
            print(f"✅ Movimiento guardado con ID: {movimiento.id}")

            # ===== SI ES UN PAGO, PROCESAR LA RELACIÓN =====
            if movimiento.tipo == 'PAGO':
                # ... (el resto del código de pago queda igual) ...
                item_pagado_id = request.POST.get('compra_relacionada')
                monto_pagado = movimiento.monto
                
                print(f"🔗 Item a pagar ID desde campo oculto: {item_pagado_id}")

                if item_pagado_id and item_pagado_id.isdigit():
                    try:
                        item_pagado_id = int(item_pagado_id)
                        item_pagado = Movimiento.objects.get(id=item_pagado_id)
                        print(f"✅ Item encontrado: {item_pagado.tipo} - {item_pagado.descripcion}")
                        
                        pagado_actual = item_pagado.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
                        saldo_restante = item_pagado.monto - pagado_actual
                        
                        if monto_pagado > saldo_restante + 0.01:
                            messages.error(request, f'El monto a pagar (${monto_pagado}) excede el saldo restante (${saldo_restante})')
                            return redirect('nuevo_movimiento')
                        
                        relacion = PagoCompra.objects.create(
                            pago=movimiento,
                            compra_id=item_pagado.id,
                            monto_aplicado=monto_pagado
                        )
                        print(f"✅ Relación PagoCompra creada con ID: {relacion.id}")
                        
                        if item_pagado.tipo == 'MENSUALIDAD':
                            print(f"💰 Mensualidad {item_pagado.id} pagada correctamente")
                        
                        messages.success(request, f'✅ Pago aplicado correctamente')
                        
                        movimiento.tarjeta.actualizar_saldo()
                        print(f"💰 Saldo de tarjeta actualizado")
                        
                    except Movimiento.DoesNotExist:
                        print(f"❌ ERROR: No existe el item con ID {item_pagado_id}")
                        messages.error(request, 'Error: El item seleccionado no existe')
                    except Exception as e:
                        print(f"❌ ERROR: {str(e)}")
                        messages.error(request, f'Error al procesar el pago: {str(e)}')
                else:
                    print("⚠️ Pago sin item relacionado válido")
                    messages.warning(request, '⚠️ Pago guardado sin relación')

            messages.success(request, '✅ ¡Movimiento registrado exitosamente!')
            return redirect('lista_movimientos')
        else:
            print("❌ Formulario inválido")
            print(f"Errores del formulario: {form.errors}")
            messages.error(request, '❌ Error en el formulario')
            return render(request, 'tarjetas_app/nuevo_movimiento.html', {
                'form': form,
                'formset': PagoCompraFormSet(prefix='pagos')
            })
    else:
        form = MovimientoForm()
        formset = PagoCompraFormSet(prefix='pagos')
        print("📄 GET en nuevo_movimiento")

    return render(request, 'tarjetas_app/nuevo_movimiento.html', {'form': form, 'formset': formset})

# ========== NUEVO ESTABLECIMIENTO ==========
@login_required
def nuevo_establecimiento(request):
    if request.method == 'POST':
        form = EstablecimientoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Establecimiento creado exitosamente!')
            return redirect('lista_establecimientos')
    else:
        form = EstablecimientoForm()
    return render(request, 'tarjetas_app/nuevo_establecimiento.html', {'form': form})

# ========== LISTAS BÁSICAS ==========
@login_required
def lista_personas(request):
    personas = Persona.objects.all()
    return render(request, 'tarjetas_app/lista_personas.html', {'personas': personas})

@login_required
def lista_tarjetas(request):
    tarjetas = Tarjeta.objects.all().order_by('banco', 'numero')
    return render(request, 'tarjetas_app/lista_tarjetas.html', {'tarjetas': tarjetas})

@login_required
def lista_establecimientos(request):
    establecimientos = Establecimiento.objects.all()
    return render(request, 'tarjetas_app/lista_establecimientos.html', {'establecimientos': establecimientos})

@login_required
def lista_movimientos(request):
    movimientos = Movimiento.objects.exclude(
        tipo='COMPRA', es_a_meses=True
    ).order_by('-fecha', '-fecha_registro')
    
    buscar = request.GET.get('buscar')
    tipo = request.GET.get('tipo')
    persona_id = request.GET.get('persona')
    tarjeta_id = request.GET.get('tarjeta')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if buscar:
        movimientos = movimientos.filter(
            Q(descripcion__icontains=buscar) |
            Q(establecimiento__nombre__icontains=buscar) |
            Q(persona__nombre__icontains=buscar) |
            Q(tarjeta__banco__icontains=buscar) |
            Q(tarjeta__numero__icontains=buscar)
        )
    
    if tipo:
        movimientos = movimientos.filter(tipo=tipo)
    
    if persona_id:
        movimientos = movimientos.filter(persona_id=persona_id)
    
    if tarjeta_id:
        movimientos = movimientos.filter(tarjeta_id=tarjeta_id)
    
    if fecha_desde:
        movimientos = movimientos.filter(fecha__gte=fecha_desde)
    
    if fecha_hasta:
        movimientos = movimientos.filter(fecha__lte=fecha_hasta)
    
    personas = Persona.objects.filter(activo=True)
    tarjetas = Tarjeta.objects.filter(activa=True)
    
    return render(request, 'tarjetas_app/lista_movimientos.html', {
        'movimientos': movimientos,
        'personas': personas,
        'tarjetas': tarjetas
    })

# ========== EDITAR Y ELIMINAR ==========
@login_required
def editar_tarjeta(request, tarjeta_id):
    tarjeta = get_object_or_404(Tarjeta, id=tarjeta_id)
    todas_las_personas = Persona.objects.filter(activo=True)
    usuarios_asignados = tarjeta.usuarios.values_list('id', flat=True)
    
    if request.method == 'POST':
        form = TarjetaForm(request.POST, instance=tarjeta)
        fecha_mm_aa = request.POST.get('fecha_vencimiento_tarjeta_mm_aa', '')
        fecha_convertida = convertir_fecha_vencimiento(fecha_mm_aa)
        post_data = request.POST.copy()
        post_data['fecha_vencimiento_tarjeta'] = fecha_convertida
        form = TarjetaForm(post_data, instance=tarjeta)
        
        if form.is_valid():
            tarjeta = form.save(commit=False)
            tarjeta.fecha_vencimiento_tarjeta = fecha_convertida
            usuarios_ids = request.POST.get('usuarios_ids', '')
            if usuarios_ids:
                usuarios_ids = [int(id) for id in usuarios_ids.split(',') if id.isdigit()]
                usuarios = Persona.objects.filter(id__in=usuarios_ids)
                tarjeta.save()
                tarjeta.usuarios.set(usuarios)
            else:
                tarjeta.save()
                if tarjeta.titular:
                    tarjeta.usuarios.add(tarjeta.titular)
            messages.success(request, '¡Tarjeta actualizada exitosamente!')
            return redirect('lista_tarjetas')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = TarjetaForm(instance=tarjeta)
    
    context = {
        'form': form,
        'tarjeta': tarjeta,
        'todas_las_personas': todas_las_personas,
        'usuarios_asignados': list(usuarios_asignados),
        'es_edicion': True,
    }
    return render(request, 'tarjetas_app/nueva_tarjeta.html', context)

@login_required
def eliminar_tarjeta(request, tarjeta_id):
    tarjeta = get_object_or_404(Tarjeta, id=tarjeta_id)
    if request.method == 'POST':
        tarjeta.delete()
        messages.success(request, '¡Tarjeta eliminada exitosamente!')
        return redirect('lista_tarjetas')
    return render(request, 'tarjetas_app/confirmar_eliminar.html', {
        'objeto': tarjeta,
        'tipo': 'tarjeta',
        'volver_url': 'lista_tarjetas'
    })

@login_required
def editar_persona(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id)
    if request.method == 'POST':
        form = PersonaForm(request.POST, instance=persona)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Persona actualizada exitosamente!')
            return redirect('lista_personas')
    else:
        form = PersonaForm(instance=persona)
    return render(request, 'tarjetas_app/nueva_persona.html', {'form': form})

@login_required
def eliminar_persona(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id)
    if request.method == 'POST':
        persona.delete()
        messages.success(request, '¡Persona eliminada exitosamente!')
        return redirect('lista_personas')
    return render(request, 'tarjetas_app/confirmar_eliminar.html', {
        'objeto': persona,
        'tipo': 'persona',
        'volver_url': 'lista_personas'
    })

@login_required
def editar_establecimiento(request, establecimiento_id):
    establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
    if request.method == 'POST':
        form = EstablecimientoForm(request.POST, instance=establecimiento)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Establecimiento actualizado exitosamente!')
            return redirect('lista_establecimientos')
    else:
        form = EstablecimientoForm(instance=establecimiento)
    return render(request, 'tarjetas_app/nuevo_establecimiento.html', {'form': form})

@login_required
def eliminar_establecimiento(request, establecimiento_id):
    establecimiento = get_object_or_404(Establecimiento, id=establecimiento_id)
    if request.method == 'POST':
        establecimiento.delete()
        messages.success(request, '¡Establecimiento eliminado exitosamente!')
        return redirect('lista_establecimientos')
    return render(request, 'tarjetas_app/confirmar_eliminar.html', {
        'objeto': establecimiento,
        'tipo': 'establecimiento',
        'volver_url': 'lista_establecimientos'
    })

@login_required
def editar_movimiento(request, movimiento_id):
    movimiento = get_object_or_404(Movimiento, id=movimiento_id)
    if request.method == 'POST':
        form = MovimientoForm(request.POST, instance=movimiento)
        if form.is_valid():
            movimiento = form.save(commit=False)
            if movimiento.tipo != 'COMPRA':
                movimiento.establecimiento = None
            movimiento.save()
            messages.success(request, '✅ ¡Movimiento actualizado exitosamente!')
            return redirect('lista_movimientos')
    else:
        form = MovimientoForm(instance=movimiento)
    return render(request, 'tarjetas_app/nuevo_movimiento.html', {'form': form})

@login_required
def eliminar_movimiento(request, movimiento_id):
    movimiento = get_object_or_404(Movimiento, id=movimiento_id)
    tarjeta = movimiento.tarjeta
    
    if request.method == 'POST':
        if movimiento.tipo == 'COMPRA' and movimiento.es_a_meses:
            LiberacionMensualidad.objects.filter(movimiento=movimiento).delete()
        tarjeta_id = tarjeta.id
        movimiento.delete()
        tarjeta_actualizada = get_object_or_404(Tarjeta, id=tarjeta_id)
        tarjeta_actualizada.actualizar_saldo()
        messages.success(request, '✅ ¡Movimiento eliminado exitosamente!')
        return redirect('lista_movimientos')
    
    return render(request, 'tarjetas_app/confirmar_eliminar.html', {
        'objeto': movimiento,
        'tipo': 'movimiento',
        'volver_url': 'lista_movimientos'
    })

# ========== API PARA DASHBOARD ==========
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

# ========== DETALLE PERSONA ==========
@login_required
def detalle_persona(request, persona_id):
    from itertools import chain
    from operator import attrgetter
    
    persona = get_object_or_404(Persona, id=persona_id)
    tarjetas = Tarjeta.objects.filter(usuarios=persona)
    tarjeta_id = request.GET.get('tarjeta')
    
    compras = Movimiento.objects.filter(
        persona=persona,
        tipo__in=['COMPRA', 'COMISION', 'INTERES'],
        es_a_meses=False
    ).order_by('fecha')

    mensualidades = Movimiento.objects.filter(
        persona=persona,
        tipo='MENSUALIDAD'
    ).order_by('fecha')

    pagos = Movimiento.objects.filter(
        persona=persona,
        tipo='PAGO'
    ).order_by('fecha')
    
    compras_meses = Movimiento.objects.filter(
        persona=persona,
        tipo='COMPRA',
        es_a_meses=True
    ).order_by('fecha')

    if tarjeta_id:
        compras = compras.filter(tarjeta_id=tarjeta_id)
        mensualidades = mensualidades.filter(tarjeta_id=tarjeta_id)
        pagos = pagos.filter(tarjeta_id=tarjeta_id)
        compras_meses = compras_meses.filter(tarjeta_id=tarjeta_id)
        tarjeta_seleccionada = get_object_or_404(Tarjeta, id=tarjeta_id)
    else:
        tarjeta_seleccionada = None

    movimientos_combinados = list(chain(compras, mensualidades, pagos))
    movimientos_combinados.sort(key=lambda x: (x.fecha, x.id))

    context = {
        'persona': persona,
        'tarjetas': tarjetas,
        'tarjeta_seleccionada': tarjeta_seleccionada,
        'movimientos_combinados': movimientos_combinados,
        'compras_meses': compras_meses,
    }
    return render(request, 'tarjetas_app/detalle_persona.html', context)

# ========== MOVIMIENTOS TARJETA ==========
@login_required
def movimientos_tarjeta(request, tarjeta_id):
    tarjeta = get_object_or_404(Tarjeta, id=tarjeta_id, activa=True)
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    compras = Movimiento.objects.filter(
        tarjeta=tarjeta,
        tipo__in=['COMPRA', 'COMISION', 'INTERES']
    ).order_by('fecha')

    if fecha_desde:
        compras = compras.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        compras = compras.filter(fecha__lte=fecha_hasta)

    for compra in compras:
        compra.pagos_ordenados = compra.pagos_recibidos.all().order_by('fecha')

    pagos_sin_asignar = Movimiento.objects.filter(
        tarjeta=tarjeta,
        tipo='PAGO'
    ).exclude(
        id__in=PagoCompra.objects.values('pago_id')
    ).order_by('fecha')

    if fecha_desde:
        pagos_sin_asignar = pagos_sin_asignar.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        pagos_sin_asignar = pagos_sin_asignar.filter(fecha__lte=fecha_hasta)

    context = {
        'tarjeta': tarjeta,
        'compras': compras,
        'pagos_sin_asignar': pagos_sin_asignar,
    }
    return render(request, 'tarjetas_app/movimientos_tarjeta.html', context)

# ========== COMPRAS POR PERSONA (API) ==========
def compras_por_persona(request, persona_id):
    """Devuelve los movimientos que pueden ser pagados (compras normales y mensualidades)"""
    from django.db.models import Sum, F, Q
    
    data = []
    
    # 1. COMPRAS NORMALES con saldo pendiente
    compras_normales = Movimiento.objects.filter(
        persona_id=persona_id,
        tipo__in=['COMPRA', 'COMISION', 'INTERES'],
        es_a_meses=False
    ).annotate(
        total_pagado=Sum('pagos_recibidos__monto_aplicado')
    ).filter(
        Q(total_pagado__isnull=True) | Q(monto__gt=F('total_pagado'))
    ).order_by('-fecha')
    
    for compra in compras_normales:
        pagado = compra.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
        saldo = compra.monto - pagado
        establecimiento = compra.establecimiento.nombre if compra.establecimiento else "Sin establecimiento"
        descripcion = compra.descripcion[:30] + "..." if len(compra.descripcion) > 30 else compra.descripcion
        
        texto = f"{compra.get_tipo_display()} {compra.fecha.strftime('%d/%m/%Y')} - ${compra.monto} - {establecimiento} - {descripcion}"
        data.append({
            'id': compra.id,
            'texto': texto,
            'saldo': float(saldo),
            'tipo': 'compra_normal'
        })
    
    # 2. MENSUALIDADES pendientes (de compras a meses)
    mensualidades = Movimiento.objects.filter(
        persona_id=persona_id,
        tipo='MENSUALIDAD'
    ).annotate(
        total_pagado=Sum('pagos_recibidos__monto_aplicado')
    ).filter(
        Q(total_pagado__isnull=True) | Q(monto__gt=F('total_pagado'))
    ).order_by('-fecha')
    
    for mensualidad in mensualidades:
        pagado = mensualidad.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
        saldo = mensualidad.monto - pagado
        
        texto = f"{mensualidad.descripcion} - ${mensualidad.monto}"
        data.append({
            'id': mensualidad.id,
            'texto': texto,
            'saldo': float(saldo),
            'tipo': 'mensualidad'
        })
    
    return JsonResponse(data, safe=False)

# ========== CARGA MENSUALIDAD (CORREGIDA DEFINITIVAMENTE) ==========

# ========== CARGA MENSUALIDAD (VERSIÓN FINAL - CORREGIDA) ==========
# ========== CARGA MENSUALIDAD (VERSIÓN FINAL - CON ELIMINACIÓN) ==========
@login_required
def cargar_mensualidad(request, compra_id):
    """Carga la SIGUIENTE mensualidad de una compra a meses"""
    try:
        compra = Movimiento.objects.get(id=compra_id, tipo='COMPRA', es_a_meses=True)
    except:
        messages.error(request, 'Compra no encontrada')
        return redirect('dashboard')
    
    # Buscar TODAS las mensualidades existentes por su descripción exacta
    mensualidades_existentes = []
    for i in range(1, compra.numero_meses + 1):
        existe = Movimiento.objects.filter(
            descripcion=f"Mensualidad {i}/{compra.numero_meses} de compra {compra.id}",
            tipo='MENSUALIDAD'
        ).exists()
        if existe:
            mensualidades_existentes.append(i)
    
    print(f"📊 Compra {compra.id}: Mensualidades existentes: {mensualidades_existentes}")
    
    # Si ya están todas, no hacer nada
    if len(mensualidades_existentes) >= compra.numero_meses:
        messages.error(request, f'Esta compra ya tiene todas las mensualidades cargadas.')
        return redirect('detalle_persona', persona_id=compra.persona.id)
    
    # Encontrar el primer número faltante
    siguiente_mes = 1
    while siguiente_mes in mensualidades_existentes:
        siguiente_mes += 1
    
    print(f"➡️ Siguiente mensualidad a crear: {siguiente_mes}/{compra.numero_meses}")
    
    # Calcular cashback
    if compra.monto_cashback and compra.monto_cashback > 0:
        cashback_mensual = compra.monto_cashback / compra.numero_meses
    else:
        cashback_mensual = 0
        if compra.establecimiento and compra.establecimiento.porcentaje_cashback > 0:
            porcentaje = compra.establecimiento.porcentaje_cashback / 100
            cashback_mensual = (compra.monto / compra.numero_meses) * porcentaje
            compra.monto_cashback = compra.monto * porcentaje
            compra.save(update_fields=['monto_cashback'])
    
    # Crear la mensualidad
    nueva_mensualidad = Movimiento.objects.create(
        tarjeta=compra.tarjeta,
        persona=compra.persona,
        establecimiento=compra.establecimiento,
        tipo='MENSUALIDAD',
        monto=compra.monto_mensual,
        monto_cashback=cashback_mensual,
        descripcion=f"Mensualidad {siguiente_mes}/{compra.numero_meses} de compra {compra.id}",
        fecha=date.today(),
        es_a_meses=False
    )
    print(f"✅ Mensualidad {siguiente_mes}/{compra.numero_meses} creada con ID: {nueva_mensualidad.id}")
    
    # Registrar liberación
    LiberacionMensualidad.objects.create(
        movimiento=compra,
        monto=compra.monto_mensual,
        numero_mes=siguiente_mes
    )
    
    # Actualizar meses_pagados
    compra.meses_pagados = max(mensualidades_existentes + [siguiente_mes]) if mensualidades_existentes else siguiente_mes
    
    # ===== NUEVA LÓGICA: Si ya se pagaron todos los meses, ELIMINAR la compra original =====
    if compra.meses_pagados >= compra.numero_meses:
        print(f"🗑️ ¡Compra {compra.id} completada! Eliminando del historial...")
        tarjeta_id = compra.tarjeta.id  # Guardamos para actualizar saldo después
        persona_id = compra.persona.id   # Guardamos para redireccionar
        
        # Eliminar la compra original
        compra.delete()
        
        # Actualizar saldo de la tarjeta
        tarjeta = Tarjeta.objects.get(id=tarjeta_id)
        tarjeta.actualizar_saldo()
        
        messages.success(
            request, 
            f'✅ Mensualidad {siguiente_mes}/{compra.numero_meses} cargada correctamente. '
            f'¡Compra completada y eliminada del historial!'
        )
        
        return redirect('detalle_persona', persona_id=persona_id)
    else:
        # Si no es la última, solo guardamos los cambios
        compra.save()
        
        messages.success(
            request, 
            f'✅ Mensualidad {siguiente_mes}/{compra.numero_meses} cargada correctamente. '
            f'Cashback: ${cashback_mensual:.2f}'
        )
        
        return redirect('detalle_persona', persona_id=compra.persona.id)
# ========== REPORTES ==========
@login_required 
def reporte_cashback_persona(request, persona_id):
    return redirect('dashboard')

@login_required
def reporte_cashback_general(request):
    return redirect('dashboard')

@login_required
def reporte_deudas(request):
    return redirect('dashboard')