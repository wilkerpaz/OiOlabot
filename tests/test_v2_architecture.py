"""Integration tests for v2 architecture."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from factories.base import BotFactory
from factories.main_factory import MainBotFactory
from factories.liturgy_factory import LiturgyBotFactory
from bots.base import BaseBot
from bots.main_bot import MainBot
from bots.liturgy_bot import LiturgyBot
from mixins.welcome import WelcomeMixin
from mixins.feed import FeedMixin
from mixins.liturgy import LiturgyMixin
from util.database.base import BaseDatabase
from util.database.main_db import MainDatabase
from util.database.liturgy_db import LiturgyDatabase
from util.scrapers.base import BaseScraper
from util.scrapers.liturgia import LiturgiaScraper
from util.scrapers.homilia import HomiliaScraper
from util.scrapers.santo import SantoScraper
from util.feedhandler import FeedHandler
from util.datehandler import DateHandler
from worker.feed_job import FeedJob
from worker.liturgy_job import LiturgyJob


class TestFactoryPattern:
    """Test Abstract Factory pattern for bot creation."""

    def test_main_bot_factory_creates_client(self):
        """MainBotFactory should create a Pyrogram Client."""
        factory = MainBotFactory()
        client = factory.create_client()
        assert client is not None
        assert hasattr(client, 'run')

    def test_main_bot_factory_creates_database(self):
        """MainBotFactory should create MainDatabase."""
        factory = MainBotFactory()
        db = factory.create_database()
        assert isinstance(db, MainDatabase)

    def test_liturgy_bot_factory_creates_client(self):
        """LiturgyBotFactory should create a Pyrogram Client."""
        factory = LiturgyBotFactory()
        client = factory.create_client()
        assert client is not None

    def test_liturgy_bot_factory_creates_database(self):
        """LiturgyBotFactory should create LiturgyDatabase."""
        factory = LiturgyBotFactory()
        db = factory.create_database()
        assert isinstance(db, LiturgyDatabase)


class TestBotInitialization:
    """Test bot initialization and lifecycle."""

    @patch('factories.main_factory.Client')
    def test_main_bot_initializes(self, mock_client_class):
        """MainBot should initialize with factory."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        factory = MainBotFactory()
        bot = MainBot(factory)

        assert bot.client is not None
        assert bot.db is not None
        assert isinstance(bot.db, MainDatabase)

    @patch('factories.liturgy_factory.Client')
    def test_liturgy_bot_initializes(self, mock_client_class):
        """LiturgyBot should initialize with factory."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        factory = LiturgyBotFactory()
        bot = LiturgyBot(factory)

        assert bot.client is not None
        assert bot.db is not None
        assert isinstance(bot.db, LiturgyDatabase)

    @patch('factories.main_factory.Client')
    def test_main_bot_registers_handlers(self, mock_client_class):
        """MainBot should register all handlers."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        factory = MainBotFactory()
        bot = MainBot(factory)

        # Verify add_handler was called (handlers registered)
        assert mock_client.add_handler.called


