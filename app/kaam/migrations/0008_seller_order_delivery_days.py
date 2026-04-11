from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kaam', '0007_seller_commerce_settings_and_return_amounts'),
    ]

    operations = [
        migrations.AddField(
            model_name='seller',
            name='order_delivery_days',
            field=models.PositiveSmallIntegerField(default=3),
        ),
    ]
