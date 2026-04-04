from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0028_posttag'),
    ]

    operations = [
        migrations.AddField(
            model_name='posttag',
            name='is_read',
            field=models.BooleanField(default=False),
        ),
    ]
