# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta

class Persona(models.Model):
    """Personas que usan las tarjetas"""
    nombre = models.CharField(max_length=100, verbose_name="Nombre completo")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_registro = models.DateField(auto_now_add=True, verbose_name="Fecha de registro")
    email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    
    class Meta:
        verbose_name = "Persona"
        verbose_name_plural = "Personas"
        ordering = ['nombre']
    
    def __str__(self):
        return f"{self.nombre} ({'Activo' if self.activo else 'Inactivo'})"
    
    def deuda_total(self):
        """Calcula la deuda total de esta persona en todas las tarjetas"""
        total = 0
        for movimiento in self.movimientos.filter(tipo__in=['COMPRA', 'COMISION', 'INTERES']):
            total += movimiento.monto
        for movimiento in self.movimientos.filter(tipo__in=['PAGO', 'CASHBACK']):
            total -= movimiento.monto
        return max(total, 0)


class Tarjeta(models.Model):
    """Tarjetas de crédito"""
    TIPO_CHOICES = [
        ('VISA', 'Visa'),
        ('MASTERCARD', 'MasterCard'),
        ('AMEX', 'American Express'),
        ('OTRO', 'Otro'),
    ]
    
    numero = models.CharField(max_length=19, unique=True, verbose_name="Número de tarjeta")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='VISA', verbose_name="Tipo de tarjeta")
    banco = models.CharField(max_length=100, verbose_name="Nombre del banco")
    titular = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name='tarjetas_titular', verbose_name="Titular principal", null=True, blank=True)
    # fecha_vencimiento_pago = models.IntegerField(help_text="Día del mes (1-31) para el pago")
    fecha_vencimiento_pago = models.IntegerField(help_text="Día del mes (1-31) para el pago",default=15)  # ← VALOR POR DEFECTO)
    
    # 🔴 CORREGIDO: Este campo ahora acepta NULL y tiene valor por defecto
    fecha_vencimiento_tarjeta = models.DateField(
        verbose_name="Fecha de vencimiento de la tarjeta (MM/AA)",
        null=True,  # 🔴 PERMITIR NULL TEMPORALMENTE
        blank=True,  # 🔴 PERMITIR VACÍO EN FORMULARIOS
        default=date.today() + timedelta(days=365*3),  # 🔴 VALOR POR DEFECTO: 3 años
        help_text="Formato: MM/AA (Ej: 12/25 para Diciembre 2025)"
    )
    
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Límite de crédito", default=0)
    saldo_actual = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Saldo actual", default=0)
    usuarios = models.ManyToManyField(Persona, verbose_name="Personas que la usan")
    activa = models.BooleanField(default=True, verbose_name="Tarjeta activa")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    
    class Meta:
        verbose_name = "Tarjeta"
        verbose_name_plural = "Tarjetas"
        ordering = ['banco', 'numero']
    
    def __str__(self):
        return f"{self.banco} - ****{self.numero[-4:]}"
    
    def saldo_disponible(self):
        """Calcula el saldo disponible en la tarjeta"""
        return self.limite_credito - self.saldo_actual
    
    def actualizar_saldo(self):
        """Actualiza el saldo actual sumando todos los movimientos"""
        from django.db.models import Sum
        cargos = self.movimientos.filter(tipo__in=['COMPRA', 'COMISION', 'INTERES']).aggregate(
            total=Sum('monto'))['total'] or 0
        abonos = self.movimientos.filter(tipo__in=['PAGO', 'CASHBACK']).aggregate(
            total=Sum('monto'))['total'] or 0
        self.saldo_actual = cargos - abonos
        self.save()


class Establecimiento(models.Model):
    """Establecimientos donde se hacen compras"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre del establecimiento")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    porcentaje_cashback = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name="Porcentaje de cashback (%)"
    )
    activo = models.BooleanField(default=True, verbose_name="Activo")
    
    class Meta:
        verbose_name = "Establecimiento"
        verbose_name_plural = "Establecimientos"
        ordering = ['nombre']
    
    def __str__(self):
        cashback = f" ({self.porcentaje_cashback}% CB)" if self.porcentaje_cashback > 0 else ""
        return f"{self.nombre}{cashback}"


class Movimiento(models.Model):
    """Movimientos de las tarjetas (cargos y abonos)"""
    TIPO_CHOICES = [
        ('COMPRA', 'Compra'),
        ('PAGO', 'Pago'),
        ('COMISION', 'Comisión'),
        ('INTERES', 'Interés'),
        ('CASHBACK', 'Cashback'),
    ]
       
    tarjeta = models.ForeignKey(Tarjeta, on_delete=models.CASCADE, related_name='movimientos', verbose_name="Tarjeta")
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name='movimientos', verbose_name="Persona")
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.CASCADE, verbose_name="Establecimiento",null=True,blank=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name="Tipo de movimiento")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto")
    monto_cashback = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=0,
        verbose_name="Cashback generado"
    )
    descripcion = models.TextField(verbose_name="Descripción")
    fecha = models.DateField(verbose_name="Fecha del movimiento")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    
    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-fecha', '-fecha_registro']
    
    def __str__(self):
        return f"{self.get_tipo_display()} - ${self.monto} - {self.persona.nombre}"
    
    def calcular_cashback(self):
        """Calcula automáticamente el cashback si es una compra"""
        if self.tipo == 'COMPRA' and self.establecimiento.porcentaje_cashback > 0:
            return (self.monto * self.establecimiento.porcentaje_cashback) / 100
        return 0
    
    def save(self, *args, **kwargs):
        # Calcular cashback automáticamente al guardar
        if self.tipo == 'COMPRA':
            self.monto_cashback = self.calcular_cashback()
        
        # Actualizar saldo de la tarjeta
        super().save(*args, **kwargs)
        self.tarjeta.actualizar_saldo()
    
    def es_cargo(self):
        """Determina si es un cargo (compra, comisión, interés)"""
        return self.tipo in ['COMPRA', 'COMISION', 'INTERES']
    
    def es_abono(self):
        """Determina si es un abono (pago, cashback)"""
        return self.tipo in ['PAGO', 'CASHBACK']
    
    @property
    def saldo_pendiente(self):
        """Calcula el saldo pendiente si es una compra"""
        if self.tipo not in ['COMPRA', 'COMISION', 'INTERES']:
            return 0
        total_pagado = self.pagos_recibidos.aggregate(total=models.Sum('monto_aplicado'))['total'] or 0
        return self.monto - total_pagado
    
    
    
    
class PagoCompra(models.Model):
    """Relaciona un pago con una compra y guarda el monto aplicado"""
    pago = models.ForeignKey('Movimiento', on_delete=models.CASCADE, related_name='pagos_a_compras')
    compra = models.ForeignKey('Movimiento', on_delete=models.CASCADE, related_name='pagos_recibidos')
    monto_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('pago', 'compra')
        verbose_name = "Pago aplicado a compra"
        verbose_name_plural = "Pagos aplicados a compras"

    def __str__(self):
        return f"Pago {self.pago.id} → ${self.monto_aplicado} a compra {self.compra.id}"