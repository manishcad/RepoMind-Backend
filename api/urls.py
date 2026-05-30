from django.urls import path
from .views import AnalyzeRepoView, ChatRepoView,Home

urlpatterns = [
    path('analyze/', AnalyzeRepoView.as_view(), name='analyze_repo'),
    path('chat/', ChatRepoView.as_view(), name='chat_repo'),
    path('', Home.as_view(), name='chat_repo'),
]
