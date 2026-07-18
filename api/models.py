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


class GroupQuerySet(models.QuerySet):
    def active(self):
        return self.filter(deleted_at__isnull=True)


class GroupManager(models.Manager.from_queryset(GroupQuerySet)):
    pass


class Group(models.Model):
    public_id = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(
        blank=True,
        default="",
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_chat_groups",
    )
    members = models.ManyToManyField(
        User,
        through="GroupMembership",
        related_name="chat_groups",
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = GroupManager()

    class Meta:
        db_table = "chat_groups"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(
                update_fields=[
                    "deleted_at",
                    "updated_at",
                ]
            )

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()

        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"grp_{secrets.token_hex(6)}"

            if not Group.objects.filter(
                public_id=public_id
            ).exists():
                return public_id


class GroupMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    custom_roles = models.ManyToManyField(
        "AccessRole",
        related_name="group_memberships",
        blank=True,
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "group_memberships"
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_group_membership",
            ),
        ]
        indexes = [
            models.Index(
                fields=["group", "role"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.group.name} ({self.role})"
        )


class GroupInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        CANCELED = "canceled", "Canceled"

    public_id = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_group_invitations",
    )
    invitee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_group_invitations",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "group_invitations"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "invitee"],
                condition=models.Q(status="pending"),
                name="unique_pending_group_invitation",
            ),
        ]

    def __str__(self):
        return (
            f"{self.invitee.username} -> "
            f"{self.group.name} ({self.status})"
        )

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()

        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"ginv_{secrets.token_hex(6)}"

            if not GroupInvitation.objects.filter(
                public_id=public_id
            ).exists():
                return public_id


class AccessPermission(models.TextChoices):
    MANAGE_GROUP = "manage_group", "Manage Group"
    MANAGE_MEMBERS = "manage_members", "Manage Members"
    MANAGE_ROLES = "manage_roles", "Manage Roles"
    MANAGE_INVITATIONS = (
        "manage_invitations",
        "Manage Invitations",
    )

    MANAGE_CHANNEL = "manage_channel", "Manage Channel"
    MANAGE_TOPICS = "manage_topics", "Manage Topics"
    MANAGE_CHANNEL_MEMBERS = (
        "manage_channel_members",
        "Manage Channel Members",
    )

    SEND_MESSAGES = "send_messages", "Send Messages"
    EDIT_MESSAGES = "edit_messages", "Edit Messages"
    DELETE_MESSAGES = "delete_messages", "Delete Messages"


class AccessRoleQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            deleted_at__isnull=True,
        )


class AccessRoleManager(
    models.Manager.from_queryset(AccessRoleQuerySet)
):
    pass


class AccessRole(models.Model):
    public_id = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    name = models.CharField(
        max_length=100,
    )
    permissions = models.JSONField(
        default=list,
        blank=True,
    )

    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="custom_roles",
        null=True,
        blank=True,
    )
    channel = models.ForeignKey(
        "Channel",
        on_delete=models.CASCADE,
        related_name="custom_roles",
        null=True,
        blank=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_access_roles",
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = AccessRoleManager()

    class Meta:
        db_table = "access_roles"
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(group__isnull=False)
                        & models.Q(channel__isnull=True)
                    )
                    |
                    (
                        models.Q(group__isnull=True)
                        & models.Q(channel__isnull=False)
                    )
                ),
                name="access_role_exactly_one_scope",
            ),
            models.UniqueConstraint(
                fields=["group", "name"],
                condition=models.Q(
                    group__isnull=False,
                    deleted_at__isnull=True,
                ),
                name="unique_active_group_role_name",
            ),
            models.UniqueConstraint(
                fields=["channel", "name"],
                condition=models.Q(
                    channel__isnull=False,
                    deleted_at__isnull=True,
                ),
                name="unique_active_channel_role_name",
            ),
        ]

    def __str__(self):
        if self.group_id:
            return f"{self.group.name} - {self.name}"

        return f"{self.channel.name} - {self.name}"

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def scope_type(self):
        if self.group_id:
            return "group"

        return "channel"

    def has_permission(self, permission):
        return permission in self.permissions

    def soft_delete(self):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(
                update_fields=[
                    "deleted_at",
                    "updated_at",
                ]
            )

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()

        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"rol_{secrets.token_hex(6)}"

            if not AccessRole.objects.filter(
                public_id=public_id
            ).exists():
                return public_id


class ChannelQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            deleted_at__isnull=True,
        )


class ChannelManager(
    models.Manager.from_queryset(ChannelQuerySet)
):
    pass


class Channel(models.Model):
    public_id = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.TextField(
        blank=True,
        default="",
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_channels",
    )
    members = models.ManyToManyField(
        User,
        through="ChannelMembership",
        related_name="joined_channels",
        blank=True,
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = ChannelManager()

    class Meta:
        db_table = "channels"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(
                update_fields=[
                    "deleted_at",
                    "updated_at",
                ]
            )

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()

        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"chn_{secrets.token_hex(6)}"

            if not Channel.objects.filter(
                public_id=public_id
            ).exists():
                return public_id


class ChannelMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="channel_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    custom_roles = models.ManyToManyField(
        "AccessRole",
        related_name="channel_memberships",
        blank=True,
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "channel_memberships"
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["channel", "user"],
                name="unique_channel_membership",
            ),
        ]
        indexes = [
            models.Index(
                fields=["channel", "role"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} - "
            f"{self.channel.name} ({self.role})"
        )


class TopicQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            deleted_at__isnull=True,
            channel__deleted_at__isnull=True,
        )


class TopicManager(
    models.Manager.from_queryset(TopicQuerySet)
):
    pass


class Topic(models.Model):
    public_id = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
    )
    channel = models.ForeignKey(
        Channel,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.TextField(
        blank=True,
        default="",
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_channel_topics",
    )
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    objects = TopicManager()

    class Meta:
        db_table = "channel_topics"
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=[
                    "channel",
                    "created_at",
                ]
            ),
        ]

    def __str__(self):
        return f"{self.channel.name} - {self.name}"

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        if self.deleted_at is None:
            self.deleted_at = timezone.now()
            self.save(
                update_fields=[
                    "deleted_at",
                    "updated_at",
                ]
            )

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = self._generate_public_id()

        super().save(*args, **kwargs)

    @staticmethod
    def _generate_public_id():
        while True:
            public_id = f"top_{secrets.token_hex(6)}"

            if not Topic.objects.filter(
                public_id=public_id
            ).exists():
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
