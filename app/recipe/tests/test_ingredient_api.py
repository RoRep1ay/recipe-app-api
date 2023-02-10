from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient

from recipe.serializers import IngredientSerializer

INGREDIENTS_URL = reverse('recipe:ingredient-list')

def create_user(email='user@example.com', password='123test'):
    return get_user_model().objects.create_user(email=email, password=password)

def detail_url(ingredient_id):
    return reverse('recipe:ingredient-detail', args=[ingredient_id])

class PublicIngredientAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
    

    def test_auth_required(self):
        res = self.client.get(INGREDIENTS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
    
class PrivateIngredientAPITestCase(TestCase):

    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(user=self.user)
    
    def test_retrieve_ingredients(self):
        Ingredient.objects.create(user=self.user, name='Sugar')
        Ingredient.objects.create(user=self.user, name='Salt')
        res = self.client.get(INGREDIENTS_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        ingredients = Ingredient.objects.all().order_by('-name')
        serializer = IngredientSerializer(ingredients, many=True,)
        self.assertEqual(res.data, serializer.data)
    
    def test_ingredient_limited_by_user(self):
        user = create_user('user2@exapmle.com',)
        Ingredient.objects.create(user=user, name='Salt')

        ingredient = Ingredient.objects.create(user=self.user, name='Sugar')
        res = self.client.get(INGREDIENTS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['name'], ingredient.name)
        self.assertEqual(res.data[0]['id'], ingredient.id)
    
    def test_update_ingredient(self):
        ingredient = Ingredient.objects.create(user=self.user, name='Sugar')

        url = detail_url(ingredient.id)
        payload = {'name': 'Salt'}
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        ingredient.refresh_from_db()

        self.assertEqual(payload['name'], ingredient.name)
    
    def test_delete_ingredient(self):
        ingredient = Ingredient.objects.create(user=self.user, name='To be deleted')
        url = detail_url(ingredient_id=ingredient.id)
        res = self.client.delete(url,)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        ingredients = Ingredient.objects.filter(user=self.user)
        self.assertFalse(ingredients.exists())

