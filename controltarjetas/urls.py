# controltarjetas/urls.py
from django.contrib import admin
from django.urls import path
from tarjetas_app import views
from tarjetas_app.views_api import api_personas_tarjeta

urlpatterns = [
    path('admin/', admin.site.urls),
    path('tarjetas/api/personas/<int:tarjeta_id>/', api_personas_tarjeta, name='api_personas_tarjeta'),
    
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('crear-admin/', views.crear_usuario_admin, name='crear_admin'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Detalle de persona (agregar esta función)
    path('persona/<int:persona_id>/', views.detalle_persona, name='detalle_persona'),
    path('persona/<int:persona_id>/tarjeta/<int:tarjeta_id>/', views.detalle_persona, name='detalle_persona_tarjeta'),
    path('api/compras/<int:persona_id>/', views.compras_por_persona, name='compras_por_persona'),
    


    # Listas
    path('personas/', views.lista_personas, name='lista_personas'),
    path('tarjetas/', views.lista_tarjetas, name='lista_tarjetas'),
    path('establecimientos/', views.lista_establecimientos, name='lista_establecimientos'),
    path('movimientos/', views.lista_movimientos, name='lista_movimientos'),
    
    # Formularios NUEVOS
    path('personas/nueva/', views.nueva_persona, name='nueva_persona'),
    path('tarjetas/nueva/', views.nueva_tarjeta, name='nueva_tarjeta'),
    path('establecimientos/nuevo/', views.nuevo_establecimiento, name='nuevo_establecimiento'),
    path('movimientos/nuevo/', views.nuevo_movimiento, name='nuevo_movimiento'),
    
    # EDITAR Y ELIMINAR
    path('tarjetas/editar/<int:tarjeta_id>/', views.editar_tarjeta, name='editar_tarjeta'),
    path('tarjetas/eliminar/<int:tarjeta_id>/', views.eliminar_tarjeta, name='eliminar_tarjeta'),
    path('personas/editar/<int:persona_id>/', views.editar_persona, name='editar_persona'),
    path('personas/eliminar/<int:persona_id>/', views.eliminar_persona, name='eliminar_persona'),
    path('establecimientos/editar/<int:establecimiento_id>/', views.editar_establecimiento, name='editar_establecimiento'),
    path('establecimientos/eliminar/<int:establecimiento_id>/', views.eliminar_establecimiento, name='eliminar_establecimiento'),
    path('movimientos/editar/<int:movimiento_id>/', views.editar_movimiento, name='editar_movimiento'),
    path('movimientos/eliminar/<int:movimiento_id>/', views.eliminar_movimiento, name='eliminar_movimiento'),
    
    # Reportes (agregar estas funciones o mantener redirecciones)
    path('reportes/cashback/persona/<int:persona_id>/', views.reporte_cashback_persona, name='reporte_cashback_persona'),
    path('reportes/cashback/', views.reporte_cashback_general, name='reporte_cashback_general'),
    path('reportes/deudas/', views.reporte_deudas, name='reporte_deudas'),
    path('tarjeta/<int:tarjeta_id>/movimientos/', views.movimientos_tarjeta, name='movimientos_tarjeta'),
]