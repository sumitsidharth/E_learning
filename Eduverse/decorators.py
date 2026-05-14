from django.contrib.auth.decorators import user_passes_test

def student_required(view_func=None, redirect_field_name='next', login_url='Eduverse:login'):
    actual_decorator = user_passes_test(
        lambda u: u.is_active and u.is_authenticated and u.is_student,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

def teacher_required(view_func=None, redirect_field_name='next', login_url='Eduverse:login'):
    actual_decorator = user_passes_test(
        lambda u: u.is_active and u.is_authenticated and u.is_teacher,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator
