from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated

from api.serializers import (
    AccessRoleSerializer,
    AssignAccessRoleSerializer,
    CreateAccessRoleSerializer,
    GroupMembershipSerializer,
    UpdateAccessRoleSerializer,
)
from api.services.roles import (
    RoleServiceError,
    assign_group_role,
    create_group_role,
    delete_group_role,
    list_group_roles,
    remove_assigned_group_role,
    update_group_role,
)
from api.utils.responses import (
    error_response,
    no_content_response,
    success_response,
)


def _handle_service_error(exc):
    return error_response(
        exc.code,
        exc.message,
        exc.status_code,
    )


@extend_schema(
    tags=["Group Roles"],
    summary="List custom group roles",
    description="Lists custom access roles created within the specified group.",
    methods=["GET"],
    responses={200: AccessRoleSerializer(many=True)},
)
@extend_schema(
    tags=["Group Roles"],
    summary="Create custom group role",
    description="Creates a custom access role in the group with specific permissions (requires MANAGE_ROLES permission).",
    methods=["POST"],
    request=CreateAccessRoleSerializer,
    responses={
        201: AccessRoleSerializer,
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="Forbidden."),
    },
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def group_role_list_create(
    request,
    group_id,
):
    if request.method == "GET":
        try:
            roles = list_group_roles(
                group_id,
                request.user,
            )
        except RoleServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            AccessRoleSerializer(
                roles,
                many=True,
            ).data
        )

    serializer = CreateAccessRoleSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        role = create_group_role(
            group_id,
            request.user,
            serializer.validated_data,
        )
    except RoleServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        AccessRoleSerializer(role).data,
        status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Group Roles"],
    summary="Update custom group role",
    description="Updates role name, position, or permissions. Requires MANAGE_ROLES permission.",
    methods=["PATCH"],
    request=UpdateAccessRoleSerializer,
    responses={200: AccessRoleSerializer, 400: OpenApiResponse(description="Validation error.")},
)
@extend_schema(
    tags=["Group Roles"],
    summary="Delete custom group role",
    description="Deletes a custom access role from the group. Requires MANAGE_ROLES permission.",
    methods=["DELETE"],
    responses={204: OpenApiResponse(description="Role deleted successfully.")},
)
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def group_role_detail(
    request,
    group_id,
    role_id,
):
    if request.method == "PATCH":
        serializer = UpdateAccessRoleSerializer(
            data=request.data
        )

        if not serializer.is_valid():
            return error_response(
                "VALIDATION_ERROR",
                "Invalid request data.",
                status.HTTP_400_BAD_REQUEST,
                serializer.errors,
            )

        try:
            role = update_group_role(
                group_id,
                role_id,
                request.user,
                serializer.validated_data,
            )
        except RoleServiceError as exc:
            return _handle_service_error(exc)

        return success_response(
            AccessRoleSerializer(role).data
        )

    try:
        delete_group_role(
            group_id,
            role_id,
            request.user,
        )
    except RoleServiceError as exc:
        return _handle_service_error(exc)

    return no_content_response()


@extend_schema(
    tags=["Group Roles"],
    summary="Assign role to group member",
    description="Assigns a custom access role to a specific group member.",
    request=AssignAccessRoleSerializer,
    responses={
        200: GroupMembershipSerializer,
        400: OpenApiResponse(description="Validation error."),
        403: OpenApiResponse(description="Forbidden."),
    },
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_member_role_assign(
    request,
    group_id,
    user_id,
):
    serializer = AssignAccessRoleSerializer(
        data=request.data
    )

    if not serializer.is_valid():
        return error_response(
            "VALIDATION_ERROR",
            "Invalid request data.",
            status.HTTP_400_BAD_REQUEST,
            serializer.errors,
        )

    try:
        membership = assign_group_role(
            group_id,
            user_id,
            serializer.validated_data["role_id"],
            request.user,
        )
    except RoleServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        GroupMembershipSerializer(
            membership
        ).data
    )


@extend_schema(
    tags=["Group Roles"],
    summary="Remove assigned role from group member",
    description="Removes an assigned custom access role from a group member.",
    responses={
        200: GroupMembershipSerializer,
        403: OpenApiResponse(description="Forbidden."),
        404: OpenApiResponse(description="Role assignment not found."),
    },
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def group_member_role_remove(
    request,
    group_id,
    user_id,
    role_id,
):
    try:
        membership = remove_assigned_group_role(
            group_id,
            user_id,
            role_id,
            request.user,
        )
    except RoleServiceError as exc:
        return _handle_service_error(exc)

    return success_response(
        GroupMembershipSerializer(
            membership
        ).data
    )