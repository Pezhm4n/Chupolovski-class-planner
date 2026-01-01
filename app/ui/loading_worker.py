import time
from PyQt5.QtCore import QThread, pyqtSignal
from app.core.logger import setup_logging
from app.data.courses_db import get_db

logger = setup_logging()

class InitialLoadWorker(QThread):
    """
    Worker thread that loads courses DIRECTLY from the database.
    Bypasses all legacy JSON caching logic to ensure data consistency.
    """
    
    # Signals matching the original interface
    progress = pyqtSignal(str)
    courses_loaded = pyqtSignal(int)
    finished = pyqtSignal(bool)
    cache_hit = pyqtSignal(bool)
    
    def __init__(self, db=None, use_cache=True):
        super().__init__()
        self.db = db if db is not None else get_db()
        self.use_cache = False # Force disable cache logic
        self.start_time = None
        self.end_time = None
    
    def run(self):
        """Execute the loading in background thread"""
        try:
            self.start_time = time.time()
            self.progress.emit("در حال خواندن مستقیم از دیتابیس...")

            # 1. Fetch all courses from DB and convert them to the UI/legacy format
            from app.core.golestan_integration import load_courses_from_database
            from app.core.config import COURSES
            from app.core.data_manager import load_user_added_courses

            courses_dict = load_courses_from_database(self.db)

            # 2. Update the global COURSES variable
            COURSES.clear()
            COURSES.update(courses_dict)

            # 3. Load user-added courses (if any)
            try:
                load_user_added_courses()
            except Exception as e:
                logger.warning(f"Failed to load user courses: {e}")

            # 4. Report success
            count = len(COURSES)
            self.end_time = time.time()
            duration = self.end_time - self.start_time

            logger.info(f"✅ DIRECT DB LOAD: Loaded {count} courses in {duration:.2f}s")

            self.courses_loaded.emit(count)
            self.finished.emit(True)

        except Exception as e:
            logger.error(f"❌ Error in Direct DB Loader: {e}")
            import traceback
            traceback.print_exc()
            self.finished.emit(False)