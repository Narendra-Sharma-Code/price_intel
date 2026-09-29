import os
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///price_intel.db')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    USE_CACHED_DATA = os.getenv('USE_CACHED_DATA', 'false').lower() == 'true'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEFAULT_ANNUAL_INTEREST_RATE = Decimal('12')  # documented assumption: used when user doesn't supply a rate; see README "EMI and Offer Assumptions"
