import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import requests

from predoc_tracker.monitor import run_monitor
from predoc_tracker.notify import Alert, send_telegram
from predoc_tracker.match import MatchResult
from predoc_tracker.parse import parse_opportunities
from predoc_tracker.settings import AppConfig, NotificationConfig
from test_parser import SAMPLE_HTML


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name) / 'state.json'
        self.config = AppConfig(notifications=NotificationConfig(channels=['telegram']))
        self.record = parse_opportunities(SAMPLE_HTML)[0]
        self.environment = patch.dict(os.environ, {
            'PREDOC_TELEGRAM_BOT_TOKEN': 'test-token', 'PREDOC_TELEGRAM_CHAT_ID': 'test-chat',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @patch('predoc_tracker.monitor.fetch_page')
    @patch('predoc_tracker.monitor.parse_opportunities')
    @patch('predoc_tracker.monitor.send_telegram')
    def test_partial_failure_retries_only_unsent_then_sends_updates(self, send, parse, fetch):
        fetch.return_value = SimpleNamespace(html='fixture')
        other = replace(self.record, opportunity_id='other')
        parse.return_value = [self.record, other]
        send.side_effect = [None, RuntimeError('delivery failed')]
        with self.assertRaises(RuntimeError):
            run_monitor(self.config, self.state)
        self.assertEqual(json.loads(self.state.read_text()), {
            self.record.opportunity_id: self.record.content_hash,
        })
        send.reset_mock(side_effect=True)
        run_monitor(self.config, self.state)
        self.assertEqual(send.call_count, 1)
        send.reset_mock()
        run_monitor(self.config, self.state)
        send.assert_not_called()
        parse.return_value = [replace(self.record, content_hash='changed')]
        run_monitor(self.config, self.state)
        self.assertEqual(send.call_args.args[0][0].event_type, 'updated')
        self.assertNotIn('other', json.loads(self.state.read_text()))

    @patch('predoc_tracker.monitor.fetch_page')
    def test_empty_parse_preserves_state(self, fetch):
        self.state.write_text('{"existing": "hash"}')
        fetch.return_value = SimpleNamespace(html='<html></html>')
        with self.assertRaisesRegex(RuntimeError, 'No listings parsed'):
            run_monitor(self.config, self.state)
        self.assertEqual(json.loads(self.state.read_text()), {'existing': 'hash'})

    @patch('predoc_tracker.monitor.send_telegram')
    @patch('predoc_tracker.monitor.fetch_page')
    def test_preview_does_not_send_or_create_state(self, fetch, send):
        fetch.return_value = SimpleNamespace(html=SAMPLE_HTML)
        run_monitor(self.config, self.state, notify=False)
        send.assert_not_called()
        self.assertFalse(self.state.exists())


class TelegramTests(unittest.TestCase):
    @patch('predoc_tracker.notify.time.sleep')
    @patch('predoc_tracker.notify.requests.post')
    def test_rate_limit_retries_and_paces(self, post, sleep):
        post.side_effect = [
            SimpleNamespace(status_code=429, json=lambda: {'parameters': {'retry_after': 5}}),
            SimpleNamespace(status_code=200, json=lambda: {'ok': True}),
        ]
        alert = Alert('new', 'Job', '', '', '', '', MatchResult(True, 1, []))
        with patch.dict(os.environ, {'TEST_TOKEN': 'secret', 'TEST_CHAT': 'chat'}):
            send_telegram([alert], bot_token_env='TEST_TOKEN', chat_id_env='TEST_CHAT')
        self.assertEqual(post.call_count, 2)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [6, 3.2])

    @patch('predoc_tracker.notify.requests.post')
    def test_connection_error_does_not_expose_token(self, post):
        post.side_effect = requests.ConnectionError('URL includes secret')
        alert = Alert('new', 'Job', '', '', '', '', MatchResult(True, 1, []))
        with patch.dict(os.environ, {'TEST_TOKEN': 'secret', 'TEST_CHAT': 'chat'}):
            with self.assertRaises(RuntimeError) as raised:
                send_telegram([alert], bot_token_env='TEST_TOKEN', chat_id_env='TEST_CHAT')
        self.assertNotIn('secret', str(raised.exception))
