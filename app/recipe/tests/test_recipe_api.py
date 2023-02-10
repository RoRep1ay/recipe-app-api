from decimal import Decimal 

import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APIClient

from core.models import ( Recipe, Tag, Ingredient )
from recipe.serializers import (RecipeSerializer, RecipeDetailSerializer,)


RECIPE_URL = reverse('recipe:recipe-list')

def detail_url(recipe_id):
    return reverse('recipe:recipe-detail', args=[ recipe_id ])

def image_upload_url(recipe_id):
    return reverse('recipe:recipe-upload-image', args=[recipe_id])


def create_recipe(user, **params):
    defaults = {
        'title':'Sample title',
        'time_minutes':22,
        'price':Decimal('2.2'),
        'description':'Sample Description',
        'link':'https://example.com/recipe.pdf',
    }
    defaults.update(params)
    recipe = Recipe.objects.create(user=user, **defaults)
    return recipe

def create_user(**params):
    return get_user_model().objects.create_user(**params)

class PublicRecipeAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
    
    def test_auth_required(self):
        res = self.client.get(RECIPE_URL)

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

class PrivateRecipeAPITest(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(email='test@eaxmple.com', password='testpass123')
        self.client.force_authenticate(self.user)
    
    def test_retrieve_recipes(self):
        create_recipe(user=self.user,)
        create_recipe(user=self.user,)

        res = self.client.get(RECIPE_URL)
        recipes = Recipe.objects.all().order_by('-id')

        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)

    def test_retrieves_list_limited_to_user(self):
        other_user = create_user(email='test2@example.com', password='testpass123')
        create_recipe(user=other_user,)
        create_recipe(user=self.user,)

        res = self.client.get(RECIPE_URL)
        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, serializer.data)
    
    def test_get_detail_url(self):
        recipe = create_recipe(user=self.user)
        url = detail_url(recipe.id)

        res = self.client.get(url)
        serializer = RecipeDetailSerializer(recipe)
        self.assertEqual(res.data, serializer.data)
    
    def test_create_recipe(self):
        payload = {
            'title':'Sample test',
            'time_minutes':22,
            'price':Decimal('2.2'),
            'description':'Sample Description',
            'link':'https://example.com/recipe.pdf',
        }
        res = self.client.post(RECIPE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipe = Recipe.objects.get(id=res.data['id'])
        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        origin_link = 'https://example.com/recipe.pdf'
        recipe = create_recipe(user=self.user, title='Smaple recipe title', link=origin_link)

        payload = { 'title': 'New Recipe title'}
        url = detail_url(recipe_id=recipe.id)
        
        res = self.client.patch(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        
        self.assertEqual(recipe.title, payload['title'])
        self.assertEqual(recipe.link, origin_link)
        self.assertEqual(recipe.user, self.user)
    
    def test_full_update(self):
        recipe = create_recipe(
            user=self.user,
            title='Sample test',
            link='https://example.com/test.pdf',
            description='This is a test',
        )

        payload = {
            'title': 'New Recipe Title',
            'link': 'https://example.com/new.pdf',
            'description':'Haha',
            'time_minutes':10,
            'price': Decimal(10.0),
        }
        
        url = detail_url(recipe.id)
        res = self.client.put(url, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()

        for k, v in payload.items():
            self.assertEqual(getattr(recipe, k), v)
        
        self.assertEqual(recipe.user, self.user)
    
    def test_update_user_return_error(self):
        new_user = create_user(email='user@example.com', password='testpasss')
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)

        payload = {'user': new_user.id}
        res=self.client.patch(url, payload )

        recipe.refresh_from_db()
        self.assertEqual(recipe.user, self.user)

    def test_delete_recipe_successful(self):
        recipe = create_recipe(user=self.user)
        url = detail_url(recipe.id)

        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Recipe.objects.filter(id=recipe.id).exists())
    
    def test_delete_other_recipe_error(self):
        new_user = create_user(email='new2@example.com.', password='123123123')
        recipe = create_recipe(user=new_user)

        url = detail_url(recipe.id)
        res = self.client.delete(url)
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        payload = {
            'title':'curry',
            'time_minutes':'30',
            'price':Decimal(20.0),
            'tags':[{
                'name':'Thai'
            }, { 'name': 'Deinner'}]
        }
        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)

        for tag in payload['tags']:
            exists = recipe.tags.filter(name=tag['name'], user=self.user).exists()
            self.assertTrue(exists)
    
    def test_create_recipe_with_existing_tags(self):
        tag_indian = Tag.objects.create(name='Indian', user=self.user)
        payload = {
            'title': 'Indian Curry',
            'time_minutes': '20',
            'price': Decimal(30),
            'tags': [
                {
                    'name': 'Indian',
                },
                {
                    'name': 'Breakfast',
                },
            ]
        }
        res = self.client.post(RECIPE_URL, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.tags.count(), 2)
        self.assertIn(tag_indian, recipe.tags.all())
        
        for tag in payload['tags']:
            exists = recipe.tags.filter(user=self.user, name=tag['name']).exists()
            self.assertTrue(exists)
    
    def test_create_tag_on_update(self):
        recipe = create_recipe(user=self.user)
        payload = { 'tags': [
            {
                'name': 'hehe',
            },
            {
                'name': 'lol',
            }
        ]}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_tag = Tag.objects.get(user = self.user, name = 'hehe')
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        tag_breakfast = Tag.objects.create(name='breakfast', user=self.user)
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(name='Lunch', user=self.user)
        payload = {
            'tags': [{
                'name': 'Lunch'
            }]
        }
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        tag = Tag.objects.create(name='abc', user=self.user)
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {'tags': []}
        url = detail_url(recipe.id)
        
        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)
    
    def test_create_recipe_with_ingredient(self):
        payload = {
            'title': 'Test',
            'time_minutes': 60,
            'price': Decimal(20.0),
            'ingredients': [
                { 'name': 'Sugar', },
                { 'name': 'Salt', },
            ]
        }

        res = self.client.post(RECIPE_URL, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)

        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(name=ingredient['name'], user=self.user).exists()
            self.assertTrue(exists)

    def test_create_with_recipe_with_existing_ingredient(self):
        ingredient = Ingredient.objects.create(user=self.user, name='Sugar')

        payload = {
            'title': 'Test',
            'time_minutes': 60,
            'price': Decimal(20.0),
            'ingredients': [
                { 'name': 'Sugar', },
                { 'name': 'Salt', },
            ]
        }

        res = self.client.post(RECIPE_URL, data=payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        recipes = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipes.count(), 1)
        recipe = recipes[0]
        self.assertEqual(recipe.ingredients.count(), 2)

        for ingredient in payload['ingredients']:
            exists = recipe.ingredients.filter(name=ingredient['name'], user=self.user).exists()
            self.assertTrue(exists)
    
    def test_create_ingredients_on_update(self):
        recipe = create_recipe(user=self.user)
        payload = {
            'ingredients': [
                {'name': 'Sugar'},
                {'name': 'Salt'},
            ]
        }

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ingredients = Ingredient.objects.filter(user=self.user).order_by('-name').all()

        for ingredient in payload['ingredients']:
            exists = ingredients.filter(name=ingredient['name'],user=self.user).exists()
            self.assertTrue(exists)
    
    def test_update_recipe_assign_ingredient(self):
        recipe = create_recipe(user=self.user)
        ingredient1 = Ingredient.objects.create(name='Sugar', user=self.user)
        recipe.ingredients.add(ingredient1)

        ingredient2 = Ingredient.objects.create(name='Salt', user=self.user)
        payload = {'ingredients': [{'name': 'Salt'}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn(ingredient2, recipe.ingredients.all())
        self.assertNotIn(ingredient1, recipe.ingredients.all())
    
    def test_clear_recipe_ingredients(self):
        ingredient = Ingredient.objects.create(name='Sugar', user=self.user)
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = { 'ingredients': []}
        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        self.assertEqual(recipe.ingredients.count(), 0)
    
    def test_update_same_ingredient_should_not_create_new_ingredient(self):
        ingredient = Ingredient.objects.create(name='Sugar', user=self.user)
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient)

        payload = { 'ingredients': [{'name': 'Sugar'}] }
        url = detail_url(recipe.id)

        res = self.client.patch(url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        recipe.refresh_from_db()
        ingredients = Ingredient.objects.filter(user=self.user).all()
        self.assertEqual(ingredients.count(), 1)

class ImageUploadTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user('test@example.com', 'pass123')
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()
    
    def test_upload_image(self):
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix='.jpg') as image_file:
            img = Image.new('RGB', (10, 10))
            img.save(image_file, format='JPEG')
            image_file.seek(0)
            payload = {'image': image_file}
            res = self.client.post(url, payload, format='multipart')
    
        self.recipe.refresh_from_db()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('image', res.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))
    
    def test_upload_image_bad_request(self):
        url = image_upload_url(self.recipe.id)
        payload = {'image': '123'}
        res = self.client.post(url, payload, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
