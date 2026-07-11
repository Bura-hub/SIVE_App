from django.db import migrations


class Migration(migrations.Migration):
    """
    Índice único parcial case-insensitive sobre auth_user.email para cerrar el
    TOCTOU del registro (dos cuentas con el mismo correo por carrera SELECT+INSERT).

    - LOWER(email): el correo es único sin distinguir mayúsculas.
    - WHERE email <> '': no aplica a cuentas sin correo (email en blanco), que el
      modelo User de Django permite.
    - IF NOT EXISTS: idempotente.

    Si al aplicar fallara por correos duplicados YA existentes en la BD, NO se borran
    datos: la migración fallará y hay que limpiar/normalizar esos correos primero
    (p. ej. corregir los duplicados en el admin) y volver a migrar.
    """

    dependencies = [
        ('authentication', '0003_authtoken_refresh_token'),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS auth_user_email_ci_uniq "
                "ON auth_user (LOWER(email)) WHERE email <> '';",
            reverse_sql="DROP INDEX IF EXISTS auth_user_email_ci_uniq;",
        ),
    ]
