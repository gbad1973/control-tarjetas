
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Q, Prefetch
from datetime import date, datetime, timedelta
from .models import Persona, Tarjeta, Establecimiento, Movimiento, PagoCompra, LiberacionMensualidad
from .forms import PersonaForm, TarjetaForm, EstablecimientoForm, MovimientoForm, PagoCompraFormSet
from django.contrib import messages
from django.http import JsonResponse
from django.db import models
from itertools import chain
from operator import attrgetter
from decimal import Decimal
from django.core.paginator import Paginator


import csv
from django.http import HttpResponse


print("=== ARCHIVO views.py CARGADO CORRECTAMENTE ===")

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
    from django.db.models import Sum
    
    tarjetas = Tarjeta.objects.filter(activa=True)
    tarjeta_id = request.GET.get('tarjeta')
    
    # Seleccionar tarjeta
    tarjeta_seleccionada = None
    if tarjeta_id:
        tarjeta_seleccionada = get_object_or_404(Tarjeta, id=tarjeta_id)
    elif tarjetas.exists():
        tarjeta_seleccionada = tarjetas.first()
    
    personas = []
    saldo_total_tarjeta = 0
    
    if tarjeta_seleccionada:
        usuarios = tarjeta_seleccionada.usuarios.filter(activo=True)
        for persona in usuarios:
            # Calcular deuda de la persona
            deuda_persona = 0
            
            # Compras normales pendientes
            compras = Movimiento.objects.filter(
                persona=persona,
                tarjeta=tarjeta_seleccionada,
                tipo='COMPRA',
                es_a_meses=False
            )
            for c in compras:
                pagado = c.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
                saldo = c.monto - pagado
                if saldo > 0:
                    deuda_persona += saldo
            
            # Mensualidades pendientes
            mensualidades = Movimiento.objects.filter(
                persona=persona,
                tarjeta=tarjeta_seleccionada,
                tipo='MENSUALIDAD'
            )
            for m in mensualidades:
                pagado = m.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
                saldo = m.monto - pagado
                if saldo > 0:
                    deuda_persona += saldo
            
            # Acumular para saldo total de la tarjeta
            saldo_total_tarjeta += deuda_persona
            
            # Cashback de la persona
            cashback_persona = Movimiento.objects.filter(
                persona=persona,
                tarjeta=tarjeta_seleccionada,
                tipo__in=['COMPRA', 'MENSUALIDAD']
            ).aggregate(total=Sum('monto_cashback'))['total'] or 0
            
            personas.append({
                'id': persona.id,
                'nombre': persona.nombre,
                'activo': persona.activo,
                'saldo_pendiente': deuda_persona,
                'total_movimientos': compras.count(),
                'cashback': cashback_persona,
            })
    
    # Calcular retenciones (mensualidades pendientes de compras a meses)
    retenciones = 0
    compras_meses = Movimiento.objects.filter(
        tarjeta=tarjeta_seleccionada,
        tipo='COMPRA',
        es_a_meses=True
    ) if tarjeta_seleccionada else []
    
    for c in compras_meses:
        # Calcular cuánto falta por pagar de esta compra a meses
        pagado = c.monto_mensual * c.meses_pagados if c.monto_mensual else 0
        pendiente = c.monto - pagado
        retenciones += pendiente
    
    # Totales
    total_limite = tarjeta_seleccionada.limite_credito if tarjeta_seleccionada else 0
    total_disponible = total_limite - saldo_total_tarjeta - retenciones
    total_cashback = Movimiento.objects.filter(
        tarjeta=tarjeta_seleccionada,
        tipo__in=['COMPRA', 'MENSUALIDAD']
    ).aggregate(total=Sum('monto_cashback'))['total'] or 0 if tarjeta_seleccionada else 0
    
    context = {
        'personas': personas,
        'tarjetas': tarjetas,
        'tarjeta_seleccionada': tarjeta_seleccionada,
        'total_limite': total_limite,
        'total_saldo': saldo_total_tarjeta,
        'total_disponible': total_disponible,
        'total_movimientos': Movimiento.objects.filter(tarjeta=tarjeta_seleccionada).count() if tarjeta_seleccionada else 0,
        'total_cashback': total_cashback,
        'retenciones': retenciones,
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

# ========== NUEVO MOVIMIENTO ==========

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
            
            if movimiento.tipo == 'COMPRA':
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
                
                if movimiento.establecimiento and movimiento.establecimiento.porcentaje_cashback > 0:
                    porcentaje = movimiento.establecimiento.porcentaje_cashback / 100
                    movimiento.monto_cashback = movimiento.monto * porcentaje
                else:
                    movimiento.monto_cashback = 0
            
            if movimiento.tipo != 'COMPRA':
                movimiento.establecimiento = None
            
            movimiento.save()
            print(f"✅ Movimiento guardado con ID: {movimiento.id}")

            # ===== SI ES UN PAGO, PROCESAR RELACIONES =====
            if movimiento.tipo == 'PAGO':
                compras_ids = []
                montos_aplicados = []
                
                total_forms = int(request.POST.get('pagos-TOTAL_FORMS', 0))
                for i in range(total_forms):
                    compra_id = request.POST.get(f'pagos-{i}-compra')
                    monto = request.POST.get(f'pagos-{i}-monto_aplicado')
                    delete = request.POST.get(f'pagos-{i}-DELETE', False)
                    
                    if compra_id and monto and not delete:
                        compras_ids.append(compra_id)
                        montos_aplicados.append(monto)
                
                print(f"🔗 IDs de compras a pagar: {compras_ids}")
                print(f"💰 Montos a aplicar: {montos_aplicados}")
                
                if compras_ids and montos_aplicados:
                    monto_total = 0
                    for i, compra_id in enumerate(compras_ids):
                        try:
                            compra = Movimiento.objects.get(id=compra_id)
                            monto_aplicar = Decimal(montos_aplicados[i])
                            
                            # Crear relación
                            PagoCompra.objects.create(
                                pago=movimiento,
                                compra=compra,
                                monto_aplicado=monto_aplicar
                            )
                            print(f"✅ Relación: Pago {movimiento.id} → Compra {compra.id} : ${monto_aplicar}")
                            monto_total += monto_aplicar
                            
                        except Exception as e:
                            print(f"❌ Error: {e}")
                    
                    messages.success(request, f'✅ Pago aplicado a {len(compras_ids)} compra(s)')
                    movimiento.tarjeta.actualizar_saldo()
                else:
                    messages.warning(request, '⚠️ Pago guardado sin compras asociadas')

            messages.success(request, '✅ ¡Movimiento registrado!')
            return redirect('lista_movimientos')
        else:
            print("❌ Formulario inválido")
            return render(request, 'tarjetas_app/nuevo_movimiento.html', {
                'form': form,
                'formset': PagoCompraFormSet(prefix='pagos')
            })
    else:
        form = MovimientoForm()
        formset = PagoCompraFormSet(prefix='pagos')
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

# ========== LISTA MOVIMIENTOS (CORREGIDA Y AGRUPADA) ==========

@login_required
def lista_movimientos(request):
    from django.db.models import Prefetch, Sum, Q
    from django.core.paginator import Paginator
    from django.http import HttpResponse
    
    try:
        # Leer parámetro de límite
        limit = request.GET.get('limit', '50')
        
        # Obtener pagos con sus compras (con manejo de errores)
        pagos = Movimiento.objects.filter(tipo='PAGO').select_related('persona', 'tarjeta').order_by('fecha', 'id')
        
        # Obtener todas las compras
        compras = Movimiento.objects.filter(tipo='COMPRA').select_related('persona', 'tarjeta')
        
        # Obtener todas las mensualidades
        mensualidades = Movimiento.objects.filter(tipo='MENSUALIDAD').select_related('persona', 'tarjeta', 'establecimiento')
        
        # Crear lista de IDs de compras pagadas
        compras_pagadas_ids = set(PagoCompra.objects.values_list('compra_id', flat=True))
        
        # Construir lista final
        movimientos_final = []
        
        # PRIMERO: Compras NO pagadas (excluyendo compras a meses)
        for compra in compras:
            if compra.id not in compras_pagadas_ids and not compra.es_a_meses:
                movimientos_final.append({
                    'id': compra.id,
                    'fecha': compra.fecha,
                    'descripcion': compra.descripcion,
                    'cargo': compra.monto,
                    'abono': None,
                    'persona': compra.persona,
                    'tarjeta': compra.tarjeta,
                    'tipo': 'COMPRA',
                    'is_detalle': False,
                    'monto_aplicado': None
                })
        
        # SEGUNDO: Mensualidades
        for m in mensualidades:
            pagado = PagoCompra.objects.filter(compra=m).aggregate(total=Sum('monto_aplicado'))['total'] or 0
            saldo = m.monto - pagado
            if saldo > 0:
                movimientos_final.append({
                    'id': m.id,
                    'fecha': m.fecha,
                    'descripcion': m.descripcion,
                    'cargo': saldo,
                    'abono': None,
                    'persona': m.persona,
                    'tarjeta': m.tarjeta,
                    'tipo': 'MENSUALIDAD',
                    'is_detalle': False,
                    'monto_aplicado': None
                })
        
        # TERCERO: Pagos con sus compras
        for pago in pagos:
            # Pago principal
            movimientos_final.append({
                'id': pago.id,
                'fecha': pago.fecha,
                'descripcion': pago.descripcion,
                'cargo': None,
                'abono': pago.monto,
                'persona': pago.persona,
                'tarjeta': pago.tarjeta,
                'tipo': 'PAGO',
                'is_detalle': False,
                'monto_aplicado': None,
                'grupo': pago.id
            })
            
            # Detalles de compras pagadas
            detalles = PagoCompra.objects.filter(pago=pago).select_related('compra')
            for pc in detalles:
                movimientos_final.append({
                    'id': pc.compra.id,
                    'fecha': pago.fecha,
                    'descripcion': f"↳ {pc.compra.descripcion} (Aplicado: ${pc.monto_aplicado:.2f})",
                    'cargo': pc.monto_aplicado,
                    'abono': None,
                    'persona': pc.compra.persona,
                    'tarjeta': pc.compra.tarjeta,
                    'tipo': 'COMPRA_PAGADA',
                    'is_detalle': True,
                    'monto_aplicado': pc.monto_aplicado,
                    'grupo': pago.id,
                    'suborden': 1
                })
        
        # ORDENAR
        movimientos_final.sort(key=lambda x: (str(x.get('fecha', '1900-01-01')), x.get('grupo', x.get('id', 0)), x.get('suborden', 0)))
        
        # Calcular totales
        total_cargos = sum(m.get('cargo', 0) for m in movimientos_final if m.get('cargo') and not m.get('is_detalle'))
        total_abonos = sum(m.get('abono', 0) for m in movimientos_final if m.get('abono'))
        saldo = total_cargos - total_abonos
        
        # Filtrar por búsqueda
        buscar = request.GET.get('buscar')
        tipo = request.GET.get('tipo')
        persona_id = request.GET.get('persona')
        tarjeta_id = request.GET.get('tarjeta')
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        
        movimientos_filtrados = []
        for m in movimientos_final:
            incluir = True
            if buscar and buscar.lower() not in m.get('descripcion', '').lower() and (not m.get('persona') or buscar.lower() not in m['persona'].nombre.lower()):
                incluir = False
            if incluir and tipo and tipo != '' and m.get('tipo') != tipo:
                incluir = False
            if incluir and persona_id and persona_id != '' and (not m.get('persona') or str(m['persona'].id) != persona_id):
                incluir = False
            if incluir and tarjeta_id and tarjeta_id != '' and (not m.get('tarjeta') or str(m['tarjeta'].id) != tarjeta_id):
                incluir = False
            if incluir and fecha_desde and m.get('fecha') and str(m['fecha']) < fecha_desde:
                incluir = False
            if incluir and fecha_hasta and m.get('fecha') and str(m['fecha']) > fecha_hasta:
                incluir = False
            if incluir:
                movimientos_filtrados.append(m)
        
        # Aplicar límite
        if limit == 'todos':
            movimientos_mostrar = movimientos_filtrados
            limite_usado = 'todos'
        else:
            try:
                limit_int = int(limit)
                movimientos_mostrar = movimientos_filtrados[:limit_int]
                limite_usado = limit_int
            except:
                movimientos_mostrar = movimientos_filtrados[:50]
                limite_usado = 50
        
        personas = Persona.objects.filter(activo=True)
        tarjetas = Tarjeta.objects.filter(activa=True)
        
        context = {
            'movimientos': movimientos_mostrar,
            'personas': personas,
            'tarjetas': tarjetas,
            'total_cargos': total_cargos,
            'total_abonos': total_abonos,
            'saldo': saldo,
            'limite_actual': limite_usado,
            'total_movimientos_filtrados': len(movimientos_filtrados),
        }
        return render(request, 'tarjetas_app/lista_movimientos.html', context)
    
    except Exception as e:
        import traceback
        return HttpResponse(f"Error en lista_movimientos: {str(e)}<br><br><pre>{traceback.format_exc()}</pre>")


   
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

# ========== DETALLE PERSONA (CORREGIDO CON MENSUALIDADES) ==========

@login_required
def detalle_persona(request, persona_id):
    from django.db.models import Sum, Prefetch
    from decimal import Decimal
    
    persona = get_object_or_404(Persona, id=persona_id)
    tarjetas = Tarjeta.objects.filter(usuarios=persona)
    tarjeta_id = request.GET.get('tarjeta')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    # Obtener todas las compras de la persona (excluyendo compras a meses)
    compras = Movimiento.objects.filter(
        persona=persona,
        tipo='COMPRA',
        es_a_meses=False
    ).select_related('tarjeta', 'establecimiento').order_by('fecha')
    
    # Obtener todas las mensualidades de la persona
    mensualidades = Movimiento.objects.filter(
        persona=persona,
        tipo='MENSUALIDAD'
    ).select_related('tarjeta', 'establecimiento').order_by('fecha')
    
    # Obtener todos los pagos de la persona con sus relaciones
    pagos = Movimiento.objects.filter(
        persona=persona,
        tipo='PAGO'
    ).prefetch_related(
        Prefetch('pagos_a_compras', queryset=PagoCompra.objects.select_related('compra'))
    ).select_related('tarjeta').order_by('fecha')
    
    # Aplicar filtros
    if tarjeta_id:
        compras = compras.filter(tarjeta_id=tarjeta_id)
        mensualidades = mensualidades.filter(tarjeta_id=tarjeta_id)
        pagos = pagos.filter(tarjeta_id=tarjeta_id)
    if fecha_desde:
        compras = compras.filter(fecha__gte=fecha_desde)
        mensualidades = mensualidades.filter(fecha__gte=fecha_desde)
        pagos = pagos.filter(fecha__gte=fecha_desde)
    if fecha_hasta:
        compras = compras.filter(fecha__lte=fecha_hasta)
        mensualidades = mensualidades.filter(fecha__lte=fecha_hasta)
        pagos = pagos.filter(fecha__lte=fecha_hasta)
    
    # Construir lista de movimientos
    movimientos = []
    
    # PRIMERO: Agregar compras con saldo pendiente
    for compra in compras:
        total_pagado = compra.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
        saldo = compra.monto - total_pagado
        if saldo > 0:
            movimientos.append({
                'tipo': 'COMPRA_PENDIENTE',  # ← CORREGIDO
                'id': compra.id,
                'fecha': compra.fecha,
                'descripcion': compra.descripcion,
                'monto': compra.monto,
                'saldo': saldo,
                'tarjeta': compra.tarjeta,
                'establecimiento': compra.establecimiento.nombre if compra.establecimiento else '',
                'cashback': compra.monto_cashback,
            })
    
    # SEGUNDO: Agregar mensualidades con saldo pendiente
    for m in mensualidades:
        pagado = m.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0
        saldo = m.monto - pagado
        if saldo > 0:
            movimientos.append({
                'tipo': 'MENSUALIDAD',
                'id': m.id,
                'fecha': m.fecha,
                'descripcion': m.descripcion,
                'monto': m.monto,
                'saldo': saldo,
                'tarjeta': m.tarjeta,
                'establecimiento': m.establecimiento.nombre if m.establecimiento else '',
                'cashback': m.monto_cashback,
            })
    
    # TERCERO: Agregar pagos con sus compras pagadas
    for pago in pagos:
        # Pago principal
        item_pago = {
            'tipo': 'PAGO',
            'id': pago.id,
            'fecha': pago.fecha,
            'descripcion': pago.descripcion,
            'monto': pago.monto,
            'tarjeta': pago.tarjeta,
            'detalles': []
        }
        
        # Compras pagadas por este pago
        for pc in pago.pagos_a_compras.all():
            item_pago['detalles'].append({
                'tipo': 'COMPRA_PAGADA',
                'id': pc.compra.id,
                'descripcion': pc.compra.descripcion,
                'monto': pc.monto_aplicado,
                'monto_aplicado': pc.monto_aplicado,
                'tarjeta': pc.compra.tarjeta,
                'establecimiento': pc.compra.establecimiento.nombre if pc.compra.establecimiento else '',
                'cashback': pc.compra.monto_cashback,
                'fecha': pc.compra.fecha,
            })
        
        movimientos.append(item_pago)
    
    # Ordenar por fecha
    #movimientos.sort(key=lambda x: x['fecha'])
    movimientos.sort(key=lambda x: x['fecha'])
    
    # Obtener compras a meses (para el botón de cargar mensualidades)
    compras_meses = Movimiento.objects.filter(
        persona=persona,
        tipo='COMPRA',
        es_a_meses=True
    ).order_by('fecha')
    
    if tarjeta_id:
        compras_meses = compras_meses.filter(tarjeta_id=tarjeta_id)
    
    # Tarjeta seleccionada
    tarjeta_seleccionada = None
    if tarjeta_id:
        tarjeta_seleccionada = get_object_or_404(Tarjeta, id=tarjeta_id)
    
    context = {
        'persona': persona,
        'tarjetas': tarjetas,
        'tarjeta_seleccionada': tarjeta_seleccionada,
        'movimientos_agrupados': movimientos,
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

# ========== CARGA MENSUALIDAD ==========
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

# ==========. ESTO ES PARA EXPORTAR A  EXCEL. ======================

def exportar_excel_movimientos(request, persona_id=None):
    """Exporta movimientos a Excel (formato CSV)"""
    if persona_id:
        persona = get_object_or_404(Persona, id=persona_id)
        movimientos = Movimiento.objects.filter(persona=persona).order_by('-fecha')
        nombre_archivo = f"movimientos_{persona.nombre.replace(' ', '_')}.csv"
    else:
        movimientos = Movimiento.objects.all().order_by('-fecha')
        nombre_archivo = "movimientos_todos.csv"
    
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    
    writer = csv.writer(response)
    
    # Cabeceras
    writer.writerow(['ID', 'Fecha', 'Tipo', 'Descripción', 'Monto', 'Cashback', 'Persona', 'Tarjeta', 'Establecimiento'])
    
    # Datos
    for m in movimientos:
        writer.writerow([
            m.id,
            m.fecha.strftime('%d/%m/%Y'),
            m.get_tipo_display(),
            m.descripcion,
            f"{m.monto:.2f}",
            f"{m.monto_cashback:.2f}" if m.monto_cashback else '0.00',
            m.persona.nombre,
            f"{m.tarjeta.banco} - ****{m.tarjeta.numero[-4:]}",
            m.establecimiento.nombre if m.establecimiento else ''
        ])
    
    return response

# ================= CONTROL DE COMPRAS A MESES.  ========================

@login_required
def reporte_compras_meses(request):
    """Reporte de compras a meses con su estado y mensualidades"""
    from django.db.models import Sum
    
    compras_meses = Movimiento.objects.filter(
        tipo='COMPRA',
        es_a_meses=True
    ).select_related('persona', 'tarjeta', 'establecimiento').order_by('fecha')
    
    reporte = []
    total_general = 0
    total_pagado_general = 0
    total_pendiente_general = 0
    
    for c in compras_meses:
        # Calcular mensualidades generadas
        mensualidades = Movimiento.objects.filter(
            tipo='MENSUALIDAD',
            descripcion__icontains=f"compra {c.id}"
        ).order_by('fecha')
        
        monto_mensual = c.monto / c.numero_meses
        total_mensualidades = mensualidades.count()
        monto_pagado = monto_mensual * total_mensualidades
        monto_pendiente = c.monto - monto_pagado
        
        # Obtener detalles de cada mensualidad
        detalle_mensualidades = []
        for i, m in enumerate(mensualidades, 1):
            detalle_mensualidades.append({
                'numero': i,
                'monto': m.monto,
                'pagado': m.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0,
                'saldo': m.monto - (m.pagos_recibidos.aggregate(total=Sum('monto_aplicado'))['total'] or 0)
            })
        
        reporte.append({
            'id': c.id,
            'fecha': c.fecha,
            'descripcion': c.descripcion,
            'persona': c.persona,
            'tarjeta': c.tarjeta,
            'establecimiento': c.establecimiento.nombre if c.establecimiento else '-',
            'monto_total': c.monto,
            'numero_meses': c.numero_meses,
            'monto_mensual': monto_mensual,
            'mensualidades_generadas': total_mensualidades,
            'mensualidades_pendientes': c.numero_meses - total_mensualidades,
            'monto_pagado': monto_pagado,
            'monto_pendiente': monto_pendiente,
            'porcentaje_completado': (total_mensualidades / c.numero_meses) * 100 if c.numero_meses > 0 else 0,
            'detalle_mensualidades': detalle_mensualidades,
        })
        
        total_general += c.monto
        total_pagado_general += monto_pagado
        total_pendiente_general += monto_pendiente
    
    context = {
        'reporte': reporte,
        'total_general': total_general,
        'total_pagado_general': total_pagado_general,
        'total_pendiente_general': total_pendiente_general,
        'total_compras': len(reporte),
    }
    return render(request, 'tarjetas_app/reporte_compras_meses.html', context)

# ========== REPORTES ==========
@login_required
def reporte_cashback(request):
    """Reporte de cashback agrupado por porcentaje (ordenado de mayor a menor)"""
    from django.db.models import Sum
    
    # Reporte por porcentaje
    reporte_porcentaje = {}
    
    # Compras normales (NO a meses)
    compras = Movimiento.objects.filter(
        tipo='COMPRA',
        es_a_meses=False,
        establecimiento__isnull=False,
        establecimiento__porcentaje_cashback__gt=0
    ).select_related('establecimiento')
    
    for c in compras:
        pct = c.establecimiento.porcentaje_cashback
        if pct not in reporte_porcentaje:
            reporte_porcentaje[pct] = {
                'monto_total': 0,
                'cashback': 0,
            }
        reporte_porcentaje[pct]['monto_total'] += c.monto
        reporte_porcentaje[pct]['cashback'] += c.monto_cashback
    
    # Mensualidades
    mensualidades = Movimiento.objects.filter(
        tipo='MENSUALIDAD',
        establecimiento__isnull=False,
        establecimiento__porcentaje_cashback__gt=0
    ).select_related('establecimiento')
    
    for m in mensualidades:
        pct = m.establecimiento.porcentaje_cashback
        if pct not in reporte_porcentaje:
            reporte_porcentaje[pct] = {
                'monto_total': 0,
                'cashback': 0,
            }
        reporte_porcentaje[pct]['monto_total'] += m.monto
        reporte_porcentaje[pct]['cashback'] += m.monto_cashback
    
    # Ordenar de mayor a menor porcentaje
    reporte_porcentaje_ordenado = []
    for pct in sorted(reporte_porcentaje.keys(), reverse=True):
        data = reporte_porcentaje[pct]
        reporte_porcentaje_ordenado.append({
            'porcentaje': pct,
            'monto_total': data['monto_total'],
            'cashback': data['cashback'],
        })
    
    # Totales generales
    total_monto = sum(d['monto_total'] for d in reporte_porcentaje_ordenado)
    total_cashback = sum(d['cashback'] for d in reporte_porcentaje_ordenado)
    
    context = {
        'reporte_porcentaje_ordenado': reporte_porcentaje_ordenado,
        'total_monto': total_monto,
        'total_cashback': total_cashback,
    }
    return render(request, 'tarjetas_app/reporte_cashback.html', context)

@login_required 
def reporte_cashback_persona(request, persona_id):
    return redirect('dashboard')

@login_required
def reporte_cashback_general(request):
    return redirect('dashboard')

@login_required
def reporte_deudas(request):
    return redirect('dashboard')