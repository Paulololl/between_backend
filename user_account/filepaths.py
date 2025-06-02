
# ALl filepaths

def applicant_resume(instance, filename):
    return f'Applicant/{instance.user.email} | {str(instance.user.user_id)[-12:]}/resume/{filename}'


def applicant_enrollment_record(instance, filename):
    return f'Applicant/{instance.user.email} | {str(instance.user.user_id)[-12:]}/enrollment_record/{filename}'


def company_background_image(instance, filename):
    return f'Company/{instance.user.email} | {str(instance.user.user_id)[-12:]}/background_image/{filename}'


def company_profile_picture(instance, filename):
    return f'Company/{instance.user.email} | {str(instance.user.user_id)[-12:]}/profile_picture/{filename}'


def coordinator_program_logo(instance, filename):
    return f'Coordinator/{instance.user.email} | {str(instance.user.user_id)[-12:]}/program_logo/{filename}'


def coordinator_signature(instance, filename):
    return f'Coordinator/{instance.user.email} | {str(instance.user.user_id)[-12:]}/signature/{filename}'

