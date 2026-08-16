import logging
from app.core.services.result import Result
from app.core.credentials import load_local_credentials, save_local_credentials, delete_local_credentials
from app.core.golestan_integration import update_courses_from_golestan

class GolestanService:
    """Service responsible for Golestan network operations and credentials."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        
    def check_local_credentials(self) -> Result:
        """Checks if local credentials exist."""
        try:
            credentials = load_local_credentials()
            if credentials is None:
                return Result(success=False, message="No local credentials found")
            return Result(success=True, data=credentials)
        except Exception as e:
            self.logger.error(f"Error checking local credentials: {e}")
            return Result(success=False, error=str(e))
            
    def get_masked_student_number(self) -> Result:
        """Returns the masked student number if credentials exist."""
        result = self.check_local_credentials()
        if not result.success:
            return result
        
        student_number = result.data['student_number']
        masked = student_number[:3] + '*' * (len(student_number) - 3) if len(student_number) > 3 else '*' * len(student_number)
        return Result(success=True, data={'masked_student': masked})
        
    def save_credentials(self, student_number: str, password: str, remember: bool) -> Result:
        """Saves credentials if requested."""
        if not remember:
            return Result(success=True)
            
        try:
            save_local_credentials(student_number, password, remember)
            return Result(success=True)
        except Exception as e:
            self.logger.error(f"Error saving credentials: {e}")
            return Result(success=False, error=str(e))
            
    def delete_credentials(self) -> Result:
        """Deletes saved credentials."""
        try:
            if delete_local_credentials():
                self.logger.info("Golestan credentials file deleted successfully")
                return Result(success=True, message="اطلاعات ذخیره‌شده گلستان حذف شد.")
            else:
                self.logger.error("Failed to delete Golestan credentials file")
                return Result(success=False, error="Failed to delete file")
        except Exception as e:
            self.logger.error(f"Error in delete_credentials: {e}")
            return Result(success=False, error=str(e))

    def fetch_courses(self, student_number: str = "", password: str = "") -> Result:
        """Fetches courses synchronously from Golestan API."""
        try:
            if not student_number or not password:
                creds = self.check_local_credentials()
                if not creds.success:
                    return Result(success=False, error="اطلاعات ورود به سامانه گلستان یافت نشد.")
                student_number = creds.data.get('student_number', '')
                password = creds.data.get('password', '')

            self.logger.debug("Fetching courses from Golestan")
            update_courses_from_golestan(username=student_number, password=password)
            return Result(success=True, message="اطلاعات دروس با موفقیت از سامانه گلستان دریافت شد.")
        except Exception as e:
            self.logger.error(f"Error fetching from Golestan: {e}")
            return Result(success=False, error=str(e))

    def manual_fetch_courses(self, student_number: str = "", password: str = "") -> Result:
        """Manual fetch from Golestan using stored or provided credentials."""
        return self.fetch_courses(student_number, password)
