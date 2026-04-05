from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kaam', '0006_product_product_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='seller',
            name='allow_cod',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='seller',
            name='allow_exchanges',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='seller',
            name='allow_online_payment',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='seller',
            name='allow_refunds',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='order',
            name='return_items_json',
            field=models.TextField(blank=True, default='[]'),
        ),
        migrations.AddField(
            model_name='order',
            name='return_refund_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name='order',
            name='return_exchange_variant',
            field=models.TextField(blank=True),
        ),
    ]