class TestMixins:
    """Test mixin composition and handler methods."""

    def test_welcome_mixin_has_methods(self):
        """WelcomeMixin should have all handler methods."""
        mixin = WelcomeMixin()
        assert hasattr(mixin, '_register_welcome_handlers')
        assert hasattr(mixin, '_on_new_chat_members')
        assert hasattr(mixin, '_on_left_chat_member')
        assert hasattr(mixin, 'set_welcome')
        assert hasattr(mixin, 'set_goodbye')
        assert hasattr(mixin, 'disable_welcome')
        assert hasattr(mixin, 'disable_goodbye')
        assert hasattr(mixin, 'lock_settings')
        assert hasattr(mixin, 'unlock_settings')
        assert hasattr(mixin, 'quiet_mode')
        assert hasattr(mixin, 'unquiet_mode')
        assert hasattr(mixin, '_check_permissions')

    def test_feed_mixin_has_methods(self):
        """FeedMixin should have all handler methods."""
        mixin = FeedMixin()
        assert hasattr(mixin, '_register_feed_handlers')
        assert hasattr(mixin, 'add_feed_url')
        assert hasattr(mixin, 'list_feed_urls')
        assert hasattr(mixin, 'remove_feed_url')

    def test_liturgy_mixin_has_methods(self):
        """LiturgyMixin should have all handler methods."""
        mixin = LiturgyMixin()
        assert hasattr(mixin, '_register_liturgy_handlers')
        assert hasattr(mixin, 'today_liturgy')
        assert hasattr(mixin, 'yesterday_liturgy')
        assert hasattr(mixin, 'tomorrow_liturgy')
        assert hasattr(mixin, 'sunday_liturgy')
        assert hasattr(mixin, 'saint_of_day')
        assert hasattr(mixin, 'show_calendar')
        assert hasattr(mixin, 'handle_calendar_selection')
        assert hasattr(mixin, 'start_daily_delivery')
        assert hasattr(mixin, 'stop_daily_delivery')
        assert hasattr(mixin, '_send_liturgy')


class TestDatabase:
    """Test database abstraction."""

    def test_main_database_instantiation(self):
        """MainDatabase should instantiate with DB number."""
        db = MainDatabase(0)
        assert db is not None

    def test_liturgy_database_instantiation(self):
        """LiturgyDatabase should instantiate with DB number."""
        db = LiturgyDatabase(1)
        assert db is not None

    def test_main_database_has_methods(self):
        """MainDatabase should have all required methods."""
        db = MainDatabase(0)
        methods = [
            'get_group_config', 'set_group_config',
            'get_urls_activated', 'get_urls_deactivated',
            'activate_all_urls', 'add_url_subscription',
            'remove_url_for_chat', 'get_chat_urls',
            'get_chats_for_url', 'update_url_metadata',
            'get_url_metadata', 'backup', 'list_admins',
        ]
        for method in methods:
            assert hasattr(db, method), f"Missing method: {method}"

    def test_liturgy_database_has_methods(self):
        """LiturgyDatabase should have all required methods."""
        db = LiturgyDatabase(1)
        methods = [
            'add_daily_liturgy_subscription',
            'remove_daily_liturgy_subscription',
            'get_active_subscriptions',
            'get_deactivated_subscriptions',
            'activate_all_subscriptions',
            'set_last_send',
            'cache_audio_file_id',
            'get_cached_audio_file_id',
            'list_admins',
        ]
        for method in methods:
            assert hasattr(db, method), f"Missing method: {method}"


class TestScrapers:
    """Test scraper abstraction and implementations."""

    def test_liturgia_scraper_instantiation(self):
        """LiturgiaScraper should instantiate with optional date."""
        scraper = LiturgiaScraper()
        assert scraper is not None
        assert hasattr(scraper, 'fetch')
        assert hasattr(scraper, 'safe_fetch')

    def test_homilia_scraper_instantiation(self):
        """HomiliaScraper should instantiate."""
        scraper = HomiliaScraper()
        assert scraper is not None
        assert hasattr(scraper, 'fetch')
        assert hasattr(scraper, 'safe_fetch')

    def test_santo_scraper_instantiation(self):
        """SantoScraper should instantiate."""
        scraper = SantoScraper()
        assert scraper is not None
        assert hasattr(scraper, 'fetch')
        assert hasattr(scraper, 'safe_fetch')

    @pytest.mark.asyncio
    async def test_scrapers_safe_fetch_returns_string(self):
        """All scrapers safe_fetch should return string (fallback on error)."""
        for scraper_class in [LiturgiaScraper, HomiliaScraper, SantoScraper]:
            scraper = scraper_class()
            result = await scraper.safe_fetch()
            assert isinstance(result, str)


