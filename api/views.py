from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils import clone_and_analyze_repo, chat_with_repo

class AnalyzeRepoView(APIView):
    def post(self, request):
        repo_url = request.data.get('repo_url')
        
        if not repo_url:
            return Response({'error': 'repo_url is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            analysis_result = clone_and_analyze_repo(repo_url)
            return Response({'analysis': analysis_result}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChatRepoView(APIView):
    def post(self, request):
        repo_url = request.data.get('repo_url')
        messages = request.data.get('messages', [])
        
        if not repo_url:
            return Response({'error': 'repo_url is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not messages or len(messages) == 0:
            return Response({'error': 'messages array is required'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            reply = chat_with_repo(repo_url, messages)
            return Response({'reply': reply}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
