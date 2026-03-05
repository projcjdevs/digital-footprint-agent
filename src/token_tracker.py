import time
from src.config import Config

class RateLimiter:
    def __init__(self, rpm_limit: int):
        self.rpm_limit = rpm_limit
        self.timestamps: list[float] = [] 
    
    def _purge_old(self):
        cutoff = time.time() - 60
        self.timestamps = [t for t in self.timestamps if t > cutoff]

    def can_send(self) -> bool:
        self._purge_old()
        return len(self.timestamps) < self.rpm_limit
    
    def wait_time(self) -> float:
        self._purge_old()
        if len(self.timestamps) < self.rpm_limit:
            return 0.0
        
        oldest = self.timestamps[0]
        return (oldest + 60) - time.time()
        
    def record(self):
        self.timestamps.append(time.time())

gemini_limiter = RateLimiter(Config.GEMINI_RPM_LIMIT)
groq_limiter = RateLimiter(Config.GROQ_RPM_LIMIT)