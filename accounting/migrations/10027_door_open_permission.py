from django.db import migrations, models


def grant_existing_administrators(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")

    content_type, _ = ContentType.objects.get_or_create(
        app_label="accounting", model="dooraccesslog"
    )
    permission, _ = Permission.objects.get_or_create(
        content_type=content_type,
        codename="open_office_door",
        defaults={"name": "Can open the physical office door"},
    )
    administrator, _ = Group.objects.get_or_create(name="Διαχειριστής")
    administrator.permissions.add(permission)
    for user in User.objects.filter(is_superuser=True, is_active=True):
        user.user_permissions.add(permission)


def revoke_migration_grants(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")
    User = apps.get_model("auth", "User")
    permission = Permission.objects.filter(
        content_type__app_label="accounting",
        codename="open_office_door",
    ).first()
    if permission:
        for group in Group.objects.filter(name="Διαχειριστής"):
            group.permissions.remove(permission)
        for user in User.objects.filter(user_permissions=permission):
            user.user_permissions.remove(permission)
        permission.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "10026_voipcalllog_call_set_null"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="dooraccesslog",
            options={
                "ordering": ["-timestamp"],
                "permissions": [
                    ("open_office_door", "Can open the physical office door"),
                ],
                "verbose_name": "Log Πρόσβασης Πόρτας",
                "verbose_name_plural": "Logs Πρόσβασης Πόρτας",
            },
        ),
        migrations.AlterField(
            model_name="dooraccesslog",
            name="result",
            field=models.CharField(
                choices=[
                    ("attempted", "Attempted"),
                    ("success", "Επιτυχία"),
                    ("failed", "Αποτυχία"),
                    ("timeout", "Timeout"),
                    ("offline", "Εκτός Σύνδεσης"),
                    ("denied", "Denied"),
                    ("rate_limited", "Rate limited"),
                ],
                max_length=20,
                verbose_name="Αποτέλεσμα",
            ),
        ),
        migrations.RunPython(
            grant_existing_administrators,
            revoke_migration_grants,
        ),
    ]
