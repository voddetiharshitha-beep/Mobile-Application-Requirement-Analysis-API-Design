from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return response

    status_code = response.status_code

    if status_code == 400:
        error_code = "VALIDATION_ERROR"
        message = "Validation failed."
    elif status_code == 401:
        error_code = "AUTHENTICATION_REQUIRED"
        message = "Authentication credentials were not provided."
    elif status_code == 403:
        error_code = "PERMISSION_DENIED"
        message = "You do not have permission to perform this action."
    elif status_code == 404:
        error_code = "NOT_FOUND"
        message = "The requested resource was not found."
    elif status_code == 405:
        error_code = "METHOD_NOT_ALLOWED"
        message = "This HTTP method is not allowed."
    elif status_code == 429:
        error_code = "THROTTLED"
        message = "Too many requests."
    else:
        error_code = "API_ERROR"
        message = "An error occurred while processing the request."

    data = response.data

    if status_code == 400 and isinstance(data, dict):
        message = "Validation failed."
    elif isinstance(data, dict) and "detail" in data:
        message = str(data["detail"])

    response.data = {
        "success": False,
        "message": message,
        "error_code": error_code,
        "data": data if status_code == 400 else None,
    }

    return response