from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0003_product_out_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='series_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='product',
            name='is_bundle',
            field=models.BooleanField(default=False),
        ),
    ]
