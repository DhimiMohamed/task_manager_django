from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Category, Task
from django.utils import timezone

User = get_user_model()

class CategoryModelTest(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )

    def test_category_creation(self):
        # Test creating a category with required fields
        category = Category.objects.create(
            name='Work',
            color='#FF5733',
            user=self.user
        )
        self.assertEqual(category.name, 'Work')
        self.assertEqual(category.color, '#FF5733')
        self.assertEqual(category.user.email, 'test@example.com')

    def test_category_default_color(self):
        # Test default color value
        category = Category.objects.create(
            name='Personal',
            user=self.user  # Color not specified
        )
        self.assertEqual(category.color, '#CCCCCC')  # Default color


class TaskModelTest(TestCase):
    def setUp(self):
        # Create a test user and category
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='Work',
            user=self.user
        )
        self.due_date = timezone.now().date() + timezone.timedelta(days=7)

    def test_task_creation(self):
        # Test creating a task with required fields
        task = Task.objects.create(
            user=self.user,
            title='Complete project',
            description='Finish the Django project',
            due_date=self.due_date,
            status='pending',
            priority=2
        )
        self.assertEqual(task.title, 'Complete project')
        self.assertEqual(task.status, 'pending')
        self.assertEqual(task.priority, 2)
        self.assertEqual(task.user.email, 'test@example.com')

    def test_task_default_values(self):
        # Test default values (status, priority)
        task = Task.objects.create(
            user=self.user,
            title='Review code'
        )
        self.assertEqual(task.status, 'pending')  # Default status
        self.assertEqual(task.priority, 1)  # Default priority
        self.assertIsNone(task.category)  # Optional field

    def test_task_with_category(self):
        # Test assigning a category to a task
        task = Task.objects.create(
            user=self.user,
            title='Meeting',
            category=self.category
        )
        self.assertEqual(task.category.name, 'Work')

    def test_task_optional_fields(self):
        # Test optional fields (description, due_date, times)
        task = Task.objects.create(
            user=self.user,
            title='Optional fields test'
        )
        self.assertIsNone(task.description)
        self.assertIsNone(task.due_date)
        self.assertIsNone(task.start_time)
        self.assertIsNone(task.end_time)
# ------------------------------------------------------------------------views.py tests
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta


class CategoryViewsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='John',
            last_name='Doe',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(
            name='Work',
            color='#FF5733',
            user=self.user
        )

    def test_category_list_create(self):
        # Test listing categories
        url = reverse('category-list-create')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # Test creating category
        data = {'name': 'Personal', 'color': '#33FF57'}
        response = self.client.post(url, data, format='json')
        # print("Response Status Code:", response.status_code)
        # print("Response Data:", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_category_detail(self):
        url = reverse('category-detail', args=[self.category.id])
        
        # Test retrieving
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test updating
        data = {'name': 'Work Updated'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test deleting
        response = self.client.delete(url)
        # print("Response Status Code:", response.status_code)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class TaskViewsTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(
            name='Work',
            user=self.user
        )
        self.task = Task.objects.create(
            user=self.user,
            title='Test Task',
            due_date=timezone.now().date() + timedelta(days=1)
        )

    def test_task_list_create(self):
        url = reverse('task-list-create')
        
        # Test listing
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test creating
        data = {
            'title': 'New Task',
            'due_date': (timezone.now() + timedelta(days=2)).date().isoformat(),
            'category': self.category.id,  # Including the category ID in the data
            'start_time': timezone.now().time().isoformat(),  # Optional: Adding a start time
            'end_time': (timezone.now() + timedelta(hours=1)).time().isoformat(),  # Optional: Adding an end time
            'priority': 3,  # Priority is optional, so you can include it
            'status': 'pending',  # Default, but being explicit
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_task_detail(self):
        url = reverse('task-detail', args=[self.task.id])
        
        # Test retrieving
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test updating
        data = {'title': 'Updated Task'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test deleting
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_task_filtering(self):
        # Create completed task
        Task.objects.create(
            user=self.user,
            title='Completed Task',
            status='completed'
        )
        
        # Test status filter
        url = reverse('task-list-create') + '?status=completed'
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['status'], 'completed')


class TaskDateRangeViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create tasks with different dates
        self.today = timezone.now().date()
        Task.objects.create(user=self.user, title='Today', due_date=self.today)
        Task.objects.create(user=self.user, title='Tomorrow', due_date=self.today + timedelta(days=1))

    def test_date_range_filter(self):
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        url = reverse('task-list-between-dates') + f'?start_date={today.isoformat()}&end_date={tomorrow.isoformat()}'
        response = self.client.get(url)
        self.assertEqual(len(response.data), 2)

    # def test_invalid_date_range(self):
    #     today = timezone.now().date()
    #     yesterday = today - timedelta(days=1)
    #     url = reverse('task-list-between-dates')
    #     params = {
    #         'start_date': today.isoformat(),
    #         'end_date': yesterday.isoformat()
    #     }
        
        # url = reverse('task-list-between-dates') + f'?start_date={today.isoformat()}&end_date={yesterday.isoformat()}'
        # response = self.client.get(url, params)
        # self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    # ---------------------------------------------------------------------------------------
    def test_no_tasks_in_date_range(self):
        today = timezone.now().date()  # Current date
        yesterday = today - timedelta(days=1)  # One day before today
        url = reverse('task-list-between-dates')
        far_future = self.today + timedelta(days=365)
        params = {
            'start_date': (far_future - timedelta(days=1)).strftime('%Y-%m-%d'),
            'end_date': far_future.strftime('%Y-%m-%d')
        }
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
        
# ------------------------------------------------------------------------------------------------------------------------------------
class TaskStatisticsViewTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=self.user)
        
        # Create test data
        work = Category.objects.create(name='Work', user=self.user)
        Task.objects.create(user=self.user, title='Task 1', status='completed', category=work)
        Task.objects.create(user=self.user, title='Task 2', status='pending')

    def test_statistics(self):
        url = reverse('task-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        
        # Basic counts
        self.assertEqual(data['total_tasks'], 2)
        self.assertEqual(data['completed_tasks'], 1)
        self.assertEqual(data['pending_tasks'], 1)
        
        # Category breakdown
        self.assertEqual(len(data['categories']), 2)  # Work and Uncategorized