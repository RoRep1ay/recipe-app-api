from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Tag

from recipe.serializers import TagSerializer

TAGS_URL = reverse('recipe:tag-list')

def create_user(email='test@example.com', password='testpass'):
    return get_user_model().objects.create_user(email, password)

def detail_url(tag_id):
    return reverse('recipe:tag-detail', args=[tag_id])

class PublicTagsAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
    
    def test_auth_required(self):
        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

class PrivateTagAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)
    
    def test_retrieve_tags(self):
        Tag.objects.create(user=self.user, name='Tag1')
        Tag.objects.create(user=self.user, name='Tag2')
        res = self.client.get(TAGS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        tags = Tag.objects.all().order_by('-name')
        serializer = TagSerializer(tags, many=True)
        self.assertEqual(res.data, serializer.data)
    
    def test_tag_limit_for_user(self):
        user2 = create_user(email='test2@example.com')
        Tag.objects.create(user=user2, name='Tag1')
        tag = Tag.objects.create(user=self.user, name='ASD')

        res = self.client.get(TAGS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], tag.name)
        self.assertEqual(res.data[0]['id'], tag.id)
    
    def test_update_tag(self):
        tag = Tag.objects.create(user=self.user, name='Tag1')
        payload = { 'name': 'New Tag' }
        url = detail_url(tag.id)

        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        tag.refresh_from_db()

        self.assertEqual(tag.name, payload['name'])
    
    def test_delete_tag(self):
        tag = Tag.objects.create(user=self.user, name='To be deleted')
        url = detail_url(tag.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tag.objects.filter(id=tag.id).exists())