class TestWorkerJobs:
    """Test worker job instantiation and methods."""

    def test_feed_job_instantiation(self):
        """FeedJob should instantiate with database and token."""
        db = MainDatabase(0)
        job = FeedJob(db, "test_token")
        assert job.db is db
        assert job.bot_token == "test_token"
        assert hasattr(job, 'run')

    def test_liturgy_job_instantiation(self):
        """LiturgyJob should instantiate with database, token, and scrapers."""
        db = LiturgyDatabase(1)
        scrapers = [LiturgiaScraper(), HomiliaScraper(), SantoScraper()]
        job = LiturgyJob(db, "test_token_ld", scrapers)
        assert job.db is db
        assert job.bot_token == "test_token_ld"
        assert job.scrapers == scrapers
        assert hasattr(job, 'run')

    def test_feed_job_format_entry(self):
        """FeedJob should format feed entries correctly."""
        db = MainDatabase(0)
        job = FeedJob(db, "test_token")

        entry = {
            "title": "Test Title",
            "link": "https://example.com",
            "summary": "Test summary",
        }

        formatted = job._format_entry(entry)
        assert "Test Title" in formatted
        assert "https://example.com" in formatted
        assert "Test summary" in formatted

    def test_feed_job_format_entry_empty(self):
        """FeedJob should return empty string for empty entries."""
        db = MainDatabase(0)
        job = FeedJob(db, "test_token")

        result = job._format_entry({})
        assert result == ""


class TestUtilities:
    """Test utility functions."""

    def test_feedhandler_format_url_string(self):
        """FeedHandler should format URL strings correctly."""
        assert FeedHandler.format_url_string("example.com") == "http://example.com"
        assert FeedHandler.format_url_string("https://example.com") == "https://example.com"
        assert FeedHandler.format_url_string("http://example.com") == "http://example.com"

    def test_datehandler_get_datetime_now(self):
        """DateHandler should return timezone-aware datetime."""
        now = DateHandler.get_datetime_now()
        assert now is not None
        assert now.tzinfo is not None

    def test_datehandler_date(self):
        """DateHandler should extract date from datetime."""
        now = DateHandler.get_datetime_now()
        date = DateHandler.date(now)
        assert date is not None
        assert hasattr(date, 'year')
        assert hasattr(date, 'month')
        assert hasattr(date, 'day')


class TestIntegration:
    """End-to-end integration tests."""

    @patch('factories.main_factory.Client')
    def test_main_bot_full_initialization(self, mock_client_class):
        """MainBot should fully initialize with all mixins."""
        mock_client = MagicMock()
        mock_client.add_handler = MagicMock()
        mock_client_class.return_value = mock_client

        factory = MainBotFactory()
        bot = MainBot(factory)

        # Verify bot has all mixin methods
        assert hasattr(bot, 'add_feed_url')  # From FeedMixin
        assert hasattr(bot, 'set_welcome')   # From WelcomeMixin
        assert hasattr(bot, 'register_handlers')
        assert hasattr(bot, 'client')
        assert hasattr(bot, 'db')

    @patch('factories.liturgy_factory.Client')
    def test_liturgy_bot_full_initialization(self, mock_client_class):
        """LiturgyBot should fully initialize with all mixins."""
        mock_client = MagicMock()
        mock_client.add_handler = MagicMock()
        mock_client_class.return_value = mock_client

        factory = LiturgyBotFactory()
        bot = LiturgyBot(factory)

        # Verify bot has all mixin methods
        assert hasattr(bot, 'add_feed_url')      # From FeedMixin
        assert hasattr(bot, 'set_welcome')       # From WelcomeMixin
        assert hasattr(bot, 'today_liturgy')     # From LiturgyMixin
        assert hasattr(bot, 'register_handlers')
        assert hasattr(bot, 'client')
        assert hasattr(bot, 'db')

    def test_factory_pattern_creates_independent_instances(self):
        """Factories should create independent instances."""
        factory1 = MainBotFactory()
        factory2 = MainBotFactory()

        db1 = factory1.create_database()
        db2 = factory2.create_database()

        # Different instances
        assert db1 is not db2
        # Same type
        assert type(db1) == type(db2)
