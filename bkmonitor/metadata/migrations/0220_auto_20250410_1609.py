# Generated by Django 3.2.25 on 2025-04-10 08:09

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metadata", "0219_recordrule_bk_tenant_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bkdatastorage",
            name="table_id",
            field=models.CharField(max_length=128, verbose_name="结果表名"),
        ),
        migrations.AlterField(
            model_name="esstorage",
            name="table_id",
            field=models.CharField(max_length=128, verbose_name="结果表名"),
        ),
        migrations.AddField(
            model_name="bkdatastorage",
            name="bk_tenant_id",
            field=models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID"),
        ),
        migrations.AddField(
            model_name="bkdatastorage",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AddField(
            model_name="essnapshotindice",
            name="bk_tenant_id",
            field=models.CharField(default="system", max_length=256, null=True, verbose_name="租户ID"),
        ),
        migrations.AddField(
            model_name="esstorage",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AddField(
            model_name="spacerelatedstorageinfo",
            name="bk_tenant_id",
            field=models.CharField(max_length=128, null=True, verbose_name="租户ID"),
        ),
        migrations.AlterUniqueTogether(
            name="bkdatastorage",
            unique_together={("table_id", "bk_tenant_id")},
        ),
        migrations.AlterUniqueTogether(
            name="esstorage",
            unique_together={("table_id", "bk_tenant_id")},
        ),
        migrations.AlterUniqueTogether(
            name="storageclusterrecord",
            unique_together={("table_id", "cluster_id", "enable_time", "bk_tenant_id")},
        ),
    ]
