import time
import logging
from functools import wraps
from contextlib import contextmanager

# ==============================
# CONSTANTS (Avoid Magic Numbers)
# ==============================
TAX_RATE = 0.15
MIN_PASSWORD_LENGTH = 8

# ==============================
# LOGGING SETUP
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==============================
# VALIDATION FUNCTIONS (Refactoring)
# ==============================
def validate_email(email):
    if "@" not in email:
        raise ValueError("Invalid email")
    return True

def is_password_valid(password):
    return len(password) >= MIN_PASSWORD_LENGTH

# ==============================
# USER FUNCTIONS
# ==============================
def create_user(email, password):
    validate_email(email)
    if not is_password_valid(password):
        raise ValueError("Password too short")
    logger.info("User created successfully")

# ==============================
# SMALL FUNCTIONS (Instead of long function)
# ==============================
def validate_order(order):
    if not order:
        raise ValueError("Invalid order")

def calculate_totals(order):
    order['total'] = order.get('amount', 0) * TAX_RATE

def update_inventory(order):
    logger.info("Inventory updated")

def send_notifications(order):
    logger.info("Notification sent")

def process_order(order):
    validate_order(order)
    calculate_totals(order)
    update_inventory(order)
    send_notifications(order)

# ==============================
# OPTIMIZED ALGORITHM
# ==============================
def find_pairs_optimized(numbers, target):
    pairs = []
    seen = set()
    for num in numbers:
        complement = target - num
        if complement in seen:
            pairs.append((complement, num))
        seen.add(num)
    return pairs

# ==============================
# GENERATOR (Memory Efficient)
# ==============================
def read_large_file_efficiently(filename):
    with open(filename, 'r') as file:
        for line in file:
            yield line.strip()

# ==============================
# CUSTOM EXCEPTION
# ==============================
class InsufficientFundsError(Exception):
    def __init__(self, balance, amount):
        super().__init__(f"Required: {amount}, Available: {balance}")

# ==============================
# BANK ACCOUNT CLASS
# ==============================
class BankAccount:
    def __init__(self, balance):
        self.balance = balance

    def withdraw(self, amount):
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount)
        self.balance -= amount
        logger.info(f"Withdraw successful: {amount}")

# ==============================
# CONTEXT MANAGER
# ==============================
@contextmanager
def database_connection(connection_string):
    print("Connecting to database...")
    connection = {"status": "connected"}  # Dummy connection
    try:
        yield connection
    except Exception:
        print("Rolling back...")
        raise
    finally:
        print("Connection closed")

# ==============================
# RETRY DECORATOR
# ==============================
class TemporaryError(Exception):
    pass

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except TemporaryError:
                    logger.warning(f"Retry {attempt+1}...")
                    time.sleep(delay)
            raise TemporaryError("Max retries reached")
        return wrapper
    return decorator

@retry(max_attempts=3, delay=1)
def unstable_function():
    raise TemporaryError("Temporary failure")

# ==============================
# CIRCUIT BREAKER
# ==============================
class CircuitBreaker:
    def __init__(self, max_failures=3, reset_timeout=5):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.reset_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit is OPEN")

        try:
            result = func(*args, **kwargs)
            self.failures = 0
            self.state = "CLOSED"
            return result
        except Exception:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.max_failures:
                self.state = "OPEN"
            raise

# ==============================
# USER DATA PROCESSOR (FINAL CLEAN DESIGN)
# ==============================
class UserDataProcessor:
    MIN_AGE = 13
    VALID_PREFERENCES = {'sports', 'music', 'books'}

    def __init__(self, user_data):
        self.user_data = user_data
        self._validate_input()

    def _validate_input(self):
        if not isinstance(self.user_data, dict):
            raise ValueError("User data must be a dictionary")
        self._validate_email()
        self._validate_age()
        self._validate_preferences()

    def _validate_email(self):
        email = self.user_data.get('email')
        if not email or '@' not in email:
            raise ValueError("Invalid email")

    def _validate_age(self):
        age = self.user_data.get('age')
        if not age or age < self.MIN_AGE:
            raise ValueError("Age must be >= 13")

    def _validate_preferences(self):
        prefs = self.user_data.get('preferences', [])
        invalid = set(prefs) - self.VALID_PREFERENCES
        if invalid:
            raise ValueError(f"Invalid preferences: {invalid}")

    def process(self):
        try:
            logger.info("Processing user data...")
            return "Processed Successfully"
        except Exception as e:
            logger.error(f"Error: {e}")
            raise

# ==============================
# MAIN TEST BLOCK
# ==============================
if __name__ == "__main__":
    try:
        # User creation
        create_user("test@example.com", "password123")

        # Order processing
        order = {"amount": 100}
        process_order(order)

        # Algorithm test
        print(find_pairs_optimized([1, 2, 3, 4], 5))

        # Bank account test
        acc = BankAccount(100)
        acc.withdraw(50)

        # Context manager
        with database_connection("db://localhost") as db:
            print("Using DB:", db)

        # Retry test
        try:
            unstable_function()
        except Exception as e:
            print("Retry failed:", e)

        # Circuit breaker test
        cb = CircuitBreaker()
        try:
            cb.call(lambda: 1 / 0)
        except:
            print("Circuit breaker triggered")

        # User data processor
        user = {
            "email": "user@test.com",
            "age": 20,
            "preferences": ["sports"]
        }
        processor = UserDataProcessor(user)
        print(processor.process())

    except Exception as e:
        logger.exception(f"Main Error: {e}")