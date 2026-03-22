from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0004_product_series_name_is_bundle'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='layout_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='product',
            name='layout_rank',
            field=models.IntegerField(default=9999),
        ),
        migrations.AddField(
            model_name='product',
            name='sort_priority',
            field=models.IntegerField(default=0),
        ),
    ]
