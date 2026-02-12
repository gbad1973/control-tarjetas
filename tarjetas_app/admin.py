# tarjetas_app/admin.py
from django.contrib import admin
from .models import Persona, Tarjeta, Establecimiento, Movimiento

# ==============================================
# CLASE PARA OCULTAR MODELOS DEL MENÚ IZQUIERDO
# ==============================================
class HiddenModelAdmin(admin.ModelAdmin):
    # Esto oculta el modelo del menú lateral izquierdo
    def has_module_permission(self, request):
        return False

# ==============================================
# PERSONAS (OCULTO DEL MENÚ)
# ==============================================
@admin.register(Persona)
class PersonaAdmin(HiddenModelAdmin):
    list_display = ('nombre', 'activo', 'email', 'telefono', 'fecha_registro')
    list_filter = ('activo',)
    search_fields = ('nombre', 'email', 'telefono')
    list_editable = ('activo',)
    
    # Pero SI puede accederse si se conoce la URL directa
    # Para bloquear completamente, cambia esto a:
    # def has_add_permission(self, request):
    #     return False
    # def has_change_permission(self, request):
    #     return False
    # def has_delete_permission(self, request):
    #     return False

# ==============================================
# TARJETAS (VISIBLE PERO CON TEMPLATE LIMPIO)
# ==============================================
@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    list_display = ('banco', 'numero_formateado', 'limite_credito', 'saldo_actual', 
                   'saldo_disponible', 'activa', 'fecha_vencimiento_pago')
    list_filter = ('banco', 'activa', 'fecha_vencimiento_pago')
    search_fields = ('numero', 'banco')
    filter_horizontal = ('usuarios',)
    
    # Template personalizado SIN barra lateral
    change_form_template = 'admin/tarjetas_app/tarjeta/change_form.html'
    add_form_template = 'admin/tarjetas_app/tarjeta/change_form.html'
    
    def numero_formateado(self, obj):
        return f"****{obj.numero[-4:]}"
    numero_formateado.short_description = "Número"

# ==============================================
# ESTABLECIMIENTOS (OCULTO DEL MENÚ)
# ==============================================
@admin.register(Establecimiento)
class EstablecimientoAdmin(HiddenModelAdmin):
    list_display = ('nombre', 'porcentaje_cashback', 'activo')
    list_filter = ('activo', 'porcentaje_cashback')
    search_fields = ('nombre', 'descripcion')

# ==============================================
# MOVIMIENTOS (OCULTO DEL MENÚ)
# ==============================================
@admin.register(Movimiento)
class MovimientoAdmin(HiddenModelAdmin):
    list_display = ('fecha', 'tarjeta', 'persona', 'establecimiento', 'tipo', 'monto', 'monto_cashback')
    list_filter = ('tipo', 'fecha', 'tarjeta', 'persona')
    search_fields = ('descripcion', 'persona__nombre', 'establecimiento__nombre')
    date_hierarchy = 'fecha'

# ==============================================
# OPCIONAL: También oculta Grupos y Usuarios si quieres
# ==============================================
from django.contrib.auth.models import Group, User

# Para ocultar Grupos:
class GroupAdmin(HiddenModelAdmin):
    pass

# Para ocultar Usuarios:
class UserAdmin(HiddenModelAdmin):
    pass

# Desregistra y vuelve a registrar para aplicar el ocultamiento
admin.site.unregister(Group)
admin.site.unregister(User)
admin.site.register(Group, GroupAdmin)
admin.site.register(User, UserAdmin)