from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kaam', '0007_alter_product_product_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='display_title',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
    ]
