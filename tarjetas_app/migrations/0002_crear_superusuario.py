from django.db import migrations
from django.contrib.auth.hashers import make_password

def crear_superusuario(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    # Verifica si ya existe para no duplicar
    if not User.objects.filter(username='tu_usuario').exists():
        User.objects.create(
            username='tu_usuario',
            email='tu_email@example.com',
            password=make_password('tu_contraseña_segura'),
            is_superuser=True,
            is_staff=True,
            is_active=True
        )

def eliminar_superusuario(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    User.objects.filter(username='tu_usuario').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('tarjetas_app', '0003_alter_tarjeta_fecha_vencimiento_tarjeta'),  # Ajusta el número según tu última migración
    ]

    operations = [
        migrations.RunPython(crear_superusuario, eliminar_superusuario),
    ]