from django.db import models
from django.contrib.auth.models import User
import uuid

class Repository(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='repositories', null=True, blank=True)
    github_url = models.URLField(max_length=500)
    summary = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.github_url

class FileChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='chunks')
    file_name = models.CharField(max_length=255)
    chunk_text = models.TextField()
    # vector_embedding will be added when we setup pgvector in PostgreSQL
    
    def __str__(self):
        return f"{self.repository.github_url} - {self.file_name}"

class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='chats')
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat for {self.repository.github_url} at {self.created_at}"
