from django.apps import AppConfig


class BooksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "books"
    verbose_name = "Verito Tech books"

    def ready(self):
        from django.contrib.auth.models import User
        from django.db.models.signals import post_save

        from books.access import ensure_profile

        def on_user_save(sender, instance, **kwargs):
            if kwargs.get("raw"):
                return
            ensure_profile(instance)

        post_save.connect(on_user_save, sender=User, dispatch_uid="books.ensure_profile")
