from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0026_remove_order_food_remove_order_food_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='addresto',
            name='is_accepting_orders',
            field=models.BooleanField(default=True),
        ),
    ]
