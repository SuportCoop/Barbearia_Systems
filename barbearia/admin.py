from django.contrib import admin
from barbearia.models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name",)

