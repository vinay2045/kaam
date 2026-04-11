import re
from typing import Dict, List, Optional

class SpamGuard:
    # Whitelisted email domains
    ALLOWED_DOMAINS = {
        'gmail.com',
        'hotmail.com',
        'yahoo.com',
        'outlook.com',
        'icloud.com'
    }

    # Prohibited keywords in names, addresses, and UTRs
    BLOCKED_KEYWORDS = {
        'dummy', 'test', 'fake', 'spam', 'none', 'nothing', 'demo', 
        'null', 'abcd', 'asdf', 'qwerty', '1234'
    }

    @staticmethod
    def _clean_string(s: str) -> str:
        """Removes all non-alphanumeric characters and converts to lowercase."""
        if not s:
            return ""
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

    @classmethod
    def contains_spam_keywords(cls, s: str) -> bool:
        """Checks if a string contains any blocked keywords after cleaning."""
        cleaned = cls._clean_string(s)
        for keyword in cls.BLOCKED_KEYWORDS:
            if keyword in cleaned:
                return True
        return False

    @classmethod
    def is_valid_email(cls, email: str) -> (bool, str):
        if not email or '@' not in email:
            return False, "Invalid email format."
        
        email = email.lower().strip()
        domain = email.split('@')[-1]
        
        if domain not in cls.ALLOWED_DOMAINS:
            return False, f"We only accept emails from: {', '.join(sorted(cls.ALLOWED_DOMAINS))}"
        
        # Check if the prefix of the email contains spam keywords
        prefix = email.split('@')[0]
        if cls.contains_spam_keywords(prefix):
            return False, "This email looks like dummy data."
            
        return True, ""

    @classmethod
    def is_valid_phone(cls, phone: str) -> (bool, str):
        # Extract digits
        digits = re.sub(r'[^0-9]', '', str(phone))
        
        if len(digits) < 7:
            return False, "Phone number is too short."
        
        if len(digits) > 15:
            return False, "Phone number is too long."

        # Block repeating digits (e.g., 9999999999)
        if len(set(digits)) == 1:
            return False, "Invalid phone number (all digits same)."

        # Block common long sequences (8+ digits)
        sequences = ["12345678", "01234567", "87654321", "98765432"]
        for seq in sequences:
            if seq in digits:
                return False, "Invalid phone number (long sequential digits)."

        return True, ""

    @classmethod
    def is_quality_address(cls, line1: str, city: str, state: str, pincode: str) -> (bool, str):
        # Normalize and check keywords
        all_text = f"{line1} {city} {state} {pincode}"
        if cls.contains_spam_keywords(all_text):
            return False, "Address contains placeholder/dummy keywords."

        # Check line1 length
        if len(line1.strip()) < 5:
            return False, "Address is too short. Please provide a full address."

        # Check for non-gibberish (repetitive chars)
        if re.search(r'(.)\1{4,}', line1): # 5+ repeating chars
            return False, "Address contains repetitive characters (gibberish)."

        # Pincode validation: must be alphanumeric and not a simple pattern
        clean_pin = cls._clean_string(pincode)
        if len(clean_pin) < 3:
            return False, "Pincode/ZIP is too short."
        if len(set(clean_pin)) == 1 and len(clean_pin) > 3:
            return False, "Invalid Pincode/ZIP format."

        return True, ""

    @classmethod
    def is_valid_utr(cls, utr: str, payment_method: str) -> (bool, str):
        if payment_method != 'online':
            return True, ""
            
        if not utr or len(utr.strip()) < 8:
            return False, "UTR/Transaction ID must be at least 8 characters long."
            
        if cls.contains_spam_keywords(utr):
            return False, "Transaction ID contains dummy keywords."

        # Block generic sequences in UTR
        if re.sub(r'[^0-9]', '', utr) in ["12345678", "11111111", "00000000"]:
            return False, "Invalid Transaction ID format."

        return True, ""

    @classmethod
    def is_valid_name(cls, name: str) -> (bool, str):
        if not name or len(name.strip()) < 2:
            return False, "Name is too short."
            
        if cls.contains_spam_keywords(name):
            return False, "Name contains dummy keywords."
            
        if all(char.isdigit() for char in name.replace(" ", "")):
            return False, "Name cannot be entirely numeric."
            
        return True, ""


from django.core.cache import cache

class RateLimiter:
    """
    High-performance Rate Limiter using Django's cache backend.
    """
    
    @staticmethod
    def get_client_ip(request) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @classmethod
    def is_rate_limited(cls, request, action_key: str, limit: int = 1, period_seconds: int = 180) -> bool:
        """
        Checks if the request IP is rate-limited for a specific action.
        Default: 1 request per 180 seconds (3 minutes).
        """
        ip = cls.get_client_ip(request)
        cache_key = f"rl_{action_key}_{ip}"
        
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return True
        
        # Increment and set/renew expiration
        new_count = current_count + 1
        cache.set(cache_key, new_count, period_seconds)
        return False
