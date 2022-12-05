from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from http import HTTPStatus
from django.core.cache import cache

from ..models import Post, Group


User = get_user_model()


class PostsURLTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test')
        cls.group = Group.objects.create(
            title='Тестовый заголовок',
            slug='test-slug',
            description='Тестовый текст',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост больше 15 символов',
        )

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_urls_for_guests_users_authors(self):
        templates_url_names = {
            self.guest_client.get('/'): HTTPStatus.OK,
            self.guest_client.get(f'/group/{self.group.slug}/'): HTTPStatus.OK,
            self.guest_client.get(f'/profile/{self.user.username}/'
                                  ): HTTPStatus.OK,
            self.guest_client.get(f'/posts/{self.post.id}/'): HTTPStatus.OK,
            self.authorized_client.get('/create/'
                                       ): HTTPStatus.OK,
            self.authorized_client.get(f'/posts/{self.post.id}/edit/'
                                       ): HTTPStatus.OK,
            self.guest_client.get('/unexisting_page/'
                                  ): HTTPStatus.NOT_FOUND,
        }
        for address, response in templates_url_names.items():
            with self.subTest(address=address):
                self.assertEqual(address.status_code, response)

    def test_urls_users(self):
        cache.clear()
        templates_url_names = {
            '/': 'posts/index.html',
            f'/group/{self.group.slug}/': 'posts/group_list.html',
            f'/profile/{self.user.username}/': 'posts/profile.html',
            f'/posts/{self.post.id}/': 'posts/post_detail.html',
            '/create/': 'posts/create_post.html',
            f'/posts/{self.post.id}/edit/': 'posts/create_post.html',
            '/unexisting_page/': 'core/404.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)
