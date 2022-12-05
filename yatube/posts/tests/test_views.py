import tempfile
import shutil
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse


from ..models import Post, Group, Comment, Follow
from ..forms import PostForm

User = get_user_model()


class PostsViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
        cls.user = User.objects.create_user(username='test')
        cls.new_user = User.objects.create_user(username='test2')
        cls.new_authorized_client = Client()
        cls.new_authorized_client.force_login(cls.new_user)
        cls.group = Group.objects.create(
            title='Тестовый заголовок',
            slug='test-slug',
            description='Тестовый текст',
        )
        image = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        cls.image = SimpleUploadedFile(
            name='small.gif',
            content=image,
            content_type='image/gif'
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост больше 15 символов',
            image=cls.image
        )
        cls.comment = Comment.objects.create(
            post=cls.post,
            author=cls.user,
            text='Тестовый комментарий к посту',
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_pages_uses_correct_template(self):
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list',
                    args=(self.group.slug,)): 'posts/group_list.html',
            reverse('posts:profile',
                    args=(self.user.username,)):
                        'posts/profile.html',
            reverse('posts:post_detail',
                    args=(self.post.id,)):
                        'posts/post_detail.html',
            reverse('posts:post_edit',
                    args=(self.post.id,)):
                        'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
        }

        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def check_context_contains_page_or_post(self, context, post=False):
        if post:
            self.assertIn('post', context)
            post = context['post']
        else:
            self.assertIn('page', context)
            post = context['page'][0]
        self.assertEqual(post.author, PostsViewTests.user)
        self.assertEqual(post.pub_date, PostsViewTests.post.pub_date)
        self.assertEqual(post.text, PostsViewTests.post.text)
        self.assertEqual(post.image, PostsViewTests.post.image)
        self.assertEqual(post.group, PostsViewTests.post.group)

    def check_context_contains_group(self, context):
        self.assertIn('group', context)
        group = context['group']
        self.assertEqual(group.title, PostsViewTests.group.title)
        self.assertEqual(group.description, PostsViewTests.group.description)

    def test_index_page_context_is_correct(self):
        response = self.guest_client.get(reverse('posts:index'))
        self.assertEqual(len(response.context['page_obj']), 1)

    def test_profile_page_context_is_correct(self):
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': 'test'}))
        self.assertEqual(self.user, response.context.get('author'))

    def test_post_page_context_is_correct(self):
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.id})
        )
        self.check_context_contains_page_or_post(response.context, post=True)
        self.assertIn('user', response.context)
        self.assertEqual(response.context['user'], PostsViewTests.user)

    def test_create_edit_post_context_is_correct(self):
        urls = (
            (True, reverse('posts:post_edit',
                           kwargs={'post_id': self.post.id})),
            (True, reverse('posts:post_create'))
        )
        for is_edit_value, url in urls:
            with self.subTest(url=url):
                response = self.authorized_client.get(
                    reverse('posts:post_edit',
                            kwargs={'post_id': self.post.id})
                )
                self.assertIn('form', response.context)
                self.assertIsInstance(response.context['form'], PostForm)

                self.assertIn('is_edit', response.context)
                is_edit = response.context['is_edit']
                self.assertIsInstance(is_edit, bool)
                self.assertEqual(is_edit, is_edit_value)

    def test_new_post_with_group_is_correct(self):
        new_group = Group.objects.create(
            title='New Test group',
            slug='new-test-group',
            description='new test description',
        )
        new_post = Post.objects.create(
            author=self.user,
            text='Тестовый пост с новой группой',
            group=new_group,
        )
        response = self.authorized_client.get(
            reverse('posts:index')
        )
        self.assertIn(new_post, response.context['page_obj'])
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': new_group.slug})
        )
        self.assertIn(new_post, response.context['page_obj'])
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug})
        )
        self.assertNotIn(new_post, response.context['page_obj'])
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': self.user.username})
        )

    def test_group_page_context_is_correct(self):
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': self.group.slug})
        )
        self.check_context_contains_group(response.context)

    def test_cache_works(self):
        response = self.authorized_client.get(reverse('posts:index'))
        before_clearing_the_cache = response.content

        Post.objects.create(
            group=PostsViewTests.group,
            text='Новый текст, после кэша',
            author=User.objects.get(username='test'))

        cache.clear()

        response = self.authorized_client.get(reverse('posts:index'))
        after_clearing_the_cache = response.content
        self.assertNotEqual(before_clearing_the_cache,
                            after_clearing_the_cache)

    def test_authorized_user_can_follow(self):
        response = self.new_authorized_client.get(reverse(
            'posts:profile_follow',
            kwargs={'username': self.user.username}
        ))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Follow.objects.filter(
            user=self.new_user, author=self.user
        ).exists())

    def test_authorized_user_can_unfollow(self):
        response = self.new_authorized_client.get(reverse(
            'posts:profile_unfollow',
            kwargs={'username': self.user.username}
        ))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Follow.objects.filter(
            user=self.new_user, author=self.user
        ).exists())

    def test_authorized_user_can_publish_comment(self):
        response = self.authorized_client.get(
            reverse('posts:post_detail', kwargs={'post_id': self.post.pk})
        )

        context_comment = response.context['comments'][0]

        self.assertEqual(context_comment, self.comment)

    def test_unauthorized_user_cant_publish_comment(self):
        comments_count = Comment.objects.count()
        address = reverse(
            'posts:add_comment',
            kwargs={'post_id': self.post.id}
        )

        response = self.guest_client.post(address, follow=True)

        self.assertRedirects(
            response,
            reverse('users:login') + '?next=' + address
        )
        self.assertEqual(Comment.objects.count(), comments_count)


class PaginatorViewsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='test')
        cls.authorized_client = Client()
        cls.authorized_client.force_login(cls.user)
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        MAX_NUM_OF_POSTS = 15
        posts = (
            Post(
                author=cls.user,
                text=f'Тестовый пост №{i}',
                group=cls.group) for i in range(MAX_NUM_OF_POSTS))
        Post.objects.bulk_create(posts)

    def test_pages_with_pagination_contain_ten_and_four_records(self):
        pages_names = [
            reverse('posts:index'),
            reverse('posts:group_list', kwargs={'slug': self.group.slug}),
            reverse('posts:profile', kwargs={'username': self.user.username}),
        ]
        pages = (
            (1, 10),
            (2, 5)
        )
        for reverse_name in pages_names:
            for page, count in pages:
                response = self.authorized_client.get(
                    reverse_name, {"page": page}
                )
                self.assertEqual(
                    len(response.context['page_obj']),
                    count
                )
