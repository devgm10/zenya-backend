from django.urls import path
from core.views import StatusView, CountryView

urlpatterns = [
    # ---------- Status urls ----------
    path('status/list/', StatusView.as_view()),           # GET → all
    path('status/list/<uuid:pk>', StatusView.as_view()),  # GET → one specific record
    path('status/save/', StatusView.as_view()),           # POST → create
    path('status/update/', StatusView.as_view()),         # PUT → update

    # ---------- Country urls ----------
    path('country/list/', CountryView.as_view()),           # GET → all
    path('country/list/<uuid:pk>', CountryView.as_view()),  # GET → one specific record
    path('country/save/', CountryView.as_view()),           # POST → create
    path('country/update/', CountryView.as_view()),         # PUT → update
]