from rest_framework.response import Response
from rest_framework import status


def success_response(data, status_code=status.HTTP_200_OK, meta=None):
    body = {"success": True, "data": data}
    if meta is not None:
        body["meta"] = meta
    return Response(body, status=status_code)


def error_response(code, message, status_code=status.HTTP_400_BAD_REQUEST, details=None):
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return Response({"success": False, "error": error}, status=status_code)


def no_content_response():
    return Response(status=status.HTTP_204_NO_CONTENT)
