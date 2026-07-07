from rest_framework.views import exception_handler

from .utils.responses import error_response


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return None

    if isinstance(response.data, dict) and "success" in response.data:
        return response

    status_code = response.status_code
    message = "درخواست نامعتبر است."
    code = "BAD_REQUEST"
    details = None

    if status_code == 401:
        code = "UNAUTHORIZED"
        message = "ایمیل یا رمز عبور نادرست است."
    elif status_code == 404:
        code = "NOT_FOUND"
        message = "منبع مورد نظر یافت نشد."
    elif status_code == 403:
        code = "FORBIDDEN"
        message = "شما اجازه دسترسی به این منبع را ندارید."
    elif isinstance(response.data, dict):
        if "detail" in response.data:
            message = str(response.data["detail"])
        else:
            details = response.data
            message = "اطلاعات ارسالی نامعتبر است."
            code = "VALIDATION_ERROR"

    return error_response(code, message, status_code, details)
