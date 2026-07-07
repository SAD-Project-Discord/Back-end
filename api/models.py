import secrets

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, username, name, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        if not username:
            raise ValueError("Users must have a username.")

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            username=username,
            name=name,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, username, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    public_id = models.CharField(max_length=32, unique=True, editable=False)
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255)
    bio = models.TextField(blank=True, default="")
    profile_picture = models.URLField(blank=True, default="")
    provider = models.CharField(max_length=50, default="local")
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "name"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"usr_{secrets.token_hex(6)}"
            if not User.objects.filter(public_id=public_id).exists():
                return public_id


class AuthSession(models.Model):
    public_id = models.CharField(max_length=32, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_sessions")
    refresh_jti = models.CharField(max_length=255, unique=True)
    device = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "auth_sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.public_id} ({self.user.email})"

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def revoke(self):
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.save(update_fields=["revoked_at"])

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"ses_{secrets.token_hex(6)}"
            if not AuthSession.objects.filter(public_id=public_id).exists():
                return public_id


class MessageQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)

    def for_direct(self, user_a, user_b):
        return self.active().filter(
            message_type=Message.MessageType.DIRECT,
        ).filter(
            models.Q(user=user_a, receiver=user_b) | models.Q(user=user_b, receiver=user_a)
        )

    def for_group(self, group_id):
        return self.active().filter(message_type=Message.MessageType.GROUP, group_id=group_id)

    def for_channel(self, channel_id, topic_id=None):
        queryset = self.active().filter(
            message_type=Message.MessageType.CHANNEL,
            channel_id=channel_id,
        )
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        return queryset


class MessageManager(models.Manager.from_queryset(MessageQuerySet)):
    pass


class Message(models.Model):
    class MessageType(models.TextChoices):
        DIRECT = "direct", "Direct"
        GROUP = "group", "Group"
        CHANNEL = "channel", "Channel"

    public_id = models.CharField(max_length=32, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="messages")
    message_type = models.CharField(
        max_length=16,
        choices=MessageType.choices,
        db_index=True,
        default=MessageType.CHANNEL,
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_messages",
        null=True,
        blank=True,
    )
    group_id = models.CharField(max_length=32, blank=True, default="", db_index=True)
    channel_id = models.CharField(max_length=32, blank=True, default="", db_index=True)
    topic_id = models.CharField(max_length=32, blank=True, default="", db_index=True)
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="replies",
        null=True,
        blank=True,
    )
    content = models.TextField()
    file_url = models.URLField(blank=True, default="")
    media = models.JSONField(default=list, blank=True)
    reactions = models.JSONField(default=list, blank=True)
    is_edited = models.BooleanField(default=False)
    pinned = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MessageManager()

    class Meta:
        db_table = "messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["message_type", "group_id", "created_at"]),
            models.Index(fields=["message_type", "channel_id", "topic_id", "created_at"]),
        ]

    def __str__(self):
        return f"{self.public_id} ({self.message_type})"

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(update_fields=["deleted_at", "updated_at"])

    def get_room_name(self):
        from api.constants import channel_room_name, direct_room_name, group_room_name

        if self.message_type == self.MessageType.DIRECT:
            return direct_room_name(self.user.public_id, self.receiver.public_id)
        if self.message_type == self.MessageType.GROUP:
            return group_room_name(self.group_id)
        return channel_room_name(self.channel_id, self.topic_id or None)

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"msg_{secrets.token_hex(6)}"
            if not Message.objects.filter(public_id=public_id).exists():
                return public_id
