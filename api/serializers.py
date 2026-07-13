from rest_framework import serializers

from api.models import (
    AuthSession,
    Group,
    GroupInvitation,
    GroupMembership,
    Message,
    User,
)

class UserSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="public_id", read_only=True)
    avatar_url = serializers.URLField(source="profile_picture", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "name",
            "bio",
            "avatar_url",
            "created_at",
            "updated_at",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["username", "email", "password", "name"]

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("کاربری با این ایمیل قبلاً ثبت‌نام کرده است.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("این نام کاربری قبلاً استفاده شده است.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class AuthSessionSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = AuthSession
        fields = ["id", "created_at", "expires_at", "device"]


def message_to_dict(message):
    return {
        "id": message.public_id,
        "sender_id": message.user.public_id,
        "receiver_id": message.receiver.public_id if message.receiver else None,
        "group_id": message.group_id or None,
        "channel_id": message.channel_id or None,
        "topic_id": message.topic_id or None,
        "content": message.content,
        "reply_to_id": message.reply_to.public_id if message.reply_to else None,
        "is_edited": message.is_edited,
        "is_deleted": message.is_deleted,
        "media": message.media or [],
        "reactions": message.reactions or [],
        "created_at": message.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": message.updated_at.isoformat().replace("+00:00", "Z"),
    }


class MessageSerializer(serializers.Serializer):
    def to_representation(self, instance):
        return message_to_dict(instance)


class SendMessageSerializer(serializers.Serializer):
    receiver_id = serializers.CharField(required=False, allow_blank=True)
    group_id = serializers.CharField(required=False, allow_blank=True)
    channel_id = serializers.CharField(required=False, allow_blank=True)
    topic_id = serializers.CharField(required=False, allow_blank=True)
    content = serializers.CharField(required=False, allow_blank=True)
    reply_to_id = serializers.CharField(required=False, allow_blank=True)
    file_url = serializers.URLField(required=False, allow_blank=True)
    media_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )


class EditMessageSerializer(serializers.Serializer):
    content = serializers.CharField()


class PublicUserProfileSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="public_id", read_only=True)
    avatar_url = serializers.URLField(
        source="profile_picture",
        read_only=True,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "name",
            "bio",
            "avatar_url",
            "created_at",
            "updated_at",
        ]


class UpdateUserProfileSerializer(serializers.ModelSerializer):
    avatar_url = serializers.URLField(
        source="profile_picture",
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "name",
            "bio",
            "avatar_url",
        ]
        extra_kwargs = {
            "username": {"required": False},
            "name": {"required": False},
            "bio": {
                "required": False,
                "allow_blank": True,
            },
        }

    def validate_username(self, value):
        users = User.objects.filter(username__iexact=value)

        if self.instance is not None:
            users = users.exclude(pk=self.instance.pk)

        if users.exists():
            raise serializers.ValidationError(
                "این نام کاربری قبلاً استفاده شده است."
            )

        return value


class CreateGroupSerializer(serializers.Serializer):
    name = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )


class GroupMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(
        source="user.public_id",
        read_only=True,
    )
    username = serializers.CharField(
        source="user.username",
        read_only=True,
    )
    name = serializers.CharField(
        source="user.name",
        read_only=True,
    )

    class Meta:
        model = GroupMembership
        fields = [
            "user_id",
            "username",
            "name",
            "role",
            "joined_at",
        ]


class GroupSerializer(serializers.ModelSerializer):
    id = serializers.CharField(
        source="public_id",
        read_only=True,
    )
    creator_id = serializers.CharField(
        source="creator.public_id",
        read_only=True,
    )
    members = GroupMembershipSerializer(
        source="memberships",
        many=True,
        read_only=True,
    )
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "creator_id",
            "member_count",
            "members",
            "created_at",
            "updated_at",
        ]

    def get_member_count(self, obj):
        return obj.memberships.count()


class CreateGroupInvitationSerializer(serializers.Serializer):
    invitee_id = serializers.CharField()


class GroupInvitationSerializer(serializers.ModelSerializer):
    id = serializers.CharField(
        source="public_id",
        read_only=True,
    )
    group_id = serializers.CharField(
        source="group.public_id",
        read_only=True,
    )
    group_name = serializers.CharField(
        source="group.name",
        read_only=True,
    )
    inviter_id = serializers.CharField(
        source="inviter.public_id",
        read_only=True,
    )
    inviter_username = serializers.CharField(
        source="inviter.username",
        read_only=True,
    )
    invitee_id = serializers.CharField(
        source="invitee.public_id",
        read_only=True,
    )

    class Meta:
        model = GroupInvitation
        fields = [
            "id",
            "group_id",
            "group_name",
            "inviter_id",
            "inviter_username",
            "invitee_id",
            "status",
            "created_at",
            "responded_at",
        ]


class RespondGroupInvitationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["accept", "reject"],
    )