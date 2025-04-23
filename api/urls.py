from django.urls import path
from .views import (
    DocumentListCreate, 
    DocumentDetail,
    ResultDetail,
)

urlpatterns = [
    path('documents/', DocumentListCreate.as_view(), name='document-list-create'),
    path('documents/<uuid:document_id>/', DocumentDetail.as_view(), name='document-detail'),
    path('documents/<uuid:document_id>/result/', ResultDetail.as_view(), name='document-result'),
] 