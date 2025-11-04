from django.urls import path
from core.views import StatusView, CountryView

urlpatterns = [
    # ---------- Status urls ----------
    path('status/save/', StatusView.as_view()),    # POST → create
    path('status/update/', StatusView.as_view()),  # PUT → update

    # ---------- Country urls ----------
    path('country/save/', CountryView.as_view()),    # POST → create
    path('country/update/', CountryView.as_view()),  # PUT → update
]