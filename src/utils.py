import hashlib
import time

def generate_hash() -> str:
   """
   Generate a unique hash for a commit based on timestamp
   """
   timestamp = str(time.time()).encode()
   return hashlib.sha1(timestamp).hexdigest()[:8]
