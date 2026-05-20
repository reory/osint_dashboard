# Give webhooks web addresses so FastAPI knows where to send the data.
# Add Dashboard routes

from django.urls import path
from . import views

urlpatterns = [
    # UI Pages
    path("", views.dashboard_home, name="dashboard_home"),
    path("scan/trigger/", views.trigger_scan, name="trigger_scan"),
    path("results/<int:search_id>/", views.view_results, name="view_results"),
    path("history/clear", views.clear_history, name="clear_history"),

    # Background webhooks
    path("webhook/status/", views.webhook_update_status, name="webhook_update_status"),
    path("webhook/result/", views.webhook_receive_result, name="webhook_receive_result"),
]