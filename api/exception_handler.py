from rest_framework.views import exception_handler

from .utils.responses import error_response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(response.data, dict) and "success" in response.data:
        return response

    status_code = response.status_code
    message = "Invalid request."
    code = "BAD_REQUEST"
    details = None

    if status_code == 401:
        code = "UNAUTHORIZED"
        message = "Invalid credentials or token expired."
    elif status_code == 404:
        code = "NOT_FOUND"
        message = "Requested resource not found."
    elif status_code == 403:
        code = "FORBIDDEN"
        message = "You do not have permission to perform this action."
    elif isinstance(response.data, dict):
        if "detail" in response.data:
            message = str(response.data["detail"])
        else:
            details = response.data
            message = "Invalid request data."
            code = "VALIDATION_ERROR"

    return error_response(code, message, status_code, details)
