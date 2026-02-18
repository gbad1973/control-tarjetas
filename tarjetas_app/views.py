# tarjetas_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from datetime import date, datetime, timedelta
from .models import Persona, Tarjeta, Establecimiento, Movimiento, PagoCompra
from .forms import PersonaForm, TarjetaForm, EstablecimientoForm, MovimientoForm, PagoCompraFormSet
from django.contrib import messages
from django.http import JsonResponse
from django.db import models



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
    
    context = {
        'personas': personas,
        'tarjetas': tarjetas,
        'tarjeta_seleccionada': tarjeta_seleccionada,
        'total_limite': total_limite,
        'total_saldo': total_saldo,
        'total_disponible': total_disponible,
        'total_movimientos': Movimiento.objects.count(),
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

# ========== FUNCIÓN AUXILIAR PARA CONVERTIR MM/AA A FECHA ==========
def convertir_fecha_vencimiento(valor_mm_aa):
    """Convierte string MM/AA a objeto date (último día del mes)"""
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

# ========== NUEVO MOVIMIENTO - CORREGIDO DEFINITIVO ==========
@login_required
def nuevo_movimiento(request):
    if request.method == 'POST':
        form = MovimientoForm(request.POST)
        if form.is_valid():
            movimiento = form.save(commit=False)
            if movimiento.tipo != 'COMPRA':
                movimiento.establecimiento = None
            movimiento.save()

            # Si es un pago, procesamos el formset
            if movimiento.tipo == 'PAGO':
                formset = PagoCompraFormSet(request.POST, prefix='pagos')
                if formset.is_valid():
                    # Validar que no se exceda el saldo pendiente de cada compra
                    errores_saldo = False
                    montos_por_compra = {}
                    for pago_form in formset:
                        if pago_form.cleaned_data and not pago_form.cleaned_data.get('DELETE', False):
                            compra = pago_form.cleaned_data['compra']
                            monto = pago_form.cleaned_data['monto_aplicado']
                            if compra.id in montos_por_compra:
                                montos_por_compra[compra.id] += monto
                            else:
                                montos_por_compra[compra.id] = monto

                    for compra_id, monto_total in montos_por_compra.items():
                        try:
                            compra = Movimiento.objects.get(id=compra_id)
                            saldo_actual = compra.saldo_pendiente
                            if monto_total > saldo_actual:
                                errores_saldo = True
                                messages.error(
                                    request,
                                    f'La compra "{compra}" tiene saldo pendiente de ${saldo_actual:.2f}. '
                                    f'No puedes aplicar ${monto_total:.2f}.'
                                )
                        except Movimiento.DoesNotExist:
                            errores_saldo = True
                            messages.error(request, f'Compra con ID {compra_id} no existe.')

                    if errores_saldo:
                        movimiento.delete()
                        return render(request, 'tarjetas_app/nuevo_movimiento.html', {
                            'form': form,
                            'formset': formset
                        })

                    # Si todo está bien, guardamos los PagoCompra
                    for pago_form in formset:
                        if pago_form.cleaned_data and not pago_form.cleaned_data.get('DELETE', False):
                            pago_compra = pago_form.save(commit=False)
                            pago_compra.pago = movimiento
                            pago_compra.save()
                else:
                    # Si el formset no es válido, eliminamos el movimiento y mostramos error
                    movimiento.delete()
                    messages.error(request, 'Error en la distribución del pago. Revisa los montos.')
                    return render(request, 'tarjetas_app/nuevo_movimiento.html', {'form': form, 'formset': formset})
            messages.success(request, '✅ ¡Movimiento registrado exitosamente!')
            return redirect('lista_movimientos')
        else:
            messages.error(request, '❌ Error en el formulario')
    else:
        form = MovimientoForm()
        formset = PagoCompraFormSet(prefix='pagos')

    return render(request, 'tarjetas_app/nuevo_movimiento.html', {'form': form, 'formset': formset})
# *************************************************************
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
    movimientos = Movimiento.objects.all().order_by('-fecha', '-fecha_registro')
    
    # 🔴 APLICAR FILTROS
    buscar = request.GET.get('buscar')
    tipo = request.GET.get('tipo')
    persona_id = request.GET.get('persona')
    tarjeta_id = request.GET.get('tarjeta')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if buscar:
        movimientos = movimientos.filter(
            models.Q(descripcion__icontains=buscar) |
            models.Q(establecimiento__nombre__icontains=buscar) |
            models.Q(persona__nombre__icontains=buscar) |
            models.Q(tarjeta__banco__icontains=buscar) |
            models.Q(tarjeta__numero__icontains=buscar)
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
# ========== EDITAR TARJETA ==========
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
            
            # Misma lógica para edición
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
    
    if request.method == 'POST':
        movimiento.delete()
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
    """API para obtener personas y estadísticas de una tarjeta específica"""
    try:
        tarjeta = Tarjeta.objects.get(id=tarjeta_id, activa=True)
    except Tarjeta.DoesNotExist:
        return JsonResponse({'error': 'Tarjeta no encontrada'}, status=404)
    
    personas = tarjeta.usuarios.filter(activo=True)
    movimientos_count = Movimiento.objects.filter(tarjeta=tarjeta).count()
    
    personas_data = []
    for persona in personas:
        movimientos = Movimiento.objects.filter(
            tarjeta=tarjeta,
            persona=persona
        )
        
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

# ========== DETALLE PERSONA (MODIFICADA) ==========
@login_required
def detalle_persona(request, persona_id):
    persona = get_object_or_404(Persona, id=persona_id)
    tarjetas = Tarjeta.objects.filter(usuarios=persona)

    tarjeta_id = request.GET.get('tarjeta')
    # Obtener todas las compras (incluyendo comisiones e intereses) ordenadas por fecha ascendente
    compras = Movimiento.objects.filter(
        persona=persona,
        tipo__in=['COMPRA', 'COMISION', 'INTERES']
    ).order_by('fecha')

    if tarjeta_id:
        compras = compras.filter(tarjeta_id=tarjeta_id)
        tarjeta_seleccionada = get_object_or_404(Tarjeta, id=tarjeta_id)
    else:
        tarjeta_seleccionada = None

    # Pagos sin asignar (sin ningún PagoCompra)
    pagos_sin_asignar = Movimiento.objects.filter(
        persona=persona,
        tipo='PAGO'
    ).exclude(
        id__in=PagoCompra.objects.values('pago_id')
    ).order_by('fecha')

    if tarjeta_id:
        pagos_sin_asignar = pagos_sin_asignar.filter(tarjeta_id=tarjeta_id)

    context = {
        'persona': persona,
        'tarjetas': tarjetas,
        'tarjeta_seleccionada': tarjeta_seleccionada,
        'compras': compras,
        'pagos_sin_asignar': pagos_sin_asignar,
    }
    return render(request, 'tarjetas_app/detalle_persona.html', context)

# ********** MOVIMIENTOS TARJETAS ************************************
@login_required
def movimientos_tarjeta(request, tarjeta_id):
    """Vista para ver TODOS los movimientos de una tarjeta específica, agrupados por compra"""
    tarjeta = get_object_or_404(Tarjeta, id=tarjeta_id, activa=True)

    # Filtrar por fecha (opcional)
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    # Obtener todas las compras (cargos) de la tarjeta, ordenadas por fecha ascendente
    compras = Movimiento.objects.filter(
        tarjeta=tarjeta,
        tipo__in=['COMPRA', 'COMISION', 'INTERES']
    ).order_by('fecha')

    if fecha_desde:
        compras = compras.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        compras = compras.filter(fecha__lte=fecha_hasta)

    # Para cada compra, obtener sus pagos (no hace falta recalcular saldo, la propiedad ya lo hace)
    for compra in compras:
        compra.pagos_ordenados = compra.pagos_recibidos.all().order_by('fecha')

    # Pagos que no están asociados a ninguna compra (pagos sin asignar)
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

#  ===================== compras por persona.  ==================================
def compras_por_persona(request, persona_id):
    """Devuelve las compras de una persona que tienen saldo pendiente"""
    compras = Movimiento.objects.filter(
        persona_id=persona_id,
        tipo__in=['COMPRA', 'COMISION', 'INTERES']
    ).order_by('-fecha')
    
    data = []
    for compra in compras:
        total_pagado = compra.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
        saldo = compra.monto - total_pagado
        if saldo > 0:  # Solo si aún debe algo
            establecimiento = compra.establecimiento.nombre if compra.establecimiento else "Sin establecimiento"
            descripcion = compra.descripcion[:30] + "..." if len(compra.descripcion) > 30 else compra.descripcion
            texto = f"Compra {compra.fecha.strftime('%d/%m/%Y')} - ${compra.monto} - {establecimiento} - {descripcion}"
            data.append({
                'id': compra.id,
                'texto': texto,
                'saldo': float(saldo)  # ← NUEVO: enviamos el saldo
            })
    
    return JsonResponse(data, safe=False)

# ========== REPORTES (PENDIENTES) ==========
@login_required 
def reporte_cashback_persona(request, persona_id):
    return redirect('dashboard')

@login_required
def reporte_cashback_general(request):
    return redirect('dashboard')

@login_required
def reporte_deudas(request):
    return redirect('dashboard')