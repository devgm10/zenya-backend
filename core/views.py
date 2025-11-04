from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.models import Status, Country
from core.serializers import StatusSerializer, CountrySerializer
from core.utils.generic_crud import GenericCrud

class StatusView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.crud = GenericCrud(
            model=Status,
            serializer_class=StatusSerializer,
            table_name='core_status',
            module_name='STATUS',
            unique_fields=['name_es', 'name_en', 'abbreviation']
        )

    def post(self, request):
        """Create a new status"""
        return self.crud.create(request)

    def put(self, request):
        """Update an existing status (id must come in the body)"""
        return self.crud.update(request)


class CountryView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.crud = GenericCrud(
            model=Country,
            serializer_class=CountrySerializer,
            table_name='core_country',
            module_name='COUNTRY',
            unique_fields=['name_es', 'name_en', 'abbreviation', 'iso_code', 'phone_code']
        )

    def post(self, request):
        """Create a new country"""
        return self.crud.create(request)

    def put(self, request):
        """Update an existing country (id must come in the body)"""
        return self.crud.update(request)