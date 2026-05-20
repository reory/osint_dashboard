# This file is Django's core configuration engine to include 
# the new scanner web addresses.

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("scanner.urls")), # Include webhook paths
]
