import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_remove_backup_codes'),
    ]

    operations = [
        migrations.AddField(
            model_name='authtoken',
            name='refresh_token',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='access_tokens',
                to='authentication.refreshtoken',
                verbose_name='Token de refresco emparejado',
            ),
        ),
    ]
